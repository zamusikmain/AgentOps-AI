"""Offline v0.5 contracts; no Google requests and no fixture-aware production logic."""
import asyncio,time,json
from unittest.mock import MagicMock
import pytest
from sqlalchemy import select,func
from app.db import Base,KnowledgeDocument,KnowledgeVector,EmbeddingCache
from app.main import create_app
from app.embeddings import MockEmbeddingProvider,GoogleEmbeddingProvider,EmbeddingError,normalize,signature,cache_key
from app.hybrid_search import rrf
from fastapi.testclient import TestClient
from test_rag import settings,context,upload,agent,ask,TOKEN

def ready(c,identifier):
    deadline=time.monotonic()+min(c.app.state.knowledge.settings.embedding_timeout_seconds*3,90)+5
    while time.monotonic()<deadline:
        d=c.get('/api/knowledge/documents/'+identifier).json()
        if d['embedding_status']!='indexing' and d['embedding_status']!='not_indexed':return d
        time.sleep(.02)
    pytest.fail('Embedding indexing timeout')

@pytest.mark.parametrize('value,dim', [([0,0],2),([1,float('nan')],2),([1,float('inf')],2),([True,1],2),([1],2),([1,1e15],2)],ids=['zero','nan','inf','bool','dimension','huge'])
def test_invalid_vectors(value,dim):
    with pytest.raises(EmbeddingError):normalize(value,dim)

def test_mock_cache_signature_and_rrf():
    p=MockEmbeddingProvider();q=MockEmbeddingProvider()
    assert p.embed(['Unseen random text'],'query')==q.embed(['Unseen random text'],'document')
    assert cache_key(p,'a')!=cache_key(p,'b')
    assert cache_key(p,'a','query')!=cache_key(p,'a','document')
    q.dimension=128;assert signature(p)!=signature(q)
    assert rrf(['a','b'],['b','c'])['b']==1/62+1/61

def test_google_sdk_offline_contract(settings):
    settings.embedding_external_enabled=True;settings.gemini_api_key='test-offline-key'
    from pydantic import SecretStr
    settings.gemini_api_key=SecretStr('test-offline-key')
    p=GoogleEmbeddingProvider(settings);p.client=MagicMock()
    p.client.models.embed_content.return_value.embeddings=[MagicMock(values=[1.0]+[0.0]*767),MagicMock(values=[0.0,1.0]+[0.0]*766)]
    assert len(p.embed(['alpha','beta'],'document'))==2
    args=p.client.models.embed_content.call_args.kwargs
    assert len(args['contents'])==2 and args['config'].task_type is None
    assert args['model']=='gemini-embedding-2' and args['config'].output_dimensionality==768
    p.client.models.embed_content.return_value.embeddings=[]
    with pytest.raises(EmbeddingError,match='invalid_batch'):p.embed(['x'],'query')

def test_external_disabled_never_contacts_google(settings):
    settings.embedding_provider='google';p=GoogleEmbeddingProvider(settings)
    with pytest.raises(EmbeddingError,match='consent'):p.embed(['private'],'query')
    assert p.client is None and p.requests==0
    app=create_app(settings,embedding_provider=p);Base.metadata.create_all(app.state.engine)
    with TestClient(app,headers={'Authorization':'Bearer '+TOKEN}) as c:
        d=upload(c);assert ready(c,d['id'])['embedding_status']=='needs_consent'
        assert c.post('/api/knowledge/documents/'+d['id']+'/reindex',json={'external_consent':True}).status_code==403
        assert p.requests==0

@pytest.mark.parametrize('mode',['lexical','semantic','hybrid'])
def test_search_modes_permission_scores_and_history(settings,mode):
    with context(settings) as c:
        d=upload(c);assert ready(c,d['id'])['embedded_chunks']==6
        a=agent(c,[d['id']]);body={'agent_id':a['id'],'question':'RPO RTO','search_mode':mode}
        r=c.post('/api/knowledge/search',json=body);assert r.status_code==200,r.text
        result=r.json();assert result['mode']==mode and result['mock_embeddings']
        hit=result['matches'][0];assert hit['page']==2 and hit['rank']==1
        assert 'semantic_score' in hit and 'lexical_score' in hit and hit['reasons']
        p=c.app.state.knowledge.vectors.provider;before=p.requests
        assert c.post('/api/knowledge/search',json={**body,'document_ids':['forbidden']}).status_code==403
        assert p.requests==before
        assert '99 часов' not in json.dumps(result,ensure_ascii=False)
        run=ask(c,a,'Какие RPO и RTO установлены?');assert run['status']=='completed'
        calls=c.get('/api/tool-calls?run_kind=single&run_id='+run['id']).json()['items'];assert calls[0]['result']['mode']=='hybrid'

