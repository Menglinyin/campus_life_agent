import io
import json
import wave
import httpx
import pytest
from app.api import voice
AUTH = {'Authorization': 'Bearer tests-alice'}

@pytest.fixture
def wav():
    output = io.BytesIO()
    with wave.open(output, 'wb') as audio:
        audio.setnchannels(1); audio.setsampwidth(2); audio.setframerate(16000)
        audio.writeframes(b'\0\0' * 160)
    return output.getvalue()

@pytest.fixture
def mock_voice_http(monkeypatch):
    original = httpx.AsyncClient
    def install(handler):
        def factory(**kwargs):
            return original(transport=httpx.MockTransport(handler), **kwargs)
        monkeypatch.setattr(voice.httpx, 'AsyncClient', factory)
    return install

def test_unconfigured_services_return_503(client, ask, wav):
    assert client.post('/api/voice/transcribe', headers=AUTH, files={'audio': ('x.wav', wav, 'audio/wav')}).status_code == 503
    data = ask('2026-10-04教室').json()
    assert client.post('/api/voice/synthesize', headers=AUTH, json={'message_id': data['message_id']}).status_code == 503

def test_asr_multipart_contract_and_transcript_can_feed_agent(client, ask, wav, mock_voice_http):
    client.app.state.services.settings.asr_url = 'http://voice.invalid/asr'
    def handler(request):
        assert str(request.url) == 'http://voice.invalid/asr'
        assert 'multipart/form-data' in request.headers['content-type']
        assert b'name="audio"' in request.content and wav in request.content
        return httpx.Response(200, json={'text': '2026-10-04查询教室'})
    mock_voice_http(handler)
    result = client.post('/api/voice/transcribe', headers=AUTH, files={'audio': ('x.wav', wav, 'audio/wav')})
    assert result.status_code == 200
    assert ask(result.json()['text']).json()['results'][0]['rows'][0]['id'] == 'room-open'

@pytest.mark.parametrize('failure', ['http', 'missing_text', 'wrong_type', 'too_long', 'timeout'])
def test_asr_bad_upstream_is_sanitized(client, wav, mock_voice_http, failure):
    client.app.state.services.settings.asr_url = 'http://voice.invalid/asr'
    def handler(request):
        if failure == 'timeout': raise httpx.ReadTimeout('PRIVATE_UPSTREAM_TRACE', request=request)
        values = {'missing_text': {}, 'wrong_type': {'text': 7}, 'too_long': {'text': 'x' * 10001}}
        return httpx.Response(500, text='PRIVATE_UPSTREAM_TRACE') if failure == 'http' else httpx.Response(200, json=values[failure])
    mock_voice_http(handler)
    result = client.post('/api/voice/transcribe', headers=AUTH, files={'audio': ('x.wav', wav, 'audio/wav')})
    assert result.status_code == 503 and 'PRIVATE_UPSTREAM_TRACE' not in result.text

def test_asr_rejects_upload_over_eight_mib_before_upstream_call(client, mock_voice_http):
    client.app.state.services.settings.asr_url = 'http://voice.invalid/asr'
    def handler(request): pytest.fail('Oversized upload must not reach upstream')
    mock_voice_http(handler)
    result = client.post('/api/voice/transcribe', headers=AUTH, files={'audio': ('x.wav', b'x' * (8 * 1024 * 1024 + 1), 'audio/wav')})
    assert result.status_code == 413

def test_tts_synthesizes_owned_assistant_text_and_returns_wav(client, ask, wav, mock_voice_http):
    client.app.state.services.settings.tts_url = 'http://voice.invalid/tts'
    data = ask('2026-10-04教室').json()
    def handler(request):
        assert str(request.url) == 'http://voice.invalid/tts'
        assert json.loads(request.content) == {'text': data['answer'][:1000], 'voice': 'default'}
        return httpx.Response(200, content=wav)
    mock_voice_http(handler)
    result = client.post('/api/voice/synthesize', headers=AUTH, json={'message_id': data['message_id']})
    assert result.status_code == 200 and result.content == wav
    assert result.headers['content-type'] == 'audio/wav'

@pytest.mark.parametrize('failure', ['http', 'invalid_wav', 'oversized', 'timeout'])
def test_tts_bad_upstream_is_sanitized(client, ask, mock_voice_http, failure):
    client.app.state.services.settings.tts_url = 'http://voice.invalid/tts'
    data = ask('2026-10-04教室').json()
    def handler(request):
        if failure == 'timeout': raise httpx.ReadTimeout('PRIVATE_TRACE', request=request)
        status, body = {'http': (500, b'PRIVATE_TRACE'), 'invalid_wav': (200, b'not WAV'),
                        'oversized': (200, b'RIFF' + b'x' * (16 * 1024 * 1024))}[failure]
        return httpx.Response(status, content=body)
    mock_voice_http(handler)
    result = client.post('/api/voice/synthesize', headers=AUTH, json={'message_id': data['message_id']})
    assert result.status_code == 503 and 'PRIVATE_TRACE' not in result.text

def test_tts_does_not_accept_arbitrary_text_or_user_message(client, ask, mock_voice_http):
    client.app.state.services.settings.tts_url = 'http://voice.invalid/tts'
    def handler(request): pytest.fail('Unauthorized synthesis reached upstream')
    mock_voice_http(handler)
    assert client.post('/api/voice/synthesize', headers=AUTH, json={'text': 'arbitrary'}).status_code == 422
    data = ask('2026-10-04教室').json()
    history = client.get(f"/api/sessions/{data['session_id']}/messages", headers=AUTH).json()
    user_message = next(m['id'] for m in history['messages'] if m['role'] == 'user')
    assert client.post('/api/voice/synthesize', headers=AUTH, json={'message_id': user_message}).status_code == 404
