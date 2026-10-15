import time,json,concurrent.futures
import pytest
from fastapi.testclient import TestClient
from app.main import create_app
from app.config import Settings
from app.db import Base,LLMConfiguration
from app.live_envelope import Envelope
from app.providers import ProviderError
@pytest.fixture
def client(tmp_path):
 s=Settings(_env_file=None,database_url=f'sqlite:///{tmp_path/"main.db"}',checkpoint_database_path=tmp_path/'cp.db',knowledge_storage_path=tmp_path/'docs',api_token='owner',local_mcp_enabled=False,llm_principals=[{'token':'other','tenant':'workspace','user':'other','role':'operator'},{'token':'foreign','tenant':'foreign','user':'owner','role':'admin'},{'token':'viewer','tenant':'workspace','user':'owner','role':'viewer'}])
 app=create_app(s);Base.metadata.create_all(app.state.engine)
 with TestClient(app,headers={'Authorization':'Bearer owner'}) as c:yield c

def wait(c,id):
 for _ in range(400):
  r=c.get('/api/validation/smoke/runs/'+id).json()
  if r['status'] not in ('queued','running'):return r
  time.sleep(.05)
 pytest.fail('smoke timed out')

def test_stage_a_blocked_even_before_preparation(client):
 status=client.get('/api/validation/smoke/status').json();assert status['real_enabled'] is False;assert status['real_metrics']=='NOT VERIFIED';assert status['model'] is None
 assert client.post('/api/validation/smoke/runs',json={'mode':'REAL_EXECUTION'}).status_code==403
 r=client.post('/api/validation/smoke/runs',json={'mode':'REAL_DRY_RUN'});assert r.status_code==202;assert r.json()['result']['external_calls']==0
 assert client.get('/api/llm/summary').json()['requests']==0

def test_corpus_isolation_and_complete_history_review(client):
 prepared=client.post('/api/validation/smoke/prepare');assert prepared.status_code==200,prepared.text
 p=prepared.json();assert len(p['documents'])==5;assert p['dataset']['questions']==12
 assert client.get('/api/knowledge/documents').json().get('items',[])==[]
 r=client.post('/api/validation/smoke/runs',json={});assert r.status_code==202,r.text
 run=wait(client,r.json()['id']);assert run['status']=='completed',run
 assert len(run['cases'])==12;assert run['result']['external_calls']==0;assert run['result']['verification']=='MOCK'
 assert len(run['traces'])==11;assert run['result']['envelope']['generation']==11
 access=next(c for c in run['cases'] if c['case_id']=='access');assert access['result']['verification']['status']=='inaccessible'
 assert 'VAULT-777' not in json.dumps(run['cases'])
 injection=next(c for c in run['cases'] if c['case_id']=='injection');assert all('Ignore all' not in m['excerpt'] for m in injection['result']['retrieved_evidence'])
 endpoint='/api/validation/smoke/runs/'+run['id']
 review=client.post(endpoint+'/reviews',json={'case_id':'fact-code','verdict':'correct','notes':'Reviewed literal evidence.'});assert review.status_code==201
 first=client.get(endpoint).json();assert len(first['human_reviews'])==1;assert first['cases']==run['cases']
 assert client.post(endpoint+'/reviews',json={'case_id':'fact-code','verdict':'partially_correct','notes':'Second opinion'}).status_code==201
 assert len(client.get(endpoint).json()['human_reviews'])==2
 for token in ('other','foreign'):
  h={'Authorization':'Bearer '+token};assert client.get(endpoint,headers=h).status_code==404;assert client.get(endpoint+'/export',headers=h).status_code==404;assert client.post(endpoint+'/reviews',json={'case_id':'fact-code','verdict':'correct'},headers=h).status_code==404
 assert client.post(endpoint+'/reviews',json={'case_id':'fact-code','verdict':'correct'},headers={'Authorization':'Bearer viewer'}).status_code==403
 assert client.post(endpoint+'/reviews',json={'case_id':'fact-code','verdict':'correct','notes':'api_key=secret'}).status_code==422
 # A new service instance reads persistent isolated data, without mutating result rows.
 from app.live_smoke import Smoke
 reopened=Smoke(client.app.state.smoke.runtime(__import__('app.llm_reliability',fromlist=['Scope']).Scope()).settings,())
 # root derives from documents parent, so use original root for reopened service.
 reopened.root=client.app.state.smoke.root
 assert len(reopened.read(__import__('app.llm_reliability',fromlist=['Scope']).Scope(),run['id'])['human_reviews'])==2
 for v,engine in reopened.runtimes.values():engine.dispose()

