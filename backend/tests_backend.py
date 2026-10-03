from datetime import datetime
from zoneinfo import ZoneInfo
import asyncio
import numpy as np
import pytest
from fastapi.testclient import TestClient
from app.main import create_app
from app.settings import Settings
from app.rag.embedding_validation import validate_vectors,verify_lengths
from app.rag.chunking import chunk_text
from app.memory.session_store import SessionStore
from app.storage.models import KnowledgeChunk
AUTH={'Authorization':'Bearer demo-token'}
OTHER={'Authorization':'Bearer other-token'}
@pytest.fixture
def client(tmp_path):
    settings=Settings(database_url=f'sqlite:///{tmp_path}/test.db',user_tokens={'demo-token':'demo-student','other-token':'other-student'})
    with TestClient(create_app(settings)) as c: yield c

def ask(client,message,**kw): return client.post('/api/chat',json={'message':message,**kw},headers=AUTH)

def test_start_and_auth(client):
    assert client.get('/api/health').status_code==200
    assert client.post('/api/chat',json={'message':'你好'}).status_code==401

def test_multitool(client):
    r=ask(client,'今天查空闲教室，并推荐食堂菜品')
    assert r.status_code==200,r.text
    data=r.json(); assert len(data['results'])==2
    assert data['results'][0]['rows'][0]['name']=='演示教室101'
    assert data['mode']=='demo'

def test_slots_and_history(client):
    r=ask(client,'找空闲教室').json(); assert '哪一天' in r['answer']
    second=ask(client,'今天',session_id=r['session_id']).json(); assert second['results'][0]['rows']
    history=client.get('/api/sessions/'+r['session_id']+'/messages',headers=AUTH).json()
    assert len(history['messages'])==4 and history['version']==2

def test_ownership(client):
    r=ask(client,'今天吃什么菜').json()
    assert client.get('/api/sessions/'+r['session_id']+'/messages',headers=OTHER).status_code==404
    assert client.post('/api/chat',json={'message':'今天','session_id':r['session_id']},headers=OTHER).status_code==404
    assert client.post('/api/charts',json={'message_id':r['message_id']},headers=OTHER).status_code==404

def test_preference_override(client):
    first=ask(client,'我不吃辣，今天推荐食堂菜品').json(); assert len(first['results'][0]['rows'])==1
    second=ask(client,'我现在可以吃微辣，今天推荐食堂菜品',session_id=first['session_id']).json()
    assert len(second['results'][0]['rows'])==2
    assert client.get('/api/preferences',headers=AUTH).json()['spice']==1

def test_budget_filter(client):
    result=ask(client,'今天推荐菜，预算10元').json()
    assert all(x['price']<=10 for x in result['results'][0]['rows'])

def test_chart(client):
    r=ask(client,'今天推荐菜品').json()
    chart=client.post('/api/charts',json={'message_id':r['message_id']},headers=AUTH)
    assert chart.status_code==200,chart.text
    assert chart.json()['options']['series'][0]['data']==[10.0,15.0]

def test_rag_acl(client):
    s=client.app.state.services
    with s.db.transaction() as db: db.add(KnowledgeChunk(id='private-rule',source='private',owner='other-student',text='旁听机密资料：只给其他用户'))
    s.rag.refresh(); found=s.rag.search('旁听规则','demo-student')
    assert found and all(x['owner']=='public' for x in found)
    assert any(x['id']=='private-rule' for x in s.rag.search('旁听机密资料','other-student'))

def test_invalid_date_and_body(client):
    assert ask(client,'2026-99-99 查询教室').status_code==422
    assert ask(client,'').status_code==422
    assert ask(client,'查教室',session_id='not-uuid').status_code==422

def test_voice_unconfigured(client):
    assert client.post('/api/voice/transcribe',headers=AUTH,files={'audio':('x.wav',b'RIFF','audio/wav')}).status_code==503
    r=ask(client,'今天教室').json()
    assert client.post('/api/voice/synthesize',headers=AUTH,json={'message_id':r['message_id']}).status_code==503

def test_vectors_and_lengths():
    with pytest.raises(ValueError): validate_vectors(np.zeros((1,1024)),1)
    with pytest.raises(ValueError): validate_vectors([[float('nan')]],1)
    class Tokenizer:
        def encode(self,text,**kw): return list(text)+[1,2]
    with pytest.raises(ValueError): verify_lengths(['abc'],Tokenizer(),4)
    assert chunk_text('abcdefgh',4,1)==['abcd','defg','gh']

