from pathlib import Path
import numpy as np
import pytest
from voice.asr.audio_normalization import NormalizedAudio
from voice.asr.funasr_adapter import FunASRAdapter, load_vocabulary
from voice.tts.cosyvoice_adapter import CosyVoiceAdapter, load_registry, waveform_array
from voice.common.errors import VoiceError

@pytest.fixture
def asr_setup(settings, tmp_path):
    settings.asr_model_dir = tmp_path / 'paraformer'; settings.asr_model_dir.mkdir()
    settings.asr_vad_dir = tmp_path / 'vad'; settings.asr_vad_dir.mkdir()
    settings.asr_punc_dir = tmp_path / 'punc'; settings.asr_punc_dir.mkdir()
    settings.vocabulary = tmp_path / 'vocabulary.txt'; settings.vocabulary.write_text('# comment\n旁听\n食堂\n旁听\n', encoding='utf-8')
    return settings

@pytest.fixture
def tts_setup(settings, tmp_path):
    settings.tts_model_dir = tmp_path / 'sft'; settings.tts_model_dir.mkdir()
    for name in ['cosyvoice.yaml', 'spk2info.pt', 'llm.pt', 'flow.pt', 'hift.pt', 'campplus.onnx', 'speech_tokenizer_v1.onnx']:
        (settings.tts_model_dir / name).write_bytes(b'TEST_FIXTURE_NOT_A_MODEL')
    settings.voice_registry = tmp_path / 'voices.yaml'; settings.voice_registry.write_text('voices:\n  default: 中文女\n', encoding='utf-8')
    return settings

def test_funasr_loads_once_and_passes_rate_hotwords_vad_punc(asr_setup):
    captured = {}
    class Model:
        def generate(self, **kwargs):
            captured['generate'] = kwargs
            return [{'text': '旁听'}, {'text': '食堂'}]
    def factory(**kwargs): captured['factory'] = kwargs; return Model()
    adapter = FunASRAdapter(asr_setup, factory)
    audio = NormalizedAudio(np.ones(3200, dtype=np.float32))
    assert adapter.transcribe(audio) == '旁听 食堂'
    assert captured['factory']['vad_model'] == str(asr_setup.asr_vad_dir)
    assert captured['factory']['punc_model'] == str(asr_setup.asr_punc_dir)
    assert captured['factory']['trust_remote_code'] is False
    assert captured['generate']['fs'] == 16000
    assert captured['generate']['hotword'] == '旁听 食堂'
    assert captured['generate']['cache'] == {}
    assert captured['generate']['input'] is audio.samples

@pytest.mark.parametrize('result', [None, [{'text': 5}], [{'unexpected': 'value'}], [{'text': 'x' * 10001}]])
def test_asr_malformed_sdk_result_is_not_sent_to_agent(asr_setup, result):
    class Model:
        def generate(self, **kwargs): return result
    adapter = FunASRAdapter(asr_setup, lambda **kwargs: Model())
    with pytest.raises(VoiceError): adapter.transcribe(NormalizedAudio(np.ones(3200)))

def test_missing_asr_path_fails_before_sdk_download(settings, tmp_path):
    settings.asr_model_dir = tmp_path / 'missing'
    def factory(**kwargs): pytest.fail('No model download should be attempted')
    with pytest.raises(ValueError): FunASRAdapter(settings, factory)

def test_vocabulary_limit_and_whitespace_are_checked(tmp_path):
    path = tmp_path / 'words.txt'; path.write_text('contains space')
    with pytest.raises(ValueError): load_vocabulary(path)
    path.write_text('\n'.join(f'word{i}' for i in range(201)))
    with pytest.raises(ValueError): load_vocabulary(path)

def test_cosyvoice_sft_generator_chunks_are_concatenated_in_order(tts_setup):
    seen = []
    class Model:
        sample_rate = 22050
        def list_available_spks(self): return ['中文女']
        def inference_sft(self, text, speaker, stream):
            seen.append((text, speaker, stream))
            yield {'tts_speech': np.array([[.1, .2]])}
            yield {'tts_speech': np.array([[.3]])}
    def factory(path, **kwargs):
        assert kwargs == {'load_jit': False, 'load_trt': False, 'fp16': False}
        return Model()
    adapter = CosyVoiceAdapter(tts_setup, factory)
    audio, rate = adapter.synthesize(['第一句。', '第二句。'], 'default')
    np.testing.assert_allclose(audio, [.1, .2, .3, .1, .2, .3])
    assert rate == 22050 and seen == [('第一句。', '中文女', False), ('第二句。', '中文女', False)]

def test_cosyvoice_unknown_speaker_fails_at_startup(tts_setup):
    class Model:
        sample_rate = 22050
        def list_available_spks(self): return ['another']
    with pytest.raises(ValueError, match='speakers'): CosyVoiceAdapter(tts_setup, lambda *a, **kw: Model())

def test_cosyvoice_missing_weights_fails_before_import(settings, tmp_path):
    settings.tts_model_dir = tmp_path / 'missing'
    with pytest.raises(ValueError, match='checkpoint'): CosyVoiceAdapter(settings)

@pytest.mark.parametrize('value', [[], [[1, 2], [3, 4]], [np.nan], [np.inf]])
def test_bad_waveforms_rejected(value):
    with pytest.raises(ValueError): waveform_array(value)

def test_tensor_output_is_detached_and_clipped():
    class Tensor:
        def detach(self): return self
        def cpu(self): return self
        def numpy(self): return np.array([[2., -.5]])
    np.testing.assert_array_equal(waveform_array(Tensor()), [1., -.5])

def test_registry_uses_safe_yaml_and_requires_default(tmp_path):
    path = tmp_path / 'registry.yaml'
    path.write_text('voices:\n  other: 中文女\n', encoding='utf-8')
    with pytest.raises(ValueError): load_registry(path)
