import asyncio,json
from concurrent.futures import ThreadPoolExecutor
import httpx,pytest
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from sqlalchemy import select,func
from .conftest import DAY,TOKEN
from mcp_servers.common.schemas import ToolArgs,FeedbackArgs
from mcp_servers.common.config import ServerSettings
from mcp_servers.common.idempotency import submit
from mcp_servers.query import classrooms,courses,dishes,secondhand
from mcp_servers.recommendation import dishes as recommended
from app.storage.models import Feedback
async def exchange(url,tool=None,args=None,user='alice'):
    async with asyncio.timeout(10):
        async with streamablehttp_client(url,headers={'Authorization':'Bearer '+TOKEN,'X-Campus-User':user}) as (read,write,_):
            async with ClientSession(read,write) as session:
                await session.initialize();tools=await session.list_tools()
                if tool is None:return tools
                return await session.call_tool(tool,arguments=args or {})
def unpack(result):
    assert not result.isError
    return json.loads(''.join(c.text for c in result.content if c.type=='text'))
def test_config_fails_closed(settings):
    for token in ['', 'demo-token','CHANGE_ME_GENERATE_NEW_SERVICE_TOKEN','x'*25+'\n']:
        with pytest.raises(ValueError):ServerSettings(_env_file=None,mcp_token=token).require_token()
    with pytest.raises(ValueError):ServerSettings(_env_file=None,mcp_token=TOKEN,mcp_allowed_users=['public'])
def test_local_query_filters_and_field_whitelist(runtime):
    args=ToolArgs(date=DAY)
    assert [r['id'] for r in classrooms.run(runtime,args,'alice')['rows']]==['room-a']
    assert 'private_admin_note' not in classrooms.run(runtime,args,'alice')['rows'][0]
    assert [r['id'] for r in courses.run(runtime,args,'alice')['rows']]==['course-a']
    assert len(dishes.run(runtime,args,'alice')['rows'])==2
    assert secondhand.run(runtime,ToolArgs(query='教材'),'alice')['rows']==[]
    assert classrooms.run(runtime,ToolArgs(),'alice')['needs_date']
def test_recommendation_sql_preferences_and_override(runtime):
    assert [r['id'] for r in recommended.run(runtime,ToolArgs(date=DAY),'alice')['rows']]==['dish-a']
    assert [r['id'] for r in recommended.run(runtime,ToolArgs(date=DAY,budget=20,spice=1),'alice')['rows']]==['dish-b','dish-a']
    assert recommended.run(runtime,ToolArgs(date=DAY,budget=0),'alice')['rows']==[]
def test_review_sequential_replay_conflict_and_owner(runtime):
    args=FeedbackArgs(target_kind='dishes',target_id='dish-a',rating=5,idempotency_key='review-key-0001',comment='测试评价')
    first=submit(runtime,'alice',args);second=submit(runtime,'alice',args)
    assert not first['replayed'] and second['replayed'] and first['rows']==second['rows']
    with pytest.raises(ValueError):submit(runtime,'alice',args.model_copy(update={'rating':4}))
    other=submit(runtime,'bob',args)
    assert other['rows'][0]['id']!=first['rows'][0]['id']
    assert 'request_hash' not in first['rows'][0] and 'user_id' not in first['rows'][0]
def test_review_db_concurrent_idempotency(runtime):
    args=FeedbackArgs(target_kind='dishes',target_id='dish-a',rating=5,idempotency_key='concurrent-key-0001')
    with ThreadPoolExecutor(max_workers=8) as pool:results=list(pool.map(lambda _:submit(runtime,'alice',args),range(8)))
    assert len({r['rows'][0]['id'] for r in results})==1
    assert sum(not r['replayed'] for r in results)==1
    with runtime.db.transaction() as s:assert s.scalar(select(func.count()).select_from(Feedback))==1
