"""Check a GuardBit deployment using only Python's standard library."""

import argparse
import json
import math
import sys
from http.client import HTTPException
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, build_opener


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def main(argv=None):
    parser = argparse.ArgumentParser(description="Cek /health dan Chromium (DEBUG=true).")
    parser.add_argument("base_url", help="URL dasar backend, contoh http://localhost:8000")
    args = parser.parse_args(argv)
    try:
        url = urlsplit(args.base_url)
        if (
            url.scheme not in {"http", "https"} or not url.hostname
            or url.username is not None or url.password is not None
            or url.query or url.fragment or url.path not in {"", "/"}
            or any(character.isspace() for character in args.base_url)
        ):
            raise ValueError
        url.port
    except ValueError:
        print("GAGAL URL dasar: gunakan origin HTTP(S), tanpa kredensial, path, query, atau fragmen.")
        return 1

    handlers = [NoRedirect()]
    if url.hostname in {"localhost", "127.0.0.1", "::1"}:
        handlers.append(ProxyHandler({}))
    opener = build_opener(*handlers)
    failed = False
    for path in ("/health", "/debug/playwright"):
        try:
            with opener.open(args.base_url.rstrip("/") + path, timeout=60) as response:
                if response.status != 200:
                    raise ValueError
                payload = json.load(response)
            if not isinstance(payload, dict):
                raise ValueError
            if path == "/health":
                valid = payload.get("status") == "ok" and isinstance(payload.get("version"), str) and bool(payload["version"].strip())
            else:
                duration = payload.get("launch_ms")
                valid = (
                    isinstance(payload.get("chromium_version"), str)
                    and bool(payload["chromium_version"].strip())
                    and type(duration) in (int, float)
                    and math.isfinite(duration) and duration >= 0
                )
            if not valid:
                raise ValueError
        except HTTPError as error:
            error.close()
            hint = " (pastikan DEBUG=true)" if path == "/debug/playwright" and error.code == 404 else ""
            print(f"GAGAL {path}: HTTP {error.code}{hint}")
            failed = True
        except (URLError, OSError, HTTPException):
            print(f"GAGAL {path}: koneksi gagal atau timeout")
            failed = True
        except (ValueError, UnicodeError, OverflowError):
            print(f"GAGAL {path}: respons JSON tidak sesuai kontrak")
            failed = True
        else:
            print(f"OK {path}")
    return int(failed)


if __name__ == "__main__":
    sys.exit(main())
