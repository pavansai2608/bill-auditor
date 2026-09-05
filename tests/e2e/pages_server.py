"""A local stand-in for GitHub Pages, close enough to catch the real failures.

Two behaviours that a plain `python -m http.server` does not have, and that are
exactly what breaks a Vite SPA on Pages:

  * everything is under a project subpath, so an asset written against "/"
    404s here the same way it would in production;
  * an unknown path is answered with 404.html *and a real 404 status*, which
    is what Pages does and why the router has to be able to boot from it.
"""

import sys
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

DIST = Path(sys.argv[1]).resolve()
PREFIX = sys.argv[2]  # e.g. /bill-auditor/
PORT = int(sys.argv[3])


class Handler(SimpleHTTPRequestHandler):
    def _resolve(self):
        path = self.path.split("?", 1)[0].split("#", 1)[0]
        if not path.startswith(PREFIX):
            return None, 404
        rel = path[len(PREFIX) :]
        if rel in ("", "/"):
            rel = "index.html"
        candidate = (DIST / rel.lstrip("/")).resolve()
        if DIST not in candidate.parents and candidate != DIST:
            return None, 404
        if candidate.is_dir():
            candidate = candidate / "index.html"
        if candidate.is_file():
            return candidate, 200
        return DIST / "404.html", 404

    def do_GET(self):
        target, status = self._resolve()
        if target is None or not target.is_file():
            self.send_response(404)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"404")
            return
        body = target.read_bytes()
        self.send_response(status)
        self.send_header("Content-Type", self.guess_type(str(target)))
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        sys.stderr.write(f"{self.address_string()} {fmt % args}\n")


HTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
