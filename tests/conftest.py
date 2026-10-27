import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from amagi_crawlers.demo import DemoSites


@pytest.fixture(scope="session")
def demo():
    with DemoSites() as sites:
        yield sites


class _Server:
    """A throwaway local site. ``route(path, user_agent)`` returns (status, headers, body);
    a body of None drops the connection without answering."""

    def __init__(self, route):
        server = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):  # noqa: N802
                ua = self.headers.get("User-Agent", "")
                server.seen.append((self.path, ua))
                status, headers, body = route(self.path, ua)
                if body is None:
                    self.close_connection = True
                    self.connection.shutdown(socket.SHUT_RDWR)
                    return
                data = body.encode("utf-8")
                self.send_response(status)
                for k, v in headers:
                    self.send_header(k, v)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, *args):
                pass

            def handle_one_request(self):
                try:
                    super().handle_one_request()
                except OSError:
                    self.close_connection = True

        self.seen = []
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        self.url = "http://127.0.0.1:%d" % self.httpd.server_address[1]

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()


@pytest.fixture
def serve():
    servers = []

    def make(route):
        s = _Server(route)
        servers.append(s)
        return s

    yield make
    for s in servers:
        s.close()


@pytest.fixture
def dead_url():
    """A local port with nothing listening on it."""
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return "http://127.0.0.1:%d" % port
