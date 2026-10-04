"""Loopback static frontend + same-origin API proxy; development use only."""
import argparse
import http.client
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
from urllib.parse import urlsplit, unquote

ROOT = Path(__file__).resolve().parent
ALLOWED_API = re.compile(r'^/api/(health|chat|preferences|charts|voice/(transcribe|synthesize)|sessions/[0-9a-fA-F-]+/messages)$')
MAX_REQUEST = 9 * 1024 * 1024
MAX_RESPONSE = 17 * 1024 * 1024


def backend_origin(value):
    origin = urlsplit(value)
    if origin.scheme not in ('http', 'https') or not origin.hostname or origin.path not in ('', '/') or origin.query or origin.fragment or origin.username or origin.password:
        raise ValueError('Backend must be an HTTP(S) origin without credentials/path/query')
    _ = origin.port  # Validate port syntax/range.
    return origin


class Handler(SimpleHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def log_message(self, format, *args):
        # Never print Authorization, bodies, or user-controlled query strings.
        pass

    def end_headers(self):
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('X-Frame-Options', 'DENY')
        self.send_header('Cache-Control', 'no-store')
        super().end_headers()

    def error_json(self, status, detail):
        # Early rejection may leave an unread upload body; discard the connection.
        self.close_connection = True
        data = json.dumps({'detail': detail}, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header('Connection', 'close')
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        if self.command != 'HEAD':
            self.wfile.write(data)

    def static_allowed(self):
        path = unquote(urlsplit(self.path).path)
        relative = path.lstrip('/') or 'index.html'
        target = (ROOT / relative).resolve()
        if not target.is_relative_to(ROOT) or not target.is_file():
            return False
        relative = target.relative_to(ROOT).as_posix()
        return not any(part.startswith('.') for part in target.relative_to(ROOT).parts) and (relative == 'index.html' or relative.startswith(('css/', 'js/', 'vendor/')))

    def do_GET(self):
        if urlsplit(self.path).path.startswith('/api/'):
            self.proxy()
        elif self.static_allowed():
            super().do_GET()
        else:
            self.error_json(404, 'Not found')

    def do_HEAD(self):
        if self.static_allowed():
            super().do_HEAD()
        else:
            self.error_json(404, 'Not found')

    def do_POST(self):
        self.proxy()

    def proxy(self):
        path = urlsplit(self.path).path
        if not ALLOWED_API.fullmatch(path):
            self.error_json(404, 'Unknown API route')
            return
        # Avoid sending credentials across a malicious page's cross-origin request.
        origin = self.headers.get('Origin')
        if origin and urlsplit(origin).netloc != self.headers.get('Host'):
            self.error_json(403, 'Cross-origin request refused')
            return
        if self.headers.get('Transfer-Encoding'):
            self.close_connection = True
            self.error_json(400, 'Chunked upload unsupported')
            return
        try:
            length = int(self.headers.get('Content-Length', '0'))
        except ValueError:
            self.close_connection = True
            self.error_json(400, 'Invalid length')
            return
        if not 0 <= length <= MAX_REQUEST:
            self.close_connection = True
            self.error_json(413, 'Request exceeds limit')
            return
        self.connection.settimeout(30)
        try:
            body = self.rfile.read(length) if length else None
            if body is not None and len(body) != length:
                self.close_connection = True
                self.error_json(400, 'Incomplete request')
                return
        except OSError:
            self.close_connection = True
            self.error_json(408, 'Upload timeout')
            return
        target = self.server.backend
        connection_type = http.client.HTTPSConnection if target.scheme == 'https' else http.client.HTTPConnection
        upstream = connection_type(target.hostname, target.port, timeout=330)
        headers = {name: value for name, value in self.headers.items() if name.lower() in ('authorization', 'content-type', 'accept')}
        try:
            upstream.request(self.command, self.path, body=body, headers=headers)
            response = upstream.getresponse()
            data = response.read(MAX_RESPONSE + 1)
            if len(data) > MAX_RESPONSE:
                self.error_json(502, 'Upstream response too large')
                return
            self.send_response(response.status)
            self.send_header('Content-Type', response.getheader('Content-Type', 'application/octet-stream'))
            request_id = response.getheader('X-Request-ID')
            if request_id:
                self.send_header('X-Request-ID', request_id)
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        except (OSError, http.client.HTTPException):
            self.error_json(502, 'Backend unavailable')
        finally:
            upstream.close()


def make_server(port=8002, backend='http://127.0.0.1:8000'):
    origin = backend_origin(backend)
    server = ThreadingHTTPServer(('127.0.0.1', port), Handler)
    server.backend = origin
    return server


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8002)
    parser.add_argument('--backend', default='http://127.0.0.1:8000')
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error('Invalid port')
    try:
        server = make_server(args.port, args.backend)
    except (ValueError, OSError):
        parser.error('Invalid backend origin or unavailable local port')
    print(f'Frontend: http://127.0.0.1:{args.port}; API proxy configured', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
