import asyncio,json,time,hashlib
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from app.main import create_app
from app.config import Settings
from app.db import Base,ValidationRun,LLMExecution,LLMConfiguration
from app.validation import ValidationInput
from app.profiling import Profile,distribution
from app.embeddings import MockEmbeddingProvider,signature,normalize,cache_key
from app.embedding_validation import compatibility

@pytest.fixture
def client(tmp_path):
 s=Settings(_env_file=None,database_url=f'sqlite:///{tmp_path/"v09.db"}',checkpoint_database_path=tmp_path/'cp.db',knowledge_storage_path=tmp_path/'docs',api_token='owner',local_mcp_enabled=False,llm_principals=[{'token':'viewer','tenant':'foreign','user':'viewer','role':'viewer'}])
 app=create_app(s);Base.metadata.create_all(app.state.engine)
 with TestClient(app,headers={'Authorization':'Bearer owner'}) as c:yield c

def test_builtin_integrity_and_no_gold_change(client):
 rows=client.get('/api/validation/datasets').json()['items'];assert [r['questions'] for r in rows]==[40,64,12]
 assert all(len(r['hash'])==64 for r in rows)

def independent(client):
 body={'id':'separate','version':1,'name':'Private independent fixture','questions':[{'id':'unanswerable','question':'Private question marker not for export','language':'en','expected_behavior':'abstain','scope':[]}]}
 assert client.post('/api/validation/datasets',json=body).status_code==201
 return body

def wait(client,rid):
 for _ in range(200):
  r=client.get('/api/validation/runs/'+rid).json()
  if r['status'] not in ('queued','running'):return r
  time.sleep(.03)
 pytest.fail('Validation did not complete')

def test_independent_version_immutable_and_export_privacy(client):
 body=independent(client);body['questions'][0]['question']='Changed';assert client.post('/api/validation/datasets',json=body).status_code==409
 run=client.post('/api/validation/runs',json={'dataset_id':'separate'});assert run.status_code==202;run=wait(client,run.json()['id']);assert run['status']=='completed',run
 assert run['result']['verification']=='MOCK';assert run['result']['quality']['hybrid']['answer_correct']==1
 for format in ('json','md','csv'):
  r=client.get(f'/api/validation/runs/{run["id"]}/export/{format}');assert r.status_code==200;assert 'Private question marker' not in r.text
 assert client.get('/api/validation/runs/'+run['id'],headers={'Authorization':'Bearer viewer','X-Tenant-ID':'workspace'}).status_code==404
 assert client.get(f'/api/validation/runs/{run["id"]}/export/json',headers={'Authorization':'Bearer viewer'}).status_code==404
 assert client.get('/api/llm/requests').json()['items'][0]['operation']=='validation'

def test_dry_run_zero_provider_calls(client):
 independent(client);before=client.get('/api/llm/summary').json()['requests']
 body={'dataset_id':'separate','mode':'REAL_DRY_RUN','provider':'gemini','model':'gemini-unknown'}
 plan=client.post('/api/validation/readiness',json=body).json();assert plan['status']=='BLOCKED';codes={b['code'] for b in plan['blockers']};assert 'real_execution_disabled' in codes and 'pricing_unverified' in codes
 r=client.post('/api/validation/runs',json=body);assert r.status_code==202;assert r.json()['result']['verification']=='DRY RUN'
 assert client.get('/api/llm/summary').json()['requests']==before
 body['mode']='REAL_EXECUTION';assert client.post('/api/validation/runs',json=body).status_code==403

def test_rbac_mutation_and_header_spoof(client):
 independent(client)
 h={'Authorization':'Bearer viewer','X-Tenant-ID':'workspace'}
 assert client.get('/api/validation/datasets',headers=h).json()['items']==[]
 assert client.post('/api/validation/datasets',json={'id':'x'},headers=h).status_code==422
 assert client.post('/api/validation/runs',json={'dataset_id':'separate'},headers=h).status_code==403
 assert client.post('/api/validation/prepare/v1',headers=h).status_code==403

