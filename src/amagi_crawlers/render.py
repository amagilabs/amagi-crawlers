"""Text, CSV, markdown and JSON output."""
from __future__ import annotations

import csv
import io
import json
from typing import List

from . import __version__
from .check import BOTH, CONFLICT, ERROR, ROBOTS, UNKNOWN, SiteResult


def _cut(text: str, width: int) -> str:
    return text if len(text) <= width else text[: width - 3] + "..."


def counts(sites: List[SiteResult]) -> dict:
    out = {"checks": 0, "allowed": 0, "robots": 0, "server": 0, "conflicts": 0, "unknown": 0, "error": 0}
    for s in sites:
        for b in s.bots:
            out["checks"] += 1
            if b.verdict == ERROR:
                out["error"] += 1
            elif b.verdict == UNKNOWN:
                out["unknown"] += 1
            elif b.verdict == CONFLICT:
                out["conflicts"] += 1
                out["server"] += 1
            elif b.verdict in (ROBOTS, BOTH):
                out["robots"] += 1
                out["server"] += b.verdict == BOTH
            else:
                out["allowed"] += 1
    return out


def summary_line(sites: List[SiteResult]) -> str:
    c = counts(sites)
    n = len(sites)
    line = (f"{n} site{'s' if n != 1 else ''}, {c['checks']} bot check{'s' if c['checks'] != 1 else ''}: {c['allowed']} allowed, "
            f"{c['robots']} blocked by robots.txt, {c['server']} refused by the server, "
            f"{c['conflicts']} conflict{'s' if c['conflicts'] != 1 else ''}")
    if c["unknown"]:
        line += f", {c['unknown']} unknown"
    if c["error"]:
        line += f", {c['error']} not checked (site unreachable)"
    return line + "."


def text(sites: List[SiteResult]) -> str:
    out: List[str] = []
    for s in sites:
        out.append(f"{s.target.label}{s.target.path if s.target.path != '/' else ''}")
        if s.error:
            out.append(f"  unreachable: {s.error}")
            out.append("")
            continue
        tail = f" ({s.vendor})" if s.vendor else ""
        out.append(f"  robots.txt {s.robots_status} | llms.txt {s.llms_txt} | browser {s.baseline}{tail}"
                   + (" | tdm-reservation 1" if s.tdm_reserved else ""))
        if s.page_missing:
            out.append(f"  note: the page returns {s.baseline} to a plain browser request too, so bot results are"
                       " UNKNOWN; check a page that exists")
        elif not s.baseline_ok:
            out.append("  note: the site also blocks a plain browser request from this checker, so a refused bot"
                       " is UNKNOWN, not a conflict")
        out.append(f"  {'BOT':<18} {'USE':<9} {'ROBOTS.TXT':<30} {'HTTP':<10} VERDICT")
        for b in s.bots:
            out.append(f"  {b.bot.token:<18} {b.bot.use:<9} {_cut(b.robots_rule, 30):<30} "
                       f"{_cut(b.http, 10):<10} {b.label}")
        out.append("")
    out.append(summary_line(sites))
    conflicts = [(s, b) for s in sites for b in s.conflicts]
    if conflicts:
        out.append("Conflicts (robots.txt allows the bot, the server refuses it):")
        for s, b in conflicts:
            out.append(f"  {s.target.label:<24} {b.bot.token:<18} {b.note}")
    return "\n".join(out) + "\n"


CSV_FIELDS = ["site", "url", "bot", "operator", "use", "robots_allowed", "robots_rule", "http",
              "server_blocked", "page_opt_outs", "verdict", "label", "conflict", "note",
              "robots_txt", "llms_txt", "browser", "vendor", "checked_at"]


def _yn(v) -> str:
    return "" if v is None else ("yes" if v else "no")


def to_csv(sites: List[SiteResult]) -> str:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=CSV_FIELDS, lineterminator="\n")
    w.writeheader()
    for s in sites:
        for b in s.bots:
            w.writerow({
                "site": s.target.label, "url": s.target.url(s.target.path), "bot": b.bot.token,
                "operator": b.bot.operator, "use": b.bot.use,
                "robots_allowed": _yn(b.robots_allowed if b.verdict != ERROR else None),
                "robots_rule": b.robots_rule, "http": b.http, "server_blocked": _yn(b.server_blocked),
                "page_opt_outs": "; ".join(b.page), "verdict": b.verdict, "label": b.label,
                "conflict": _yn(b.conflict), "note": b.note, "robots_txt": s.robots_status,
                "llms_txt": s.llms_txt, "browser": s.baseline, "vendor": s.vendor,
                "checked_at": s.checked_at,
            })
    return buf.getvalue()


