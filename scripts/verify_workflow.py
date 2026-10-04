"""Exercise actual CLI scripts and real demo backend in a disposable workspace."""
import sys
from pathlib import Path
if not __package__:sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import argparse,json,os,socket,subprocess,tempfile,time
from datetime import datetime
from zoneinfo import ZoneInfo
import httpx
from scripts.common import ROOT,report,run_cli,ScriptError

def verify_workflow():
    env={k:v for k,v in os.environ.items() if not k.startswith('CAMPUS_')}
    env['NO_PROXY']='127.0.0.1,localhost'
    results={};process=None
    with tempfile.TemporaryDirectory(prefix='campus-scripts-workflow-') as directory:
        temp=Path(directory);file=temp/'workflow.env'
        file.write_text('CAMPUS_DEMO=true\nCAMPUS_DATABASE_URL=sqlite:///'+(temp/'campus.db').as_posix()+'\nCAMPUS_EMBEDDING_BACKEND=demo\nCAMPUS_LLM_BASE_URL=\nCAMPUS_RERANKER_MODEL=\nCAMPUS_CHROMA_PATH=\nCAMPUS_REDIS_URL=\nCAMPUS_MCP_SERVERS={}\n')
        def command(module,*args):
            done=subprocess.run([sys.executable,'-m',module,*map(str,args)],cwd=ROOT,env=env,capture_output=True,text=True,timeout=45)
            if done.returncode:raise ScriptError('Workflow failed in '+module+'; raw subprocess output omitted')
            return json.loads(done.stdout)
        try:
            results['database_preview']=command('scripts.initialize_database','--env-file',file)
            assert not (temp/'campus.db').exists()
            results['database_apply']=command('scripts.initialize_database','--env-file',file,'--apply')
            generated=temp/'business';day=datetime.now(ZoneInfo('Asia/Shanghai')).date().isoformat()
            done=subprocess.run([sys.executable,'-m','data.generate','--output',str(generated),'--base-date',day,'--days','1'],cwd=ROOT,env=env,capture_output=True,text=True,timeout=10)
            if done.returncode:raise ScriptError('Synthetic fixture generation failed')
            results['business_preview']=command('scripts.import_business_data','--business-dir',generated,'--env-file',file)
            results['business_apply']=command('scripts.import_business_data','--business-dir',generated,'--env-file',file,'--apply')
            knowledge=temp/'rule.md';knowledge.write_text('合成旁听规则：先征得任课老师同意，保持课堂秩序。')
            results['knowledge_apply']=command('scripts.ingest_knowledge',knowledge,'--source','workflow-synthetic-rule','--env-file',file,'--apply')
            results['bm25']=command('scripts.rebuild_bm25','--env-file',file)
            results['embeddings']=command('scripts.verify_embeddings','--env-file',file)
            results['parameters']=command('scripts.export_parameters','--env-file',file)
            results['schema']=command('migrations.manage','--env-file',file,'check')
            with socket.socket() as sock:
                sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
            with (temp/'backend.log').open('w') as log:
                process=subprocess.Popen([sys.executable,'config/launch.py','--env-file',str(file),'--port',str(port)],cwd=ROOT,env=env,stdout=log,stderr=log)
                base=f'http://127.0.0.1:{port}'
                with httpx.Client(trust_env=False,timeout=1) as client:
                    for _ in range(150):
                        if process.poll() is not None:raise ScriptError('Temporary backend failed to start')
                        try:
                            if client.get(base+'/api/health').status_code==200:break
                        except httpx.HTTPError:pass
                        time.sleep(.1)
                    else:raise ScriptError('Temporary backend startup timed out')
                results['health']=command('scripts.smoke_test','--base-url',base)
                results['chat_chart']=command('scripts.smoke_test','--base-url',base,'--chat','--chart')
            checks=['init preview without file','actual Alembic upgrade','business CSV preview/apply','knowledge chunk+embedding+SQL','public BM25 validation','embedding dimension/length','redacted parameters TTL=259200','schema matches head','real HTTP liveness','real HTTP Agent chat and price chart']
            assert results['database_apply']['revisions']==['0004']
            assert results['business_apply']['knowledge_imported'] is False
            assert results['bm25']['eligible_chunks']>0 and results['bm25']['sample_result_ids']
            assert results['parameters']['settings']['session_ttl']==259200
            assert results['embeddings']['dimension']==1024
            assert 'price_chart' in results['chat_chart']['checks']
            return {'status':'passed','checks':checks,'embedding_backend':'demo_hash_test_double','sql':'temporary SQLite','model_download':'not run','mcp_remote':'not run','gpu':'not run','benchmark':False}
        finally:
            if process is not None:
                process.terminate()
                try:process.wait(timeout=10)
                except subprocess.TimeoutExpired:process.kill();process.wait()

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path);a=p.parse_args()
    report(verify_workflow(),a.output)
if __name__=='__main__':raise SystemExit(run_cli(main))