def test_dataset_integrity_tamper(client):
 independent(client)
 with client.app.state.sessions() as db:r=db.get(LLMConfiguration,'workspace:validation_dataset:separate:1');r.body={**r.body,'name':'tampered'};db.commit()
 assert client.post('/api/validation/readiness',json={'dataset_id':'separate'}).status_code==409

def test_request_limits_and_unknown_model(client):
 response=client.post('/api/validation/readiness',json={'max_requests':1,'retrieval_modes':['lexical','semantic','hybrid']});assert response.status_code==200;assert 'validation_request_limit' in [r['code'] for r in response.json()['blockers']]
 assert client.post('/api/validation/readiness',json={'mode':'MOCK_ONLY','provider':'gemini'}).status_code==422

def test_embedding_namespace_readonly(client):
 p=MockEmbeddingProvider(128);q=MockEmbeddingProvider(256);assert signature(p)!=signature(q);assert cache_key(p,'sample')!=cache_key(q,'sample')
 vector=p.embed(['document text'],'document')[0];assert sum(v*v for v in vector)==pytest.approx(1)
 assert compatibility(client.app.state.knowledge,[])['mutated'] is False

def test_profile_statistics_and_commit_counts(client):
 p=Profile().start()
 try:
  with client.app.state.sessions() as db:db.add(LLMConfiguration(id='measurement',tenant_id='workspace',kind='test',name='test',body={}));db.commit()
  result=p.snapshot();assert result['counts']['commits']==1;assert result['counts']['sqlite_writes']==1;assert result['phases_ms']['sqlite_commit']>=0
 finally:p.stop()
 assert distribution([1,2,3])['p95_ms'] is None;assert distribution(list(range(100)))['p99_ms']==98

def test_custom_token_stop(client):
 independent(client);r=client.post('/api/validation/runs',json={'dataset_id':'separate','max_total_tokens':128,'max_output_tokens':128});assert r.status_code==202;r=wait(client,r.json()['id']);assert r['status']=='failed';assert r['result']['error']=='validation_token_limit'

def test_real_mechanism_only_with_local_injected_provider(tmp_path):
 from app.providers import MockProvider,Reply
 # Isolated settings object and non-network adapter; never changes the working configuration.
 class ContractStub(MockProvider):
  calls=0
  async def generate(self,snapshot,messages,remaining):
   self.calls+=1;assert 'expected_answer' not in json.dumps(messages);return Reply(text='{"found":false,"citations":[]}',input_tokens=3,output_tokens=4,usage_source='reported')
 s=Settings(_env_file=None,database_url=f'sqlite:///{tmp_path/"stub-live.db"}',checkpoint_database_path=tmp_path/'cp.db',knowledge_storage_path=tmp_path/'docs',api_token='owner',local_mcp_enabled=False,llm_provider='gemini',gemini_api_key='contract-placeholder',real_validation_enabled=True,validation_transport_is_stub=True,external_api_enabled=True,allowed_external_providers=['gemini'],allowed_external_operations=['validation'])
 stub=ContractStub();app=create_app(s,provider=stub);Base.metadata.create_all(app.state.engine)
 with TestClient(app,headers={'Authorization':'Bearer owner'}) as c:
  independent(c)
  assert c.put('/api/llm/models',json={'provider':'gemini','model':'contract-fixture','display_name':'LOCAL CONTRACT FIXTURE','availability':'available','compatible':True,'last_verified':'CONTRACT_TESTED','capabilities':['structured'],'pricing_version':'fixture-free','input_rate':0,'output_rate':0}).status_code==200
  assert c.put('/api/llm/budget',json={'request_usd':0,'day_usd':0,'month_usd':0}).status_code==200
  request={'dataset_id':'separate','mode':'REAL_DRY_RUN','provider':'gemini','model':'contract-fixture','budget_usd':0,'max_requests':1,'max_output_tokens':128}
  p=c.post('/api/validation/readiness',json=request).json();assert p['status']=='BLOCKED'
  a=c.post('/api/validation/approvals',json={'plan_hash':p['hash'],'dataset_hash':p['dataset']['hash'],'provider':'gemini','model':'contract-fixture','user_approved':True,'admin_approved':True,'data_approved':True});assert a.status_code==201
  request['mode']='REAL_EXECUTION';request['approval_id']=a.json()['id'];r=c.post('/api/validation/runs',json=request);assert r.status_code==202,r.json();r=wait(c,r.json()['id']);assert r['status']=='completed',r;assert r['result']['verification']=='CONTRACT_TESTED';assert r['result']['external_calls']==0;assert stub.calls==1
  assert c.post('/api/validation/runs',json=request).status_code==403;assert stub.calls==1

