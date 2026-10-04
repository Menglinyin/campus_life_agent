import asyncio
import json
import httpx
import pytest
from app.agent.model_client import ModelClient
from app.core.errors import ServiceError

def test_vllm_openai_request_contract(settings):
    settings.llm_base_url = 'http://model.invalid/v1'; settings.llm_api_key = 'tests-only-key'
    async def run():
        client = ModelClient(settings)
        await client.http.aclose()
        def handler(request):
            assert str(request.url) == 'http://model.invalid/v1/chat/completions'
            assert request.headers['authorization'] == 'Bearer tests-only-key'
            data = json.loads(request.content)
            assert data['model'] == 'Qwen3-32B-AWQ'
            assert data['chat_template_kwargs']['enable_thinking'] is False
            assert data['tool_choice'] == 'auto' and data['max_tokens'] == 768
            assert data['messages'][0]['content'] == '查询'
            return httpx.Response(200, json={'choices': [{'message': {'role': 'assistant', 'content': '测试回答'}}]})
        client.http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        try: assert (await client.chat([{'role': 'user', 'content': '查询'}], []))['content'] == '测试回答'
        finally: await client.close()
    asyncio.run(run())

@pytest.mark.parametrize('failure', ['http', 'malformed', 'timeout'])
def test_model_dependency_failures_wrap_private_details(settings, failure):
    settings.llm_base_url = 'http://model.invalid/v1'
    async def run():
        client = ModelClient(settings); await client.http.aclose()
        def handler(request):
            if failure == 'timeout': raise httpx.ReadTimeout('PRIVATE_TRACE', request=request)
            return httpx.Response(500, text='PRIVATE_TRACE') if failure == 'http' else httpx.Response(200, json={})
        client.http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        try:
            with pytest.raises(ServiceError) as exc: await client.chat([], [])
            assert str(exc.value) == 'Model unavailable'
        finally: await client.close()
    asyncio.run(run())