def test_redis_ttl_and_fallback(client):
    r=ask(client,'今天教室').json(); repo=client.app.state.services.conversations
    class Cache:
        def __init__(self): self.data={}; self.ttl=None
        def get(self,key): return self.data.get(key)
        def setex(self,key,ttl,value): self.data[key]=value; self.ttl=ttl
        def delete(self,key): self.data.pop(key,None)
    class Connection: client=Cache()
    memory=SessionStore(Connection(),repo,259200)
    assert memory.get('demo-student',r['session_id'])['version']==1
    assert Connection.client.ttl==259200
    ask(client,'今天教室',session_id=r['session_id'])
    assert memory.get('demo-student',r['session_id'])['version']==2
    from redis.exceptions import ConnectionError
    Connection.client.get=lambda _: (_ for _ in ()).throw(ConnectionError())
    assert memory.get('demo-student',r['session_id'])['version']==2

def test_sql_restart(tmp_path):
    settings=Settings(database_url=f'sqlite:///{tmp_path}/persist.db')
    with TestClient(create_app(settings)) as c: r=ask(c,'我不吃辣，今天推荐菜品').json()
    with TestClient(create_app(settings)) as c:
        assert c.get('/api/preferences',headers=AUTH).json()['spice']==0
        assert len(c.get('/api/sessions/'+r['session_id']+'/messages',headers=AUTH).json()['messages'])==2

def test_vllm_loop(client):
    s=client.app.state.services; s.settings.llm_base_url='http://mock/v1'; original=s.model
    class Model:
        def __init__(self): self.calls=0
        async def chat(self,messages,tools):
            self.calls+=1
            if self.calls==1: return {'role':'assistant','content':None,'tool_calls':[{'id':'c1','type':'function','function':{'name':'query_classrooms','arguments':'{}'}}]}
            assert messages[-1]['role']=='tool'
            return {'role':'assistant','content':'已找到演示教室101。'}
    s.model=Model()
    try:
        r=ask(client,'今天查教室'); assert r.status_code==200,r.text
        assert '演示教室101' in r.json()['answer']
    finally: s.model=original

def test_disallowed_tool(client):
    with pytest.raises(ValueError): asyncio.run(client.app.state.services.executor.execute('pay',{},'demo-student',{}))

def test_chroma_acl(tmp_path):
    pytest.importorskip('chromadb')
    from app.rag.embedding import Embedding
    from app.storage.chroma import ChromaStore
    embed=Embedding(Settings())
    store=ChromaStore(str(tmp_path/'chroma'),'demo-test')
    chunks=[{'id':'a','owner':'public','source':'public','text':'旁听规则'},{'id':'b','owner':'other','source':'private','text':'旁听秘密'}]
    store.upsert(chunks,embed.encode([x['text'] for x in chunks]))
    assert store.search(embed.encode(['旁听'])[0],'demo-student',2)==['a']

def test_model_http_contract(client):
    import httpx
    s=client.app.state.services; s.settings.llm_base_url='http://example/v1'; old=s.model.http
    def handler(request):
        import json
        payload=json.loads(request.content)
        assert str(request.url)=='http://example/v1/chat/completions'
        assert payload['chat_template_kwargs']['enable_thinking'] is False
        assert payload['tools']
        return httpx.Response(200,json={'choices':[{'message':{'role':'assistant','content':'测试回答'}}]})
    s.model.http=httpx.AsyncClient(transport=httpx.MockTransport(handler))
    try: assert asyncio.run(s.model.chat([{'role':'user','content':'你好'}], [{'type':'function'}]))['content']=='测试回答'
    finally:
        asyncio.run(s.model.http.aclose()); s.model.http=old

def test_model_cannot_invent_missing_date(client):
    s=client.app.state.services; original=s.model; s.settings.llm_base_url='http://mock/v1'
    class Model:
        async def chat(self,messages,tools):
            return {'role':'assistant','content':None,'tool_calls':[{'id':'x','type':'function','function':{'name':'query_classrooms','arguments':'{"date":"2026-10-03"}'}}]}
    s.model=Model()
    try:
        r=ask(client,'查询空闲教室').json()
        assert '哪一天' in r['answer'] and not r['results']
    finally: s.model=original

def test_rule_question_goes_to_rag(client):
    r=ask(client,'旁听规则是什么').json()
    assert r['results'][0]['tool']=='search_knowledge'
    assert '演示旁听规则' in r['answer']
