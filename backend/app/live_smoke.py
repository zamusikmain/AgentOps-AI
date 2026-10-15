"""Stage A only. Separate per-principal SQLite, documents and vector/cache namespace."""
import asyncio,hashlib,json,re,threading
from pathlib import Path
from typing import Literal
from pydantic import BaseModel,ConfigDict,Field
from sqlalchemy import select
from fastapi import APIRouter,Request
from .config import Settings
from .db import Base,database,LLMConfiguration,EvaluationCase,LLMExecution,Agent,KnowledgeDocument,serialize,uid,now
from .providers import MockProvider
from .embeddings import MockEmbeddingProvider,signature
from .llm_reliability import Reliability,Scope
from .knowledge_store import KnowledgeStore
from .evaluation import Evaluator,synthetic_pdf
from .validation import Validation,ValidationInput
from .live_smoke_dataset import corpus,PATH
from .live_envelope import active_envelope
from .services import ServiceError
from .profiling import distribution

class ReviewInput(BaseModel):
 model_config=ConfigDict(extra='forbid')
 case_id:str=Field(min_length=1,max_length=60)
 verdict:Literal['correct','partially_correct','incorrect','unsupported','correct_abstention','false_abstention']
 notes:str=Field(default='',max_length=2000)
class SmokeInput(BaseModel):
 model_config=ConfigDict(extra='forbid')
 mode:Literal['MOCK_ONLY','REAL_DRY_RUN','REAL_EXECUTION']='MOCK_ONLY'
 model:str|None=Field(default=None,min_length=1,max_length=120,pattern=r'^(?:models/)?[a-z][a-z0-9.-]{1,119}$')
 max_generation_calls:int=Field(default=12,ge=1,le=12)
 max_embedding_calls:int=Field(default=41,ge=0,le=41)
 max_total_requests:int=Field(default=52,ge=1,le=52)
 max_output_tokens:int=Field(default=512,ge=128,le=512)
 max_total_tokens:int=Field(default=150000,ge=128,le=150000)
 duration_seconds:int=Field(default=120,ge=1,le=120)
 budget_usd:float|None=Field(default=None,ge=0,le=1,allow_inf_nan=False)
class GuardedMock(MockProvider):
 async def generate(self,snapshot,messages,remaining):
  guard=active_envelope.get()
  if guard:guard.claim('generation','mock','mock-v1',len(json.dumps([snapshot,messages],ensure_ascii=False).encode())+2048+remaining,0)
  return await super().generate(snapshot,messages,remaining)
class GuardedEmbedding(MockEmbeddingProvider):
 def embed(self,texts,task):
  guard=active_envelope.get()
  if guard:guard.claim('embedding','mock',self.model,sum(len(t.encode()) for t in texts),0)
  return super().embed(texts,task)
