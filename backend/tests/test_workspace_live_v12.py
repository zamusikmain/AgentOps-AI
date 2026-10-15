"""v1.2 fixtures only. No external Google transport is permitted by these tests."""
import asyncio
import time
import json
from concurrent.futures import ThreadPoolExecutor
import pytest
from app.live_authorization import LiveAuthorizations,DispatchGrant,GrantInput,GENERATION_MODEL,EMBEDDING_MODEL
from app.db import Base,database,LLMConfiguration,KnowledgeVector,LLMExecution
from app.llm_reliability import Scope
from app.providers import ProviderError,Reply
from app.workspace_smoke import dataset
from test_ai_workspaces_v11 import env,login,workspace,indexed,post

@pytest.fixture
def ledger(tmp_path):
    engine,sessions=database(f'sqlite:///{tmp_path/"grants.db"}');Base.metadata.create_all(engine)
    ledger=LiveAuthorizations(sessions);scope=Scope();data={'document':'synthetic-sha'}
    body=GrantInput(dataset_id='synthetic',document_ids=list(data),max_requests=2,max_tokens=100,max_budget_usd=.01,confirmation='AUTHORIZE THIS DATA AND THESE LIMITS')
    state=ledger.create(scope,'workspace-id',body,data)
    guard=DispatchGrant(ledger,scope,'workspace-id',state['id'],'synthetic',lambda:data,lambda:True)
    yield ledger,guard,scope,state,data
    engine.dispose()

def test_atomic_parallel_shared_request_limit(ledger):
    _,guard,*_=ledger
    def claim(_):
        try:guard.claim('generation','gemini',GENERATION_MODEL,10,.001);return True
        except ProviderError:return False
    with ThreadPoolExecutor(max_workers=8) as pool:result=list(pool.map(claim,range(12)))
    assert sum(result)==2
    assert guard.check()['requests']==2 and guard.check()['tokens']==20

@pytest.mark.parametrize('change,code', [('revoked','live_authorization_revoked'),('expires_at','live_authorization_expired'),('dataset_id','live_data_changed')])
def test_each_dispatch_revalidates_durable_grant(ledger,change,code):
    book,guard,_,state,_=ledger
    with book.sessions() as db:
        r=db.get(LLMConfiguration,'live_grant:'+state['id']);r.body={**r.body,change:True if change=='revoked' else 0 if change=='expires_at' else 'foreign'};db.commit()
    with pytest.raises(ProviderError,match=code):guard.claim('embedding','google',EMBEDDING_MODEL,1,.001)

@pytest.mark.parametrize('operation,provider,model,tokens,cost,code',[
    ('generation','gemini','foreign-model',1,.001,'pricing_unverified'),
    ('embedding','gemini',EMBEDDING_MODEL,1,.001,'model_denied'),
    ('generation','gemini',GENERATION_MODEL,101,.001,'live_token_limit'),
    ('generation','gemini',GENERATION_MODEL,1,.02,'budget_exceeded'),
    ('generation','gemini',GENERATION_MODEL,1,None,'pricing_unverified'),
])
def test_budget_and_model_rejections(ledger,operation,provider,model,tokens,cost,code):
    with pytest.raises(ProviderError,match=code):ledger[1].claim(operation,provider,model,tokens,cost)
    assert ledger[1].check()['requests']==0

def test_usage_is_not_invoice_and_is_idempotent(ledger):
    book,guard,scope,state,_=ledger
    rid=guard.claim('generation','gemini',GENERATION_MODEL,20,.001)
    reply=Reply(input_tokens=4,output_tokens=7,reasoning_tokens=2,usage_source='reported')
    guard.reported(rid,reply);guard.reported(rid,reply)
    current=book.get(scope,'workspace-id',state['id'])
    assert current['reported_input_tokens']==4 and current['reported_output_tokens']==7 and current['reported_thinking_tokens']==2
    assert current['tokens']==20 and current['reserved_nano_usd']==1000000 and current['actual_cost_usd'] is None

def test_reported_token_overrun_revokes_grant(ledger):
    book,guard,scope,state,_=ledger
    rid=guard.claim('generation','gemini',GENERATION_MODEL,10,.001)
    with pytest.raises(ProviderError,match='budget_overrun'):
        guard.reported(rid,Reply(input_tokens=20,output_tokens=1,usage_source='reported'))
    assert book.get(scope,'workspace-id',state['id'])['revoked']
    with pytest.raises(ProviderError,match='revoked'):guard.claim('generation','gemini',GENERATION_MODEL,10,.001)

