from fastapi import Request, UploadFile, File
from voice.common.settings import VoiceSettings
from voice.common.http import base_app
from voice.common.errors import SizeError, VoiceError
from .audio_normalization import normalize_audio
from .funasr_adapter import FunASRAdapter

def create_app(settings=None, engine_factory=None):
    settings = settings or VoiceSettings()
    app = base_app('asr', settings, engine_factory or (lambda: FunASRAdapter(settings)))
    @app.post('/asr')
    async def transcribe(request: Request, audio: UploadFile = File(...)):
        content = bytearray()
        try:
            while chunk := await audio.read(65536):
                content.extend(chunk)
                if len(content) > settings.max_upload_bytes: raise SizeError()
        finally: await audio.close()
        def process():
            normalized = normalize_audio(bytes(content), settings)
            try: text = request.app.state.engine.transcribe(normalized)
            except VoiceError: raise
            except Exception as exc: raise VoiceError() from exc
            if not isinstance(text, str) or len(text) > 10000: raise VoiceError()
            return {'text': text, 'duration_seconds': round(normalized.duration, 3), 'sample_rate': 16000}
        return await request.app.state.runner.run(process, settings.asr_timeout_seconds)
    return app

app = create_app()
