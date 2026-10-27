"""amagi-crawlers command line."""
from __future__ import annotations

import argparse
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from typing import List, Optional

from . import __version__, render
from .bots import BOTS, select
from .check import Target, check_site

EPILOG = """examples:
  amagi-crawlers example.com
  amagi-crawlers -f clients.txt -o report.md -o report.csv
  amagi-crawlers example.com/blog/post --bots GPTBot,ClaudeBot,PerplexityBot
  amagi-crawlers --demo          (three local sample sites, no internet needed)

exit codes: 0 no conflicts, 1 at least one conflict (robots.txt allows a bot, the server refuses it),
2 usage error or no site could be reached."""


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="amagi-crawlers",
        description="Check which AI crawlers can reach each site: robots.txt rules, X-Robots-Tag and "
                    "robots meta opt-outs, and the HTTP answer the server gives each bot's user agent.",
        epilog=EPILOG, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("sites", nargs="*", metavar="SITE", help="domain or URL (example.com, https://example.com/page)")
    p.add_argument("-f", "--file", action="append", default=[], metavar="FILE",
                   help="read sites from a file, one per line (# comments allowed)")
    p.add_argument("--bots", metavar="LIST", help="comma list of bot tokens to check (default: all, see --list-bots)")
    p.add_argument("--path", metavar="PATH", help="page to check on every site (default: / or the URL's own path)")
    p.add_argument("--format", choices=sorted(render.FORMATS), default="text", help="stdout format (default: text)")
    p.add_argument("-o", "--output", action="append", default=[], metavar="FILE",
                   help="also write a report; .csv, .md, .json or .txt picks the format (repeatable)")
    p.add_argument("--no-fetch", action="store_true",
                   help="skip the per-bot requests; check robots.txt and page tags only")
    p.add_argument("--timeout", type=float, default=10.0, metavar="S", help="seconds per request (default 10)")
    p.add_argument("--delay", type=float, default=0.3, metavar="S",
                   help="pause between requests to the same site (default 0.3)")
    p.add_argument("--workers", type=int, default=4, metavar="N", help="sites checked in parallel (default 4)")
    p.add_argument("-q", "--quiet", action="store_true", help="print nothing to stdout")
    p.add_argument("--list-bots", action="store_true", help="show the crawler catalog and exit")
    p.add_argument("--demo", action="store_true", help="check three local sample sites (no internet)")
    p.add_argument("--version", action="version", version=f"amagi-crawlers {__version__}")
    return p


def _read_sites(paths: List[str]) -> List[str]:
    out: List[str] = []
    for path in paths:
        with open(path, encoding="utf-8-sig") as fh:
            for line in fh:
                line = line.split("#", 1)[0].strip()
                if line:
                    out.append(line)
    return out


def list_bots() -> str:
    rows = [f"{'TOKEN':<19} {'OPERATOR':<13} {'USE':<9} {'UA SOURCE':<11} USER AGENT"]
    for b in BOTS:
        rows.append(f"{b.token:<19} {b.operator:<13} {b.use:<9} {b.source:<11} {b.ua or '(' + b.note + ')'}")
    return "\n".join(rows) + "\n"


def _write(path: str, sites, fallback: str) -> None:
    fmt = render.EXTENSIONS.get(os.path.splitext(path)[1].lower(), fallback)
    with open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write(render.FORMATS[fmt](sites))


def main(argv: Optional[List[str]] = None) -> int:
    args = _parser().parse_args(argv)
    if args.list_bots:
        sys.stdout.write(list_bots())
        return 0
    if args.workers < 1 or args.timeout <= 0 or args.delay < 0:
        print("amagi-crawlers: --workers must be 1 or more, --timeout above 0, --delay 0 or more", file=sys.stderr)
        return 2
    try:
        raw = list(args.sites) + _read_sites(args.file)
    except OSError as err:
        print(f"amagi-crawlers: cannot read {err.filename}: {err.strerror}", file=sys.stderr)
        return 2
    if not raw and not args.demo:
        print("amagi-crawlers: give at least one site, -f FILE, or --demo (see --help)", file=sys.stderr)
        return 2
    try:
        targets = [Target.parse(s, args.path) for s in raw]
    except ValueError as err:
        print(f"amagi-crawlers: {err}", file=sys.stderr)
        return 2
    bots = select(args.bots)

    demo = None
    delay = args.delay
    if args.demo:
        from .demo import DemoSites
        demo = DemoSites().__enter__()
        for site in demo.sites:
            t = Target.parse(site.url, args.path)
            targets.append(Target(site.name, t.base, t.path))
        delay = 0.0
    try:
        progress = sys.stderr.isatty() and not args.quiet and len(targets) > 1

        def run(t: Target):
            if progress:
                print(f"checking {t.label} ...", file=sys.stderr, flush=True)
            return check_site(t, bots, timeout=args.timeout, delay=delay, fetch_bots=not args.no_fetch)

        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            sites = list(pool.map(run, targets))
    finally:
        if demo is not None:
            demo.__exit__(None, None, None)

    if not args.quiet:
        out = render.FORMATS[args.format](sites)
        try:
            sys.stdout.write(out)
        except UnicodeEncodeError:
            sys.stdout.write(out.encode("ascii", "replace").decode("ascii"))
    for path in args.output:
        try:
            _write(path, sites, args.format)
        except OSError as err:
            print(f"amagi-crawlers: cannot write {path}: {err.strerror}", file=sys.stderr)
            return 2
        if not args.quiet:
            print(f"wrote {path}")
    if all(s.error for s in sites):
        return 2
    return 1 if any(s.conflicts for s in sites) else 0
