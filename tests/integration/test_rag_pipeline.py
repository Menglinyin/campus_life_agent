import numpy as np
import pytest
from app.rag.bm25_index import rank_bm25
from app.rag.hybrid_retrieval import HybridRetriever
from app.rag.embedding import Embedding
from app.settings import Settings

AUTH = {'Authorization': 'Bearer tests-alice'}

def test_rule_route_uses_real_rag_and_preserves_sources(ask):
    response = ask('旁听规则是什么')
    assert response.status_code == 200
    data = response.json()
    assert data['results'][0]['tool'] == 'search_knowledge'
    assert '测试公开规则' in data['answer']
    assert 'BOB_ONLY' not in str(data)

def test_private_chunks_filtered_before_fusion_and_per_user(client):
    rag = client.app.state.services.rag
    alice = rag.search('旁听规则 私有笔记', 'alice')
    bob = rag.search('旁听规则 私有笔记', 'bob')
    assert {row['owner'] for row in alice} <= {'alice', 'public'}
    assert {row['owner'] for row in bob} <= {'bob', 'public'}
    assert 'rule-alice' in {r['id'] for r in alice}
    assert 'rule-bob' in {r['id'] for r in bob}
    assert 'rule-bob' not in {r['id'] for r in alice}

def test_sql_upsert_and_refresh_retrieve_updated_text_without_duplicates(client):
    service = client.app.state.services
    row = {'id': 'updated-rule', 'owner': 'public', 'source': '测试更正来源', 'text': '食堂规则：窗口公示菜单。'}
    service.knowledge.upsert([row]); service.rag.refresh()
    assert any(r['id'] == row['id'] for r in service.rag.search('食堂规则', 'alice'))
    row['text'] = '食堂规则：菜单更新以窗口公示为准。'
    service.knowledge.upsert([row]); service.rag.refresh()
    matches = [r for r in service.knowledge.all() if r['id'] == row['id']]
    assert len(matches) == 1 and matches[0]['text'] == row['text']

def test_bm25_keyword_match_and_unrelated_query_excluded():
    chunks = [{'id': 'rule', 'text': '旁听课程规则'}, {'id': 'dish', 'text': '食堂菜品价格'}]
    assert rank_bm25('旁听', chunks) == ['rule']
    assert rank_bm25('火星探测器', chunks) == []
    assert rank_bm25('旁听', []) == []

def test_hybrid_rrf_promotes_candidate_seen_in_both_retrievals(monkeypatch):
    from types import SimpleNamespace
    from app.rag import hybrid_retrieval
    chunks = [{'id': x, 'text': x, 'owner': 'public', 'source': 'fixture'} for x in ['a', 'b', 'c']]
    class Encoder:
        def encode(self, texts):
            return np.array([[1., 0.]]) if texts == ['query'] else np.array([[1., 0.], [.9, .1], [.8, .2]])
    monkeypatch.setattr(hybrid_retrieval, 'rank_bm25', lambda query, candidates: ['b'])
    settings = SimpleNamespace(reranker_model='', chroma_path='', retrieval_k=2)
    rag = HybridRetriever(SimpleNamespace(all=lambda: chunks), Encoder(), settings)
    assert [r['id'] for r in rag.search('query', 'alice')] == ['b', 'a']

def test_reranker_receives_only_authorized_candidates(client):
    rag = client.app.state.services.rag
    class Reranker:
        def rank(self, query, chunks, k):
            assert all(c['owner'] in {'public', 'alice'} for c in chunks)
            return list(reversed(chunks))[:k]
    rag.reranker = Reranker(); rag.settings.retrieval_k = 1
    assert len(rag.search('旁听规则', 'alice')) == 1

@pytest.mark.chroma
def test_real_chroma_persistence_upsert_and_access_filter(tmp_path):
    pytest.importorskip('chromadb', reason='Install tests/requirements-chroma.txt')
    from app.storage.chroma import ChromaStore
    embedding = Embedding(Settings(_env_file=None, embedding_backend='demo'))
    rows = [{'id': 'public', 'owner': 'public', 'source': 'fixture', 'text': '旁听规则公开'},
            {'id': 'alice', 'owner': 'alice', 'source': 'fixture', 'text': '旁听规则ALICE_ONLY'},
            {'id': 'bob', 'owner': 'bob', 'source': 'fixture', 'text': '旁听规则BOB_ONLY'}]
    path = str(tmp_path / 'chroma')
    store = ChromaStore(path, 'tests-demo-1024')
    store.upsert(rows, embedding.encode([r['text'] for r in rows]))
    rows[0]['text'] = '旁听规则公开资料更正'
    store.upsert(rows[:1], embedding.encode([rows[0]['text']]))
    reopened = ChromaStore(path, 'tests-demo-1024')
    assert reopened.collection.count() == 3
    assert reopened.collection.get(ids=['public'])['documents'] == ['旁听规则公开资料更正']
    assert set(reopened.search(embedding.encode(['旁听规则'])[0], 'alice', 3)) == {'public', 'alice'}
    assert set(reopened.search(embedding.encode(['旁听规则'])[0], 'bob', 3)) == {'public', 'bob'}
