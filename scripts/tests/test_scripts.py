import hashlib,json,os,subprocess,sys
from pathlib import Path
from types import SimpleNamespace
import httpx,pytest
from scripts.common import ROOT,ScriptError,report
from scripts.initialize_database import initialize
from scripts.import_business_data import import_business
from scripts.ingest_knowledge import ingest
from scripts.rebuild_bm25 import rebuild
from scripts.verify_embeddings import verify
from scripts.export_parameters import parameters
from scripts.smoke_test import smoke
from scripts.download_models import plan,download
from scripts.check_environment import inspect_environment

@pytest.fixture
def env_file(tmp_path,monkeypatch):
    for key in list(os.environ):
        if key.startswith('CAMPUS_'):monkeypatch.delenv(key)
    file=tmp_path/'demo.env'
    file.write_text('CAMPUS_DEMO=true\nCAMPUS_DATABASE_URL=sqlite:///'+(tmp_path/'campus.db').as_posix()+'\nCAMPUS_EMBEDDING_BACKEND=demo\n')
    return file

def test_init_preview_no_file_and_apply_runs_real_migrations(env_file):
    path=env_file.parent/'campus.db'
    assert initialize(env_file)['connected'] is False and not path.exists()
    result=initialize(env_file,apply=True)
    assert result['revisions']==['0004'] and len(result['tables'])==11
    assert initialize(env_file,apply=True)['revisions']==['0004']

def test_apply_import_refuses_unmigrated_database(env_file):
    with pytest.raises(Exception):import_business(env_file=env_file,apply=True)
    assert not (env_file.parent/'campus.db').exists()

def test_business_dry_run_and_actual_import_do_not_import_knowledge(env_file):
    result=import_business(env_file=env_file)
    assert result['business_rows']['dishes']==12 and result['knowledge_imported'] is False
    assert not (env_file.parent/'campus.db').exists()
    initialize(env_file,apply=True)
    import_business(env_file=env_file,apply=True)
    from scripts.common import load_settings
    from app.storage.mysql import Database
    from app.storage.models import Dish,KnowledgeChunk
    from sqlalchemy import select,func
    db=Database(load_settings(env_file=env_file).database_url)
    with db.transaction() as s:
        assert s.scalar(select(func.count()).select_from(Dish))==12
        assert s.scalar(select(func.count()).select_from(KnowledgeChunk))==0
    db.close()

def test_knowledge_preview_apply_idempotency_and_source_scope(env_file,tmp_path):
    file=tmp_path/'rule.md';file.write_text('校园旁听规则：请征得老师同意。'*60)
    result=ingest(file,env_file=env_file)
    assert not result['sql_written'] and not result['embedding_validated']
    assert not (tmp_path/'campus.db').exists()
    initialize(env_file,apply=True)
    result=ingest(file,owner='public',source='reviewed-rule-v1',env_file=env_file,apply=True)
    assert result['chunks']>1 and result['embedding_validated'] and not result['chroma_written']
    ingest(file,owner='public',source='reviewed-rule-v1',env_file=env_file,apply=True)
    private=tmp_path/'private.md';private.write_text('PRIVATE_NOTE_DO_NOT_EXPORT 旁听规则')
    ingest(private,owner='student-a',env_file=env_file,apply=True)
    public_report=rebuild(env_file=env_file)
    assert public_report['eligible_chunks']==result['chunks'] and not public_report['live_index_refreshed']
    assert 'PRIVATE_NOTE' not in json.dumps(public_report)
    with pytest.raises(ScriptError):rebuild(env_file=env_file,owner='student-a')
    selected=rebuild(env_file=env_file,owner='student-a',include_private=True)
    assert selected['eligible_chunks']==result['chunks']+1

@pytest.mark.parametrize('suffix,value',[('.pdf','text'),('.txt','   '),('.md','')])
def test_invalid_knowledge_sources_rejected_without_db(env_file,tmp_path,suffix,value):
    file=tmp_path/('input'+suffix);file.write_text(value)
    with pytest.raises(Exception):ingest(file,env_file=env_file)
    assert not (tmp_path/'campus.db').exists()

def test_embeddings_dimension_finite_normalized_and_no_silent_truncation(env_file,tmp_path):
    result=verify(env_file=env_file)
    assert result['dimension']==1024 and result['finite'] and result['norm_min']==pytest.approx(1)
    assert result['test_double'] and not result['truncation_used']
    file=tmp_path/'long.txt';file.write_text('校园生活助手'*400)
    with pytest.raises(ValueError):verify(env_file=env_file,file=file,chunk=False)
    result=verify(env_file=env_file,file=file)
    assert result['chunks']>1 and result['max_input_units_including_special_tokens']<=1024
    assert not (tmp_path/'campus.db').exists()

def test_parameter_export_redacts_all_config_credentials(env_file):
    with env_file.open('a') as file:
        file.write('CAMPUS_DATABASE_URL=mysql+pymysql://user:DB_SECRET@db/campus\nCAMPUS_REDIS_URL=redis://:REDIS_SECRET@db/0\nCAMPUS_USER_TOKENS={"USER_TOKEN_SECRET":"student-private"}\nCAMPUS_MCP_TOKEN=MCP_TOKEN_SECRET\nCAMPUS_LLM_API_KEY=LLM_KEY_SECRET\n')
    encoded=json.dumps(parameters(env_file=env_file))
    for secret in ['DB_SECRET','REDIS_SECRET','USER_TOKEN_SECRET','student-private','MCP_TOKEN_SECRET','LLM_KEY_SECRET']:
        assert secret not in encoded
    assert '259200' in encoded

