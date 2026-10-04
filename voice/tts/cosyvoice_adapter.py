from pathlib import Path
import importlib
import re
import subprocess
import sys
import numpy as np
import yaml
from voice.common.errors import VoiceError

def load_registry(path):
    value = yaml.safe_load(Path(path).read_text(encoding='utf-8'))
    if not isinstance(value, dict) or set(value) != {'voices'}:
        raise ValueError('Registry must contain only voices mapping')
    voices = value['voices']
    if not isinstance(voices, dict) or 'default' not in voices or len(voices) > 16:
        raise ValueError('Configure <=16 voices including default')
    for key, speaker in voices.items():
        if not isinstance(key, str) or not re.fullmatch(r'[a-z][a-z0-9_]{0,31}', key):
            raise ValueError('Invalid public voice identifier')
        if not isinstance(speaker, str) or not speaker.strip() or len(speaker) > 64:
            raise ValueError('Invalid SFT speaker identifier')
    return voices

def waveform_array(value):
    if hasattr(value, 'detach'): value = value.detach().cpu().numpy()
    array = np.asarray(value, dtype=np.float32)
    if array.ndim == 2 and array.shape[0] == 1: array = array[0]
    if array.ndim != 1 or not len(array) or not np.isfinite(array).all():
        raise ValueError('CosyVoice output must be finite mono audio')
    return np.clip(array, -1, 1)

class CosyVoiceAdapter:
    kind = 'cosyvoice-300m-sft'
    def __init__(self, settings, model_factory=None):
        directory = Path(settings.tts_model_dir).resolve()
        required = ('cosyvoice.yaml', 'spk2info.pt', 'llm.pt', 'flow.pt', 'hift.pt',
                    'campplus.onnx', 'speech_tokenizer_v1.onnx')
        if not all((directory / name).is_file() for name in required):
            raise ValueError('Configure a complete local CosyVoice-300M-SFT checkpoint')
        if model_factory is None:
            source = Path(settings.cosyvoice_source).resolve()
            if not (source / 'cosyvoice/cli/cosyvoice.py').is_file() or not (source / 'third_party/Matcha-TTS').is_dir():
                raise ValueError('Configure official CosyVoice source checkout including submodules')
            if settings.cosyvoice_commit:
                commit = subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip()
                if commit != settings.cosyvoice_commit: raise ValueError('CosyVoice checkout commit mismatch')
            sys.path.insert(0, str(source / 'third_party/Matcha-TTS'))
            sys.path.insert(0, str(source))
            module = importlib.import_module('cosyvoice.cli.cosyvoice')
            if not Path(module.__file__).resolve().is_relative_to(source):
                raise ValueError('Imported cosyvoice does not match configured source checkout')
            model_factory = module.CosyVoice
        self.model = model_factory(str(directory), load_jit=False, load_trt=False, fp16=settings.tts_fp16)
        self.voices = load_registry(settings.voice_registry)
        available = set(self.model.list_available_spks())
        if not set(self.voices.values()) <= available:
            raise ValueError('Registry refers to SFT speakers missing from checkpoint')
        self.sample_rate = int(self.model.sample_rate)
        if not 8000 <= self.sample_rate <= 48000: raise ValueError('Invalid TTS sample rate')
        self.max_frames = min(int(settings.max_tts_seconds * self.sample_rate), (settings.max_tts_bytes - 44) // 2)

    def synthesize(self, chunks, voice):
        if voice not in self.voices: raise ValueError('Unknown voice')
        segments = []; total = 0
        try:
            for text in chunks:
                for result in self.model.inference_sft(text, self.voices[voice], stream=False):
                    if not isinstance(result, dict) or 'tts_speech' not in result: raise ValueError('Invalid TTS result')
                    speech = waveform_array(result['tts_speech'])
                    total += len(speech)
                    if total > self.max_frames: raise ValueError('TTS audio exceeds limits')
                    segments.append(speech)
            if not segments: raise ValueError('Empty TTS audio')
            return np.concatenate(segments), self.sample_rate
        except Exception as exc: raise VoiceError() from exc
