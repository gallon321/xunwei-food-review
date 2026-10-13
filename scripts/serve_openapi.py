"""Temporary localhost-only OpenAPI import bridge for the Apifox web UI."""
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

DOCUMENT = Path(__file__).resolve().parent.parent / 'docs/openapi.json'
ORIGIN = 'https://app.apifox.com'


class DocumentHandler(BaseHTTPRequestHandler):
    def end_headers(self):
        if self.headers.get('Origin') == ORIGIN:
            self.send_header('Access-Control-Allow-Origin', ORIGIN)
            self.send_header('Access-Control-Allow-Credentials', 'true')
            self.send_header('Vary', 'Origin')
        self.send_header('Cache-Control', 'no-store')
        super().end_headers()

    def do_OPTIONS(self):
        if self.path != '/openapi.json' or self.headers.get('Origin') != ORIGIN:
            self.send_error(403)
            return
        self.send_response(204)
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', self.headers.get('Access-Control-Request-Headers', 'Content-Type'))
        if self.headers.get('Access-Control-Request-Private-Network') == 'true':
            self.send_header('Access-Control-Allow-Private-Network', 'true')
        self.end_headers()

    def do_GET(self):
        if self.path != '/openapi.json':
            self.send_error(404)
            return
        data = DOCUMENT.read_bytes()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)


if __name__ == '__main__':
    print('Temporary Apifox document URL: http://127.0.0.1:8765/openapi.json', flush=True)
    HTTPServer(('127.0.0.1', 8765), DocumentHandler).serve_forever()
