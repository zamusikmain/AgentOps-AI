import asyncio,json
import pytest
from sqlalchemy import select
from app.config import Settings
from app.db import Base,database,LLMExecution,BudgetReservation,LLMConfiguration
from app.providers import MockProvider,ProviderError,Reply
from app.llm_reliability import Reliability,category

def layer(tmp_path,**kwargs):
 s=Settings(_env_file=None,database_url=f'sqlite:///{tmp_path/"llm.db"}',**kwargs);engine,sessions=database(s.database_url);Base.metadata.create_all(engine);l=Reliability(sessions,s,MockProvider());l.seed();return l

def run(l):return asyncio.run(l.execute({'model':'mock','instructions':'Read data','prompt':'Private text'},[{'role':'user','parts':[{'text':'Private text'}]}],128))

def test_mock_trace(tmp_path):
 l=layer(tmp_path);r=run(l)
 with l.sessions() as db:
  saved=db.get(LLMExecution,r.request_id);assert saved.status=='success';assert saved.content is None;assert 'Private text' not in json.dumps(saved.metadata_json);assert saved.usage['source']=='estimated';assert saved.model=='mock-v1';assert saved.metadata_json['prompt_version']==1

def test_external_key_not_permission(tmp_path):
 l=layer(tmp_path,llm_provider='gemini',gemini_api_key='test-key')
 with pytest.raises(ProviderError,match='external_api_disabled'):run(l)

def test_unverified_model(tmp_path):
 l=layer(tmp_path,llm_provider='gemini',external_api_enabled=True,allowed_external_providers=['gemini'],allowed_external_operations=['generation'])
 with pytest.raises(ProviderError,match='model_unverified'):run(l)

@pytest.mark.parametrize('code,status,expected',[('provider_auth',401,'authentication'),('denied',403,'authorization'),('rate_limit',429,'rate_limit'),('provider_timeout',None,'timeout'),('budget_exceeded',None,'budget'),('bad_response',None,'invalid_response'),('model_unavailable',404,'provider_unavailable')])
def test_categories(code,status,expected):assert category(ProviderError(code,status))==expected

def test_retry(tmp_path):
 class Flaky(MockProvider):
  calls=0
  async def generate(self,*args):
   self.calls+=1
   if self.calls==1:raise ProviderError('rate_limit',429)
   return Reply(text='ok',input_tokens=2,output_tokens=1)
 l=layer(tmp_path);l.adapter=Flaky()
 with l.sessions() as db:r=db.get(LLMConfiguration,'workspace:policy:execution');r.body={**r.body,'max_attempts':2,'backoff_seconds':0};db.commit()
 r=run(l);assert l.adapter.calls==2
 with l.sessions() as db:assert db.get(LLMExecution,r.request_id).retry_count==1

def test_auth_no_retry(tmp_path):
 class Auth(MockProvider):
  calls=0
  async def generate(self,*args):self.calls+=1;raise ProviderError('provider_auth',401)
 l=layer(tmp_path);l.adapter=Auth()
 with pytest.raises(ProviderError):run(l)
 assert l.adapter.calls==1

def test_atomic_budget(tmp_path):
 from concurrent.futures import ThreadPoolExecutor
 l=layer(tmp_path)
 with l.sessions() as db:
  r=db.get(LLMConfiguration,'workspace:budget:limits');r.body={'request_usd':1,'day_usd':1,'month_usd':1};db.add_all([LLMExecution(id=str(i),trace_id=str(i),tenant_id='workspace',user_id='owner',provider='gemini',model='test',operation='generation') for i in range(4)]);db.commit()
 def reserve(i):
  try:l.reserve(str(i),1,{'provider':'gemini','model':'test'},.6);return True
  except ProviderError:return False
 with ThreadPoolExecutor(4) as executor:assert sum(executor.map(reserve,range(4)))==1
 l.recover()
 with l.sessions() as db:assert db.scalar(select(BudgetReservation)).status=='uncertain'

def test_invalid_not_success(tmp_path):
 class Bad(MockProvider):
  async def generate(self,*args):return Reply(text='invalid',input_tokens=-1)
 l=layer(tmp_path);l.adapter=Bad()
 with pytest.raises(ProviderError):run(l)
 with l.sessions() as db:assert db.scalar(select(LLMExecution)).status=='failed'


def test_rbac_and_prompts(tmp_path):
 from fastapi.testclient import TestClient
 from app.main import create_app
 s=Settings(_env_file=None,database_url=f'sqlite:///{tmp_path/"api.db"}',checkpoint_database_path=tmp_path/'cp.db',knowledge_storage_path=tmp_path/'docs',api_token='owner',local_mcp_enabled=False,llm_principals=[{'token':'viewer','tenant':'other','user':'u','role':'viewer'}])
 app=create_app(s);Base.metadata.create_all(app.state.engine)
 with TestClient(app,headers={'Authorization':'Bearer owner'}) as c:
  body={'prompt_id':'generation','version':1,'template':'safe','purpose':'generation','change_description':'immutable'}
  assert c.post('/api/llm/prompts',json=body).status_code==409
  body['version']=2;assert c.post('/api/llm/prompts',json=body).status_code==201
  assert c.put('/api/llm/prompts/generation/2/active').status_code==200
  body['version']=3;body['template']='api_key=secret';assert c.post('/api/llm/prompts',json=body).status_code==422
  h={'Authorization':'Bearer viewer','X-Tenant-ID':'workspace'}
  assert c.get('/api/llm/prompts',headers=h).json()['items']==[]
  assert c.put('/api/llm/policy',json={},headers=h).status_code==403
  assert c.get('/api/agents',headers=h).status_code==401
  assert c.put('/api/llm/policy',json={'fallback_enabled':True}).status_code==422
  assert c.put('/api/llm/budget',json={'provider_usd':{'gemini':-1}}).status_code==422

