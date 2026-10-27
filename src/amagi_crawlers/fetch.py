"""One GET with a chosen user agent. Redirects are followed by hand so every hop keeps that user
agent, and so a block on a redirect target is seen. Stdlib only."""
from __future__ import annotations

import socket
import ssl
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import List, Optional, Tuple
from urllib.parse import urljoin

MAX_BYTES = 256 * 1024
MAX_REDIRECTS = 5


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


_OPENER = urllib.request.build_opener(_NoRedirect)


@dataclass
class Response:
    url: str                        # final URL after redirects
    status: Optional[int]           # None when no HTTP response came back
    headers: List[Tuple[str, str]] = field(default_factory=list)  # names lower-cased, repeats kept
    body: bytes = b""
    error: str = ""                 # network-level failure: timeout, reset, DNS, TLS
    redirects: List[str] = field(default_factory=list)

    def header(self, name: str) -> Optional[str]:
        name = name.lower()
        return next((v for k, v in self.headers if k == name), None)

    def header_all(self, name: str) -> List[str]:
        name = name.lower()
        return [v for k, v in self.headers if k == name]

    @property
    def text(self) -> str:
        ctype = self.header("content-type") or ""
        charset = "utf-8"
        for part in ctype.split(";")[1:]:
            k, _, v = part.strip().partition("=")
            if k.lower() == "charset" and v:
                charset = v.strip("\"' ")
        try:
            return self.body.decode(charset, errors="replace")
        except LookupError:
            return self.body.decode("utf-8", errors="replace")

    @property
    def ok(self) -> bool:
        return self.status is not None and 200 <= self.status < 300


def _describe(exc: BaseException) -> str:
    reason = getattr(exc, "reason", exc)
    if isinstance(reason, (socket.timeout, TimeoutError)) or "timed out" in str(reason):
        return "timeout"
    if isinstance(reason, ConnectionResetError):
        return "connection reset"
    if isinstance(reason, ConnectionRefusedError):
        return "connection refused"
    if isinstance(reason, socket.gaierror):
        return "DNS lookup failed"
    if isinstance(reason, ssl.SSLError):
        return f"TLS error: {getattr(reason, 'reason', None) or reason}"
    text = str(reason) or type(reason).__name__
    return text[:120]


def fetch(url: str, user_agent: str, timeout: float = 10.0,
          max_bytes: int = MAX_BYTES, max_redirects: int = MAX_REDIRECTS) -> Response:
    redirects: List[str] = []
    current = url
    for _ in range(max_redirects + 1):
        req = urllib.request.Request(current, headers={
            "User-Agent": user_agent,
            "Accept": "text/html,application/xhtml+xml,text/plain;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        })
        try:
            resp = _OPENER.open(req, timeout=timeout)
        except urllib.error.HTTPError as err:
            resp = err
        except (urllib.error.URLError, OSError, ValueError) as err:
            return Response(current, None, error=_describe(err), redirects=redirects)
        try:
            status = resp.getcode() if hasattr(resp, "getcode") else resp.code
            headers = [(k.lower(), v) for k, v in (resp.headers.items() if resp.headers else [])]
            try:
                body = resp.read(max_bytes)
            except (OSError, ValueError, AttributeError) as err:
                return Response(current, status, headers, b"", _describe(err), redirects)
        finally:
            try:
                resp.close()
            except Exception:
                pass
        location = next((v for k, v in headers if k == "location"), None)
        if status in (301, 302, 303, 307, 308) and location:
            redirects.append(current)
            current = urljoin(current, location)
            continue
        return Response(current, status, headers, body, "", redirects)
    return Response(current, None, error=f"more than {max_redirects} redirects", redirects=redirects)