def test_changed_document_revocation_and_cross_scope(ledger):
    book,guard,scope,state,data=ledger
    with pytest.raises(Exception):book.get(Scope('foreign','owner','admin'),'workspace-id',state['id'])
    data['document']='changed'
    with pytest.raises(ProviderError,match='live_data_changed'):guard.check()

def test_disabled_gate_and_revocation(ledger):
    book,guard,scope,state,_=ledger
    guard.enabled=lambda:False
    with pytest.raises(ProviderError,match='live_execution_disabled'):guard.check()
    book.revoke(scope,'workspace-id',state['id']);guard.enabled=lambda:True
    with pytest.raises(ProviderError,match='revoked'):guard.check()

def test_fixture_flag_does_not_authorize_real_transport():
    from app.unscoped_dispatch import UnscopedDispatch
    from app.config import Settings
    from app.providers import GeminiProvider,MockProvider
    settings=Settings(_env_file=None,validation_transport_is_stub=True)
    provider=GeminiProvider(settings)
    guard=UnscopedDispatch(settings,lambda _:provider)
    with pytest.raises(ProviderError,match='live_user_approval_required'):
        guard.claim('generation','gemini',GENERATION_MODEL,10,.001)
    assert provider.client is None
    fixture=UnscopedDispatch(settings,lambda _:MockProvider())
    assert fixture.claim('generation','gemini',GENERATION_MODEL,10,0)=='offline-contract'

@pytest.mark.parametrize('operation',['generation','embedding'])
def test_configured_secret_cannot_reach_sdk(operation):
    from app.config import Settings
    from app.providers import GeminiProvider
    from app.embeddings import GoogleEmbeddingProvider,EmbeddingError
    settings=Settings(_env_file=None,gemini_api_key='SYNTHETIC-CONTRACT-KEY-DO-NOT-SEND',embedding_external_enabled=True)
    if operation=='generation':
        provider=GeminiProvider(settings)
        with pytest.raises(ProviderError,match='sensitive_context_denied'):
            asyncio.run(provider.generate({'model':GENERATION_MODEL,'instructions':'Untrusted data','tools':[]},[{'role':'user','parts':[{'text':settings.gemini_api_key.get_secret_value()}]}],128))
    else:
        provider=GoogleEmbeddingProvider(settings)
        with pytest.raises(EmbeddingError,match='sensitive_context_denied'):provider.embed([settings.gemini_api_key.get_secret_value()],'document')
    assert provider.client is None

def test_dataset_version_does_not_replace_legacy():
    data,checksum=dataset()
    assert len(data['documents'])==3 and len(data['questions'])==10 and len(checksum)==64
    assert sum(q['language']=='ru' for q in data['questions'])==5
    assert all('criteria' in q and 'expected_citations' in q for q in data['questions'])
    from app.live_smoke_dataset import corpus
    assert len(corpus()[0]['questions'])==12

def test_smoke_scores_displayed_answer_and_separates_citation_expectations():
    from app.workspace_smoke import score_case
    quote='Access reviews occur every 45 days.'
    q={'id':'en-positive','expected_abstention':False,'expected_answer':['45'],'expected_evidence':[quote],'expected_citations':[{'document':'Policy','page':1}]}
    c={'document_id':'a','document':'Policy','page':1,'quote':quote}
    answer={'answer':quote,'citations':[c],'verification':{'abstained':True,'safe_answer':'Information not found.'}}
    assert not score_case(q,answer,['a'],lambda *args:True)['passed']
    answer['verification']={'abstained':False,'safe_answer':quote}
    assert score_case(q,answer,['a'],lambda *args:True)['passed']
    c['document']='Another allowed policy'
    result=score_case(q,answer,['a'],lambda *args:True)
    assert result['citation_valid'] and not result['expected_citation_match'] and not result['passed']

