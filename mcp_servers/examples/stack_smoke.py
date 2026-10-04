"""Start 3 real MCP processes + real backend against a disposable demo DB."""
import argparse,asyncio,json,os,socket,subprocess,sys,time
from pathlib import Path
from tempfile import TemporaryDirectory
from datetime import datetime
from zoneinfo import ZoneInfo
import httpx
from dotenv import dotenv_values
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from mcp_servers.configure_demo import generate,PROJECT

async def feedback_check(url,token):
    async with asyncio.timeout(10):
        async with streamablehttp_client(url,headers={'Authorization':'Bearer '+token,'X-Campus-User':'demo-student'}) as (read,write,_):
            async with ClientSession(read,write) as session:
                await session.initialize()
                args={'target_kind':'dishes','target_id':'demo-dish-1','rating':5,'comment':'合成验收评价','idempotency_key':'stack-smoke-0001'}
                outcomes=[]
                for _ in range(2):
                    result=await session.call_tool('submit_review',arguments=args)
                    if result.isError:raise RuntimeError('Feedback tool failed')
                    outcomes.append(json.loads(''.join(c.text for c in result.content if c.type=='text')))
                assert outcomes[0]['replayed'] is False and outcomes[1]['replayed'] is True
                assert outcomes[0]['rows']==outcomes[1]['rows']

def run():
    processes=[];logs=[];ports={}
    # Reserve candidate ports together so the OS cannot select duplicates.
    sockets=[]
    for kind in ['query','recommendation','feedback','backend']:
        s=socket.socket();s.bind(('127.0.0.1',0));ports[kind]=s.getsockname()[1];sockets.append(s)
    environment={k:v for k,v in os.environ.items() if not k.startswith('CAMPUS_')}
    environment['NO_PROXY']='127.0.0.1,localhost'
    with TemporaryDirectory(prefix='campus-mcp-stack-') as temp:
        try:
            for s in sockets:s.close()
            mcp_file,backend_file=generate(Path(temp)/'config',Path(temp)/'campus.db')
            text=backend_file.read_text()
            for kind,default in [('query',8100),('recommendation',8101)]:text=text.replace(f':{default}/mcp',f':{ports[kind]}/mcp')
            backend_file.write_text(text)
            for kind in ['backend','query','recommendation','feedback']:
                command=[sys.executable,'config/launch.py','--profile','demo','--env-file',str(backend_file),'--port',str(ports[kind])] if kind=='backend' else [sys.executable,'-m',f'mcp_servers.{kind}.server','--env-file',str(mcp_file),'--port',str(ports[kind])]
                log=open(Path(temp)/(kind+'.log'),'wb');logs.append(log)
                processes.append(subprocess.Popen(command,cwd=PROJECT,env=environment,stdout=log,stderr=log))
                health='/api/health' if kind=='backend' else '/health'
                with httpx.Client(trust_env=False,timeout=1) as client:
                    for _ in range(150):
                        if processes[-1].poll() is not None:raise RuntimeError('Service exited during startup')
                        try:
                            if client.get(f'http://127.0.0.1:{ports[kind]}'+health).status_code==200:break
                        except httpx.HTTPError:pass
                        time.sleep(.1)
                    else:raise RuntimeError('Service startup timed out')
            with httpx.Client(trust_env=False,timeout=30) as client:
                day=datetime.now(ZoneInfo('Asia/Shanghai')).date().isoformat()
                response=client.post(f'http://127.0.0.1:{ports["backend"]}/api/chat',headers={'Authorization':'Bearer demo-token'},json={'date':day,'message':'查询空闲教室，并推荐菜品，我不吃辣，预算10元'})
                response.raise_for_status();body=response.json()
                assert {r['tool'] for r in body['results']}=={'query_classrooms','recommend_dishes'}
                dishes=next(r['rows'] for r in body['results'] if r['tool']=='recommend_dishes')
                assert dishes and all(r['spice']==0 and r['price']<=10 for r in dishes)
            token=dotenv_values(mcp_file)['CAMPUS_MCP_TOKEN']
            # SDK uses the same loopback proxy exclusion, but never production CAMPUS values.
            previous=os.environ.get('NO_PROXY');os.environ['NO_PROXY']='127.0.0.1,localhost'
            try:asyncio.run(feedback_check(f'http://127.0.0.1:{ports["feedback"]}/mcp',token))
            finally:
                if previous is None:os.environ.pop('NO_PROXY',None)
                else:os.environ['NO_PROXY']=previous
            return {'status':'passed','services_started':4,'checks':['CLI configuration and startup','Backend Agent -> real query/recommendation MCP','Shared SQL preference filtering','Real feedback MCP idempotent replay'],'mode':'demo rules, temporary SQLite, no GPU/Redis/MySQL/voice models'}
        finally:
            for process in processes:
                if process.poll() is None:process.terminate()
            for process in processes:
                try:process.wait(timeout=10)
                except subprocess.TimeoutExpired:process.kill();process.wait()
            for log in logs:log.close()
            for s in sockets:s.close()

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--report',type=Path);args=parser.parse_args()
    try:report=run()
    except Exception:raise SystemExit('Stack smoke failed; inspect configuration/dependencies. No secrets or temporary log bodies printed.')
    if args.report:
        args.report.parent.mkdir(parents=True,exist_ok=True);args.report.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(report,ensure_ascii=False))
if __name__=='__main__':main()
