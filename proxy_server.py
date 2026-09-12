#!/usr/bin/env python3
"""9Router local proxy + static server (stdlib only).

Why: 9Router (Railway) does NOT send CORS headers, so browsers block
direct fetch() from Html.html -> you get "network error". Running this
proxy on your own machine fixes it: the browser talks to localhost
(same origin, no CORS problem) and THIS script forwards to 9Router
with your API key (curl works fine, only browsers are blocked).

Run:   python3 proxy_server.py [port, default 8000]
Open:  http://localhost:8000/Html.html
"""
import json
import os
import urllib.request
import urllib.error
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

UPSTREAM = "https://9router-production-e6c2.up.railway.app/v1"
API_KEY = os.environ.get("NINE_ROUTER_API_KEY", "sk-d042a2942b66660e-wjdw1y-30603948")
HERE = os.path.dirname(os.path.abspath(__file__))


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=HERE, **kw)

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self):
        if self.path.startswith("/v1/"):
            self._proxy()
        elif self.path == "/api/health":
            body = json.dumps({"ok": True, "upstream": UPSTREAM}).encode()
            self.send_response(200)
            self._cors()
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            super().do_GET()

    def do_POST(self):
        if self.path.startswith("/v1/"):
            self._proxy()
        else:
            self.send_error(404)

    def _proxy(self):
        length = int(self.headers.get("Content-Length", 0) or 0)
        body = self.rfile.read(length) if length else b"{}"
        url = UPSTREAM + self.path[3:]  # strip "/v1" prefix -> keep "/chat/completions" etc.
        try:
            req = urllib.request.Request(
                url, data=body,
                headers={"Content-Type": "application/json",
                         "Authorization": f"Bearer {API_KEY}"},
                method="POST" if self.command == "POST" else "GET",
            )
            with urllib.request.urlopen(req, timeout=120) as r:
                out = r.read()
                self.send_response(r.status)
                self._cors()
                self.send_header("Content-Type", r.headers.get("Content-Type", "application/json"))
                self.send_header("Content-Length", str(len(out)))
                self.end_headers()
                self.wfile.write(out)
        except urllib.error.HTTPError as e:
            out = e.read()
            self.send_response(e.code)
            self._cors()
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(out)))
            self.end_headers()
            self.wfile.write(out)
        except Exception as e:
            out = json.dumps({"error": f"proxy failed: {e}"}).encode()
            self.send_response(502)
            self._cors()
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(out)))
            self.end_headers()
            self.wfile.write(out)

    def log_message(self, *a):
        pass  # quiet; comment out for debug


if __name__ == "__main__":
    import sys
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"Open:  http://localhost:{port}/Html.html")
    print(f"Proxy: http://localhost:{port}/v1  ->  {UPSTREAM}")
    print("Stop with Ctrl+C")
    srv.serve_forever()
