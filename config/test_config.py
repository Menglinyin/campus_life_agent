from pathlib import Path
import json
import shutil
import pytest
from config.loader import CONFIG_ROOT,BACKEND_ROOT,ConfigError,load_settings,read_yaml,settings_environment

@pytest.fixture
def root(tmp_path):
    target=tmp_path/'config';shutil.copytree(CONFIG_ROOT,target,ignore=shutil.ignore_patterns('__pycache__'))
    return target

@pytest.fixture
def noenv(tmp_path):
    p=tmp_path/'empty.env';p.write_text('');return p

def test_default_and_ttl(noenv):
    s=load_settings(env_file=noenv,environ={})
    assert s.demo and s.session_ttl==259200 and s.chunk_tokens==512 and s.chunk_overlap==64
    assert s.skill_root==BACKEND_ROOT/'skill_packages'

def test_env_override(noenv):
    s=load_settings(env_file=noenv,environ={'CAMPUS_SESSION_TTL':'7200','CAMPUS_HISTORY_TURNS':'3'})
    assert s.session_ttl==7200 and s.history_turns==3

def test_dotenv_priority(tmp_path):
    env=tmp_path/'local.env';env.write_text('CAMPUS_SESSION_TTL=3600\nCAMPUS_USER_TOKENS={"local-only-test-token":"student-test"}\n')
    s=load_settings(env_file=env,environ={'CAMPUS_SESSION_TTL':'7200'})
    assert s.session_ttl==7200 and s.user_tokens=={'local-only-test-token':'student-test'}

def test_invalid_chunk_relationship(root,noenv):
    p=root/'rag.yaml';p.write_text(p.read_text().replace('chunk_overlap: 64','chunk_overlap: 512'))
    with pytest.raises(ConfigError): load_settings(env_file=noenv,environ={},config_root=root)

def test_unknown_setting(root,noenv):
    p=root/'memory.yaml';p.write_text(p.read_text().replace('session_ttl:','session_ttll:'))
    with pytest.raises(ConfigError,match='Unsupported'): load_settings(env_file=noenv,environ={},config_root=root)

def test_duplicate_yaml_key(tmp_path):
    p=tmp_path/'bad.yaml';p.write_text('settings:\n  demo: true\n  demo: false\n')
    with pytest.raises(ConfigError,match='Duplicate'):read_yaml(p)

def test_unsafe_yaml(tmp_path):
    p=tmp_path/'bad.yaml';p.write_text('settings: !!python/object/apply:os.system [echo unsafe]\n')
    with pytest.raises(ConfigError):read_yaml(p)

def test_production_missing_secrets(noenv):
    with pytest.raises(ConfigError,match='Missing required'):load_settings('production',env_file=noenv,environ={})

def production_env():
    return {'CAMPUS_DATABASE_URL':'mysql+pymysql://test:example-test-secret@127.0.0.1/campus','CAMPUS_USER_TOKENS':'{"example-test-token":"student-test"}','CAMPUS_REDIS_URL':'redis://127.0.0.1:6379/0','CAMPUS_LLM_BASE_URL':'http://127.0.0.1:8001/v1'}

def test_production_validate_only(noenv):
    s=load_settings('production',env_file=noenv,environ=production_env())
    assert not s.demo and s.embedding_backend=='bge' and s.chroma_path=='./chroma_data'

def test_production_cannot_be_overridden_to_demo(noenv):
    env={**production_env(),'CAMPUS_DEMO':'true'}
    with pytest.raises(ConfigError,match='cannot enable demo'):load_settings('production',env_file=noenv,environ=env)

def test_error_does_not_print_token(noenv):
    secret='very-private-test-token'
    with pytest.raises(ConfigError) as e:
        load_settings(env_file=noenv,environ={'CAMPUS_USER_TOKENS':'{"'+secret+'":12}'})
    assert secret not in str(e.value)

def test_environment_export(noenv):
    s=load_settings(env_file=noenv,environ={});env=settings_environment(s)
    assert env['CAMPUS_DEMO']=='true' and json.loads(env['CAMPUS_USER_TOKENS'])==s.user_tokens
    assert env['CAMPUS_SESSION_TTL']=='259200'

def test_mcp_production_requires_token(noenv):
    env={**production_env(),'CAMPUS_MCP_SERVERS':'{"query_classrooms":"http://localhost:8100/mcp"}'}
    with pytest.raises(ConfigError,match='requires service token'):load_settings('production',env_file=noenv,environ=env)
