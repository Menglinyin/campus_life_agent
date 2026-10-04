import json
from types import SimpleNamespace
import pytest
from redis.exceptions import ConnectionError
from fastapi import HTTPException
from app.memory.session_store import SessionStore

def store(cache, snapshot):
    return SessionStore(SimpleNamespace(client=cache), SimpleNamespace(snapshot=lambda user, sid: snapshot), 259200)

def test_cache_write_uses_three_days_and_user_scoped_key(cache):
    snapshot = {'version': 1, 'messages': [], 'slots': {'date': '2026-10-04'}}
    assert store(cache, snapshot).get('alice', 'session-a') == snapshot
    key, ttl, value = cache.writes[0]
    assert key == 'campus:session:alice:session-a' and ttl == 3 * 24 * 3600
    assert json.loads(value) == snapshot

def test_current_version_reuses_cache_but_version_change_refreshes(cache):
    old = {'version': 1, 'messages': [], 'slots': {}}; memory = store(cache, old)
    memory.get('alice', 's'); memory.get('alice', 's')
    assert len(cache.writes) == 1
    assert store(cache, {**old, 'version': 2}).get('alice', 's')['version'] == 2
    assert len(cache.writes) == 2

def test_redis_disconnect_and_corrupt_json_fall_back_to_sql(cache):
    snapshot = {'version': 4, 'messages': [], 'slots': {}}
    cache.data['campus:session:alice:s'] = 'malformed-json'
    assert store(cache, snapshot).get('alice', 's') == snapshot
    def broken(key): raise ConnectionError('fixture unavailable')
    cache.get = broken
    assert store(cache, snapshot).get('alice', 's') == snapshot

def test_sql_ownership_checked_before_cache_hit(cache):
    cache.data['campus:session:bob:s'] = json.dumps({'version': 1, 'messages': ['secret']})
    def denied(user, sid): raise HTTPException(404, 'Session not found')
    memory = SessionStore(SimpleNamespace(client=cache), SimpleNamespace(snapshot=denied), 259200)
    with pytest.raises(HTTPException): memory.get('bob', 's')
    assert not cache.reads

def test_invalidation_deletes_only_target_user_session(cache):
    cache.data.update({'campus:session:alice:s': 'a', 'campus:session:bob:s': 'b'})
    store(cache, {}).invalidate('alice', 's')
    assert cache.data == {'campus:session:bob:s': 'b'}
