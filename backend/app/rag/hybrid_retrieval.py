import numpy as np
from .access_filters import visible_chunks
from .bm25_index import rank_bm25
from .reranking import Reranker
from app.storage.chroma import ChromaStore
class HybridRetriever:
    def __init__(self,repo,embedding,settings):
        self.repo=repo; self.embedding=embedding; self.settings=settings
        self.reranker=Reranker(settings.reranker_model)
        self.chroma=ChromaStore(settings.chroma_path,settings.embedding_backend+settings.embedding_model+":1024") if settings.chroma_path else None
        self.refresh()
    def refresh(self):
        self.chunks=self.repo.all()
        self.vectors=self.embedding.encode([c["text"] for c in self.chunks])
        if self.chroma: self.chroma.upsert(self.chunks,self.vectors)
    def search(self,query,user):
        chunks=visible_chunks(self.chunks,user)
        if not chunks: return []
        allowed={c["id"]:c for c in chunks}
        q=self.embedding.encode([query])[0]
        if self.chroma: dense=[i for i in self.chroma.search(q,user,20) if i in allowed]
        else:
            similarities=self.vectors@q
            indices=[i for i,c in enumerate(self.chunks) if c["id"] in allowed and similarities[i]>0.05]
            indices.sort(key=lambda i:float(similarities[i]),reverse=True)
            dense=[self.chunks[i]["id"] for i in indices[:20]]
        lexical=rank_bm25(query,chunks)
        scores={}
        for ranked in [dense,lexical]:
            for rank,cid in enumerate(ranked,1): scores[cid]=scores.get(cid,0)+1/(60+rank)
        candidates=[allowed[cid] for cid in sorted(scores,key=scores.get,reverse=True)]
        return self.reranker.rank(query,candidates,self.settings.retrieval_k)
