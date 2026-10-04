"""Same-origin proxy tests with an isolated local mock upstream."""
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading

import httpx
import pytest
from frontend.serve import make_server, backend_origin


@contextmanager
def running(server):
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


class Upstream(BaseHTTPRequestHandler):
    observed = None

    def do_POST(self):
        body = self.rfile.read(int(self.headers.get('Content-Length', '0')))
        Upstream.observed = (self.path, self.headers.get('Authorization'), json.loads(body))
        data = b'{"answer":"ok"}'
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('X-Request-ID', 'test-request')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass


def test_origin_refuses_credentials_and_paths():
    assert backend_origin('http://127.0.0.1:8000').hostname == '127.0.0.1'
    for value in ['file:///tmp/a', 'http://user:secret@host', 'http://host/path', 'http://host/?token=x']:
        with pytest.raises(ValueError):
            backend_origin(value)


def test_static_only_serves_public_files():
    with running(make_server(0)) as server:
        with httpx.Client(base_url=f'http://127.0.0.1:{server.server_port}', trust_env=False) as client:
            assert client.get('/').status_code == 200
            assert client.get('/js/api.js').status_code == 200
            for path in ['/serve.py', '/package.json', '/js/../serve.py', '/js/%2e%2e/serve.py', '/tests/core.test.js']:
                assert client.get(path).status_code == 404


def test_proxy_preserves_api_auth_body_and_request_id():
    with running(ThreadingHTTPServer(('127.0.0.1', 0), Upstream)) as upstream:
        with running(make_server(0, f'http://127.0.0.1:{upstream.server_port}')) as server:
            with httpx.Client(base_url=f'http://127.0.0.1:{server.server_port}', trust_env=False) as client:
                response = client.post('/api/chat', headers={'Authorization':'Bearer test-token'}, json={'message':'今天'})
                assert response.json() == {'answer':'ok'}
                assert response.headers['X-Request-ID'] == 'test-request'
                assert Upstream.observed == ('/api/chat', 'Bearer test-token', {'message':'今天'})


def test_proxy_rejects_cross_origin_and_unknown_paths():
    with running(make_server(0)) as server:
        with httpx.Client(base_url=f'http://127.0.0.1:{server.server_port}', trust_env=False) as client:
            assert client.post('/api/chat', headers={'Origin':'https://other.invalid'}, json={}).status_code == 403
            assert client.post('/api/admin', json={}).status_code == 404


def test_upstream_failure_is_generic_502():
    # Bind then release an ephemeral port so no actual upstream instance is needed.
    empty = ThreadingHTTPServer(('127.0.0.1', 0), Upstream)
    port = empty.server_port
    empty.server_close()
    with running(make_server(0, f'http://127.0.0.1:{port}')) as server:
        with httpx.Client(base_url=f'http://127.0.0.1:{server.server_port}', trust_env=False) as client:
            response = client.get('/api/health')
            assert response.status_code == 502
            assert response.json() == {'detail':'Backend unavailable'}