def test_timeout_no_retry(tmp_path):
 class Slow(MockProvider):
  calls=0
  async def generate(self,*args):self.calls+=1;await asyncio.sleep(.1)
 l=layer(tmp_path);l.adapter=Slow()
 with l.sessions() as db:r=db.get(LLMConfiguration,'workspace:policy:execution');r.body={**r.body,'max_attempts':3,'timeout_seconds':.01};db.commit()
 with pytest.raises(ProviderError,match='provider_timeout'):run(l)
 assert l.adapter.calls==1

def test_breaker(tmp_path):
 class Broken(MockProvider):
  calls=0
  async def generate(self,*args):self.calls+=1;raise ProviderError('unavailable',503)
 l=layer(tmp_path);l.adapter=Broken()
 for _ in range(3):
  with pytest.raises(ProviderError):run(l)
 with pytest.raises(ProviderError,match='circuit_open'):run(l)
 assert l.adapter.calls==3

def test_cancel_trace(tmp_path):
 class Slow(MockProvider):
  async def generate(self,*args):await asyncio.sleep(10)
 l=layer(tmp_path);l.adapter=Slow()
 async def cancel():
  job=asyncio.create_task(l.execute({'instructions':'safe'},[],128));await asyncio.sleep(.03);job.cancel()
  with pytest.raises(asyncio.CancelledError):await job
 asyncio.run(cancel())
 with l.sessions() as db:assert db.scalar(select(LLMExecution)).status=='cancelled'

def test_half_open_single_probe_and_recovery(tmp_path):
 l=layer(tmp_path);p={'breaker_threshold':1,'breaker_cooldown_seconds':0}
 l.circuit('mock','mock-v1',p,'failure');l.circuit('mock','mock-v1',p,'enter')
 with pytest.raises(ProviderError,match='circuit_open'):l.circuit('mock','mock-v1',p,'enter')
 l.circuit('mock','mock-v1',p,'success');l.circuit('mock','mock-v1',p,'enter')

def test_fallback_needs_server_data_permission(tmp_path):
 l=layer(tmp_path)
 with l.sessions() as db:r=db.get(LLMConfiguration,'workspace:policy:execution');r.body={**r.body,'fallback_enabled':True,'fallback_provider':'mock','fallback_model':'mock-v1'};db.commit()
 class Broken(MockProvider):
  async def generate(self,*args):raise ProviderError('unavailable',503)
 l.adapter=Broken()
 with pytest.raises(ProviderError):asyncio.run(l.bind().generate({'instructions':'safe'},[],128))
 with l.sessions() as db:assert len(list(db.scalars(select(LLMExecution))))==1

def test_authorized_explicit_mock_degradation(tmp_path):
 l=layer(tmp_path,llm_provider='gemini',external_api_enabled=True,allowed_external_providers=['gemini'],allowed_external_operations=['generation'],allowed_fallback_models=['mock-v1'],fallback_data_allowed=True,mock_degradation_allowed=True)
 class Broken(MockProvider):
  async def generate(self,*args):raise ProviderError('unavailable',503)
 l.adapter=Broken()
 with l.sessions() as db:
  r=db.get(LLMConfiguration,'workspace:model:'+l.settings.gemini_model);r.body={**r.body,'availability':'available','compatible':True,'input_rate':0,'output_rate':0,'pricing_version':'stub-v1'}
  p=db.get(LLMConfiguration,'workspace:policy:execution');p.body={**p.body,'fallback_enabled':True,'fallback_provider':'mock','fallback_model':'mock-v1'}
  b=db.get(LLMConfiguration,'workspace:budget:limits');b.body={'request_usd':0,'day_usd':0,'month_usd':0};db.commit()
 r=asyncio.run(l.bind().generate({'model':l.settings.gemini_model,'instructions':'safe'},[{'role':'user','parts':[{'text':'safe'}]}],128));assert r.provider_id=='mock'
 with l.sessions() as db:
  rows=list(db.scalars(select(LLMExecution)));assert len(rows)==2;assert {r.status for r in rows}=={'failed','success'};assert all(r.fallback_count==1 for r in rows)

