import jieba
from rank_bm25 import BM25Okapi
def tokenize(text): return [t for t in jieba.lcut(text) if t.strip()]
def rank_bm25(query,chunks,k=20):
    if not chunks: return []
    terms=tokenize(query); corpus=[tokenize(c["text"]) for c in chunks]
    scores=BM25Okapi(corpus,epsilon=0.25).get_scores(terms)
    # Shared terms guard prevents unrelated zero/negative-score rows entering fusion.
    indices=[i for i,t in enumerate(corpus) if set(terms)&set(t)]
    indices.sort(key=lambda i:float(scores[i]),reverse=True)
    return [chunks[i]["id"] for i in indices[:k]]
