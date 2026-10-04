from pathlib import Path
import io
import os
import sys
import wave
import numpy as np
import pytest
PROJECT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT))
sys.path.insert(0, str(PROJECT / 'backend'))
from voice.common.settings import VoiceSettings

@pytest.fixture(autouse=True)
def environment(monkeypatch):
    for key in list(os.environ):
        if key.startswith(('VOICE_', 'CAMPUS_')): monkeypatch.delenv(key)

@pytest.fixture
def settings(): return VoiceSettings(_env_file=None)

def make_wav(rate=48000, channels=2, seconds=.2):
    samples = (np.sin(np.arange(int(rate * seconds)) * (2 * np.pi * 440 / rate)) * 8000).astype('<i2')
    if channels == 2: samples = np.repeat(samples[:, None], 2, axis=1).reshape(-1)
    stream = io.BytesIO()
    with wave.open(stream, 'wb') as output:
        output.setnchannels(channels); output.setsampwidth(2); output.setframerate(rate)
        output.writeframes(samples.tobytes())
    return stream.getvalue()

@pytest.fixture
def wav(): return make_wav()