def approved(l,rates=(1,1)):
 with l.sessions() as db:
  r=db.get(LLMConfiguration,'workspace:model:'+l.settings.gemini_model);r.body={**r.body,'availability':'available','compatible':True,'input_rate':rates[0],'output_rate':rates[1],'pricing_version':'local-stub-price-v1'}
  b=db.get(LLMConfiguration,'workspace:budget:limits');b.body={'request_usd':.01,'day_usd':.01,'month_usd':.01};db.commit()

def test_pricing_unknown_blocks(tmp_path):
 l=layer(tmp_path,llm_provider='gemini',external_api_enabled=True,allowed_external_providers=['gemini'],allowed_external_operations=['generation']);approved(l,(None,None))
 with pytest.raises(ProviderError,match='pricing_unverified'):asyncio.run(l.execute({'model':l.settings.gemini_model,'instructions':'safe'},[],128))

def test_stub_cost_reconciliation(tmp_path):
 l=layer(tmp_path,llm_provider='gemini',external_api_enabled=True,paid_operations_enabled=True,allowed_external_providers=['gemini'],allowed_external_operations=['generation']);approved(l)
 class Stub(MockProvider):
  async def generate(self,*args):return Reply(text='local SDK stub',input_tokens=10,output_tokens=20,usage_source='reported',cached_tokens=2,reasoning_tokens=3)
 l.adapter=Stub();r=asyncio.run(l.execute({'model':l.settings.gemini_model,'instructions':'safe'},[],128))
 with l.sessions() as db:
  row=db.get(LLMExecution,r.request_id);assert row.estimated_cost_usd==pytest.approx(.00003);assert row.usage['cached_tokens']==2
  reservation=db.scalar(select(BudgetReservation));assert reservation.status=='settled';assert reservation.charged_usd<reservation.reserved_usd

def test_unknown_usage_keeps_reservation(tmp_path):
 l=layer(tmp_path,llm_provider='gemini',external_api_enabled=True,paid_operations_enabled=True,allowed_external_providers=['gemini'],allowed_external_operations=['generation']);approved(l)
 class Stub(MockProvider):
  async def generate(self,*args):return Reply(text='stub without usage',usage_source='unknown')
 l.adapter=Stub();r=asyncio.run(l.execute({'model':l.settings.gemini_model},[],128))
 with l.sessions() as db:assert db.get(LLMExecution,r.request_id).estimated_cost_usd is None;assert db.scalar(select(BudgetReservation)).status=='uncertain'

def test_pricing_versions_and_regression_comparison(tmp_path):
 from fastapi.testclient import TestClient
 from app.main import create_app
 from app.db import EvaluationRun
 s=Settings(_env_file=None,database_url=f'sqlite:///{tmp_path/"price-api.db"}',checkpoint_database_path=tmp_path/'cp.db',knowledge_storage_path=tmp_path/'docs',api_token='owner',local_mcp_enabled=False)
 app=create_app(s);Base.metadata.create_all(app.state.engine)
 with TestClient(app,headers={'Authorization':'Bearer owner'}) as c:
  body={'provider':'gemini','model':'stub','display_name':'SDK stub','pricing_version':'test-v1','input_rate':1,'output_rate':2}
  assert c.put('/api/llm/models',json=body).status_code==200
  body['input_rate']=3;assert c.put('/api/llm/models',json=body).status_code==409
  body['pricing_version']='test-v2';assert c.put('/api/llm/models',json=body).status_code==200
  with app.state.sessions() as db:
   old=EvaluationRun(id='baseline',agent_id='test',document_ids=[],dataset_version='fixed',status='completed',provider_metadata={'generation':'mock'},metrics={'hybrid':{'answer_correct':40,'false_abstention_rate':0,'retrieval':{'hit_at_1':1}}})
   current=EvaluationRun(id='current',agent_id='test',document_ids=[],dataset_version='fixed',status='completed',provider_metadata={'generation':'mock'},metrics={'hybrid':{'answer_correct':39,'false_abstention_rate':.1,'retrieval':{'hit_at_1':.9}}});db.add_all([old,current]);db.commit()
  comparison=c.post('/api/llm/comparisons',json={'baseline_id':'baseline','current_id':'current'});assert comparison.status_code==200;assert comparison.json()['result']['passed'] is False
  assert len(comparison.json()['result']['modes']['hybrid']['regressions'])==3
  assert c.get('/api/llm/comparisons').json()['items']

def test_provider_usage_overrun_stops_with_recorded_cost(tmp_path):
 l=layer(tmp_path,llm_provider='gemini',external_api_enabled=True,paid_operations_enabled=True,allowed_external_providers=['gemini'],allowed_external_operations=['generation']);approved(l)
 class Stub(MockProvider):
  async def generate(self,*args):return Reply(text='unexpected overrun',input_tokens=1000000,output_tokens=20,usage_source='reported')
 l.adapter=Stub()
 with pytest.raises(ProviderError,match='budget_overrun'):asyncio.run(l.execute({'model':l.settings.gemini_model},[],128))
 with l.sessions() as db:
  r=db.scalar(select(LLMExecution));assert r.status=='failed';assert r.error_category=='budget';assert r.usage['input_tokens']==1000000;assert db.scalar(select(BudgetReservation)).status=='overdrawn'
