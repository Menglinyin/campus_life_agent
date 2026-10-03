"""Dry-run by default; --apply writes validated synthetic rows in one transaction."""
import argparse,hashlib,json,sys
from pathlib import Path
try:from .validate import DATA_ROOT,DataError,read_manifest
except ImportError:from validate import DATA_ROOT,DataError,read_manifest
ROOT=DATA_ROOT.parent
BACKEND=ROOT/'backend'
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(BACKEND))

def load_backend_settings(env_file=None):
    if (ROOT/'config/loader.py').is_file():
        from config.loader import load_settings
        settings=load_settings('demo',env_file)
    else:
        from app.settings import Settings
        settings=Settings(_env_file=str(env_file or BACKEND/'.env'))
    if not settings.demo:raise DataError('Synthetic importer only runs with CAMPUS_DEMO=true; use a test database')
    from sqlalchemy.engine import make_url
    url=make_url(settings.database_url)
    if url.drivername.startswith('sqlite') and url.database and url.database!=':memory:' and not Path(url.database).is_absolute():
        settings.database_url=url.set(database=str((BACKEND/url.database).resolve())).render_as_string(hide_password=False)
    return settings

def prepare_chunks(docs,settings):
    from app.rag.embedding import Embedding
    from app.rag.chunking import chunk_text
    from app.rag.cleaning import clean_text
    embed=Embedding(settings);chunks=[]
    for doc in docs:
        parts=chunk_text(clean_text(doc['text']),settings.chunk_tokens,settings.chunk_overlap,embed.tokenizer)
        embed.encode(parts)  # Shape, values and token length validated before writing.
        for i,part in enumerate(parts):
            # Stable document/position IDs: a shorter/newer revision must be explicitly reconciled.
            cid='synthetic-'+hashlib.sha256(f"{doc['owner']}:{doc['source']}:{i}".encode()).hexdigest()[:54]
            chunks.append({'id':cid,'source':doc['source'],'owner':doc['owner'],'text':part})
    return chunks

def apply_batches(settings,batches,chunks):
    from app.storage.mysql import Database
    from app.storage.models import Classroom,Course,Dish,SecondhandListing,KnowledgeChunk
    kinds={'classrooms':Classroom,'courses':Course,'dishes':Dish,'secondhand':SecondhandListing}
    db=Database(settings.database_url)
    try:
        db.initialize()
        with db.transaction() as session:
            for kind,rows in batches.items():
                for row in rows:session.merge(kinds[kind](**row))
            for chunk in chunks:session.merge(KnowledgeChunk(**chunk))
    finally:db.close()

def main():
    p=argparse.ArgumentParser();p.add_argument('--manifest',type=Path,default=DATA_ROOT/'manifests/sources.yaml');p.add_argument('--business-dir',type=Path);p.add_argument('--env-file',type=Path);p.add_argument('--apply',action='store_true');a=p.parse_args()
    try:
        batches,docs=read_manifest(a.manifest,business_dir=a.business_dir)
        # Dry-run does not load models, initialize DB or create any SQL tables.
        summary={'mode':'apply' if a.apply else 'dry-run','business_rows':{k:len(v) for k,v in batches.items()},'knowledge_documents':len(docs)}
        if a.apply:
            settings=load_backend_settings(a.env_file);chunks=prepare_chunks(docs,settings);apply_batches(settings,batches,chunks)
            summary['knowledge_chunks']=len(chunks);summary['next_step']='Restart backend to refresh RAG snapshot'
        print(json.dumps(summary,ensure_ascii=False))
    except (ValueError,OSError) as exc:
        # Connection errors may contain passwords: never dump exception payloads.
        if isinstance(exc,DataError):p.error(str(exc))
        p.error('Settings or source files are invalid; check configuration')
    except Exception:
        p.error('Import failed; transaction rolled back where supported. Check DB access and model setup.')
if __name__=='__main__':main()
