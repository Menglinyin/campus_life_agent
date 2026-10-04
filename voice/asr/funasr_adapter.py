from pathlib import Path
from voice.common.errors import VoiceError

def load_vocabulary(path):
    terms = []
    for line in Path(path).read_text(encoding='utf-8').splitlines():
        term = line.strip()
        if not term or term.startswith('#'): continue
        if len(term) > 64 or any(c.isspace() for c in term):
            raise ValueError('Vocabulary expects one term (no whitespace) per line, <=64 characters')
        if term not in terms: terms.append(term)
    if len(terms) > 200: raise ValueError('At most 200 hotwords')
    return ' '.join(terms)

class FunASRAdapter:
    kind = 'funasr-paraformer'
    def __init__(self, settings, model_factory=None):
        for directory in (settings.asr_model_dir, settings.asr_vad_dir, settings.asr_punc_dir):
            if directory is not None and not Path(directory).is_dir():
                raise ValueError('Configure existing local FunASR/VAD/punctuation model directories')
        if model_factory is None:
            from funasr import AutoModel
            model_factory = AutoModel
        kwargs = {'model': str(settings.asr_model_dir), 'device': settings.asr_device,
                  'disable_update': True, 'trust_remote_code': False}
        if settings.asr_vad_dir: kwargs['vad_model'] = str(settings.asr_vad_dir)
        if settings.asr_punc_dir: kwargs['punc_model'] = str(settings.asr_punc_dir)
        self.hotword = load_vocabulary(settings.vocabulary)
        self.model = model_factory(**kwargs)

    def transcribe(self, audio):
        try:
            result = self.model.generate(input=audio.samples, fs=audio.sample_rate, cache={},
                                         batch_size_s=60, hotword=self.hotword)
            if not isinstance(result, list): raise ValueError('Invalid ASR output')
            texts = []
            for item in result:
                if not isinstance(item, dict) or not isinstance(item.get('text'), str):
                    raise ValueError('Invalid ASR segment')
                texts.append(item['text'].strip())
            text = ' '.join(texts).strip()
            if len(text) > 10000: raise ValueError('ASR text exceeds contract')
            return text
        except Exception as exc:
            raise VoiceError() from exc
