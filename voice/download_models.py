"""Plan/download public official checkpoints; record resolved immutable HF revisions."""
import argparse
import json
import re
from pathlib import Path
MODELS = {
    'asr': ('funasr/SeACo-Paraformer-large', 'paraformer'),
    'vad': ('funasr/fsmn-vad', 'fsmn-vad'),
    'punc': ('funasr/ct-punc', 'ct-punc'),
    'tts': ('FunAudioLLM/CosyVoice-300M-SFT', 'CosyVoice-300M-SFT'),
}

def plan(destination, selected, revisions=None):
    revisions = revisions or {}
    if not isinstance(revisions, dict) or not set(revisions) <= set(MODELS):
        raise ValueError('Revision file must map known model keys to full HF commits')
    for revision in revisions.values():
        if not isinstance(revision, str) or not re.fullmatch(r'[0-9a-f]{40}', revision):
            raise ValueError('Use full 40-character lowercase HF commits')
    return [{'key': key, 'repo_id': MODELS[key][0],
             'directory': str((destination / MODELS[key][1]).resolve()),
             'revision': revisions.get(key)} for key in selected]

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--destination', type=Path, default=Path('models/voice'))
    parser.add_argument('--models', nargs='+', choices=tuple(MODELS), default=list(MODELS))
    parser.add_argument('--revision-file', type=Path)
    parser.add_argument('--apply', action='store_true', help='Actually download weights (can be several GB)')
    args = parser.parse_args(argv)
    revisions = json.loads(args.revision_file.read_text()) if args.revision_file else {}
    manifest = args.destination / 'voice-model-revisions.json'
    existing = json.loads(manifest.read_text(encoding='utf-8'))['revisions'] if manifest.exists() else {}
    if not args.revision_file and manifest.exists():
        revisions = existing
    jobs = plan(args.destination, list(dict.fromkeys(args.models)), revisions)
    if not args.apply:
        print(json.dumps({'downloaded': False, 'plan': jobs}, ensure_ascii=False, indent=2)); return 0
    from huggingface_hub import HfApi, snapshot_download
    args.destination.mkdir(parents=True, exist_ok=True)
    recorded = dict(existing)
    for job in jobs:
        # Resolve main once, then download only the resolved commit. Reuse recorded commits on rerun.
        revision = job['revision'] or HfApi().model_info(job['repo_id']).sha
        if not re.fullmatch(r'[0-9a-f]{40}', revision): raise ValueError('Model hub returned invalid revision')
        target = Path(job['directory'])
        if target.exists() and any(target.iterdir()) and existing.get(job['key']) != revision:
            raise ValueError('Refuse untracked or different-revision nonempty destination; use a new model directory')
        snapshot_download(repo_id=job['repo_id'], revision=revision, local_dir=job['directory'])
        recorded[job['key']] = revision
        data = {'revisions': recorded, 'models': {key: {'repo_id': MODELS[key][0], 'directory': MODELS[key][1]} for key in recorded}}
        temporary = manifest.with_suffix('.tmp')
        temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        temporary.replace(manifest)
    print(json.dumps({'downloaded': True, 'models': list(recorded), 'manifest': str(manifest.resolve())}, ensure_ascii=False))
    return 0

if __name__ == '__main__': raise SystemExit(main())
