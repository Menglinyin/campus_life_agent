import io
import wave
import numpy as np
import pytest
from voice.tts.text_normalization import normalize_text, split_text
from voice.tts.wav_encoding import encode_wav
from voice.common.errors import InputError, SizeError, VoiceError

def test_markdown_date_and_time_are_converted_to_speakable_text():
    result = normalize_text('## 教室\n**2026-10-04**，14:00，见[须知](https://example.invalid)。')
    assert result == '教室 2026年10月4日,14点整,见须知。'

def test_code_markup_control_and_model_tokens_are_not_spoken():
    result = normalize_text('正常\x00回答 <|im_start|> ```secret code``` <b>结尾</b>')
    assert result == '正常 回答 结尾'

@pytest.mark.parametrize('text', ['', '   ', '```only code```'])
def test_empty_spoken_content_rejected(text):
    with pytest.raises(InputError): normalize_text(text)

def test_invalid_dates_are_not_reinterpreted_and_length_is_not_truncated():
    assert normalize_text('2026-99-99和25:99') == '2026-99-99和25:99'
    with pytest.raises(SizeError): normalize_text('字' * 1001)

def test_chunking_preserves_content_and_limits_every_call():
    text = '第一句。第二句！' + '长' * 405
    chunks = split_text(text, 200)
    assert ''.join(chunks) == text and all(0 < len(x) <= 200 for x in chunks)

def test_real_pcm_wav_header_channels_sample_rate_and_bounds(settings):
    data = encode_wav(np.array([-2., -.5, .5, 2.]), 22050, settings)
    with wave.open(io.BytesIO(data), 'rb') as wav:
        assert wav.getnchannels() == 1 and wav.getsampwidth() == 2
        assert wav.getframerate() == 22050 and wav.getnframes() == 4
        np.testing.assert_array_equal(np.frombuffer(wav.readframes(4), dtype='<i2'), [-32767, -16384, 16384, 32767])

def test_wav_duration_and_size_are_checked(settings):
    settings.max_tts_bytes = 1024
    with pytest.raises(VoiceError): encode_wav(np.ones(1000), 16000, settings)
    settings.max_tts_seconds = 1
    with pytest.raises(VoiceError): encode_wav(np.ones(16001), 16000, settings)
