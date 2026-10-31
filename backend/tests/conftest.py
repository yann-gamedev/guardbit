from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from app import main


@pytest.fixture
def client(monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    monkeypatch.setattr(main, "engine", engine)
    with TestClient(main.app) as client:
        yield client


@pytest.fixture
def local_site():
    requests = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            requests.append((self.path, {key.lower(): value for key, value in self.headers.items()}))
            path = urlsplit(self.path).path
            status = 200
            location = None
            body = "<html><head><title>Halaman normal</title></head><body>Konten asli</body></html>"
            if path == "/ua403" and "Googlebot" in self.headers.get("User-Agent", ""):
                status = 403
            elif path == "/jsout":
                body = body.replace("</body>", '<script>location.href="https://judol.invalid/"</script></body>')
            elif path == "/httpout":
                status, location = 302, "https://judol.invalid/"
            elif path == "/redirect":
                status, location = 302, "/ok"
            elif path == "/renderout" and sum(item[0] == "/renderout" for item in requests) > 1:
                status, location = 302, "https://judol.invalid/"
            elif path == "/chain":
                remaining = int(parse_qs(urlsplit(self.path).query).get("n", ["0"])[0])
                if remaining:
                    status, location = 302, f"/chain?n={remaining - 1}"
            elif path == "/challenge":
                body = body.replace("Halaman normal", "Tunggu sebentar...")
            elif path == "/status":
                status = int(parse_qs(urlsplit(self.path).query)["code"][0])
            elif path == "/resources":
                body = body.replace("</body>", '<img src="https://other.invalid/image.png"></body>')
            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            if location:
                self.send_header("Location", location)
            self.end_headers()
            self.wfile.write(body.encode())

        def log_message(self, *_args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        # Direct loopback works for Chromium and APIRequestContext on Windows; no DNS override.
        yield f"http://127.0.0.1:{server.server_port}", requests
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
