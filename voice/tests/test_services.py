import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
import httpx
import numpy as np
import pytest
from fastapi.testclient import TestClient
from voice.asr.server import create_app as create_asr
from voice.tts.server import create_app as create_tts
from voice.common.http import BodyLimit

class ASR:
    kind = 'test-double-asr'
    def transcribe(self, audio):
        assert audio.sample_rate == 16000
        return '2026-10-04查询教室'

class TTS:
    kind = 'test-double-tts'
    voices = {'default': 'test-speaker'}
    def synthesize(self, chunks, voice):
        assert voice == 'default'
        return np.zeros(2205), 22050

def test_asr_endpoint_matches_backend_multipart_contract(settings, wav):
    with TestClient(create_asr(settings, ASR)) as client:
        assert client.get('/health').json()['engine'] == 'test-double-asr'
        result = client.post('/asr', files={'audio': ('../../badname.wav', wav, 'audio/wav')})
        assert result.status_code == 200 and result.json()['text'] == '2026-10-04查询教室'
        assert result.json()['sample_rate'] == 16000
        assert result.headers['cache-control'] == 'no-store'

def test_tts_endpoint_matches_backend_wav_contract(settings):
    with TestClient(create_tts(settings, TTS)) as client:
        result = client.post('/tts', json={'text': '测试教室101。', 'voice': 'default'})
        assert result.status_code == 200 and result.content[:4] == b'RIFF'
        assert result.content[8:12] == b'WAVE' and result.headers['content-type'] == 'audio/wav'

@pytest.mark.parametrize('body', [{'text': ''}, {'text': '字' * 1001}, {'text': 'text', 'voice': 'unknown'},
                                {'text': 'text', 'user_id': 'bob'}, {'text': 'text', 'voice': '../../path'}])
def test_invalid_tts_requests_do_not_reach_engine(settings, body):
    with TestClient(create_tts(settings, TTS)) as client:
        assert client.post('/tts', json=body).status_code == 422

def test_upload_limit_and_bad_audio_status(settings, wav):
    settings.max_upload_bytes = 1024
    with TestClient(create_asr(settings, ASR)) as client:
        assert client.post('/asr', files={'audio': ('bad.wav', b'invalid')}).status_code == 422
        assert client.post('/asr', files={'audio': ('large.wav', wav)}).status_code == 413
        assert client.post('/asr', content=b'x' * 70000).status_code == 413

def test_model_exception_public_response_does_not_include_upstream_details(settings):
    class Broken(TTS):
        def synthesize(self, *args): raise RuntimeError('PRIVATE_PATH_AND_TRACE')
    with TestClient(create_tts(settings, Broken)) as client:
        result = client.post('/tts', json={'text': 'hello'})
        assert result.status_code == 503 and 'PRIVATE_PATH_AND_TRACE' not in result.text

def test_chunked_body_limit_counts_actual_bytes_before_reading_more():
    async def run():
        sent = []
        async def app(scope, receive, send):
            pytest.fail('Oversized chunked body reached parser')
        chunks = iter([{'type': 'http.request', 'body': b'ab', 'more_body': True},
                       {'type': 'http.request', 'body': b'cdef', 'more_body': False}])
        async def receive(): return next(chunks)
        async def send(value): sent.append(value)
        await BodyLimit(app, 4)({'type': 'http', 'method': 'POST', 'headers': []}, receive, send)
        assert sent[0]['status'] == 413
    asyncio.run(run())

def test_real_tts_chunked_body_reports_413_before_json_parser(settings):
    with TestClient(create_tts(settings, TTS)) as client:
        result = client.post('/tts', content=iter([b'{"text":"', b'x' * 17000, b'"}']),
                             headers={'Content-Type': 'application/json'})
        assert result.status_code == 413

def test_backend_reaches_actual_voice_asgi_services(settings, wav, tmp_path, monkeypatch):
    from app.main import create_app as create_backend
    from app.settings import Settings
    from app.api import voice as backend_voice
    project = Path(__file__).resolve().parents[2]
    backend_settings = Settings(_env_file=None, database_url=f'sqlite:///{tmp_path / "backend.db"}',
                                skill_root=project / 'skills', asr_url='http://asr/asr', tts_url='http://tts/tts')
    original = httpx.AsyncClient
    with TestClient(create_asr(settings, ASR)) as asr, TestClient(create_tts(settings, TTS)) as tts, TestClient(create_backend(backend_settings)) as backend:
        routes = {'asr': asr, 'tts': tts}
        def handler(request):
            service = routes[request.url.host]
            result = service.request(request.method, request.url.path, content=request.content, headers=dict(request.headers))
            return httpx.Response(result.status_code, content=result.content, headers=dict(result.headers))
        def factory(**kwargs): return original(transport=httpx.MockTransport(handler), **kwargs)
        monkeypatch.setattr(backend_voice.httpx, 'AsyncClient', factory)
        auth = {'Authorization': 'Bearer demo-token'}
        transcript = backend.post('/api/voice/transcribe', headers=auth, files={'audio': ('x.wav', wav, 'audio/wav')})
        assert transcript.status_code == 200 and transcript.json()['text'] == '2026-10-04查询教室'
        chat = backend.post('/api/chat', headers=auth, json={'message': transcript.json()['text']})
        assert chat.status_code == 200
        audio = backend.post('/api/voice/synthesize', headers=auth, json={'message_id': chat.json()['message_id']})
        assert audio.status_code == 200 and audio.content[:4] == b'RIFF'
