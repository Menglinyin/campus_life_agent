import hashlib
from .cleaning import clean_text
from .chunking import chunk_text
def ingest_text(repo,embedding,settings,text,source,owner="public"):
    parts=chunk_text(clean_text(text),settings.chunk_tokens,settings.chunk_overlap,embedding.tokenizer)
    embedding.encode(parts)  # Validate BEFORE the SQL commit.
    chunks=[{"id":hashlib.sha256(f"{owner}:{source}:{i}:{p}".encode()).hexdigest(),"source":source,"owner":owner,"text":p} for i,p in enumerate(parts)]
    repo.upsert(chunks); return chunks
