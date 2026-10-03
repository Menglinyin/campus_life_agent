import argparse
from app.settings import Settings
from app.storage.mysql import Database
from app.storage.repositories.knowledge import Knowledge
from app.rag.embedding import Embedding
from app.rag.ingestion import ingest_text
from app.rag.collectors.documents import read_document
p=argparse.ArgumentParser(); p.add_argument('file'); p.add_argument('--owner',default='public'); args=p.parse_args()
s=Settings(); db=Database(s.database_url); db.initialize()
try:
    chunks=ingest_text(Knowledge(db),Embedding(s),s,read_document(args.file),args.file,args.owner)
    print(f'Imported {len(chunks)} chunks. Restart backend to refresh retrieval snapshot.')
finally: db.close()