def test_reindex_dedup_delete_restart(settings):
    with context(settings) as c:
        d=upload(c);ready(c,d['id']);a=agent(c,[d['id']])
        assert upload(c)['id']==d['id']
        plan=c.get('/api/knowledge/documents/'+d['id']+'/embedding-plan').json();assert plan['expected_requests']==0
        assert c.post('/api/knowledge/documents/'+d['id']+'/reindex',json={}).status_code==202
        time.sleep(.1);assert ready(c,d['id'])['embedding_status']=='ready'
        before=c.post('/api/knowledge/search',json={'agent_id':a['id'],'question':'RPO RTO','search_mode':'semantic'}).json()['matches']
    with context(settings) as c:
        after=c.post('/api/knowledge/search',json={'agent_id':a['id'],'question':'RPO RTO','search_mode':'semantic'}).json()['matches'];assert before==after
        assert c.delete('/api/knowledge/documents/'+d['id']).status_code==204
        with c.app.state.sessions() as db:
            assert db.scalar(select(func.count()).select_from(KnowledgeVector))==0
            assert db.scalar(select(func.count()).select_from(EmbeddingCache))==0

@pytest.mark.parametrize('failure',['bad','error','slow'])
def test_provider_failures_safe_lexical_fallback(settings,failure):
    class Broken(MockEmbeddingProvider):
        def embed(self,texts,task):
            if failure=='bad':return [[float('nan')]*self.dimension for _ in texts]
            if failure=='slow':time.sleep(1.2)
            raise EmbeddingError('embedding_provider_error')
    settings.embedding_timeout_seconds=1
    app=create_app(settings,embedding_provider=Broken());Base.metadata.create_all(app.state.engine)
    with TestClient(app,headers={'Authorization':'Bearer '+TOKEN}) as c:
        d=upload(c);assert ready(c,d['id'])['embedding_status']=='failed';a=agent(c,[d['id']])
        body={'agent_id':a['id'],'question':'RPO RTO'}
        r=c.post('/api/knowledge/search',json=body);assert r.status_code==200 and r.json()['warning']=='embedding_not_ready'
        assert c.post('/api/knowledge/search',json={**body,'search_mode':'semantic'}).status_code==409

def test_mcp_uploaded_pdf_scope(settings):
    settings.local_mcp_enabled=True
    with context(settings) as c:
        d=upload(c);ready(c,d['id']);a=agent(c,[d['id']],['mcp_knowledge_search'])
        task=c.post('/api/tasks',json={'title':'MCP PDF','prompt':'[MOCK_TOOL:mcp_knowledge_search] '+json.dumps({'query':'RPO RTO','mode':'semantic'}),'agent_id':a['id']}).json()
        rid=c.post('/api/tasks/'+task['id']+'/run').json()['id']
        deadline=time.monotonic()+min(c.app.state.runner.settings.execution_timeout_seconds,30)+5
        while time.monotonic()<deadline:
            run=c.get('/api/executions/'+rid).json()
            if run['status'] not in ('queued','running'):break
            time.sleep(.03)
        assert run['status']=='completed',run
        call=c.get('/api/tool-calls?run_kind=single&run_id='+rid).json()['items'][0]
        assert call['result']['mode']=='semantic' and call['result']['matches'][0]['document_id']==d['id']

def test_corrupt_stored_dimension_and_cache_version(settings):
    with context(settings) as c:
        d=upload(c);ready(c,d['id']);a=agent(c,[d['id']])
        with c.app.state.sessions() as db:
            entry=db.scalar(select(EmbeddingCache));entry.dimension=129;db.commit()
        r=c.post('/api/knowledge/search',json={'agent_id':a['id'],'question':'RPO RTO','search_mode':'semantic'})
        assert r.status_code==409 and r.json()['error']['code']=='embedding_dimension_mismatch'
    settings.embedding_dimension=128
    with context(settings) as c:
        assert c.post('/api/knowledge/documents/'+d['id']+'/reindex',json={}).status_code==202
        time.sleep(.1);assert ready(c,d['id'])['embedding_status']=='ready'
        r=c.post('/api/knowledge/search',json={'agent_id':a['id'],'question':'RPO RTO','search_mode':'semantic'})
        assert r.status_code==200 and r.json()['matches']

def test_batched_cached_unchanged_index(settings):
    settings.embedding_batch_size=2
    with context(settings) as c:
        d=upload(c);ready(c,d['id']);p=c.app.state.knowledge.vectors.provider
        assert p.requests==3
        assert c.post('/api/knowledge/documents/'+d['id']+'/reindex',json={}).status_code==202
        time.sleep(.1);assert p.requests==3
        assert upload(c)['id']==d['id'] and p.requests==3