@pytest.mark.parametrize('headers,status',[
    ({},401),({'X-Campus-User':'alice'},401),
    ({'Authorization':'Bearer wrong','X-Campus-User':'alice'},401),
    ({'Authorization':'Bearer '+TOKEN},403),
    ({'Authorization':'Bearer '+TOKEN,'X-Campus-User':'mallory'},403),
    ({'Authorization':'Bearer '+TOKEN,'X-Campus-User':'alice','Origin':'https://evil.invalid'},403),
    ({'Authorization':'Bearer '+TOKEN,'X-Campus-User':'alice','Host':'evil.invalid'},403),
])
def test_http_auth_on_each_request(servers,headers,status):
    with httpx.Client(trust_env=False) as client:
        response=client.post(servers['query'],headers=headers,json={'jsonrpc':'2.0','id':1,'method':'tools/list'})
        assert response.status_code==status
        assert TOKEN not in response.text

def test_http_upload_cap_and_health(servers):
    with httpx.Client(trust_env=False) as client:
        assert client.get(servers['query'].replace('/mcp','/health')).status_code==200
        response=client.post(servers['query'],headers={'Authorization':'Bearer '+TOKEN,'X-Campus-User':'alice'},content=b'x'*65537)
        assert response.status_code==413

def test_real_tool_discovery_and_backend_contract(servers):
    for kind,names in {'query':{'query_classrooms','query_courses','query_dishes','query_secondhand','search_knowledge'},'recommendation':{'recommend_dishes','recommend_courses'},'feedback':{'submit_review','list_my_reviews'}}.items():
        found=asyncio.run(exchange(servers[kind]));assert {t.name for t in found.tools}==names
        if kind=='feedback':assert next(t for t in found.tools if t.name=='submit_review').annotations.readOnlyHint is False
    from app.mcp.client import MCPClient
    from app.settings import Settings
    settings=Settings(_env_file=None,mcp_token=TOKEN)
    result=asyncio.run(MCPClient(settings).call(servers['query'],'query_classrooms',{'date':DAY,'query':'','budget':20},'alice'))
    assert result['rows'][0]['id']=='room-a'
    assert unpack(asyncio.run(exchange(servers['query'],'query_classrooms')))['needs_date']

def test_real_rag_and_preference_context_isolation(servers):
    async def work():
        tasks=[]
        for _ in range(4):
            for user in ['alice','bob']:
                tasks.append(exchange(servers['query'],'search_knowledge',{'query':'旁听','date':DAY},user))
                tasks.append(exchange(servers['recommendation'],'recommend_dishes',{'date':DAY},user))
        return await asyncio.gather(*tasks)
    results=asyncio.run(work())
    for i in range(0,len(results),4):
        a,ad,b,bd=map(unpack,results[i:i+4])
        assert all(r['owner'] in {'public','alice'} for r in a['rows']) and any(r['owner']=='alice' for r in a['rows'])
        assert all(r['owner'] in {'public','bob'} for r in b['rows']) and any(r['owner']=='bob' for r in b['rows'])
        assert [r['id'] for r in ad['rows']]==['dish-a']
        assert [r['id'] for r in bd['rows']]==['dish-b','dish-a']

def test_real_feedback_and_invalid_arguments(servers,runtime):
    args={'target_kind':'dishes','target_id':'dish-a','rating':5,'idempotency_key':'network-key-0001','comment':'测试评价'}
    first=unpack(asyncio.run(exchange(servers['feedback'],'submit_review',args)));second=unpack(asyncio.run(exchange(servers['feedback'],'submit_review',args)))
    assert not first['replayed'] and second['replayed']
    assert len(unpack(asyncio.run(exchange(servers['feedback'],'list_my_reviews')))['rows'])==1
    assert unpack(asyncio.run(exchange(servers['feedback'],'list_my_reviews',user='bob')))['rows']==[]
    for changes in [{'rating':6},{'target_id':'absent','idempotency_key':'missing-target-0001'},{'rating':4},{'comment':'x'*501}]:
        result=asyncio.run(exchange(servers['feedback'],'submit_review',{**args,**changes}));assert result.isError
    bad=asyncio.run(exchange(servers['query'],'query_classrooms',{'date':'not-a-date'}));assert bad.isError

