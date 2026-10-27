"""Three small local websites on 127.0.0.1 that behave the way real sites do, for ``--demo`` and the tests.

- ``shop.example``: robots.txt blocks the training crawlers and lets search and assistant bots in.
  Has an llms.txt.
- ``news.example``: robots.txt lets every bot in, but a Cloudflare-style firewall answers four AI user
  agents with 403 and challenges a fifth. llms.txt is a soft 404 (the home page, status 200).
- ``blog.example``: no robots.txt. Every page says ``noai, noimageai`` in a robots meta tag, sends
  ``X-Robots-Tag: GPTBot: noindex`` and ``tdm-reservation: 1``.

Nothing here touches the internet.
"""
from __future__ import annotations

import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Dict, List, Optional, Tuple

PAGE = """<!doctype html>
<html><head><title>{title}</title>{meta}</head>
<body><h1>{title}</h1><p>Fixture page served by amagi-crawlers --demo.</p></body></html>
"""

CHALLENGE = """<!doctype html><html><head><title>Just a moment...</title></head>
<body><script src="/cdn-cgi/challenge-platform/h/b/orchestrate/chl_page/v1"></script></body></html>
"""

SHOP_ROBOTS = """# shop.example: keep training crawlers out, let AI search in
User-agent: GPTBot
User-agent: ClaudeBot
User-agent: CCBot
User-agent: Google-Extended
User-agent: Applebot-Extended
User-agent: Meta-ExternalAgent
User-agent: Bytespider
Disallow: /

User-agent: *
Disallow: /cart
Allow: /

Sitemap: https://shop.example/sitemap.xml
"""

SHOP_LLMS = """# shop.example
> Outdoor gear, shipped from Georgia.

## Products
- [Tents](https://shop.example/tents): two to six person tents
"""

NEWS_ROBOTS = """User-agent: *
Disallow: /admin/
"""

# user-agent substring -> response the firewall gives it
NEWS_WAF: Dict[str, str] = {
    "GPTBot": "403",
    "ClaudeBot": "403",
    "PerplexityBot": "403",
    "Bytespider": "403",
    "Perplexity-User": "challenge",
}


class Site:
    def __init__(self, name: str):
        self.name = name
        self.server: Optional[ThreadingHTTPServer] = None

    @property
    def url(self) -> str:
        assert self.server is not None
        host, port = self.server.server_address[:2]
        return f"http://{host}:{port}"

    def respond(self, path: str, ua: str) -> Tuple[int, List[Tuple[str, str]], str]:
        raise NotImplementedError


class Shop(Site):
    def respond(self, path, ua):
        if path == "/robots.txt":
            return 200, [("Content-Type", "text/plain")], SHOP_ROBOTS
        if path == "/llms.txt":
            return 200, [("Content-Type", "text/markdown; charset=utf-8")], SHOP_LLMS
        if path in ("/", "/tents"):
            return 200, [("Content-Type", "text/html; charset=utf-8")], PAGE.format(title="Shop", meta="")
        return 404, [("Content-Type", "text/html")], PAGE.format(title="Not found", meta="")


class News(Site):
    CF = [("Server", "cloudflare"), ("CF-RAY", "8d2f0c1a2b3c4d5e-ATL")]

    def respond(self, path, ua):
        for needle, action in NEWS_WAF.items():
            if needle in ua:
                if action == "challenge":
                    return 403, self.CF + [("cf-mitigated", "challenge"), ("Content-Type", "text/html")], CHALLENGE
                return 403, self.CF + [("Content-Type", "text/html")], PAGE.format(title="Access denied", meta="")
        if path == "/robots.txt":
            return 200, self.CF + [("Content-Type", "text/plain")], NEWS_ROBOTS
        # every other path, llms.txt included, gets the home page: a soft 404
        return 200, self.CF + [("Content-Type", "text/html; charset=utf-8")], PAGE.format(title="News", meta="")


class Blog(Site):
    def respond(self, path, ua):
        if path == "/":
            meta = '<meta name="robots" content="noai, noimageai">'
            return 200, [("Content-Type", "text/html; charset=utf-8"), ("X-Robots-Tag", "GPTBot: noindex"),
                         ("tdm-reservation", "1")], PAGE.format(title="Blog", meta=meta)
        return 404, [("Content-Type", "text/plain")], "not found\n"


def _handler(site: Site):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            status, headers, body = site.respond(self.path.split("?", 1)[0], self.headers.get("User-Agent", ""))
            data = body.encode("utf-8")
            self.send_response(status)
            for k, v in headers:
                self.send_header(k, v)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *args):
            pass

    return Handler


class DemoSites:
    """Context manager that serves shop/news/blog on free ports and stops them afterwards."""

    def __init__(self):
        self.sites = [Shop("shop.example"), News("news.example"), Blog("blog.example")]
        self._threads: List[threading.Thread] = []

    def __enter__(self) -> "DemoSites":
        for site in self.sites:
            site.server = ThreadingHTTPServer(("127.0.0.1", 0), _handler(site))
            t = threading.Thread(target=site.server.serve_forever, daemon=True)
            t.start()
            self._threads.append(t)
        return self

    def __exit__(self, *exc):
        for site in self.sites:
            if site.server is not None:
                site.server.shutdown()
                site.server.server_close()
        for t in self._threads:
            t.join(timeout=5)

    def __getitem__(self, name: str) -> Site:
        return next(s for s in self.sites if s.name == name)
