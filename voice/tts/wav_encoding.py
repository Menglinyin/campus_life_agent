import io
import wave
import numpy as np
from voice.common.errors import VoiceError
from .cosyvoice_adapter import waveform_array

def encode_wav(samples, sample_rate, settings):
    try:
        samples = waveform_array(samples)
        if not isinstance(sample_rate, int) or not 8000 <= sample_rate <= 48000:
            raise ValueError('Invalid sample rate')
        if len(samples) / sample_rate > settings.max_tts_seconds: raise ValueError('Audio exceeds duration')
        if len(samples) * 2 + 44 > settings.max_tts_bytes: raise ValueError('Audio exceeds byte limit')
        pcm = np.rint(samples * 32767).astype('<i2').tobytes()
        buffer = io.BytesIO()
        with wave.open(buffer, 'wb') as output:
            output.setnchannels(1); output.setsampwidth(2); output.setframerate(sample_rate)
            output.writeframes(pcm)
        return buffer.getvalue()
    except (ValueError, TypeError) as exc: raise VoiceError() from exc