def test_agent_remote_mcp_end_to_end(servers,settings):
    from fastapi.testclient import TestClient
    from app.main import create_app
    from app.settings import Settings
    values={name:field.get_default(call_default_factory=True) for name,field in Settings.model_fields.items()}
    mapping={name:servers['query'] for name in ['query_classrooms','query_courses','query_secondhand','search_knowledge']};mapping['recommend_dishes']=servers['recommendation']
    values.update(database_url=settings.database_url,user_tokens={'alice-token':'alice','bob-token':'bob'},mcp_servers=mapping,mcp_token=TOKEN)
    with TestClient(create_app(Settings(_env_file=None,**values))) as client:
        response=client.post('/api/chat',headers={'Authorization':'Bearer alice-token'},json={'message':'查询空闲教室，推荐菜品，我不吃辣，预算10元','date':DAY})
        assert response.status_code==200,response.text
        results=response.json()['results'];assert {r['tool'] for r in results}=={'query_classrooms','recommend_dishes'}
        rows=next(r['rows'] for r in results if r['tool']=='recommend_dishes');assert rows and all(r['spice']==0 and r['price']<=10 for r in rows)
        sid=response.json()['session_id'];assert client.get(f'/api/sessions/{sid}/messages',headers={'Authorization':'Bearer bob-token'}).status_code==404

def test_demo_generator_uses_shared_absolute_db_and_unique_token(tmp_path):
    from mcp_servers.configure_demo import generate
    from dotenv import dotenv_values
    files=generate(tmp_path/'configuration',tmp_path/'demo.db')
    a,b=map(dotenv_values,files)
    assert a['CAMPUS_DATABASE_URL']==b['CAMPUS_DATABASE_URL']=='sqlite:///'+(tmp_path/'demo.db').as_posix()
    assert len(a['CAMPUS_MCP_TOKEN'])>=24 and a['CAMPUS_MCP_TOKEN']==b['CAMPUS_MCP_TOKEN']
    assert len(json.loads(b['CAMPUS_MCP_SERVERS']))==5 and b['CAMPUS_SESSION_TTL']=='259200'
    with pytest.raises(FileExistsError):generate(tmp_path/'configuration',tmp_path/'demo.db')

def test_owned_runtime_initialized_once_and_closed(settings,runtime,monkeypatch):
    import socket,threading,time,uvicorn
    import mcp_servers.common.server as module
    from mcp_servers.common.runtime import Runtime
    counts={'start':0,'close':0}
    class CountedRuntime(Runtime):
        def __init__(self,*args,**kwargs):
            counts['start']+=1;super().__init__(*args,**kwargs)
        def close(self):counts['close']+=1;super().close()
    monkeypatch.setattr(module,'Runtime',CountedRuntime)
    sock=socket.socket();sock.bind(('127.0.0.1',0));sock.listen(128)
    url=f'http://127.0.0.1:{sock.getsockname()[1]}/mcp'
    server=uvicorn.Server(uvicorn.Config(module.create_app('query',settings),log_level='critical',access_log=False))
    thread=threading.Thread(target=server.run,kwargs={'sockets':[sock]},daemon=True);thread.start()
    try:
        for _ in range(100):
            if server.started:break
            time.sleep(.02)
        assert server.started
        for _ in range(2):assert unpack(asyncio.run(exchange(url,'search_knowledge',{'query':'旁听'})))['rows']
        assert counts=={'start':1,'close':0}
    finally:server.should_exit=True;thread.join(timeout=5);sock.close()
    assert counts=={'start':1,'close':1}
