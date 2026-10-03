from pathlib import Path
import sys,json,os,subprocess
import pytest,yaml,jsonschema
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'vllm'))
from init_env import initialize
from check_model import check

def load(name):return yaml.safe_load((ROOT/name).read_text())

def test_compose_official_schema():
    schema_path=Path(os.environ.get('COMPOSE_SCHEMA_FILE',str(ROOT/'compose-spec.schema.json')))
    if not schema_path.is_file():pytest.skip('Official Compose schema not available locally; Docker compose config is still required')
    schema=json.loads(schema_path.read_text())
    for name in ['docker-compose.yaml','docker-compose.production.yaml','vllm/docker-compose.yaml']:
        jsonschema.validate(load(name),schema)

def test_demo_db_and_ttl():
    env=load('docker-compose.yaml')['services']['backend']['environment']
    assert env['CAMPUS_DEMO']=='true' and env['CAMPUS_SESSION_TTL']=='259200'
    assert env['CAMPUS_DATABASE_URL']=='sqlite:////srv/runtime/campus.db'

def test_dependencies_and_no_db_ports():
    prod=load('docker-compose.production.yaml')['services']
    assert prod['backend']['depends_on']['mysql']['condition']=='service_healthy'
    assert prod['backend']['depends_on']['redis']['condition']=='service_healthy'
    assert 'ports' not in prod['mysql'] and 'ports' not in prod['redis']

def test_gpu_network_and_flags():
    v=load('vllm/docker-compose.yaml')['services']['vllm']
    args=v['command'];assert args[args.index('--tensor-parallel-size')+1]=='2'
    assert args[args.index('--quantization')+1]=='awq'
    assert args[args.index('--tool-call-parser')+1]=='hermes'
    assert len(v['deploy']['resources']['reservations']['devices'][0]['device_ids'])==2
    assert load('vllm/docker-compose.yaml')['networks']['inference']['name']=='campus-inference'
    assert load('docker-compose.production.yaml')['networks']['inference']['name']=='campus-inference'

def test_bindings():
    assert load('docker-compose.yaml')['services']['nginx']['ports'][0].startswith('127.0.0.1:')
    assert load('vllm/docker-compose.yaml')['services']['vllm']['ports'][0].startswith('127.0.0.1:')

def test_init_secrets_and_modes(tmp_path):
    files=initialize(tmp_path,'production');assert len(files)==4
    from dotenv import dotenv_values
    env=dotenv_values(tmp_path/'.env')
    assert len(json.loads(env['CAMPUS_USER_TOKENS']))==1
    assert env['MYSQL_PASSWORD_URLENCODED']==(tmp_path/'secrets/mysql_password.txt').read_text().strip()
    if os.name=='posix':assert all(p.stat().st_mode & 0o777==0o600 for p in files)

def test_no_secret_overwrite(tmp_path):
    initialize(tmp_path,'production');original=(tmp_path/'.env').read_bytes()
    with pytest.raises(ValueError):initialize(tmp_path,'production')
    assert (tmp_path/'.env').read_bytes()==original

def test_demo_init_no_db_secrets(tmp_path):
    initialize(tmp_path,'demo');assert not (tmp_path/'secrets').exists()

def test_no_volume_deletion():
    s=(ROOT/'stop.sh').read_text()
    assert '--volumes' not in '\n'.join(l for l in s.splitlines() if not l.lstrip().startswith('#'))

def test_build_inputs_and_private_ignores():
    docker=(ROOT/'backend.Dockerfile').read_text()
    assert 'config/launch.py' in docker and 'USER 10001:10001' in docker
    assert '/srv/project/data/local' in docker
    for path in ['../backend/requirements.txt','../config/requirements.txt','../data/import_data.py','entrypoint.sh']:
        assert (ROOT/path).is_file()
    ignore=(ROOT/'backend.Dockerfile.dockerignore').read_text()
    assert '**/secrets' in ignore and '**/.env' in ignore

def test_nginx_contract():
    s=(ROOT/'nginx.conf').read_text()
    assert 'client_max_body_size 9m;' in s and 'proxy_read_timeout 330s;' in s
    assert 'set $campus_upstream http://backend:8000;' in s and 'proxy_pass $campus_upstream;' in s

def test_bash_syntax():
    scripts=['start.sh','stop.sh','import_data.sh','vllm/start.sh','vllm/check_gpu.sh']
    r=subprocess.run(['bash','-n',*[str(ROOT/x) for x in scripts]],capture_output=True)
    assert r.returncode==0

def model_fixture(root):
    (root/'config.json').write_text(json.dumps({'model_type':'qwen3','hidden_size':5120,'num_hidden_layers':64,'quantization_config':{'quant_method':'awq','bits':4}}))
    (root/'tokenizer_config.json').write_text('{}')
    (root/'model.safetensors').write_bytes(b'test-file-only-not-real-tensors')

def test_awq_metadata(tmp_path):
    model_fixture(tmp_path);assert check(tmp_path)

def test_unquantized_model_rejected(tmp_path):
    model_fixture(tmp_path);(tmp_path/'config.json').write_text('{"model_type":"qwen3"}')
    with pytest.raises(ValueError):check(tmp_path)

def test_missing_shard_rejected(tmp_path):
    model_fixture(tmp_path)
    (tmp_path/'model.safetensors.index.json').write_text('{"weight_map":{"a":"missing.safetensors"}}')
    with pytest.raises(ValueError):check(tmp_path)

def test_escaping_shard_rejected(tmp_path):
    model_fixture(tmp_path)
    (tmp_path/'model.safetensors.index.json').write_text('{"weight_map":{"a":"../outside.safetensors"}}')
    with pytest.raises(ValueError):check(tmp_path)
