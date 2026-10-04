from pathlib import Path
import sys,threading,time,socket
import pytest,uvicorn
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from mcp_servers.common import backend
from mcp_servers.common.config import ServerSettings
from mcp_servers.common.runtime import Runtime
from mcp_servers.common.server import create_app
from app.storage.models import Classroom,Course,Dish,SecondhandListing,KnowledgeChunk
DAY='2026-10-04'
TOKEN='test-service-token-only-for-fixtures-0123456789'
@pytest.fixture
def settings(tmp_path,monkeypatch):
    import os
    for key in list(os.environ):
        if key.startswith('CAMPUS_'):monkeypatch.delenv(key)
    monkeypatch.setenv('NO_PROXY','127.0.0.1,localhost')
    return ServerSettings(_env_file=None,database_url=f'sqlite:///{tmp_path / "mcp.db"}',mcp_token=TOKEN,mcp_allowed_users=['alice','bob'])
@pytest.fixture
def runtime(settings):
    runtime=Runtime(settings)
    with runtime.db.transaction() as s:
        for cls,id,payload in [
            (Classroom,'room-a',{'name':'测试教室A','date':DAY,'available':True,'seats':40,'private_admin_note':'DO_NOT_EXPOSE'}),
            (Classroom,'room-b',{'name':'测试教室B','date':DAY,'available':False,'seats':50}),
            (Course,'course-a',{'name':'测试人工智能课','date':DAY,'room':'测试A','time':'14:00','auditing_allowed':True}),
            (Course,'course-b',{'name':'测试通信课','date':DAY,'room':'测试B','time':'09:00','auditing_allowed':False}),
            (Dish,'dish-a',{'name':'测试清淡菜','date':DAY,'price':10,'spice':0,'vegetarian':True,'rating':4.8,'available':True}),
            (Dish,'dish-b',{'name':'测试微辣菜','date':DAY,'price':15,'spice':1,'vegetarian':False,'rating':4.9,'available':True}),
            (Dish,'dish-c',{'name':'测试售罄菜','date':DAY,'price':5,'spice':0,'vegetarian':True,'rating':5,'available':False}),
            (SecondhandListing,'item-a',{'name':'测试台灯','price':20,'status':'active'}),
            (SecondhandListing,'item-b',{'name':'测试教材','price':10,'status':'sold'})]:s.add(cls(id=id,payload=payload))
        for id,owner,text in [('rule-public','public','旁听规则需要老师同意'),('rule-alice','alice','旁听私密笔记ALICE_ONLY'),('rule-bob','bob','旁听私密笔记BOB_ONLY')]:
            s.add(KnowledgeChunk(id=id,owner=owner,source='测试来源',text=text))
    runtime.preferences.update('alice',{'budget':10,'spice':0});runtime.preferences.update('bob',{'budget':20,'spice':1})
    from app.rag.embedding import Embedding
    from app.rag.hybrid_retrieval import HybridRetriever
    from app.storage.repositories.knowledge import Knowledge
    runtime.rag=HybridRetriever(Knowledge(runtime.db),Embedding(settings),settings)
    yield runtime
    runtime.close()
@pytest.fixture
def servers(settings,runtime):
    running=[];urls={}
    try:
        for kind in ['query','recommendation','feedback']:
            sock=socket.socket();sock.bind(('127.0.0.1',0));sock.listen(128);port=sock.getsockname()[1]
            server=uvicorn.Server(uvicorn.Config(create_app(kind,settings,runtime),log_level='critical',access_log=False))
            thread=threading.Thread(target=server.run,kwargs={'sockets':[sock]},daemon=True);thread.start();running.append((server,thread,sock))
            for _ in range(100):
                if server.started:break
                if not thread.is_alive():pytest.fail('MCP server failed to start')
                time.sleep(.02)
            else:pytest.fail('MCP startup timed out')
            urls[kind]=f'http://127.0.0.1:{port}/mcp'
        yield urls
    finally:
        for server,thread,sock in running:server.should_exit=True
        for server,thread,sock in running:thread.join(timeout=5);sock.close()
