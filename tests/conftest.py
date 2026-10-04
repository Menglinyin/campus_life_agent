"""Isolated fixtures: no production credentials, databases, models or voice services."""
import json
import os
import socket
import sys
import threading
import time
from pathlib import Path
from types import SimpleNamespace
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete
PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))
sys.path.insert(0, str(PROJECT / 'backend'))
from app.main import create_app
from app.settings import Settings
from app.storage.models import Classroom, Course, Dish, SecondhandListing, KnowledgeChunk
DAY = '2026-10-04'
AUTH = {'Authorization': 'Bearer tests-alice'}
TOKEN = 'tests-only-service-token-0123456789abcdef'

def pytest_addoption(parser):
    parser.addoption('--run-chroma', action='store_true', help='Run optional real local Chroma tests')

def pytest_collection_modifyitems(config, items):
    if not config.getoption('--run-chroma'):
        for item in items:
            if 'chroma' in item.keywords:
                item.add_marker(pytest.mark.skip(reason='Opt in with --run-chroma and install requirements-chroma.txt'))

@pytest.fixture(autouse=True)
def isolated_environment(monkeypatch):
    for key in list(os.environ):
        if key.startswith('CAMPUS_'): monkeypatch.delenv(key)
    monkeypatch.setenv('NO_PROXY', '127.0.0.1,localhost')
    monkeypatch.setenv('no_proxy', '127.0.0.1,localhost')
    monkeypatch.setenv('ANONYMIZED_TELEMETRY', 'False')

@pytest.fixture
def dataset():
    base = PROJECT / 'tests' / 'fixtures'
    return {'campus': json.loads((base / 'campus.json').read_text(encoding='utf-8')),
            'knowledge': json.loads((base / 'knowledge.json').read_text(encoding='utf-8'))}

def populate(db, dataset):
    classes = {'classrooms': Classroom, 'courses': Course, 'dishes': Dish, 'secondhand': SecondhandListing}
    with db.transaction() as session:
        for cls in [*classes.values(), KnowledgeChunk]: session.execute(delete(cls))
        for kind, rows in dataset['campus'].items():
            for row in rows:
                session.add(classes[kind](id=row['id'], payload={k: v for k, v in row.items() if k != 'id'}))
        for row in dataset['knowledge']: session.add(KnowledgeChunk(**row))

@pytest.fixture
def settings(tmp_path):
    return Settings(_env_file=None, demo=True, database_url=f'sqlite:///{tmp_path / "tests.db"}',
                    user_tokens={'tests-alice': 'alice', 'tests-bob': 'bob'},
                    skill_root=PROJECT / 'skills', session_ttl=259200,
                    embedding_backend='demo', llm_base_url='', redis_url='', chroma_path='',
                    reranker_model='', mcp_servers={}, asr_url='', tts_url='')

@pytest.fixture
def client(settings, dataset):
    with TestClient(create_app(settings)) as instance:
        populate(instance.app.state.services.db, dataset)
        instance.app.state.services.rag.refresh()
        yield instance

@pytest.fixture
def ask(client):
    def call(message, *, headers=None, **fields):
        return client.post('/api/chat', headers=AUTH if headers is None else headers,
                           json={'message': message, **fields})
    return call

@pytest.fixture
def cache():
    class Cache:
        def __init__(self): self.data = {}; self.writes = []; self.deleted = []; self.reads = []
        def get(self, key): self.reads.append(key); return self.data.get(key)
        def setex(self, key, ttl, value): self.data[key] = value; self.writes.append((key, ttl, value))
        def delete(self, key): self.data.pop(key, None); self.deleted.append(key)
    return Cache()

@pytest.fixture
def live_mcp(tmp_path, dataset):
    """Pre-bound sockets avoid free-port discovery/rebind races."""
    import uvicorn
    from mcp_servers.common.config import ServerSettings
    from mcp_servers.common.runtime import Runtime
    from mcp_servers.common.server import create_app as create_mcp_app
    from app.rag.embedding import Embedding
    from app.rag.hybrid_retrieval import HybridRetriever
    from app.storage.repositories.knowledge import Knowledge
    config = ServerSettings(_env_file=None, database_url=f'sqlite:///{tmp_path / "mcp.db"}',
                            mcp_token=TOKEN, mcp_allowed_users=['alice', 'bob'],
                            embedding_backend='demo', chroma_path='', reranker_model='')
    runtime = Runtime(config); running = []; urls = {}
    try:
        populate(runtime.db, dataset)
        runtime.rag = HybridRetriever(Knowledge(runtime.db), Embedding(config), config)
        for kind in ('query', 'recommendation', 'feedback'):
            sock = socket.socket(); sock.bind(('127.0.0.1', 0)); sock.listen(128)
            port = sock.getsockname()[1]
            server = uvicorn.Server(uvicorn.Config(create_mcp_app(kind, config, runtime),
                                                   log_level='critical', access_log=False))
            thread = threading.Thread(target=server.run, kwargs={'sockets': [sock]}, daemon=True)
            running.append((server, thread, sock)); thread.start()
            deadline = time.monotonic() + 5
            while not server.started:
                if not thread.is_alive() or time.monotonic() > deadline:
                    pytest.fail(f'Local {kind} MCP service failed to start')
                time.sleep(.02)
            urls[kind] = f'http://127.0.0.1:{port}/mcp'
        yield SimpleNamespace(urls=urls, runtime=runtime, token=TOKEN)
    finally:
        for server, thread, sock in running: server.should_exit = True
        for server, thread, sock in running:
            thread.join(timeout=5); sock.close()
            if thread.is_alive(): server.force_exit = True; thread.join(timeout=2)
        runtime.close()
