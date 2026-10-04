import io
import subprocess
from pathlib import Path
import numpy as np
import pytest
from voice.asr.audio_normalization import normalize_audio
from voice.common.errors import InputError, SizeError, VoiceError, WorkTimeout
from voice.tests.conftest import make_wav

def test_real_ffmpeg_resamples_stereo_48k_to_mono_16k(wav, settings):
    audio = normalize_audio(wav, settings)
    assert audio.sample_rate == 16000 and audio.samples.dtype == np.float32
    assert audio.samples.ndim == 1 and audio.duration == pytest.approx(.2, abs=.001)
    assert np.max(np.abs(audio.samples)) > .1

@pytest.mark.parametrize('format,codec', [('webm', 'libopus'), ('mp3', 'libmp3lame'), ('flac', 'flac'), ('m4a', 'aac'), ('ogg', 'libopus')])
def test_real_compressed_audio_is_accepted(wav, settings, tmp_path, format, codec):
    source = tmp_path / 'source.wav'; source.write_bytes(wav)
    output = tmp_path / ('audio.' + format)
    subprocess.run([settings.ffmpeg, '-v', 'error', '-i', str(source), '-c:a', codec, str(output)], check=True)
    assert normalize_audio(output.read_bytes(), settings).duration == pytest.approx(.2, abs=.08)

@pytest.mark.parametrize('data', [b'', b'not audio', b'RIFF0000WAVEbad', b'#EXTM3U\nhttp://private.invalid/a.wav'])
def test_empty_malformed_and_playlist_inputs_rejected(data, settings):
    with pytest.raises(InputError): normalize_audio(data, settings)

def test_limits_reject_instead_of_silently_truncating(settings):
    settings.max_audio_seconds = .2
    with pytest.raises(SizeError): normalize_audio(make_wav(seconds=.5), settings)
    settings.max_upload_bytes = 1024
    with pytest.raises(SizeError): normalize_audio(b'x' * 1025, settings)

def test_missing_decoder_and_decoder_timeout_are_dependencies(wav, settings, monkeypatch):
    settings.ffmpeg = '/nonexistent/campus-ffmpeg'
    with pytest.raises(VoiceError): normalize_audio(wav, settings)
    def timeout(*args, **kwargs): raise subprocess.TimeoutExpired('test', .01)
    monkeypatch.setattr(subprocess, 'run', timeout)
    with pytest.raises(WorkTimeout): normalize_audio(wav, settings)

def test_upload_names_never_form_paths_and_temp_files_are_deleted(wav, settings, monkeypatch):
    original = subprocess.run; seen = []
    def capture(command, **kwargs):
        path = Path(command[command.index('-i') + 1]); seen.append(path)
        assert path.name == 'upload.bin'
        assert command[command.index('-protocol_whitelist') + 1] == 'file,pipe'
        return original(command, **kwargs)
    monkeypatch.setattr(subprocess, 'run', capture)
    normalize_audio(wav, settings)
    assert seen and not seen[0].exists()
