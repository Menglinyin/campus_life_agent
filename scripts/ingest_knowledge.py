import sys
from pathlib import Path
if not __package__:sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

import argparse
from scripts.common import load_settings,check_database,check_owner,read_text,report,run_cli,config_args,ScriptError

def ingest(file,owner='public',source=None,profile='demo',env_file=None,apply=False):
    from app.rag.cleaning import clean_text
    owner=check_owner(owner);text=read_text(file)
    if not clean_text(text).strip():raise ScriptError('Document contains no indexable text')
    source=source or Path(file).name
    if not 1<=len(source)<=255:raise ScriptError('Source label must contain 1..255 characters')
    result={'mode':'apply' if apply else 'dry-run','owner':owner,'source':source,'characters':len(text),'embedding_validated':False,'sql_written':False,'chroma_written':False}
    if apply:
        from app.storage.mysql import Database
        from app.storage.repositories.knowledge import Knowledge
        from app.rag.embedding import Embedding
        from app.rag.ingestion import ingest_text
        settings=load_settings(profile,env_file);check_database(settings)
        embedding=Embedding(settings);db=Database(settings.database_url)
        try:chunks=ingest_text(Knowledge(db),embedding,settings,text,source,owner)
        finally:db.close()
        result.update(chunks=len(chunks),embedding_validated=True,sql_written=True,next_step='Restart backend and query MCP to refresh their own RAG snapshots')
    return result

def main():
    p=argparse.ArgumentParser(description='TXT/MD -> existing chunking/embedding validation -> SQL; dry-run by default')
    config_args(p);p.add_argument('file',type=Path);p.add_argument('--owner',default='public');p.add_argument('--source');p.add_argument('--apply',action='store_true')
    a=p.parse_args();report(ingest(a.file,a.owner,a.source,a.profile,a.env_file,a.apply))
if __name__=='__main__':raise SystemExit(run_cli(main))