def test_workspace_dry_run_and_disabled_live(env,monkeypatch):
    from google import genai
    monkeypatch.setattr(genai,'Client',lambda *a,**k:pytest.fail('External client constructed'))
    c=env;login(c);w=workspace(c);p=f'/api/workspaces/{w}/';d=indexed(c,p)
    for path in ('live','dry-run','smoke'):
        assert post(c,p+path,[]).status_code==422
    dry=post(c,p+'dry-run',{'document_ids':[d['id']],'questions':1})
    assert dry.status_code==200,dry.text
    plan=dry.json();assert plan['mode']=='REAL_DRY_RUN' and plan['external_calls']==0 and plan['actual_cost_usd'] is None
    assert plan['plan']['estimated_cost_usd_upper']==.375 and 'live_execution_disabled' in plan['blockers']
    assert c.get(p+'dry-runs').json()['items'][0]['id']==plan['id']
    grant=post(c,p+'authorizations',{'dataset_id':'local','document_ids':[d['id']],'confirmation':'AUTHORIZE THIS DATA AND THESE LIMITS'})
    assert grant.status_code==201,grant.text
    identifier=grant.json()['id']
    r=post(c,p+'live',{'authorization_id':identifier,'question':'What code?'})
    assert r.status_code==403 and r.json()['error']['code']=='live_execution_disabled'
    assert post(c,p+f'google/{identifier}/reindex',{}).status_code==403
    assert c.get(p+'authorizations/'+identifier).json()['requests']==0
    status=c.get(p+'live-status?authorization_id='+identifier).json()
    assert status['status']=='LIVE BLOCKED' and status['live_status']=='UNVERIFIED'
    login(c,'other@local.test')
    assert c.get(p+'authorizations/'+identifier).status_code==404
    assert post(c,p+'dry-run',{'document_ids':[d['id']]}).status_code==404

def test_synthetic_smoke_dry_and_mock_use_real_pipeline(env,monkeypatch):
    from google import genai
    monkeypatch.setattr(genai,'Client',lambda *a,**k:pytest.fail('External client constructed'))
    c=env;login(c);w=workspace(c);p=f'/api/workspaces/{w}/'
    dry=post(c,p+'smoke',{'mode':'REAL_DRY_RUN'});assert dry.status_code==200,dry.text
    assert dry.json()['external_calls']==0 and dry.json()['plan']['plan']['generation_calls_upper']==10
    run=post(c,p+'smoke',{'mode':'MOCK_ONLY'});assert run.status_code==200,run.text
    deadline=time.monotonic()+110
    while time.monotonic()<deadline:
        result=c.get(p+'smoke/'+run.json()['id']).json()
        if result['status'] not in ('queued','running'):break
        time.sleep(.1)
    assert result['status']=='completed',result
    assert len(result['cases'])==10 and result['external_calls']==0
    assert all('execution_id' in case and 'citation_valid' in case for case in result['cases'])
    assert c.get(p+'knowledge/runs').json()['total']==10
    app=list(c.app.state.workspaces.apps.values())[0]
    with app.state.sessions() as db:
        assert list(db.scalars(__import__('sqlalchemy').select(KnowledgeVector)))
        assert all(r.provider=='mock' for r in db.scalars(__import__('sqlalchemy').select(LLMExecution)))

def test_google_namespace_uses_shared_guard_without_dispatch(env):
    c=env;login(c);w=workspace(c);p=f'/api/workspaces/{w}/';d=indexed(c,p)
    # Fixture-only activation, never reads a real API key. No SDK invocation or indexing.
    book=c.app.state.workspaces
    book.settings.workspace_live_enabled=True
    from pydantic import SecretStr
    book.settings.gemini_api_key=SecretStr('local-contract-placeholder')
    grant=post(c,p+'authorizations',{'dataset_id':'local','document_ids':[d['id']],'confirmation':'AUTHORIZE THIS DATA AND THESE LIMITS'}).json()['id']
    r=c.get(p+f'google/{grant}/knowledge/documents');assert r.status_code==200,r.text
    row=r.json()['items'][0];assert row['embedding_status']=='not_indexed'
    live=book.live.apps[grant];offline=list(book.apps.values())[0]
    assert live.state.engine.url.database!=offline.state.engine.url.database
    assert live.state.llm.external_guard is live.state.knowledge.vectors.provider.guard
    with live.state.sessions() as db:assert not list(db.scalars(__import__('sqlalchemy').select(KnowledgeVector)))
    assert post(c,p+'live',{'authorization_id':grant,'question':'What is the project code?'}).status_code==409
    assert c.get(p+'authorizations/'+grant).json()['requests']==0

