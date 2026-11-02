"""
Dev server — serves repo root at http://localhost:8000/
Strips /music prefix so paths match GitHub Pages layout.
Run: python serve.py
"""

import http.server
import socketserver
import os

PORT = 8000
ROOT = os.path.dirname(os.path.abspath(__file__))


class Handler(http.server.SimpleHTTPRequestHandler):
    def translate_path(self, path):
        path = path.split("?")[0].split("#")[0]
        if path.startswith("/music"):
            path = path[len("/music"):]
        if not path or path == "/":
            path = "/index.html"
        return os.path.join(ROOT, path.lstrip("/"))

    def log_message(self, fmt, *args):
        print(f"  {self.address_string()} {fmt % args}")


with socketserver.TCPServer(("", PORT), Handler) as httpd:
    print(f"Serving at http://localhost:{PORT}/")
    print("Press Ctrl+C to stop.\n")
    httpd.serve_forever()
