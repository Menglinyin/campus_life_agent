import asyncio
from collections import defaultdict
from datetime import datetime
from zoneinfo import ZoneInfo
from app.settings import Settings
from app.storage.mysql import Database
from app.storage.redis import RedisConnection
from app.storage.repositories.conversations import Conversations
from app.storage.repositories.preferences import Preferences
from app.storage.repositories.knowledge import Knowledge
from app.storage.repositories.campus_services import CampusServices
from app.memory.session_store import SessionStore
from app.rag.embedding import Embedding
from app.rag.hybrid_retrieval import HybridRetriever
from app.skills.loader import SkillLoader
from app.agent.model_client import ModelClient
from app.mcp.executor import Executor
from app.agent.graph import build_graph
from app.storage.models import Classroom,Dish,Course,SecondhandListing,KnowledgeChunk
class Services:
    def __init__(self,settings):
        self.settings=settings; self.db=Database(settings.database_url); self.db.initialize()
        if settings.demo: self.seed()
        self.conversations=Conversations(self.db); self.preferences=Preferences(self.db)
        self.redis=RedisConnection(settings.redis_url); self.memory=SessionStore(self.redis,self.conversations,settings.session_ttl)
        self.embedding=Embedding(settings); self.knowledge=Knowledge(self.db)
        self.rag=HybridRetriever(self.knowledge,self.embedding,settings)
        self.skills=SkillLoader(settings.skill_root); self.model=ModelClient(settings)
        self.executor=Executor(settings,CampusServices(self.db),self.rag)
        self.graph=build_graph(self); self.locks=defaultdict(asyncio.Lock)
    def seed(self):
        today=datetime.now(ZoneInfo('Asia/Shanghai')).date().isoformat()
        with self.db.transaction() as s:
            for cls,id,payload in [
                (Classroom,'demo-room-101',{'name':'演示教室101','date':today,'available':True,'seats':40}),
                (Course,'demo-course',{'name':'演示人工智能导论','date':today,'room':'演示教室202','time':'14:00','auditing_allowed':True}),
                (Dish,'demo-dish-1',{'name':'演示番茄炒蛋','date':today,'price':10,'spice':0,'vegetarian':True,'rating':4.8,'available':True}),
                (Dish,'demo-dish-2',{'name':'演示微辣鸡丁','date':today,'price':15,'spice':1,'vegetarian':False,'rating':4.6,'available':True}),
                (SecondhandListing,'demo-item',{'name':'演示二手台灯','status':'active','price':20})]:
                s.merge(cls(id=id,payload=payload))
            s.merge(KnowledgeChunk(id='demo-rule',owner='public',source='演示旁听规则（非真实校规）',text='演示规则：旁听课程须先征得任课老师同意，不影响正常课堂秩序。'))
    async def close(self):
        await self.model.close(); self.redis.close(); self.db.close()
