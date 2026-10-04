"""Decode local uploaded audio with FFmpeg into bounded mono float32 at 16 kHz."""
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
import subprocess
import numpy as np
from voice.common.errors import InputError, SizeError, VoiceError, WorkTimeout

@dataclass(frozen=True)
class NormalizedAudio:
    samples: np.ndarray
    sample_rate: int = 16000
    @property
    def duration(self): return len(self.samples) / self.sample_rate

def normalize_audio(content, settings):
    if not content: raise InputError()
    if len(content) > settings.max_upload_bytes: raise SizeError()
    # Select a demuxer from binary signatures; do not accept uploaded playlists.
    if content[:4] == b'RIFF' and content[8:12] == b'WAVE': container = 'wav'
    elif content[:4] == b'OggS': container = 'ogg'
    elif content[:4] == b'\x1aE\xdf\xa3': container = 'matroska'
    elif content[4:8] == b'ftyp': container = 'mov'
    elif content[:4] == b'fLaC': container = 'flac'
    elif content[:3] == b'ID3' or (len(content) > 1 and content[0] == 255 and content[1] & 224 == 224): container = 'mp3'
    else: raise InputError()
    with TemporaryDirectory(prefix='campus-asr-') as temporary:
        source = Path(temporary) / 'upload.bin'
        source.write_bytes(content)
        # Decode one extra second to detect excessive duration instead of silently truncating.
        command = [settings.ffmpeg, '-hide_banner', '-loglevel', 'error', '-nostdin',
                   '-protocol_whitelist', 'file,pipe', '-f', container, '-i', str(source), '-map', '0:a:0',
                   '-vn', '-sn', '-dn', '-ac', '1', '-ar', '16000',
                   '-t', str(settings.max_audio_seconds + 1), '-f', 'f32le', 'pipe:1']
        try:
            result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                    timeout=settings.decode_timeout_seconds, check=False)
        except FileNotFoundError as exc: raise VoiceError() from exc
        except subprocess.TimeoutExpired as exc: raise WorkTimeout() from exc
        if result.returncode or not result.stdout or len(result.stdout) % 4:
            raise InputError()
        samples = np.frombuffer(result.stdout, dtype='<f4').copy()
    if not np.isfinite(samples).all(): raise InputError()
    if len(samples) > int(settings.max_audio_seconds * 16000): raise SizeError()
    if len(samples) < 1600: raise InputError()
    return NormalizedAudio(np.clip(samples, -1, 1).astype(np.float32))