class Smoke:
 def __init__(self,settings,secrets):
  self.root=Path(settings.knowledge_storage_path).parent/'live-smoke';self.secrets=secrets;self.runtimes={};self.lock=asyncio.Lock();self.runtime_lock=threading.RLock()
 def runtime(self,scope):
  with self.runtime_lock:return self._runtime(scope)
 def _runtime(self,scope):
  key=hashlib.sha256(json.dumps([scope.tenant,scope.user]).encode()).hexdigest()
  if key not in self.runtimes:
   path=self.root/key;path.mkdir(parents=True,exist_ok=True)
   s=Settings(_env_file=None,database_url=f'sqlite:///{path/"benchmark.db"}',checkpoint_database_path=path/'cp.db',knowledge_storage_path=path/'documents',api_token='offline-unused',embedding_revision='GeminiLiveSmoke-v1',local_mcp_enabled=False)
   engine,sessions=database(s.database_url);Base.metadata.create_all(engine)
   llm=Reliability(sessions,s,GuardedMock());llm.seed();llm.recover()
   knowledge=KnowledgeStore(sessions,s.knowledge_storage_path,s,GuardedEmbedding())
   evaluator=Evaluator(sessions,knowledge);evaluator.llm=llm
   v=Validation(sessions,s,llm,knowledge,evaluator);v.secrets=self.secrets;v.recover();knowledge.recover()
   self.runtimes[key]=(v,engine)
  return self.runtimes[key][0]
 def integrity(self):
  data,digest=corpus()
  if PATH.with_suffix('.sha256').read_text().strip()!=digest:raise ServiceError(409,'dataset_integrity_failed')
  return data,digest
 async def prepare(self,scope):
  if scope.role not in ('admin','operator'):raise ServiceError(403,'permission_denied')
  async with self.lock:
   v=self.runtime(scope);data,digest=self.integrity();mapping={}
   for name,pages in data['documents'].items():
    d=v.knowledge.create(name,synthetic_pdf(pages));job=v.knowledge.jobs.get(d['id'])
    if job:await asyncio.wait_for(asyncio.shield(job),40)
    with v.sessions() as db:
     doc=db.get(KnowledgeDocument,d['id'])
     if doc.status!='ready' or doc.embedding_status!='ready':raise ServiceError(409,'document_unavailable')
    mapping[name]=d['id']
   permitted=[value for name,value in mapping.items() if name!='Northstar-Restricted.pdf']
   with v.sessions() as db:
    a=db.scalar(select(Agent).where(Agent.name=='GeminiLiveSmoke-v1'))
    if not a:a=Agent(name='GeminiLiveSmoke-v1',role='researcher',instructions='Synthetic evidence only.',model='mock-v1',tools=['knowledge_search'],document_ids=permitted,max_steps=1,max_tokens=512);db.add(a);db.commit()
    agent_id=a.id
   questions=[]
   for original in data['questions']:
    q={**original,'scope':[mapping[n] for n in original['scope']],'expected_sources':[{**e,'document_id':mapping[e['document_id']]} for e in original['expected_sources']]}
    # Denied source is intentionally outside assigned corpus; no excerpt is retrieved.
    if q.get('access')=='denied':q['scope']=[];q['denied_source_id']=mapping['Northstar-Restricted.pdf']
    questions.append(q)
   desc=v.datasets.save('workspace',{'id':data['id'],'version':1,'name':data['name'],'classification':'public','synthetic':True,'corpus_hash':digest,'evidence_pipeline':True,'questions':questions})
   with v.sessions() as db:
    key='workspace:smoke_manifest:1';r=db.get(LLMConfiguration,key)
    body={'agent_id':agent_id,'documents':mapping,'corpus_hash':digest,'dataset':desc,'signature':signature(v.knowledge.vectors.provider)}
    if r and r.body!=body:raise ServiceError(409,'dataset_integrity_failed')
    if not r:db.add(LLMConfiguration(id=key,tenant_id='workspace',kind='smoke_manifest',name='1',body=body));db.commit()
   return body
 def manifest(self,v):
  with v.sessions() as db:r=db.get(LLMConfiguration,'workspace:smoke_manifest:1')
  return r.body if r else None
 def body(self,v,options):
  manifest=self.manifest(v)
  if not manifest:raise ServiceError(409,'smoke_prepare_required')
  _,digest=self.integrity()
  if manifest['corpus_hash']!=digest:raise ServiceError(409,'dataset_integrity_failed')
  return ValidationInput(dataset_id='gemini-live-smoke-v1',agent_id=manifest['agent_id'],max_requests=options.max_generation_calls,max_embedding_requests=options.max_embedding_calls,max_output_tokens=options.max_output_tokens,max_total_tokens=options.max_total_tokens,timeout_seconds=options.duration_seconds)
 def readiness(self,scope,options):
  self.integrity();v=self.runtime(scope);manifest=self.manifest(v)
  if options.model and any(secret and secret in options.model for secret in self.secrets):raise ServiceError(422,'dataset_secret_denied')
  planned_generation=11;planned_embedding_upper=41;planned_total=52
  return {'status':'BLOCKED','stage':'A','live_status':'LIVE NOT VERIFIED','real_enabled':False,'gemini_status':'CONTRACT_TESTED / LIVE NOT VERIFIED','embedding_status':'CONTRACT_TESTED / LIVE NOT VERIFIED','model':options.model,'model_status':'UNVERIFIED','model_characteristics':{k:'UNVERIFIED' for k in ('api_compatibility','context_window','output_limit','structured_output','tool_calling','usage_metadata','finish_reasons','availability','pricing')},'dataset':{'name':'GeminiLiveSmoke-v1','version':1,'corpus_hash':self.integrity()[1],'questions':12},'prepared':bool(manifest),'index_namespace':'isolated per principal / GeminiLiveSmoke-v1','planned_generation_calls':planned_generation,'planned_embedding_calls_upper_bound':planned_embedding_upper,'planned_total_calls_upper_bound':planned_total,'indexing_embedding_calls':5,'maximum_retries':0,'fallback_enabled':False,'verification_calls':0,'repair_calls':0,'limits':options.model_dump(),'estimated_cost_usd':None,'provider_reported_usage':None,'billing':'NOT VERIFIED','budget_remaining_usd':options.budget_usd,'real_metrics':'NOT VERIFIED','blockers':['stage_b_user_approval_required','model_unverified','pricing_unverified','google_embedding_index_not_created'],'request_limits_ready':options.max_generation_calls>=planned_generation and options.max_embedding_calls>=planned_embedding_upper and options.max_total_requests>=planned_total,'data_to_send':'Only synthetic questions and permitted Northstar excerpts; no Gold labels or user documents.'}
 def start(self,scope,options):
  if scope.role not in ('admin','operator'):raise ServiceError(403,'permission_denied')
  if options.mode=='REAL_EXECUTION':raise ServiceError(403,'stage_b_user_approval_required')
  v=self.runtime(scope)
  if options.mode=='REAL_DRY_RUN':
   from .db import ValidationRun
   with v.sessions() as db:
    plan=self.readiness(scope,options);r=ValidationRun(tenant_id='workspace',user_id='owner',mode='REAL_DRY_RUN',dataset_id='gemini-live-smoke-v1',dataset_version=1,dataset_hash=plan['dataset']['corpus_hash'],provider='gemini',model=options.model or 'UNVERIFIED',status='completed',plan=plan,result={'verification':'DRY RUN','external_calls':0,'real_metrics':'NOT VERIFIED'},finished_at=now());db.add(r);db.commit();return self.read(scope,r.id)
  body=self.body(v,options)
  # Limits are passed as immutable per-run input, never mutable global adapter settings.
  body._smoke_limits={'total_requests':options.max_total_requests,'generation_calls':options.max_generation_calls,'embedding_calls':options.max_embedding_calls,'total_tokens':options.max_total_tokens,'cost_usd':0,'duration_seconds':options.duration_seconds,'generation_provider':'mock','generation_model':'mock-v1','embedding_provider':'mock','embedding_model':'mock-hash-ngram-v1'}
  run=v.start(Scope(),body);return self.read(scope,run["id"])
 def read(self,scope,identifier):
  v=self.runtime(scope);run=v.read(Scope(),identifier)
  with v.sessions() as db:
   cases=[serialize(c) for c in db.scalars(select(EvaluationCase).where(EvaluationCase.run_id==run['evaluation_id']))] if run['evaluation_id'] else []
   reviews=[r.body for r in db.scalars(select(LLMConfiguration).where(LLMConfiguration.kind=='smoke_review',LLMConfiguration.name==identifier).order_by(LLMConfiguration.updated_at))]
   traces=[serialize(r) for r in db.scalars(select(LLMExecution).where(LLMExecution.trace_id==identifier))]
  latencies=distribution([r['latency_ms'] for r in traces if r.get('latency_ms') is not None])
  comparison={'mock':run['result'] if run['mode']=='MOCK_ONLY' else None,'real':None,'real_status':'NOT VERIFIED','equivalence_claim':False}
  return {**run,'cases':cases,'human_reviews':reviews,'traces':traces,'real_metrics':'NOT VERIFIED','comparison':comparison,'latency':latencies,'error_rate':sum(r['status']=='failed' for r in traces)/len(traces) if traces else None}
 def review(self,scope,identifier,body):
  if scope.role not in ('admin','operator'):raise ServiceError(403,'permission_denied')
  run=self.read(scope,identifier)
  if run['status'] not in ('completed','failed','cancelled') or not any(c['case_id']==body.case_id for c in run['cases']):raise ServiceError(409,'review_case_unavailable')
  if any(s and s in body.notes for s in self.secrets) or re.search(r'AIza[\w-]{20,}|(?:api[_-]?key|password)\s*[:=]',body.notes,re.I):raise ServiceError(422,'dataset_secret_denied')
  v=self.runtime(scope);rid=uid();entry={**body.model_dump(),'id':rid,'reviewer':scope.user,'created_at':now(),'automated':False}
  with v.sessions() as db:db.add(LLMConfiguration(id='workspace:smoke_review:'+rid,tenant_id='workspace',kind='smoke_review',name=identifier,body=entry));db.commit()
  return entry
 async def close(self):
  for v,engine in self.runtimes.values():await v.close();await v.knowledge.close();await v.llm.close();engine.dispose()

