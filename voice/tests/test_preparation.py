import json
from pathlib import Path
import sys
from types import SimpleNamespace
import pytest
import yaml
from voice.download_models import plan, main
from voice.inspect_environment import inspect


def test_download_plan_defaults_do_not_import_hub_or_download(tmp_path, capsys, monkeypatch):
    monkeypatch.setitem(sys.modules, 'huggingface_hub', None)
    assert main(['--destination', str(tmp_path), '--models', 'asr', 'tts']) == 0
    result = json.loads(capsys.readouterr().out)
    assert result['downloaded'] is False
    assert result['plan'][0]['repo_id'] == 'funasr/SeACo-Paraformer-large'
    assert not list(tmp_path.iterdir())


def test_download_resolves_once_and_records_full_revision(tmp_path, monkeypatch):
    calls = []; revision = 'a' * 40
    class API:
        def model_info(self, repo): calls.append(('resolve', repo)); return SimpleNamespace(sha=revision)
    def snapshot_download(**kwargs):
        calls.append(('download', kwargs))
        path = Path(kwargs['local_dir']); path.mkdir(parents=True, exist_ok=True)
        (path / 'TEST_ONLY_NOT_A_MODEL').write_text('checkpoint fixture')
    monkeypatch.setitem(sys.modules, 'huggingface_hub', SimpleNamespace(HfApi=API, snapshot_download=snapshot_download))
    arguments = ['--destination', str(tmp_path), '--models', 'asr', '--apply']
    assert main(arguments) == 0 and main(arguments) == 0
    assert len([c for c in calls if c[0] == 'resolve']) == 1
    assert all(c[1]['revision'] == revision for c in calls if c[0] == 'download')
    assert json.loads((tmp_path / 'voice-model-revisions.json').read_text())['revisions'] == {'asr': revision}


def test_preparation_rejects_invalid_revision_and_different_model_directory(tmp_path, monkeypatch):
    with pytest.raises(ValueError): plan(tmp_path, ['asr'], {'asr': 'main'})
    target = tmp_path / 'paraformer'; target.mkdir(); (target / 'existing').write_text('original')
    monkeypatch.setitem(sys.modules, 'huggingface_hub', SimpleNamespace(
        HfApi=lambda: SimpleNamespace(model_info=lambda repo: SimpleNamespace(sha='a' * 40)),
        snapshot_download=lambda **kwargs: pytest.fail('Must not overwrite untracked checkpoint')))
    with pytest.raises(ValueError, match='nonempty'):
        main(['--destination', str(tmp_path), '--models', 'asr', '--apply'])


def test_environment_inspection_hashes_files_without_loading_models(settings, tmp_path):
    settings.asr_model_dir = tmp_path / 'model'; settings.asr_model_dir.mkdir()
    (settings.asr_model_dir / 'config.yaml').write_text('test')
    settings.cosyvoice_source = tmp_path / 'missing-source'
    result = inspect(settings, hash_files=True)
    assert result['inference_tested'] is False
    assert len(result['paths']['asr_model_dir']['sha256']['config.yaml']) == 64
    assert result['cosyvoice_commit'] is None


def test_compose_keeps_voice_services_internal_and_uses_absolute_context_variables():
    root = Path(__file__).resolve().parents[1]
    config = yaml.safe_load((root / 'deployment/docker-compose.voice.yaml').read_text())
    for name in ('asr', 'tts'):
        service = config['services'][name]
        assert 'ports' not in service
        assert service['build']['context'].startswith('${VOICE_PROJECT_DIR:')
        assert service['volumes'][0].endswith(':/models:ro')
        assert (root.parent / service['build']['dockerfile']).is_file()
    assert config['services']['backend']['environment']['CAMPUS_ASR_URL'] == 'http://asr:8200/asr'


def test_docker_recipes_require_source_commit_and_one_worker():
    root = Path(__file__).resolve().parents[1]
    text = (root / 'tts/Dockerfile').read_text()
    assert '^[0-9a-f]{40}$' in text and 'COSYVOICE_REF' in text
    for service in ('asr', 'tts'):
        assert '"--workers", "1"' in (root / service / 'Dockerfile').read_text()
