import asyncio
import json
from types import SimpleNamespace
import httpx
import pytest
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from app.mcp.client import MCPClient
from app.core.errors import ServiceError
DAY = '2026-10-04'
pytestmark = pytest.mark.local_mcp

def adapter(live_mcp, token=None):
    return MCPClient(SimpleNamespace(mcp_token=live_mcp.token if token is None else token, tool_timeout=5))

def test_real_mcp_discovery_queries_and_private_knowledge(live_mcp):
    async def run():
        headers = {'Authorization': 'Bearer ' + live_mcp.token, 'X-Campus-User': 'alice'}
        async with streamablehttp_client(live_mcp.urls['query'], headers=headers) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize(); specs = (await session.list_tools()).tools
                assert {t.name for t in specs} == {'query_classrooms', 'query_courses', 'query_dishes', 'query_secondhand', 'search_knowledge'}
                for tool in specs:
                    assert 'user_id' not in tool.inputSchema.get('properties', {})
                    assert tool.annotations.readOnlyHint is True
        client = adapter(live_mcp)
        for name, expected in [('query_classrooms', 'room-open'), ('query_courses', 'course-open'), ('query_secondhand', 'item-active')]:
            args = {} if name == 'query_secondhand' else {'date': DAY}
            result = await client.call(live_mcp.urls['query'], name, args, 'alice')
            assert result['rows'][0]['id'] == expected
        missing = await client.call(live_mcp.urls['query'], 'query_classrooms', {}, 'alice')
        assert missing['needs_date'] and missing['rows'] == []
        knowledge = await client.call(live_mcp.urls['query'], 'search_knowledge', {'query': '旁听规则 私有笔记'}, 'alice')
        assert 'rule-alice' in {r['id'] for r in knowledge['rows']}
        assert 'rule-bob' not in {r['id'] for r in knowledge['rows']}
    asyncio.run(run())

def test_real_mcp_authentication_user_scope_and_schema(live_mcp):
    async def run():
        url = live_mcp.urls['query']
        with pytest.raises(ServiceError): await adapter(live_mcp, '').call(url, 'query_classrooms', {'date': DAY}, 'alice')
        with pytest.raises(ServiceError): await adapter(live_mcp).call(url, 'query_classrooms', {'date': DAY}, 'mallory')
        with pytest.raises(ServiceError): await adapter(live_mcp).call(url, 'pay', {}, 'alice')
        with pytest.raises(ServiceError): await adapter(live_mcp).call(url, 'query_classrooms', {'spice': 3}, 'alice')
    asyncio.run(run())
    with httpx.Client(trust_env=False) as http:
        response = http.post(live_mcp.urls['query'], headers={'Authorization': 'Bearer ' + live_mcp.token,
                              'X-Campus-User': 'alice', 'Origin': 'https://untrusted.invalid'}, json={})
    assert response.status_code == 403

def test_real_mcp_preferences_and_feedback_idempotency(live_mcp):
    live_mcp.runtime.preferences.update('alice', {'budget': 10, 'spice': 0})
    async def run():
        client = adapter(live_mcp)
        recommendation = await client.call(live_mcp.urls['recommendation'], 'recommend_dishes', {'date': DAY}, 'alice')
        assert [r['id'] for r in recommendation['rows']] == ['dish-mild']
        explicit = await client.call(live_mcp.urls['recommendation'], 'recommend_dishes', {'date': DAY, 'budget': 20, 'spice': 1}, 'alice')
        assert len(explicit['rows']) == 2
        args = {'target_kind': 'classrooms', 'target_id': 'room-open', 'rating': 5,
                'comment': '测试评价', 'idempotency_key': 'tests-review-key-0001'}
        first = await client.call(live_mcp.urls['feedback'], 'submit_review', args, 'alice')
        second = await client.call(live_mcp.urls['feedback'], 'submit_review', args, 'alice')
        assert first['rows'][0]['id'] == second['rows'][0]['id']
        own = await client.call(live_mcp.urls['feedback'], 'list_my_reviews', {}, 'alice')
        other = await client.call(live_mcp.urls['feedback'], 'list_my_reviews', {}, 'bob')
        assert len(own['rows']) == 1 and other['rows'] == []
    asyncio.run(run())