def test_prepare_rbac_and_limits(client):
 assert client.post('/api/validation/smoke/prepare',headers={'Authorization':'Bearer viewer'}).status_code==403
 assert client.post('/api/validation/smoke/runs',json={'max_generation_calls':13}).status_code==422
 assert client.post('/api/validation/smoke/runs',json={'fallback':True}).status_code==422
 assert client.post('/api/validation/smoke/runs',json={'max_total_requests':-1}).status_code==422

def limits():return {'total_requests':2,'generation_calls':2,'embedding_calls':2,'total_tokens':100,'cost_usd':.1,'duration_seconds':60,'generation_provider':'mock','generation_model':'mock-v1','embedding_provider':'mock','embedding_model':'mock-hash-ngram-v1'}
@pytest.mark.parametrize('failure,code',[('unknown','pricing_unverified'),('model','model_denied'),('tokens','validation_token_limit'),('cost','budget_exceeded'),('operation','operation_denied'),('negative','invalid_usage')])
def test_envelope_fail_closed(client,failure,code):
 v=client.app.state.smoke.runtime(__import__('app.llm_reliability',fromlist=['Scope']).Scope());g=Envelope(v.sessions,failure,limits());args=['generation','mock','mock-v1',1,0]
 if failure=='unknown':args[4]=None
 if failure=='model':args[2]='paid-model'
 if failure=='tokens':args[3]=101
 if failure=='cost':args[4]=.2
 if failure=='operation':args[0]='shell'
 if failure=='negative':args[3]=-1
 with pytest.raises(ProviderError,match=code):g.claim(*args)
 assert g.view()['total']==0

def test_shared_atomic_count_reretrieval_retry_parallel(client):
 v=client.app.state.smoke.runtime(__import__('app.llm_reliability',fromlist=['Scope']).Scope());g=Envelope(v.sessions,'parallel',limits())
 def request(i):
  try:g.claim('generation' if i%2 else 'embedding','mock','mock-v1' if i%2 else 'mock-hash-ngram-v1',1,0);return True
  except ProviderError:return False
 with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:assert sum(pool.map(request,range(8)))==2
 assert g.view()['total']==2

def test_envelope_cancellation_unknown_usage_and_timeout(client):
 v=client.app.state.smoke.runtime(__import__('app.llm_reliability',fromlist=['Scope']).Scope());g=Envelope(v.sessions,'cancel',limits());g.claim('generation','mock','mock-v1',80,.08)
 # Missing usage or interrupted dispatch never releases conservative reservation.
 assert g.view()['tokens']==80;assert g.view()['estimated_usd']==.08
 with pytest.raises(ProviderError,match='validation_token_limit'):g.claim('generation','mock','mock-v1',30,0)
 with v.sessions() as db:r=db.get(LLMConfiguration,g.key);r.body={**r.body,'started':time.time()-61};db.commit()
 with pytest.raises(ProviderError,match='validation_timeout'):g.claim('generation','mock','mock-v1',1,0)

def test_smoke_request_cap_stops_embeddings(client):
 assert client.post('/api/validation/smoke/prepare').status_code==200
 r=client.post('/api/validation/smoke/runs',json={'max_total_requests':1});assert r.status_code==202
 run=wait(client,r.json()['id']);assert run['status']=='failed';assert run['result']['actual_requests']<=1

def test_corpus_hash_and_namespace(client):
 from app.live_smoke_dataset import corpus,PATH
 from app.embeddings import MockEmbeddingProvider,signature
 data,digest=corpus();assert digest==PATH.with_suffix('.sha256').read_text().strip();assert len(data['questions'])==12;assert {q['language'] for q in data['questions']}=={'ru','en'}
 v=client.app.state.smoke.runtime(__import__('app.llm_reliability',fromlist=['Scope']).Scope());assert signature(v.knowledge.vectors.provider)!=signature(MockEmbeddingProvider())
 assert v.settings.external_api_enabled is False and v.settings.embedding_external_enabled is False
