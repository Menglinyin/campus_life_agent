from datetime import date
from pathlib import Path
import os,subprocess,sys
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"backend"))
from data.generate import generate
from data.validate import DATA_ROOT,DataError,read_business,read_manifest,safe_path
from data.import_data import prepare_chunks,apply_batches
from app.settings import Settings
from app.storage.mysql import Database
from app.storage.repositories.campus_services import CampusServices
from app.storage.repositories.knowledge import Knowledge
from app.rag.embedding import Embedding
from app.rag.hybrid_retrieval import HybridRetriever
from sqlalchemy import select,func
from app.storage.models import Classroom,Dish,Course,SecondhandListing,KnowledgeChunk

@pytest.fixture
def prepared(tmp_path):
    settings=Settings(database_url=f'sqlite:///{tmp_path}/test.db')
    batches,docs=read_manifest(DATA_ROOT/'manifests/sources.yaml')
    chunks=prepare_chunks(docs,settings)
    return settings,batches,chunks

def test_manifest_counts():
    batches,docs=read_manifest(DATA_ROOT/'manifests/sources.yaml')
    assert {k:len(v) for k,v in batches.items()}=={'classrooms':9,'courses':6,'dishes':12,'secondhand':3}
    assert len(docs)==6

def test_generate_dates(tmp_path):
    generate(tmp_path,date(2027,1,1),2)
    rows=read_business(tmp_path/'dishes.csv','dishes')
    assert len(rows)==8 and {r['payload']['date'] for r in rows}=={'2027-01-01','2027-01-02'}

def test_generate_invalid_days(tmp_path):
    with pytest.raises(ValueError):generate(tmp_path,date(2026,10,3),0)

def test_invalid_bool(tmp_path):
    generate(tmp_path,date(2026,10,3),1)
    p=tmp_path/'classrooms.csv';p.write_text(p.read_text().replace(',true,',',TRUE,'))
    with pytest.raises(DataError):read_business(p,'classrooms')

def test_nan_price(tmp_path):
    generate(tmp_path,date(2026,10,3),1)
    p=tmp_path/'dishes.csv';p.write_text(p.read_text().replace(',10,',',NaN,'))
    with pytest.raises(DataError):read_business(p,'dishes')

def test_duplicate_id(tmp_path):
    generate(tmp_path,date(2026,10,3),1)
    p=tmp_path/'secondhand.csv';p.write_text(p.read_text()+p.read_text().splitlines()[1]+'\n')
    with pytest.raises(DataError):read_business(p,'secondhand')

def test_traversal():
    with pytest.raises(DataError):safe_path(DATA_ROOT,'../backend/README.md')

def test_duplicate_import(prepared):
    s,batches,chunks=prepared;apply_batches(s,batches,chunks);apply_batches(s,batches,chunks)
    db=Database(s.database_url)
    try:
        with db.transaction() as session:
            assert session.scalar(select(func.count()).select_from(Dish))==12
            assert session.scalar(select(func.count()).select_from(KnowledgeChunk))==6
    finally:db.close()

def test_query_filters(prepared):
    from app.services.recommendations import recommend_dishes
    s,batches,chunks=prepared;apply_batches(s,batches,chunks);db=Database(s.database_url)
    try:
        repo=CampusServices(db)
        rows=repo.list('dishes','2026-10-03')
        assert len(rows)==4
        filtered=recommend_dishes(rows,{'spice':0,'budget':10})
        assert len(filtered)==2 and all(x['available'] for x in filtered)
        assert len(repo.list('classrooms','2026-10-03'))==3
    finally:db.close()

def test_rag_permissions(prepared):
    s,batches,chunks=prepared;apply_batches(s,batches,chunks);db=Database(s.database_url)
    try:
        rag=HybridRetriever(Knowledge(db),Embedding(s),s)
        public=rag.search('青松资料','demo-student')
        assert all(x['owner']=='public' for x in public)
        private=rag.search('青松资料','synthetic-student-a')
        assert any(x['owner']=='synthetic-student-a' for x in private)
        assert all(x['owner']!='synthetic-student-b' for x in private)
    finally:db.close()

def test_atomic_rollback(prepared,monkeypatch):
    from sqlalchemy.orm import Session
    s,batches,chunks=prepared;real=Session.merge;counter=[0]
    def fail(self,instance,*args,**kwargs):
        counter[0]+=1
        if counter[0]==2:raise RuntimeError('simulated failure')
        return real(self,instance,*args,**kwargs)
    with monkeypatch.context() as patch:
        patch.setattr(Session,'merge',fail)
        with pytest.raises(RuntimeError):apply_batches(s,batches,chunks)
    db=Database(s.database_url)
    try:
        with db.transaction() as session:assert session.scalar(select(func.count()).select_from(Classroom))==0
    finally:db.close()

def test_dry_run_does_not_create_db(tmp_path):
    path=tmp_path/'absent.db'
    result=subprocess.run([sys.executable,str(DATA_ROOT/'import_data.py')],env={**os.environ,'CAMPUS_DATABASE_URL':f'sqlite:///{path}'},capture_output=True,text=True)
    assert result.returncode==0 and 'dry-run' in result.stdout and not path.exists()

def test_backend_api_uses_imported_rows(prepared):
    from app.main import create_app
    from fastapi.testclient import TestClient
    s,batches,chunks=prepared;apply_batches(s,batches,chunks)
    with TestClient(create_app(s)) as client:
        r=client.post('/api/chat',headers={'Authorization':'Bearer demo-token'},json={'message':'2026-10-03查询空闲教室并推荐菜品，不吃辣，预算10元'})
        assert r.status_code==200,r.text
        results=r.json()['results']
        assert any(x['id'].startswith('synthetic-room-') for x in results[0]['rows'])
        assert any(x['id'].startswith('synthetic-dish-') for x in results[1]['rows'])
        assert all(x['price']<=10 and x['spice']==0 and x['available'] for x in results[1]['rows'])