def test_sdk_workspace_index_rag_and_trace_contract(env):
    """Actual SDK and LangGraph, local HTTP fixtures only; not a Live Gemini result."""
    import httpx
    from google import genai
    from google.genai import types
    from pydantic import SecretStr
    from app.rag_answers import mock_selection
    c=env;login(c);w=workspace(c);p=f'/api/workspaces/{w}/';d=indexed(c,p)
    book=c.app.state.workspaces;book.settings.workspace_live_enabled=True
    book.settings.gemini_api_key=SecretStr('CONTRACT-ONLY-NO-REAL-KEY')
    grant=post(c,p+'authorizations',{'dataset_id':'local','document_ids':[d['id']],'max_tokens':500000,'max_budget_usd':1,'confirmation':'AUTHORIZE THIS DATA AND THESE LIMITS'}).json()['id']
    assert c.get(p+f'google/{grant}/knowledge/documents').status_code==200
    live=book.live.apps[grant];calls=[];contexts=[]
    def handler(request):
        calls.append(request.url.path)
        body=json.loads(request.content)
        if request.url.path.endswith(':batchEmbedContents'):
            return httpx.Response(200,json={'embeddings':[{'values':[1.0]+[0.0]*767} for _ in body['requests']]})
        if request.url.path.endswith(':embedContent'):
            return httpx.Response(200,json={'embedding':{'values':[1.0]+[0.0]*767}})
        context=json.loads(body['contents'][0]['parts'][0]['text']);contexts.append(context)
        return httpx.Response(200,json={'modelVersion':'LOCAL-HTTP-CONTRACT','candidates':[{'content':{'role':'model','parts':[{'text':json.dumps(mock_selection(context))}]},'finishReason':'STOP'}],'usageMetadata':{'promptTokenCount':4,'candidatesTokenCount':5,'thoughtsTokenCount':2}})
    def sdk():return genai.Client(api_key='CONTRACT-ONLY-NO-REAL-KEY',http_options=types.HttpOptions(httpx_async_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),httpx_client=httpx.Client(transport=httpx.MockTransport(handler)),retry_options=types.HttpRetryOptions(attempts=1)))
    live.state.llm.adapter.client=sdk();live.state.knowledge.vectors.provider.provider.client=sdk()
    r=post(c,p+f'google/{grant}/reindex',{});assert r.status_code==200,r.text
    deadline=time.monotonic()+30
    while time.monotonic()<deadline:
        row=c.get(p+f'google/{grant}/knowledge/documents').json()['items'][0]
        if row['embedding_status'] in ('ready','failed'):break
        time.sleep(.05)
    assert row['embedding_status']=='ready',(row.get('embedding_error'),calls)
    run=post(c,p+'live',{'authorization_id':grant,'question':'Какой внутренний код проекта Aurora Portal?'});assert run.status_code==200,run.text
    eid=run.json()['id'];deadline=time.monotonic()+35
    while time.monotonic()<deadline:
        r=c.get(p+f'google/{grant}/executions/'+eid);assert r.status_code==200,r.text
        result=r.json()
        if result['status'] not in ('queued','running'):break
        time.sleep(.1)
    assert result['status']=='completed',result
    assert len(contexts)==1 and contexts[0]['matches']
    assert all(m['document_id']==d['id'] for m in contexts[0]['matches'])
    assert result['input_tokens']==4 and result['output_tokens']==7
    assert json.loads(result['result'])['citations']
    stored=c.get(p+f'google/{grant}/knowledge/runs').json()['items'][0]
    assert stored['result']==result['result']
    state=c.get(p+'authorizations/'+grant).json()
    assert state['requests']==len(calls) and state['reported_thinking_tokens']==2
    traces=c.get(p+f'google/{grant}/llm/requests').json()['items']
    assert any(t['provider']=='gemini' and t['metadata_json']['mode']=='REAL_EXECUTION' for t in traces)
    assert all(t['metadata_json'].get('content_retained') is False for t in traces)
    assert 'CONTRACT-ONLY-NO-REAL-KEY' not in json.dumps(traces)
    assert c.get(p+'live-status?authorization_id='+grant).json()['status']=='LIVE READY'
    assert c.delete(p+'authorizations/'+grant,headers=__import__('test_ai_workspaces_v11').headers(c)).status_code==200
    assert c.get(p+'live-status?authorization_id='+grant).json()['status']=='LIVE BLOCKED'
    assert c.get(p+f'google/{grant}/executions/'+eid).json()['result']==result['result']
    assert post(c,p+'live',{'authorization_id':grant,'question':'Another question?'}).status_code==403
