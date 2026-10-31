"""Run with: python -m unittest discover -s scripts -p test_smoke_test.py"""

from contextlib import redirect_stdout
from http.server import BaseHTTPRequestHandler, HTTPServer
from io import StringIO
import json
from threading import Thread
import unittest

from smoke_test import main


class SmokeTest(unittest.TestCase):
    def test_http_responses(self):
        responses = {}
        seen = []

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                seen.append(self.path)
                status, body = responses[self.path]
                self.send_response(status)
                if status == 302:
                    self.send_header("Location", "/health")
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):
                pass

        server = HTTPServer(("127.0.0.1", 0), Handler)
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            cases = [
                (200, {"chromium_version": "123", "launch_ms": 1.5}, 0),
                (404, {}, 1),
                (503, {}, 1),
                (302, {}, 1),
                (200, {"chromium_version": "123", "launch_ms": True}, 1),
                (200, {"chromium_version": "123", "launch_ms": -1}, 1),
                (200, {"chromium_version": "123", "launch_ms": float("nan")}, 1),
                (200, {"chromium_version": "", "launch_ms": 1}, 1),
                (200, [], 1),
                (200, b"not JSON", 1),
            ]
            for status, body, expected in cases:
                with self.subTest(status=status, body=body):
                    responses["/health"] = (200, b'{"status":"ok","version":"0.1.0"}')
                    responses["/debug/playwright"] = (status, body if isinstance(body, bytes) else json.dumps(body).encode())
                    seen.clear()
                    output = StringIO()
                    with redirect_stdout(output):
                        self.assertEqual(main([f"http://127.0.0.1:{server.server_port}/"]), expected)
                    self.assertEqual(seen, ["/health", "/debug/playwright"])
                    self.assertIn("OK /health", output.getvalue())
                    self.assertIn(("GAGAL" if expected else "OK") + " /debug/playwright", output.getvalue())
            responses["/health"] = (200, b'{"status":"broken"}')
            responses["/debug/playwright"] = (200, b'{"chromium_version":"123","launch_ms":0}')
            with redirect_stdout(StringIO()) as output:
                self.assertEqual(main([f"http://127.0.0.1:{server.server_port}"]), 1)
            self.assertIn("GAGAL /health", output.getvalue())
            self.assertIn("OK /debug/playwright", output.getvalue())
        finally:
            server.shutdown()
            thread.join()
            server.server_close()
        with redirect_stdout(StringIO()) as output:
            self.assertEqual(main([f"http://127.0.0.1:{server.server_port}"]), 1)
        self.assertEqual(output.getvalue().count("GAGAL"), 2)

    def test_invalid_base_urls(self):
        for url in ("file:///tmp", "http://", "http://localhost:bad", "http://localhost/path", "http://user:pass@localhost", "http://localhost?x=1", "http://localhost#x", "http://local host"):
            with self.subTest(url=url), redirect_stdout(StringIO()):
                self.assertEqual(main([url]), 1)


if __name__ == "__main__":
    unittest.main()