def _md(text: str) -> str:
    return text.replace("|", "\\|")


def markdown(sites: List[SiteResult]) -> str:
    out: List[str] = ["# AI crawler access report", ""]
    if sites:
        out.append(f"Checked {sites[0].checked_at} with amagi-crawlers {__version__}. "
                   + summary_line(sites))
        out.append("")
    tokens: List[str] = []
    for s in sites:
        for b in s.bots:
            if b.bot.token not in tokens:
                tokens.append(b.bot.token)
    out.append("| Site | robots.txt | llms.txt | " + " | ".join(tokens) + " |")
    out.append("|---|---|---|" + "---|" * len(tokens))
    for s in sites:
        cells = {b.bot.token: b for b in s.bots}
        row = [_md(s.target.label), _md(s.robots_status), _md(s.llms_txt)]
        for t in tokens:
            b = cells.get(t)
            label = b.label if b else ""
            row.append(f"**{label}**" if b and b.conflict else label)
        out.append("| " + " | ".join(row) + " |")
    out += ["", "ALLOW = robots.txt allows the bot and the server answers it. "
            "BLOCK robots = robots.txt disallows it. "
            "CONFLICT = robots.txt allows it but the server refuses that user agent "
            "(403, a challenge page, or a dropped connection) while a browser gets through. "
            "ALLOW noai/noindex = allowed, but the page opts out with an X-Robots-Tag header or robots meta tag. "
            "UNKNOWN = robots.txt allows it, but the site also blocks a plain browser request from this checker, "
            "so a bot-specific block cannot be told apart (or the page itself is missing). ERROR = the site could not be reached.",
            ""]
    conflicts = [(s, b) for s in sites for b in s.conflicts]
    if conflicts:
        out += ["## Conflicts", ""]
        for s, b in conflicts:
            out.append(f"- **{_md(s.target.label)}**, {b.bot.token}: robots.txt `{_md(b.robots_rule)}`, "
                       f"{_md(b.note)}")
        out.append("")
    for s in sites:
        out += [f"## {_md(s.target.label)}", ""]
        if s.error:
            out += [f"Unreachable: {_md(s.error)}", ""]
            continue
        out.append(f"URL `{s.target.url(s.target.path)}`. robots.txt {_md(s.robots_status)}, "
                   f"llms.txt {_md(s.llms_txt)}, browser baseline {_md(s.baseline)}"
                   + (f" ({s.vendor})" if s.vendor else "")
                   + (", tdm-reservation: 1" if s.tdm_reserved else "") + ".")
        out += ["", "| Bot | Operator | Use | robots.txt | HTTP | Page opt-outs | Verdict | Note |",
                "|---|---|---|---|---|---|---|---|"]
        for b in s.bots:
            out.append(f"| {b.bot.token} | {_md(b.bot.operator)} | {b.bot.use} | {_md(b.robots_rule)} | "
                       f"{_md(b.http)} | {_md(', '.join(b.page)) or '-'} | {b.label} | {_md(b.note) or '-'} |")
        out.append("")
    return "\n".join(out)


def to_json(sites: List[SiteResult]) -> str:
    data = {
        "tool": "amagi-crawlers", "version": __version__, "summary": counts(sites),
        "sites": [{
            "site": s.target.label, "url": s.target.url(s.target.path), "checked_at": s.checked_at,
            "robots_txt": s.robots_status, "robots_agents": s.robots_agents, "llms_txt": s.llms_txt,
            "browser": s.baseline, "vendor": s.vendor, "tdm_reservation": s.tdm_reserved,
            "error": s.error,
            "bots": [{
                "bot": b.bot.token, "operator": b.bot.operator, "use": b.bot.use,
                "user_agent": b.bot.ua, "robots_allowed": b.robots_allowed, "robots_rule": b.robots_rule,
                "http": b.http, "http_status": b.http_status, "server_blocked": b.server_blocked,
                "page_opt_outs": b.page, "verdict": b.verdict, "label": b.label, "note": b.note,
            } for b in s.bots],
        } for s in sites],
    }
    return json.dumps(data, indent=2) + "\n"


FORMATS = {"text": text, "csv": to_csv, "markdown": markdown, "json": to_json}
EXTENSIONS = {".csv": "csv", ".md": "markdown", ".markdown": "markdown", ".json": "json", ".txt": "text"}