def test_report_refuses_overwrite(tmp_path):
    file=tmp_path/'report.json';report({'value':1},file)
    with pytest.raises(ScriptError):report({'value':2},file)
    assert json.loads(file.read_text())['value']==1

def test_environment_check_is_read_only_and_uses_actual_metadata():
    result=inspect_environment()
    assert result['dependencies']['mcp']['installed']=='1.9.4'
    assert not result['database_connected'] and not result['models_loaded'] and not result['network_probed']

def test_http_health_default_has_no_auth_or_chat():
    seen=[]
    def handler(request):
        seen.append(request)
        assert request.url.path=='/api/health' and 'Authorization' not in request.headers
        return httpx.Response(200,json={'status':'ok'})
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:result=smoke(client=client)
    assert len(seen)==1 and not result['chat_write_performed']

def test_http_chat_errors_do_not_export_token_or_body():
    def handler(request):
        if request.url.path.endswith('health'):return httpx.Response(200,json={'status':'ok'})
        return httpx.Response(401,json={'detail':'TOKEN_SECRET_AND_PRIVATE_DETAIL'})
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ScriptError) as error:smoke(chat=True,token='TEST_SECRET',client=client)
    assert 'TEST_SECRET' not in str(error.value) and 'PRIVATE_DETAIL' not in str(error.value)
    with pytest.raises(ScriptError):smoke(base_url='http://user:password@server')
    with pytest.raises(ScriptError):smoke(chart=True)

def test_model_download_preview_has_no_network_or_files(tmp_path):
    result=plan('bge-m3','a'*40,tmp_path/'model')
    assert result['network_used'] is False and not (tmp_path/'model').exists()
    for revision in ['main','v1','a'*39,'z'*40]:
        with pytest.raises(ScriptError):plan('bge-m3',revision)

def fake_hub(content,revision='a'*40):
    entries=[SimpleNamespace(rfilename=name,size=len(value),lfs={'sha256':hashlib.sha256(value).hexdigest()}) for name,value in content.items()]
    api=SimpleNamespace(model_info=lambda *args,**kwargs:SimpleNamespace(sha=revision,siblings=entries))
    def snapshot(**kwargs):
        assert kwargs['revision']==revision
        for name,value in content.items():(Path(kwargs['local_dir'])/name).write_bytes(value)
    return api,snapshot

def test_model_download_apply_mocked_hub_checks_hash_and_manifest(tmp_path):
    content={'config.json':b'{}','tokenizer_config.json':b'{}','model.safetensors':b'SYNTHETIC_NOT_REAL_WEIGHTS'}
    api,snapshot=fake_hub(content)
    output=tmp_path/'model';result=download('bge-m3','a'*40,output,api,snapshot)
    assert result['hashes_recorded'] and not result['tensor_contents_validated']
    manifest=json.loads((output/'campus_download_manifest.json').read_text())
    assert len(manifest['files'])==3 and all(row['hub_lfs_hash_checked'] for row in manifest['files'])
    with pytest.raises(ScriptError):download('bge-m3','a'*40,output,api,snapshot)

def test_model_download_corruption_refused_and_partial_cleaned(tmp_path):
    content={'config.json':b'{}','tokenizer_config.json':b'{}','model.safetensors':b'123'}
    api,good=fake_hub(content)
    def bad(**kwargs):
        good(**kwargs);(Path(kwargs['local_dir'])/'model.safetensors').write_bytes(b'124')
    with pytest.raises(ScriptError,match='hash'):download('bge-m3','a'*40,tmp_path/'model',api,bad)
    assert not (tmp_path/'model').exists() and not list(tmp_path.glob('.*partial*'))

def test_direct_script_invocation_from_external_cwd(tmp_path,monkeypatch):
    env={k:v for k,v in os.environ.items() if not k.startswith('CAMPUS_')}
    result=subprocess.run([sys.executable,str(ROOT/'scripts/export_parameters.py')],cwd=tmp_path,env=env,capture_output=True,text=True,timeout=10)
    assert result.returncode==0 and json.loads(result.stdout)['settings']['session_ttl']==259200

@pytest.mark.parametrize('name',['check_environment','initialize_database','import_business_data','ingest_knowledge','rebuild_bm25','verify_embeddings','export_parameters','smoke_test','download_models'])
def test_cli_help_all_entries(name):
    result=subprocess.run([sys.executable,'-m','scripts.'+name,'--help'],cwd=ROOT,capture_output=True,text=True,timeout=10)
    assert result.returncode==0 and 'usage:' in result.stdout

def test_shell_downloader_wrapper_uses_chosen_python(tmp_path):
    import shutil
    bash=shutil.which('bash')
    if not bash:pytest.skip('Bash not installed')
    environment={**os.environ,'CAMPUS_PYTHON':sys.executable}
    done=subprocess.run([bash,str(ROOT/'scripts/download_models.sh'),'--model','bge-m3','--revision','a'*40,'--output',str(tmp_path/'model')],cwd=tmp_path,env=environment,capture_output=True,text=True,timeout=10)
    assert done.returncode==0 and json.loads(done.stdout)['network_used'] is False
    assert not (tmp_path/'model').exists()
