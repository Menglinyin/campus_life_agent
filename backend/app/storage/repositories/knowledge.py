from sqlalchemy import select
from app.storage.models import KnowledgeChunk
class Knowledge:
    def __init__(self,db): self.db=db
    def all(self):
        with self.db.transaction() as s:
            return [{"id":x.id,"source":x.source,"owner":x.owner,"text":x.text} for x in s.scalars(select(KnowledgeChunk))]
    def upsert(self,chunks):
        with self.db.transaction() as s:
            for chunk in chunks: s.merge(KnowledgeChunk(**chunk))
