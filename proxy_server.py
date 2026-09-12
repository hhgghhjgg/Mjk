#!/usr/bin/env python3
"""MJK translator — static server + 9Router CORS proxy (stdlib only).

- Serves Html.html in the same folder.
- Forwards /v1/* to 9Router with the API key (fixes browser CORS).
- /api/health -> {"ok": true} for Railway/Render health checks.

Config (env):
  NINE_ROUTER_API_KEY : 9Router key (required in production)
  PORT                : injected by Railway/Render (default 8000 locally)
  HOST                : default 0.0.0.0 when PORT is set, else 127.0.0.1
"""
import json
import os
import urllib.request
import urllib.error
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

UPSTREAM = "https://9router-production-e6c2.up.railway.app/v1"
API_KEY = os.environ.get("NINE_ROUTER_API_KEY", "")
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
        if not API_KEY:
            out = json.dumps({"error": "NINE_ROUTER_API_KEY is not set on the server"}).encode()
            self.send_response(500)
            self._cors()
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(out)))
            self.end_headers()
            self.wfile.write(out)
            return
        length = int(self.headers.get("Content-Length", 0) or 0)
        body = self.rfile.read(length) if length else b"{}"
        url = UPSTREAM + self.path[3:]  # strip "/v1" -> keep "/chat/completions" etc.
        try:
            req = urllib.request.Request(
                url, data=body,
                headers={"Content-Type": "application/json",
                         "Authorization": "Bearer " + API_KEY},
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
            out = json.dumps({"error": "proxy failed: %s" % e}).encode()
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
    port = int(os.environ.get("PORT", sys.argv[1] if len(sys.argv) > 1 else 8000))
    host = os.environ.get("HOST", "0.0.0.0" if os.environ.get("PORT") else "127.0.0.1")
    srv = ThreadingHTTPServer((host, port), Handler)
    print("Serving %s on %s:%d -> %s" % (HERE, host, port, UPSTREAM), flush=True)
    print("Open:  http://%s:%d/Html.html" % (host, port), flush=True)
    print("Proxy: http://%s:%d/v1  ->  %s" % (host, port, UPSTREAM), flush=True)
    print("Stop with Ctrl+C", flush=True)
    srv.serve_forever()
