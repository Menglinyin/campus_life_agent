from fastapi import Request, Response
from pydantic import BaseModel, Field, ConfigDict
from voice.common.settings import VoiceSettings
from voice.common.http import base_app
from voice.common.errors import InputError, VoiceError
from .cosyvoice_adapter import CosyVoiceAdapter
from .text_normalization import normalize_text, split_text
from .wav_encoding import encode_wav

class SynthesisRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    text: str = Field(min_length=1, max_length=1000)
    voice: str = Field(default='default', pattern=r'^[a-z][a-z0-9_]{0,31}$')

def create_app(settings=None, engine_factory=None):
    settings = settings or VoiceSettings()
    app = base_app('tts', settings, engine_factory or (lambda: CosyVoiceAdapter(settings)))
    @app.post('/tts')
    async def synthesize(body: SynthesisRequest, request: Request):
        engine = request.app.state.engine
        if body.voice not in engine.voices: raise InputError()
        text = normalize_text(body.text, settings.max_text_characters)
        chunks = split_text(text, settings.tts_chunk_characters)
        def process():
            try: samples, rate = engine.synthesize(chunks, body.voice)
            except VoiceError: raise
            except Exception as exc: raise VoiceError() from exc
            return encode_wav(samples, rate, settings)
        audio = await request.app.state.runner.run(process, settings.tts_timeout_seconds)
        return Response(audio, media_type='audio/wav')
    return app

app = create_app()
