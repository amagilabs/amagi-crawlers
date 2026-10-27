"""Page-level opt-out signals and WAF fingerprints read from a response.

- ``X-Robots-Tag`` headers, global (``noai``) or scoped to a bot (``GPTBot: noindex``).
- ``<meta name="robots">`` and ``<meta name="<bot token>">`` tags.
- ``tdm-reservation`` (W3C TDMRep), as a header or a meta tag.
- Bot challenges (Cloudflare "Just a moment...", ``cf-mitigated: challenge``) and the CDN/WAF in front.
"""
from __future__ import annotations

import re
from html.parser import HTMLParser
from typing import Dict, List, Optional, Set

from .fetch import Response

# Directives that change whether a bot may use the page. noai/noimageai are the DeviantArt-style
# AI opt-outs; noindex/none keep the page out of search and answer engines.
OPT_OUT = ("noai", "noimageai", "noindex", "none")

# X-Robots-Tag directives that carry a colon themselves, so "name:" is not a bot scope.
_COLON_DIRECTIVES = {"unavailable_after", "max-snippet", "max-image-preview", "max-video-preview"}
_SCOPE = re.compile(r"^\s*([A-Za-z0-9_.\-]+)\s*:\s*(.*)$")


def x_robots(values: List[str]) -> Dict[str, Set[str]]:
    """Parse X-Robots-Tag header values into {scope: directives}; scope '' = every bot."""
    out: Dict[str, Set[str]] = {}
    for value in values:
        scope = ""
        for part in value.split(","):
            m = _SCOPE.match(part)
            if m and m.group(1).lower() not in _COLON_DIRECTIVES:
                scope, part = m.group(1).lower(), m.group(2)
            directive = part.strip().lower().split(":", 1)[0].strip()
            if directive:
                out.setdefault(scope, set()).add(directive)
    return out


class _MetaParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.metas: List[tuple] = []

    def handle_starttag(self, tag, attrs):
        if tag != "meta":
            return
        a = {k.lower(): (v or "") for k, v in attrs}
        name = a.get("name") or a.get("property") or ""
        if name:
            self.metas.append((name.strip().lower(), a.get("content", "")))

    handle_startendtag = handle_starttag


def metas(html: str) -> List[tuple]:
    """All (name, content) meta pairs in the document, names lower-cased."""
    p = _MetaParser()
    try:
        p.feed(html)
        p.close()
    except Exception:  # broken markup: keep what was read so far
        pass
    return p.metas


def is_html(resp: Response) -> bool:
    ctype = (resp.header("content-type") or "").lower()
    if "html" in ctype:
        return True
    head = resp.body[:512].lstrip().lower()
    return head.startswith((b"<!doctype html", b"<html", b"<head", b"<body"))


def page_opt_outs(resp: Optional[Response], token: str) -> List[str]:
    """Opt-out directives that apply to ``token`` on this page, as 'noai' (global) or 'noai[GPTBot]'."""
    if resp is None or not resp.ok:
        return []
    want = token.lower()
    found: List[str] = []
    for scope, directives in x_robots(resp.header_all("x-robots-tag")).items():
        if scope in ("", want):
            for d in directives:
                if d in OPT_OUT:
                    found.append(f"{d} (header)")
    if is_html(resp):
        for name, content in metas(resp.text):
            if name in ("robots", want):
                for d in content.split(","):
                    d = d.strip().lower()
                    if d in OPT_OUT:
                        found.append(f"{d} (meta)")
    return sorted(set(found))


def tdm_reserved(resp: Optional[Response]) -> bool:
    if resp is None or not resp.ok:
        return False
    if (resp.header("tdm-reservation") or "").strip() == "1":
        return True
    if is_html(resp):
        return any(n == "tdm-reservation" and c.strip() == "1" for n, c in metas(resp.text))
    return False


_CHALLENGE_MARKERS = (
    b"<title>just a moment...</title>", b"/cdn-cgi/challenge-platform/", b"cf-chl-",
    b"_incapsula_resource", b"captcha-delivery.com", b"/.well-known/sgcaptcha/",
    b"px-captcha", b"awswaf",
)


def is_challenge(resp: Optional[Response]) -> bool:
    """A bot challenge page rather than the real page (often sent with 403 or 503)."""
    if resp is None or resp.status is None:
        return False
    if (resp.header("cf-mitigated") or "").lower() == "challenge":
        return True
    body = resp.body[:65536].lower()
    return any(m in body for m in _CHALLENGE_MARKERS)


def vendor(resp: Optional[Response]) -> str:
    """The CDN/WAF in front of the site, from response headers. '' when nothing is recognised."""
    if resp is None:
        return ""
    names = {k for k, _ in resp.headers}
    server = (resp.header("server") or "").lower()
    if "cf-ray" in names or server == "cloudflare":
        return "Cloudflare"
    if "akamai" in server or "x-akamai-transformed" in names or "akamai-grn" in names:
        return "Akamai"
    if "x-sucuri-id" in names or "sucuri" in server:
        return "Sucuri"
    if "x-iinfo" in names or (resp.header("x-cdn") or "").lower() == "imperva":
        return "Imperva"
    if "x-amz-cf-id" in names or server == "cloudfront":
        return "CloudFront"
    if "x-vercel-id" in names:
        return "Vercel"
    if "x-nf-request-id" in names:
        return "Netlify"
    if "x-datadome" in names or "datadome" in server:
        return "DataDome"
    if "x-served-by" in names and "cache-" in (resp.header("x-served-by") or ""):
        return "Fastly"
    return ""
