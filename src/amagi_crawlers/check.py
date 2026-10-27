"""Check one site: robots.txt, llms.txt, a browser baseline fetch, then one fetch per bot user agent."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, List, Optional
from urllib.parse import quote, urlsplit, urlunsplit

from . import signals
from .bots import BROWSER_UA, Bot
from .fetch import Response, fetch
from .robots import Robots

# Verdict codes. CONFLICT = robots.txt lets the bot in, the server turns it away.
ALLOW = "allow"
OPT_OUT = "allow-optout"
ROBOTS = "robots"
BOTH = "robots+server"
CONFLICT = "conflict"
UNKNOWN = "unknown"   # robots.txt allows it, but the site blocks this checker's browser request too
ERROR = "error"       # the site could not be reached at all

DEAD = ("DNS lookup failed", "connection refused")  # fetch errors that make further requests pointless


@dataclass
class Target:
    label: str      # what the report calls the site ("example.com")
    base: str       # scheme://host[:port]
    path: str = "/"

    @classmethod
    def parse(cls, text: str, path: Optional[str] = None) -> "Target":
        raw = text.strip()
        if "://" not in raw:
            raw = "https://" + raw
        parts = urlsplit(raw)
        if not parts.netloc:
            raise ValueError(f"not a domain or URL: {text!r}")
        given = parts.path or "/"
        if parts.query:
            given += "?" + parts.query
        base = urlunsplit((parts.scheme.lower(), parts.netloc.lower(), "", "", ""))
        if path is not None and not path.startswith("/"):
            hint = " (Git Bash rewrote it; set MSYS_NO_PATHCONV=1)" if path[1:3] == ":/" else ""
            raise ValueError(f"--path must start with /, got {path!r}{hint}")
        return cls(parts.netloc.lower(), base, quote(path or given, safe="/?&=%:@!$'()*+,;~#"))

    def url(self, path: str) -> str:
        return self.base + path


@dataclass
class BotResult:
    bot: Bot
    robots_allowed: bool
    robots_rule: str            # "Disallow: / [GPTBot]", "allowed [*]", ...
    http: str                   # "200", "403", "challenge", "timeout", "-" (not fetched)
    http_status: Optional[int]
    server_blocked: Optional[bool]  # None = not fetched, or the baseline failed so we cannot tell
    page: List[str]             # opt-out directives that apply to this bot
    verdict: str
    note: str = ""

    @property
    def conflict(self) -> bool:
        return self.verdict == CONFLICT

    @property
    def label(self) -> str:
        return verdict_label(self)


@dataclass
class SiteResult:
    target: Target
    checked_at: str
    robots_status: str          # "200", "404 (no robots.txt)", "503 (treated as disallow all)", ...
    robots_agents: List[str]
    llms_txt: str               # "yes", "no (404)", "no (HTML page)", ...
    baseline: str               # "200", "403", "timeout"
    baseline_ok: bool
    vendor: str
    tdm_reserved: bool
    bots: List[BotResult] = field(default_factory=list)
    error: str = ""

    @property
    def conflicts(self) -> List[BotResult]:
        return [b for b in self.bots if b.conflict]

    @property
    def page_missing(self) -> bool:
        """The browser baseline got 404/410: the page is gone, not blocked."""
        return self.baseline in ("404", "410")


def _http_summary(resp: Response) -> str:
    if resp.status is None:
        return resp.error or "no response"
    if signals.is_challenge(resp):
        return "challenge"
    return str(resp.status)


def _blocked(resp: Response) -> bool:
    return resp.status is None or resp.status >= 400 or signals.is_challenge(resp)


def robots_state(resp: Response):
    """(Robots, status text, disallow_all) from the robots.txt response, per RFC 9309 section 2.3.1."""
    if resp.status is None:
        return Robots([], []), f"unreachable: {resp.error} (treated as disallow all)", True
    if 200 <= resp.status < 300:
        if signals.is_html(resp):
            return Robots([], []), f"{resp.status} but an HTML page, no rules", False
        return Robots.parse(resp.text), str(resp.status), False
    if resp.status == 429 or resp.status >= 500:
        return Robots([], []), f"{resp.status} (treated as disallow all)", True
    if resp.status in (404, 410):
        return Robots([], []), f"{resp.status} (no robots.txt)", False
    return Robots([], []), f"{resp.status} (unreadable; crawlers treat it as allow all)", False


def llms_state(resp: Response) -> str:
    if resp.status is None:
        return f"unknown ({resp.error})"
    if not resp.ok:
        return f"no ({resp.status})"
    if signals.is_html(resp):
        return "no (HTML page)"
    if not resp.body.strip():
        return "no (empty)"
    return "yes"


def verdict_for(robots_allowed: bool, server_blocked: Optional[bool], page: List[str],
                baseline_ok: bool = True, fetched: bool = False) -> str:
    if server_blocked is None:
        if not robots_allowed:
            return ROBOTS
        if fetched and not baseline_ok:
            return UNKNOWN
        return OPT_OUT if page else ALLOW
    if robots_allowed and server_blocked:
        return CONFLICT
    if not robots_allowed:
        return BOTH if server_blocked else ROBOTS
    return OPT_OUT if page else ALLOW


def verdict_label(r: BotResult) -> str:
    if r.verdict == ERROR:
        return "ERROR"
    if r.verdict == UNKNOWN:
        return "UNKNOWN"
    if r.verdict == CONFLICT:
        return f"CONFLICT {r.http}"
    if r.verdict == BOTH:
        return f"BLOCK robots+{r.http}"
    if r.verdict == ROBOTS:
        return "BLOCK robots"
    if r.verdict == OPT_OUT:
        return "ALLOW " + "/".join(sorted({p.split(" ")[0] for p in r.page}))
    return "ALLOW"


def check_site(target: Target, bots: List[Bot], *, timeout: float = 10.0, delay: float = 0.3,
               fetch_bots: bool = True, fetcher: Callable[..., Response] = fetch) -> SiteResult:
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    first = [True]

    def get(path: str, ua: str) -> Response:
        if not first[0] and delay > 0:
            time.sleep(delay)
        first[0] = False
        return fetcher(target.url(path), ua, timeout=timeout)

    robots_resp = get("/robots.txt", BROWSER_UA)
    robots, robots_status, disallow_all = robots_state(robots_resp)
    if robots_resp.status is None and robots_resp.error in DEAD:
        page = llms = robots_resp   # no point asking a host that does not resolve or answer
    else:
        page = get(target.path, BROWSER_UA)
        llms = get("/llms.txt", BROWSER_UA)

    baseline_ok = page.status is not None and not _blocked(page)
    site = SiteResult(
        target=target, checked_at=stamp, robots_status=robots_status,
        robots_agents=robots.names(), llms_txt=llms_state(llms),
        baseline=_http_summary(page), baseline_ok=baseline_ok,
        vendor=signals.vendor(page) or signals.vendor(robots_resp),
        tdm_reserved=signals.tdm_reserved(page),
    )
    if page.status is None and robots_resp.status is None:
        site.error = page.error or robots_resp.error

    for bot in bots:
        if disallow_all:
            allowed, rule = False, "robots.txt unreachable: disallow all"
        elif not robots.groups:
            status = robots_resp.status or 0
            allowed = True
            rule = ("no robots.txt" if status in (404, 410)
                    else f"robots.txt unreadable ({status})" if status >= 400 else "no rules")
        else:
            d = robots.decide(bot.token, target.path)
            allowed, rule = d.allowed, d.explain()
        resp: Optional[Response] = None
        note = bot.note
        if bot.ua and fetch_bots and not site.error:
            resp = get(target.path, bot.ua)
            http, status = _http_summary(resp), resp.status
            if baseline_ok:
                server_blocked: Optional[bool] = _blocked(resp)
                if server_blocked:
                    v = signals.vendor(resp) or site.vendor
                    note = f"browser gets {site.baseline}, this bot gets {http}" + (f" ({v})" if v else "")
            elif site.page_missing:
                server_blocked = None
                note = f"page not found (browser gets {site.baseline}); check a page that exists"
                if http != site.baseline:
                    note += f"; this bot gets {http}"
            else:
                server_blocked = None
                note = f"the site blocks this checker too (browser gets {site.baseline})"
                if http != site.baseline:
                    note += f"; this bot gets {http} instead"
        else:
            http, status, server_blocked = "-", None, None
        opt = signals.page_opt_outs(resp if resp is not None and resp.ok else page, bot.token)
        verdict = ERROR if site.error else verdict_for(allowed, server_blocked, opt, baseline_ok, resp is not None)
        if site.error:
            rule, note = "-", f"site unreachable: {site.error}"
        result = BotResult(bot, allowed, rule, http, status, server_blocked, opt, verdict, note)
        site.bots.append(result)
    return site
