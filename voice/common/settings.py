from pathlib import Path
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
ROOT = Path(__file__).resolve().parents[1]

class VoiceSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix='VOICE_', env_file=None, extra='ignore')
    max_upload_bytes: int = Field(8 * 1024 * 1024, ge=1024, le=8 * 1024 * 1024)
    max_audio_seconds: float = Field(60, ge=.1, le=60)
    decode_timeout_seconds: float = Field(5, gt=0, le=20)
    ffmpeg: str = 'ffmpeg'
    asr_timeout_seconds: float = Field(25, gt=0, le=25)
    tts_timeout_seconds: float = Field(50, gt=0, le=50)
    max_concurrency: int = Field(1, ge=1, le=4)
    asr_model_dir: Path = Path('/models/paraformer')
    asr_vad_dir: Path | None = None
    asr_punc_dir: Path | None = None
    asr_device: str = 'cpu'
    vocabulary: Path = ROOT / 'asr' / 'vocabulary.txt'
    cosyvoice_source: Path = Path('/opt/CosyVoice')
    cosyvoice_commit: str = ''
    tts_model_dir: Path = Path('/models/CosyVoice-300M-SFT')
    tts_fp16: bool = False
    voice_registry: Path = ROOT / 'tts' / 'voice_registry.yaml'
    max_text_characters: int = Field(1000, ge=1, le=1000)
    tts_chunk_characters: int = Field(200, ge=20, le=300)
    max_tts_seconds: float = Field(120, ge=1, le=300)
    max_tts_bytes: int = Field(16 * 1024 * 1024, ge=1024, le=16 * 1024 * 1024)

    @field_validator('asr_device')
    @classmethod
    def valid_device(cls, value):
        import re
        if not re.fullmatch(r'cpu|cuda(?::\d+)?', value):
            raise ValueError('asr_device must be cpu, cuda or cuda:N')
        return value

    @field_validator('cosyvoice_commit')
    @classmethod
    def valid_commit(cls, value):
        import re
        if value and not re.fullmatch(r'[0-9a-f]{40}', value):
            raise ValueError('Record the full lowercase 40-character CosyVoice commit')
        return value
