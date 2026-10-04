"""Read-only diagnostics; never imports models or downloads weights."""
import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import shutil
import subprocess
from voice.common.settings import VoiceSettings

def inspect(settings, hash_files=False):
    packages = {}
    for name in ('fastapi', 'uvicorn', 'numpy', 'funasr', 'modelscope', 'torch', 'torchaudio', 'PyYAML'):
        try: packages[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError: packages[name] = None
    paths = {key: getattr(settings, key) for key in ('asr_model_dir', 'asr_vad_dir', 'asr_punc_dir', 'tts_model_dir', 'cosyvoice_source')}
    details = {}
    for key, folder in paths.items():
        found = Path(folder).resolve() if folder is not None else None
        details[key] = {'path': str(found) if found else None, 'exists': bool(found and found.is_dir())}
        if hash_files and found and found.is_dir():
            hashes = {}
            # Only direct model files; do not traverse symlinks, caches, or source repository trees.
            if key != 'cosyvoice_source':
                for file in sorted(found.iterdir()):
                    if file.is_file() and not file.is_symlink():
                        digest = hashlib.sha256()
                        with file.open('rb') as stream:
                            for chunk in iter(lambda: stream.read(1024 * 1024), b''): digest.update(chunk)
                        hashes[file.name] = digest.hexdigest()
            details[key]['sha256'] = hashes
    source = Path(settings.cosyvoice_source)
    try:
        commit = subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True, stderr=subprocess.DEVNULL).strip()
    except (OSError, subprocess.CalledProcessError): commit = None
    return {'python': platform.python_version(), 'packages': packages, 'ffmpeg': shutil.which(settings.ffmpeg),
            'paths': details, 'cosyvoice_commit': commit, 'expected_commit': settings.cosyvoice_commit or None,
            'inference_tested': False}

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--hash-model-files', action='store_true', help='Read potentially large checkpoint files for SHA256')
    args = parser.parse_args(argv)
    print(json.dumps(inspect(VoiceSettings(), args.hash_model_files), ensure_ascii=False, indent=2))
    return 0
if __name__ == '__main__': raise SystemExit(main())