def test_smoke_cancellation_is_persisted_and_no_dispatch_retry(client):
 import asyncio
 from app.llm_reliability import Scope
 assert client.post('/api/validation/smoke/prepare').status_code==200
 v=client.app.state.smoke.runtime(Scope());original=v.llm.adapter.generate
 async def slow(snapshot,messages,remaining):
  await original(snapshot,messages,remaining)
  await asyncio.sleep(30)
 v.llm.adapter.generate=slow
 r=client.post('/api/validation/smoke/runs',json={});assert r.status_code==202
 rid=r.json()['id']
 for _ in range(100):
  with v.sessions() as db:
   from app.db import LLMExecution
   trace=db.scalar(__import__('sqlalchemy').select(LLMExecution).where(LLMExecution.trace_id==rid))
   if trace and trace.status=='running':break
  time.sleep(.01)
 cancelled=client.post('/api/validation/smoke/runs/'+rid+'/cancel');assert cancelled.status_code==200
 saved=client.get('/api/validation/smoke/runs/'+rid).json();assert saved['status']=='cancelled';assert saved['result']['external_calls']==0;assert len(saved['traces'])==1
 assert all(t['retry_count']==0 and t['fallback_count']==0 for t in saved['traces'])

def test_smoke_lock_cannot_be_overridden_by_environment(client):
 from app.llm_reliability import Scope
 v=client.app.state.smoke.runtime(Scope());v.settings.real_validation_enabled=True;v.settings.external_api_enabled=True;v.settings.embedding_external_enabled=True
 assert client.post('/api/validation/smoke/runs',json={'mode':'REAL_EXECUTION','model':'arbitrary-model'}).status_code==403
 assert client.get('/api/validation/smoke/status').json()['real_enabled'] is False

def test_exact_boundary_decimal_cost_and_dataset_version(client):
 from app.llm_reliability import Scope
 v=client.app.state.smoke.runtime(Scope());g=Envelope(v.sessions,'decimal-boundary',limits());g.claim('generation','mock','mock-v1',1,.04);g.claim('embedding','mock','mock-hash-ngram-v1',1,.06);assert g.view()['budget_remaining_usd']==0
 assert client.post('/api/validation/smoke/runs',json={'dataset':'user-private-document'}).status_code==422
 assert client.post('/api/validation/smoke/runs',json={'provider':'paid-provider'}).status_code==422
def test_prepared_embedding_boundary_uses_atomic_budget_and_unknown_hold(client):
 from app.llm_reliability import Scope
 from app.live_embedding_budget import BudgetedGoogleEmbedding
 from app.live_envelope import active_envelope
 from app.embeddings import EmbeddingError,MockEmbeddingProvider
 from app.db import BudgetReservation
 from sqlalchemy import select
 v=client.app.state.smoke.runtime(Scope());s=v.settings
 s.real_validation_enabled=True;s.external_api_enabled=True;s.embedding_external_enabled=True;s.allowed_external_providers=['google'];s.allowed_external_operations=['embedding']
 raw=MockEmbeddingProvider();raw.model='local-embedding-contract';raw.name='google'
 wrapper=BudgetedGoogleEmbedding(s,v.llm,raw)
 with pytest.raises(EmbeddingError,match='embedding_consent_required'):wrapper.embed(['Synthetic only'],'document')
 l=limits();l['total_tokens']=100000;l['embedding_provider']='google';l['embedding_model']=raw.model;g=Envelope(v.sessions,'embedding-budget',l);token=active_envelope.set(g)
 try:
  with pytest.raises(EmbeddingError,match='model_unverified'):wrapper.embed(['Synthetic only'],'document')
  with v.sessions() as db:
   r=db.get(LLMConfiguration,'workspace:model:'+raw.model);r.body={'provider':'google','model':raw.model,'availability':'available','compatible':True,'input_rate':0,'output_rate':0,'pricing_version':'LOCAL_FIXTURE'};db.commit()
  with pytest.raises(EmbeddingError,match='budget_not_configured'):wrapper.embed(['Synthetic only'],'document')
  with v.sessions() as db:r=db.get(LLMConfiguration,'workspace:budget:limits');r.body={'request_usd':0,'day_usd':0,'month_usd':0};db.commit()
  assert len(wrapper.embed(['Synthetic only'],'document')[0])==768
  with v.sessions() as db:
   reservation=db.scalar(select(BudgetReservation));assert reservation.status=='uncertain';assert reservation.charged_usd is None
  assert raw.requests==1
 finally:active_envelope.reset(token)


def test_parallel_first_readiness_initializes_once(client):
 def check(_):return client.get('/api/validation/smoke/status').status_code
 with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:assert list(pool.map(check,range(8)))==[200]*8
 assert len(client.app.state.smoke.runtimes)==1
 assert client.post('/api/validation/smoke/readiness',json={'model':'AIza-not-a-model'}).status_code==422
 assert client.post('/api/validation/smoke/readiness',json={'model':'models/owner'}).status_code==422
