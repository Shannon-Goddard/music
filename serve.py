"""
Dev server — serves ./frontend at /music/
Run: python serve.py
Then open: http://localhost:8000/music/
"""

import http.server
import socketserver
import os

PORT = 8000
FRONTEND = os.path.join(os.path.dirname(__file__), "frontend")


class Handler(http.server.SimpleHTTPRequestHandler):
    def translate_path(self, path):
        # Strip /music prefix so requests map to ./frontend/
        if path.startswith("/music"):
            path = path[len("/music"):]
        if not path or path == "/":
            path = "/index.html"
        # Resolve relative to frontend dir
        return os.path.join(FRONTEND, path.lstrip("/"))

    def log_message(self, fmt, *args):
        print(f"  {self.address_string()} {fmt % args}")


with socketserver.TCPServer(("", PORT), Handler) as httpd:
    print(f"Serving at http://localhost:{PORT}/music/")
    print("Press Ctrl+C to stop.\n")
    httpd.serve_forever()
