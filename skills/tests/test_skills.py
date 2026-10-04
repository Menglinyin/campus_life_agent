import asyncio
import json
import shutil
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

PROJECT = Path(__file__).resolve().parents[2]
ROOT = PROJECT / 'skills'
sys.path.insert(0, str(PROJECT / 'backend'))
from app.agent.nodes import Nodes
from app.schemas.tools import ToolArgs
from app.skills.loader import SkillLoader
from app.settings import Settings
from skills.validate import MAPPING, ValidationError, main, read_metadata, validate


@pytest.fixture
def copy(tmp_path):
    target = tmp_path / 'skills'
    shutil.copytree(ROOT, target, ignore=shutil.ignore_patterns('__pycache__', '.pytest_cache'))
    return target


def test_catalog_and_real_backend_contract():
    report = validate(ROOT, PROJECT / 'backend')
    assert report['backend_contract_checked']
    assert len(report['skills']) == 4
    assert all(0 < r['characters'] <= 6000 for r in report['skills'])
    assert report['automatic_reference_loading'] is False


@pytest.mark.parametrize('kind,slug', MAPPING.items())
def test_existing_loader_reads_entire_selected_package(kind, slug):
    text = (ROOT / slug / 'SKILL.md').read_text(encoding='utf-8')
    assert SkillLoader(ROOT).load([kind]) == text
    for other in set(MAPPING.values()) - {slug}:
        assert f'name: "{other}"' not in text


def test_multi_intent_prepare_injects_real_skills_and_explicit_date():
    service = SimpleNamespace(skills=SkillLoader(ROOT), settings=SimpleNamespace(history_turns=10))
    state = {'text': '2026-10-04查教室、旁听课程和食堂菜品、二手商品',
             'slots': {'date': '2026-10-03'}, 'preferences': {'spice': 0}, 'history': []}
    result = asyncio.run(Nodes(service).prepare(state))
    assert result['slots']['date'] == '2026-10-04'
    assert len(result['calls']) == 4
    for slug in MAPPING.values():
        assert f'name: "{slug}"' in result['messages'][0]['content']
    assert result['skills'] == SkillLoader(ROOT).load(['classrooms', 'dishes', 'courses', 'secondhand'])
    assert '"spice": 0' in result['messages'][0]['content']


def test_rule_question_uses_existing_knowledge_route():
    service = SimpleNamespace(skills=SkillLoader(ROOT), settings=SimpleNamespace(history_turns=10))
    result = asyncio.run(Nodes(service).prepare({'text': '旁听规范', 'preferences': {}, 'history': []}))
    assert result['skills'] == ''
    assert result['calls'][0]['function']['name'] == 'search_knowledge'


def test_references_not_implicitly_loaded():
    text = SkillLoader(ROOT).load(['classrooms'])
    assert 'seats | 记录的座位数' not in text
    assert 'references/time-slots.md' in text
    assert SkillLoader(ROOT).load(['knowledge', 'nonexistent']) == ''


def test_setting_can_point_to_new_root_without_changing_backend_default(monkeypatch):
    monkeypatch.setenv('CAMPUS_SKILL_ROOT', str(ROOT))
    settings = Settings(_env_file=None)
    assert settings.skill_root == ROOT
    assert SkillLoader(settings.skill_root).load(['courses'])


@pytest.mark.parametrize('failure', ['oversized', 'empty', 'wrong_name', 'broken_reference',
                                   'undeclared_tool', 'traversal', 'duplicate', 'false_loading'])
def test_validation_rejects_broken_packages(copy, failure):
    path = copy / 'classroom-search/SKILL.md'
    text = path.read_text(encoding='utf-8')
    catalog_path = copy / 'catalog.json'
    catalog = json.loads(catalog_path.read_text())
    if failure == 'oversized': path.write_text(text + 'x' * 6000, encoding='utf-8')
    elif failure == 'empty': path.write_text('---\nname: "classroom-search"\ndescription: "test"\n---\n')
    elif failure == 'wrong_name': path.write_text(text.replace('name: "classroom-search"', 'name: "other"'))
    elif failure == 'broken_reference': (copy / 'classroom-search/references/time-slots.md').unlink()
    elif failure == 'undeclared_tool': catalog['skills'][0]['tools'] = ['publish_listing']
    elif failure == 'traversal': catalog['skills'][0]['references'] = ['classroom-search/references/../../../secret']
    elif failure == 'duplicate': catalog['skills'][1] = catalog['skills'][0]
    elif failure == 'false_loading': catalog['automatic_reference_loading'] = True
    catalog_path.write_text(json.dumps(catalog), encoding='utf-8')
    with pytest.raises(ValidationError): validate(copy)


def test_reference_symlink_outside_root_rejected(copy, tmp_path):
    external = tmp_path / 'external.md'; external.write_text('external')
    reference = copy / 'classroom-search/references/time-slots.md'
    reference.unlink(); reference.symlink_to(external)
    with pytest.raises(ValidationError, match='escapes'): validate(copy)


def test_frontmatter_duplicate_or_unquoted_rejected():
    for text in ['---\nname: test\ndescription: "test"\n---\nbody',
                 '---\nname: "x"\nname: "x"\ndescription: "d"\n---\nbody']:
        with pytest.raises(ValidationError): read_metadata(text)


def test_cli_reports_machine_readable_result_and_nonzero_failure(copy, capsys):
    assert main(['--root', str(copy), '--json']) == 0
    assert json.loads(capsys.readouterr().out)['ok'] is True
    (copy / 'catalog.json').write_text('{malformed')
    assert main(['--root', str(copy)]) == 1
    assert 'failed' in capsys.readouterr().err


def test_documented_tool_examples_match_actual_schema():
    import re
    from app.skills.policies import allowed
    count = 0
    for file in ROOT.glob('*/SKILL.md'):
        for raw in re.findall(r'`(\{"name":.*?\})`', file.read_text(encoding='utf-8')):
            example = json.loads(raw)
            assert allowed(example['name'])
            ToolArgs.model_validate(example['arguments'])
            count += 1
    assert count >= 7


def test_actual_executor_date_guard_and_parameter_rejection():
    from app.mcp.executor import Executor
    from pydantic import ValidationError as SchemaError
    settings = SimpleNamespace(mcp_servers={}, mcp_token='', tool_timeout=15)
    executor = Executor(settings, None, None)
    for name in ('query_classrooms', 'query_courses', 'recommend_dishes'):
        assert asyncio.run(executor.execute(name, {}, 'student', {})) == {'needs_date': True, 'rows': []}
    with pytest.raises(SchemaError):
        asyncio.run(executor.execute('query_classrooms', {'user_id': 'other'}, 'student', {}))