def test_builtin_readiness_requires_all_exact_fixture_sources(client):
 a=client.post('/api/agents',json={'name':'Incomplete source scope','role':'researcher','instructions':'Read supplied context','model':'mock','tools':['knowledge_search'],'document_ids':[]}).json()
 plan=client.post('/api/validation/readiness',json={'agent_id':a['id']}).json();assert plan['status']=='BLOCKED';assert 'dataset_permission_denied' in [b['code'] for b in plan['blockers']]

def test_embedding_change_demands_explicit_reindex_without_mutating(client):
 from app.evaluation import synthetic_pdf
 async def install():
  k=client.app.state.knowledge;d=k.create('compatibility.pdf',synthetic_pdf(['A local retention policy is 7 days.']));await k.jobs[d['id']];return d['id']
 identifier=client.portal.call(install)
 assert compatibility(client.app.state.knowledge,[identifier])['status']=='READY'
 client.app.state.knowledge.vectors.provider.model='changed-model-version'
 result=compatibility(client.app.state.knowledge,[identifier]);assert result['status']=='BLOCKED';assert result['reindex_required']==[identifier];assert result['mutated'] is False

def test_same_tenant_viewer_cannot_read_owner_traces(client):
 client.app.state.validation.settings.llm_principals.append({'token':'peer','tenant':'workspace','user':'peer','role':'viewer'})
 reply=client.portal.call(client.app.state.llm.execute,{'instructions':'local'},[{'role':'user','parts':[{'text':'local'}]}],128)
 h={'Authorization':'Bearer peer','X-User-ID':'owner'}
 assert client.get('/api/llm/requests',headers=h).json()['items']==[]
 assert client.get('/api/llm/summary',headers=h).json()['requests']==0
 assert client.get('/api/llm/requests/'+reply.request_id,headers=h).status_code==404
 assert not any(i['kind']=='validation_dataset' for i in client.get('/api/llm/configuration',headers=h).json()['items'])

def test_dataset_credentials_rejected_without_storage(client):
 body={'id':'credential','version':1,'name':'AIza'+'x'*35,'questions':[{'id':'q','question':'q','language':'en','expected_behavior':'abstain','scope':[]}]}
 response=client.post('/api/validation/datasets',json=body);assert response.status_code==422;assert 'AIza' not in response.text
 assert not any(d['id']=='credential' for d in client.get('/api/validation/datasets').json()['items'])

def test_provider_selection_never_relabels_default_mock_as_gemini(tmp_path):
 from app.llm_reliability import Reliability
 from app.providers import GeminiProvider,MockProvider,ProviderError
 from app.db import database
 s=Settings(_env_file=None,database_url=f'sqlite:///{tmp_path/"selection.db"}');engine,sessions=database(s.database_url);Base.metadata.create_all(engine);l=Reliability(sessions,s,MockProvider());l.seed()
 assert isinstance(l.adapter_for('gemini'),GeminiProvider);assert l.adapter_for('gemini').client is None
 with pytest.raises(ProviderError,match='external_api_disabled'):asyncio.run(l.execute({'model':s.gemini_model,'instructions':'local'},[],128,provider='gemini'))
 assert l.adapter_for('gemini').client is None
