import json
import uuid
import pytest
DAY = '2026-10-04'
AUTH = {'Authorization': 'Bearer tests-alice'}
OTHER = {'Authorization': 'Bearer tests-bob'}

def test_multi_intent_uses_real_graph_and_filtered_sql_rows(ask):
    response = ask(f'{DAY} 查询教室、旁听课程、食堂菜品和二手物品')
    assert response.status_code == 200, response.text
    data = response.json(); results = {r['tool']: r['rows'] for r in data['results']}
    assert set(results) == {'query_classrooms', 'query_courses', 'recommend_dishes', 'query_secondhand'}
    assert [r['id'] for r in results['query_classrooms']] == ['room-open']
    assert [r['id'] for r in results['query_courses']] == ['course-open']
    assert [r['id'] for r in results['recommend_dishes']] == ['dish-mild', 'dish-spicy']
    assert [r['id'] for r in results['query_secondhand']] == ['item-active']
    assert data['mode'] == 'demo'

def test_date_clarification_resumes_pending_intent(ask, client):
    first = ask('查询空闲教室').json()
    assert '哪一天' in first['answer'] and first['results'] == []
    second = ask(DAY, session_id=first['session_id']).json()
    assert second['results'][0]['rows'][0]['id'] == 'room-open'
    history = client.get(f"/api/sessions/{first['session_id']}/messages", headers=AUTH).json()
    assert history['version'] == 2 and len(history['messages']) == 4
    assert history['slots']['date'] == DAY and 'pending' not in history['slots']

def test_preferences_override_and_are_isolated_between_students(ask, client):
    first = ask(f'我不吃辣，预算10元，{DAY}推荐菜品').json()
    assert [r['id'] for r in first['results'][0]['rows']] == ['dish-mild']
    second = ask(f'现在可以吃微辣，预算20元，{DAY}推荐菜品', session_id=first['session_id']).json()
    assert len(second['results'][0]['rows']) == 2
    assert client.get('/api/preferences', headers=AUTH).json() == {'spice': 1, 'budget': 20}
    assert client.get('/api/preferences', headers=OTHER).json() == {}

def test_chat_and_history_persist_when_app_reopens_database(client, settings, ask):
    from fastapi.testclient import TestClient
    from app.main import create_app
    first = ask(f'不吃辣，{DAY}推荐菜品').json()
    with TestClient(create_app(settings)) as reopened:
        assert reopened.get('/api/preferences', headers=AUTH).json()['spice'] == 0
        history = reopened.get(f"/api/sessions/{first['session_id']}/messages", headers=AUTH).json()
        assert history['version'] == 1 and len(history['messages']) == 2

def test_cross_user_access_denied_for_history_chat_chart_and_tts(ask, client):
    data = ask(f'{DAY} 推荐菜品').json()
    assert client.get(f"/api/sessions/{data['session_id']}/messages", headers=OTHER).status_code == 404
    assert ask(DAY, headers=OTHER, session_id=data['session_id']).status_code == 404
    for endpoint in ('charts', 'voice/synthesize'):
        assert client.post('/api/' + endpoint, json={'message_id': data['message_id']}, headers=OTHER).status_code == 404

@pytest.mark.parametrize('headers', [{}, {'Authorization': 'Bearer invalid'}, {'Authorization': 'Basic invalid'}])
def test_authentication_required(ask, headers):
    response = ask('你好', headers=headers)
    assert response.status_code == 401 and response.headers['www-authenticate'] == 'Bearer'

@pytest.mark.parametrize('message,fields', [('', {}), ('x' * 2001, {}), ('教室', {'session_id': 'bad-uuid'}),
    ('2026-99-99教室', {}), ('教室', {'date': 'invalid'})])
def test_bad_requests_return_422(ask, message, fields):
    assert ask(message, **fields).status_code == 422

def test_unknown_session_does_not_leak_data(ask):
    assert ask('教室', session_id=str(uuid.uuid4())).status_code == 404

def test_version_conflict_rolls_back_both_messages(client, ask):
    from fastapi import HTTPException
    first = ask(f'{DAY}教室').json(); repo = client.app.state.services.conversations
    with pytest.raises(HTTPException) as exc:
        repo.save_turn('alice', first['session_id'], 'stale question', 'stale answer', {}, {}, 0)
    assert exc.value.status_code == 409
    assert len(repo.snapshot('alice', first['session_id'])['messages']) == 2

@pytest.fixture
def mocked_model(client, monkeypatch):
    services = client.app.state.services
    original = services.model
    monkeypatch.setattr(services.settings, 'llm_base_url', 'http://model.invalid/v1')
    def install(model): monkeypatch.setattr(services, 'model', model)
    yield install
    services.model = original

def test_mock_model_cannot_replace_confirmed_date_or_invent_business_answer(client, ask, mocked_model):
    class Model:
        def __init__(self): self.count = 0
        async def chat(self, messages, tools):
            self.count += 1
            if self.count == 1:
                assert 'name: "classroom-search"' in messages[0]['content']
                return {'role': 'assistant', 'tool_calls': [{'id': 'call-a', 'type': 'function',
                    'function': {'name': 'query_classrooms', 'arguments': json.dumps({'date': '2026-10-05'})}}]}
            assert messages[-1]['role'] == 'tool'
            return {'role': 'assistant', 'content': '伪造的推荐教室999'}
    model = Model(); mocked_model(model)
    response = ask(f'{DAY} 查询教室'); assert response.status_code == 200, response.text
    data = response.json()
    assert data['results'][0]['rows'][0]['id'] == 'room-open'
    assert '测试教室101' in data['answer'] and '999' not in data['answer']
    assert model.count == 2

def test_mock_model_cannot_supply_a_missing_date(ask, mocked_model):
    class Model:
        async def chat(self, messages, tools):
            return {'role': 'assistant', 'tool_calls': [{'id': 'x', 'type': 'function',
                'function': {'name': 'query_classrooms', 'arguments': '{"date":"2026-10-04"}'}}]}
    mocked_model(Model())
    data = ask('查询教室').json()
    assert '哪一天' in data['answer'] and not data['results']

def test_charts_use_owned_tool_results_and_reject_non_dish_message(ask, client):
    result = ask(f'{DAY}推荐菜品').json()
    chart = client.post('/api/charts', headers=AUTH, json={'message_id': result['message_id']})
    assert chart.status_code == 200 and chart.json()['options']['series'][0]['data'] == [10., 15.]
    room = ask(f'{DAY}教室').json()
    assert client.post('/api/charts', headers=AUTH, json={'message_id': room['message_id']}).status_code == 422

def test_empty_query_results_and_request_identifier(ask):
    response = ask('2030-01-01查询教室')
    assert response.status_code == 200 and response.json()['results'][0]['rows'] == []
    assert '没有查到' in response.json()['answer']
    uuid.UUID(response.headers['x-request-id'])
