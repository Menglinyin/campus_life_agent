from pathlib import Path
from app.skills.loader import SkillLoader
from app.skills.registry import SKILLS
from skills.validate import validate
PROJECT = Path(__file__).resolve().parents[2]

def test_delivered_packages_validate_against_backend():
    assert validate(PROJECT / 'skills', PROJECT / 'backend')['ok']

def test_selected_kinds_only_and_no_truncation():
    loader = SkillLoader(PROJECT / 'skills')
    for kind, slug in SKILLS.items():
        text = (PROJECT / 'skills' / slug / 'SKILL.md').read_text(encoding='utf-8')
        assert loader.load([kind]) == text
        assert sum(f'name: "{name}"' in text for name in SKILLS.values()) == 1
    assert loader.load(['knowledge', 'unregistered']) == ''

def test_current_loader_cap_and_reference_loading_are_explicit(tmp_path):
    folder = tmp_path / 'classroom-search'; folder.mkdir()
    (folder / 'SKILL.md').write_text('字' * 6001)
    (folder / 'references').mkdir()
    (folder / 'references' / 'rule.md').write_text('REFERENCE_NOT_AUTOMATICALLY_LOADED')
    text = SkillLoader(tmp_path).load(['classrooms'])
    assert len(text) == 6000 and 'REFERENCE_NOT_AUTOMATICALLY_LOADED' not in text
