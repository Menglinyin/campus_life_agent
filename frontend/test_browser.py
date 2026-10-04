"""Run actual Chromium against temporary FastAPI + frontend proxy in one process.

Requires backend dependencies and Node Playwright with Chromium installed.
No live DB, user secrets, GPU or voice-model service is used.
"""
import argparse
import os
from pathlib import Path
import socket
import subprocess
import sys
from tempfile import TemporaryDirectory
import threading
import time

import httpx

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parent
sys.path.insert(0, str(PROJECT / 'backend'))
from app.settings import Settings
from app.main import create_app
from frontend.serve import make_server
import uvicorn


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--node', default='node')
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'artifacts')
    args = parser.parse_args()
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0))
        backend_port = listener.getsockname()[1]
    with TemporaryDirectory(prefix='campus-frontend-') as directory:
        values = {name: field.get_default(call_default_factory=True) for name, field in Settings.model_fields.items()}
        values.update(database_url=f'sqlite:///{Path(directory) / "test.db"}',
                      user_tokens={'demo-token':'demo-student', 'other-token':'other-student'})
        settings = Settings(**values, _env_file=None)
        backend = uvicorn.Server(uvicorn.Config(create_app(settings), host='127.0.0.1', port=backend_port, log_level='warning'))
        backend_thread = threading.Thread(target=backend.run, daemon=True)
        backend_thread.start()
        proxy = make_server(0, f'http://127.0.0.1:{backend_port}')
        proxy_thread = threading.Thread(target=proxy.serve_forever, daemon=True)
        proxy_thread.start()
        try:
            ready = False
            with httpx.Client(timeout=1, trust_env=False) as client:
                for _ in range(100):
                    try:
                        ready = client.get(f'http://127.0.0.1:{proxy.server_port}/api/health').status_code == 200
                    except httpx.HTTPError:
                        pass
                    if ready:
                        break
                    time.sleep(.1)
            if not ready:
                print('Temporary backend did not become ready.', file=sys.stderr)
                return 2
            environment = {**os.environ, 'FRONTEND_TEST_URL': f'http://127.0.0.1:{proxy.server_port}',
                           'FRONTEND_ARTIFACTS': str(args.output_dir.resolve())}
            result = subprocess.run([args.node, str(ROOT / 'tests/browser.cjs')], cwd=ROOT, env=environment, timeout=90)
            return result.returncode
        finally:
            proxy.shutdown()
            proxy.server_close()
            backend.should_exit = True
            backend_thread.join(timeout=10)
            proxy_thread.join(timeout=2)


if __name__ == '__main__':
    raise SystemExit(main())
