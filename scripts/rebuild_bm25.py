import sys
from pathlib import Path
if not __package__:sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

import argparse,hashlib,json
from scripts.common import load_settings,check_database,check_owner,report,run_cli,config_args,ScriptError

def rebuild(profile='demo',env_file=None,owner='public',include_private=False,query='旁听'):
    from app.storage.mysql import Database
    from app.storage.repositories.knowledge import Knowledge
    from app.rag.bm25_index import tokenize,rank_bm25
    from app.rag.access_filters import visible_chunks
    from rank_bm25 import BM25Okapi
    owner=check_owner(owner)
    if owner!='public' and not include_private:raise ScriptError('Non-public scope requires --include-private')
    if not query.strip() or len(query)>1000:raise ScriptError('Use a non-empty query up to 1000 characters')
    settings=load_settings(profile,env_file);check_database(settings)
    db=Database(settings.database_url)
    try:chunks=visible_chunks(Knowledge(db).all(),owner)
    finally:db.close()
    corpus=[tokenize(chunk['text']) for chunk in chunks]
    if any(not terms for terms in corpus):raise ScriptError('Empty tokenized chunk; clean knowledge data first')
    if corpus:BM25Okapi(corpus,epsilon=0.25).get_scores(tokenize(query))
    signature=hashlib.sha256(json.dumps([(c['id'],c['text']) for c in sorted(chunks,key=lambda c:c['id'])],ensure_ascii=False).encode()).hexdigest()
    return {'scope':owner,'eligible_chunks':len(chunks),'tokens':sum(map(len,corpus)),'corpus_sha256':signature,'sample_result_ids':rank_bm25(query,chunks),'raw_text_exported':False,'live_index_refreshed':False,'persisted_index':False,'note':'Offline BM25 validation; existing backend builds BM25 during search. Restart services after SQL knowledge changes.'}

def main():
    p=argparse.ArgumentParser(description='Build/validate scoped BM25 in this process; no hot reload or pickle')
    config_args(p);p.add_argument('--owner',default='public');p.add_argument('--include-private',action='store_true');p.add_argument('--query',default='旁听');p.add_argument('--output',type=Path)
    a=p.parse_args();report(rebuild(a.profile,a.env_file,a.owner,a.include_private,a.query),a.output)
if __name__=='__main__':raise SystemExit(run_cli(main))