def smoke_router(smoke):
 api=APIRouter(prefix='/api/validation/smoke',tags=['Gemini Live Validation'])
 def scope(request):return getattr(request.state,'llm_scope',Scope())
 @api.get('/status')
 def status(request:Request):return smoke.readiness(scope(request),SmokeInput())
 @api.post('/prepare')
 async def prepare(request:Request):return await smoke.prepare(scope(request))
 @api.post('/readiness')
 def readiness(body:SmokeInput,request:Request):return smoke.readiness(scope(request),body)
 @api.post('/runs',status_code=202)
 async def start(body:SmokeInput,request:Request):return smoke.start(scope(request),body)
 @api.get('/runs')
 def runs(request:Request):
  from .db import ValidationRun
  v=smoke.runtime(scope(request))
  with v.sessions() as db:ids=list(db.scalars(select(ValidationRun.id).order_by(ValidationRun.created_at.desc()).limit(50)))
  return {'items':[smoke.read(scope(request),i) for i in ids]}
 @api.get('/runs/{identifier}')
 def read(identifier:str,request:Request):return smoke.read(scope(request),identifier)
 @api.post('/runs/{identifier}/reviews',status_code=201)
 def review(identifier:str,body:ReviewInput,request:Request):return smoke.review(scope(request),identifier,body)
 @api.post('/runs/{identifier}/cancel')
 async def cancel(identifier:str,request:Request):
  s=scope(request)
  if s.role not in ('admin','operator'):raise ServiceError(403,'permission_denied')
  return await smoke.runtime(s).cancel(Scope(),identifier)
 @api.get('/runs/{identifier}/export')
 def export(identifier:str,request:Request):
  r=smoke.read(scope(request),identifier)
  return {k:r[k] for k in ('id','mode','model','provider','status','result','human_reviews','real_metrics')}
 return api
