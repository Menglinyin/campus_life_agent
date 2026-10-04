import sys
from pathlib import Path
if not __package__:sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

import argparse,json,os
from urllib.parse import urlsplit
from uuid import UUID
import httpx
from scripts.common import report,run_cli,ScriptError

def valid_base(value):
    url=urlsplit(value)
    if url.scheme not in {'http','https'} or not url.hostname or url.username or url.password or url.query or url.fragment:raise ScriptError('Use an HTTP(S) service URL without credentials/query/fragment')
    return value.rstrip('/')

def smoke(base_url='http://127.0.0.1:8000',chat=False,chart=False,mode='demo',token=None,client=None):
    base=valid_base(base_url)
    if chart and not chat:raise ScriptError('--chart requires --chat')
    if chat:
        token=token or os.environ.get('CAMPUS_TEST_TOKEN') or ('demo-token' if mode=='demo' else '')
        if not token or '\r' in token or '\n' in token:raise ScriptError('Set CAMPUS_TEST_TOKEN for authenticated smoke')
    owned=client is None
    client=client or httpx.Client(trust_env=False,follow_redirects=False)
    try:
        result=client.get(base+'/api/health',timeout=5)
        if result.status_code!=200 or result.json().get('status')!='ok':raise ScriptError('Health check failed')
        checks=['liveness'];summary={'status':'passed','checks':checks,'chat_write_performed':chat,'performance_benchmark':False}
        if chat:
            response=client.post(base+'/api/chat',headers={'Authorization':'Bearer '+token},json={'message':'今天查询空闲教室，并推荐食堂菜品'},timeout=300)
            if response.status_code!=200:raise ScriptError('Authenticated chat check failed; response body omitted')
            value=response.json();UUID(value['session_id']);UUID(value['message_id'])
            if not isinstance(value.get('answer'),str) or not isinstance(value.get('results'),list):raise ScriptError('Malformed chat response')
            summary['mode']=value.get('mode');checks.append('authenticated_chat')
            names=[r['tool'] for r in value['results']]
            if any(name not in {'query_classrooms','query_courses','query_secondhand','recommend_dishes','search_knowledge'} for name in names):raise ScriptError('Unrecognized tool name in chat response')
            summary['tool_names']=names
            if chart:
                response=client.post(base+'/api/charts',headers={'Authorization':'Bearer '+token},json={'message_id':value['message_id']},timeout=30)
                if response.status_code!=200:raise ScriptError('Chart check failed; ensure matching-date dish data exist')
                if not isinstance(response.json().get('options'),dict):raise ScriptError('Malformed chart options')
                checks.append('price_chart')
        return summary
    finally:
        if owned:client.close()

def main():
    p=argparse.ArgumentParser(description='Health only by default; --chat explicitly saves one test conversation')
    p.add_argument('--base-url',default='http://127.0.0.1:8000');p.add_argument('--mode',choices=['demo','production'],default='demo');p.add_argument('--chat',action='store_true');p.add_argument('--chart',action='store_true');p.add_argument('--output',type=Path)
    a=p.parse_args();report(smoke(a.base_url,a.chat,a.chart,a.mode),a.output)
if __name__=='__main__':raise SystemExit(run_cli(main))
