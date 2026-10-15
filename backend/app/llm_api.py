"""Tenant-scoped diagnostics; legacy workspace routes remain owner-only."""
import hashlib,json, re
from typing import Literal
from fastapi import APIRouter,Request,HTTPException,Query
from pydantic import BaseModel,ConfigDict,Field,model_validator
from sqlalchemy import select
from .db import LLMExecution,LLMConfiguration,PromptVersion,EvaluationRun,EvaluationCase,EvaluationComparison,BudgetReservation,serialize,now
from .llm_reliability import Scope

class Policy(BaseModel):
    model_config=ConfigDict(extra='forbid')
    timeout_seconds:int=Field(default=60,ge=1,le=120)
    max_attempts:int=Field(default=1,ge=1,le=3)
    backoff_seconds:float=Field(default=.2,ge=0,le=2)
    breaker_threshold:int=Field(default=3,ge=1,le=10)
    breaker_cooldown_seconds:int=Field(default=30,ge=1,le=300)
    fallback_enabled:bool=False
    fallback_provider:Literal['mock','gemini']|None=None
    fallback_model:str|None=Field(default=None,max_length=120)
    @model_validator(mode='after')
    def fallback(self):
        if self.fallback_enabled and (not self.fallback_provider or not self.fallback_model):raise ValueError('explicit fallback target required')
        return self
    requests_per_minute:int=Field(default=60,ge=1,le=120)
class Budget(BaseModel):
    model_config=ConfigDict(extra='forbid')
    request_usd:float|None=Field(default=None,ge=0,le=100,allow_inf_nan=False)
    day_usd:float|None=Field(default=None,ge=0,le=1000,allow_inf_nan=False)
    month_usd:float|None=Field(default=None,ge=0,le=10000,allow_inf_nan=False)
    provider_usd:dict[str,float]=Field(default_factory=dict)
    model_usd:dict[str,float]=Field(default_factory=dict)
class ModelEntry(BaseModel):
    model_config=ConfigDict(extra='forbid')
    provider:Literal['mock','gemini']
    model:str=Field(pattern=r'^[a-zA-Z0-9._/-]{1,120}$')
    display_name:str=Field(min_length=1,max_length=120)
    availability:Literal['available','unavailable','unverified']='unverified'
    compatible:bool=False
    capabilities:list[Literal['structured','tools']]=Field(default_factory=list)
    context_limit:int|None=Field(default=None,ge=1)
    output_limit:int|None=Field(default=None,ge=1,le=16384)
    streaming:Literal[False]=False
    pricing_version:str|None=Field(default=None,max_length=80)
    input_rate:float|None=Field(default=None,ge=0,allow_inf_nan=False)
    output_rate:float|None=Field(default=None,ge=0,allow_inf_nan=False)
    last_verified:str|None=Field(default=None,max_length=80)
class Prompt(BaseModel):
    model_config=ConfigDict(extra='forbid')
    prompt_id:str=Field(pattern=r'^[a-z][a-z0-9_-]{0,60}$')
    version:int=Field(ge=1,le=10000)
    template:str=Field(min_length=1,max_length=16000)
    purpose:str=Field(max_length=100)
    change_description:str=Field(max_length=1000)

def router(layer):
    api=APIRouter(prefix='/api/llm')
    def scope(request,write=False):
        s=getattr(request.state,'llm_scope',Scope())
        if write and s.role!='admin':raise HTTPException(403,'permission_denied')
        return s
    @api.get('/requests')
    def requests(request:Request,provider:str|None=None,model:str|None=None,operation:str|None=None,status:str|None=None,error_category:str|None=None,since:str|None=None,until:str|None=None,limit:int=Query(50,ge=1,le=200)):
        s=scope(request);q=select(LLMExecution).where(LLMExecution.tenant_id==s.tenant)
        if s.role!='admin':q=q.where(LLMExecution.user_id==s.user)
        for key,value in [('provider',provider),('model',model),('operation',operation),('status',status),('error_category',error_category)]:
            if value:q=q.where(getattr(LLMExecution,key)==value)
        if since:q=q.where(LLMExecution.created_at>=since)
        if until:q=q.where(LLMExecution.created_at<=until)
        with layer.sessions() as db:return {'items':[serialize(r) for r in db.scalars(q.order_by(LLMExecution.created_at.desc()).limit(limit))]}
    @api.get('/requests/{identifier}')
    def detail(identifier:str,request:Request):
        with layer.sessions() as db:
            r=db.get(LLMExecution,identifier)
            if not r or r.tenant_id!=scope(request).tenant:raise HTTPException(404,'not_found')
            if r.user_id!=scope(request).user and scope(request).role!='admin':raise HTTPException(404,'not_found')
            result=serialize(r)
            if r.operation=='evaluation' and scope(request).tenant=='workspace':
                run=db.get(EvaluationRun,r.trace_id)
                result['evaluation_status']=run.status if run else 'unavailable'
            return result
    @api.get('/summary')
    def summary(request:Request):
        s=scope(request);query=select(LLMExecution).where(LLMExecution.tenant_id==s.tenant)
        if s.role!='admin':query=query.where(LLMExecution.user_id==s.user)
        with layer.sessions() as db:rows=list(db.scalars(query))
        latencies=sorted(r.latency_ms for r in rows if r.latency_ms is not None);groups={}
        for r in rows:
            key=f'{r.created_at[:10]}|{r.provider}|{r.model}|{r.operation}';g=groups.setdefault(key,{'requests':0,'tokens':0,'cost_usd':0,'unknown_cost':0});g['requests']+=1;g['tokens']+=r.usage.get('total_tokens',0);g['unknown_cost']+=r.estimated_cost_usd is None;g['cost_usd']+=r.estimated_cost_usd or 0
        with layer.sessions() as db:
            reservations=list(db.scalars(select(BudgetReservation).where(BudgetReservation.tenant_id==scope(request).tenant)))
            comparisons=list(db.scalars(select(EvaluationComparison).where(EvaluationComparison.tenant_id==scope(request).tenant)))
        monthly={}
        for row in rows:
            key=row.created_at[:7];monthly[key]=monthly.get(key,0)+(row.estimated_cost_usd or 0)
        return {'monthly_known_cost_usd':monthly,'reserved_or_uncertain_usd':sum(r.reserved_usd for r in reservations if r.status in ('reserved','uncertain')),'evaluation_regressions':sum(not c.result.get('passed',False) for c in comparisons),'fallback_count':sum(r.fallback_count for r in rows if not r.metadata_json.get('fallback_from_request_id')),'requests':len(rows),'success':sum(r.status=='success' for r in rows),'errors':sum(r.status=='failed' for r in rows),'tokens':sum(r.usage.get('total_tokens',0) for r in rows),'unknown_usage':sum(not r.usage or r.usage.get('source')=='unknown' for r in rows),'estimated_usage':sum(r.usage.get('source')=='estimated' for r in rows),'known_cost_usd':sum(r.estimated_cost_usd or 0 for r in rows),'unknown_cost':sum(r.estimated_cost_usd is None for r in rows),'retry_count':sum(r.retry_count for r in rows),'p95_ms':latencies[min(len(latencies)-1,int(len(latencies)*.95))] if latencies else None,'groups':groups}
    @api.get('/configuration')
    def configuration(request:Request):
        with layer.sessions() as db:rows=list(db.scalars(select(LLMConfiguration).where(LLMConfiguration.tenant_id==scope(request).tenant,LLMConfiguration.kind.in_(['model','policy','budget','pricing','circuit']))))
        return {'items':[serialize(r) for r in rows],'external_api_enabled':layer.settings.external_api_enabled,'paid_operations_enabled':layer.settings.paid_operations_enabled,'fallback_enabled':layer.configuration('policy','execution',{}).get('fallback_enabled',False),'environment':layer.settings.environment_id,'concurrency':layer.settings.llm_concurrency}
    def update(request,kind,name,body):
        s=scope(request,True)
        if kind=='budget' and any(v<0 or not __import__('math').isfinite(v) for k in ('provider_usd','model_usd') for v in body.get(k,{}).values()):raise HTTPException(422,'validation_error')
        with layer.sessions() as db:
            key=f'{s.tenant}:{kind}:{name}';r=db.get(LLMConfiguration,key)
            if kind=='model' and body.get('pricing_version'):
                price={'provider':body['provider'],'model':body['model'],'version':body['pricing_version'],'input_rate':body.get('input_rate'),'output_rate':body.get('output_rate')}
                price_name=hashlib.sha256(json.dumps([body['provider'],body['model'],body['pricing_version']]).encode()).hexdigest()
                price_key=f'{s.tenant}:pricing:{price_name}';previous=db.get(LLMConfiguration,price_key)
                if previous and previous.body!=price:raise HTTPException(409,'pricing_version_immutable')
                if not previous:db.add(LLMConfiguration(id=price_key,tenant_id=s.tenant,kind='pricing',name=price_name,body=price))
            if not r:r=LLMConfiguration(id=key,tenant_id=s.tenant,kind=kind,name=name,body=body);db.add(r)
            else:r.body=body;r.version+=1;r.updated_at=now()
            db.commit();return serialize(r)
    @api.put('/models')
    def model(body:ModelEntry,request:Request):
        if body.compatible and (body.availability!='available' or not body.last_verified):raise HTTPException(422,'model_verification_required')
        return update(request,'model',body.model,body.model_dump())
    @api.put('/policy')
    def policy(body:Policy,request:Request):return update(request,'policy','execution',body.model_dump())
    @api.put('/budget')
    def budget(body:Budget,request:Request):return update(request,'budget','limits',body.model_dump())
    @api.get('/prompts')
    def prompts(request:Request):
        with layer.sessions() as db:return {'items':[serialize(r) for r in db.scalars(select(PromptVersion).where(PromptVersion.tenant_id==scope(request).tenant))]}
    @api.post('/prompts',status_code=201)
    def prompt(body:Prompt,request:Request):
        s=scope(request,True);data=body.model_dump();key=f'{s.tenant}:{body.prompt_id}:{body.version}'
        if re.search(r'(AIza[\w-]{20,}|(?:api[_-]?key|secret|password)\s*[:=])',json.dumps(data),re.I):raise HTTPException(422,'secret_in_template')
        with layer.sessions() as db:
            if db.get(PromptVersion,key):raise HTTPException(409,'prompt_version_immutable')
            r=PromptVersion(id=key,tenant_id=s.tenant,prompt_id=body.prompt_id,version=body.version,body=data,digest=hashlib.sha256(json.dumps(data,sort_keys=True).encode()).hexdigest(),status='draft');db.add(r);db.commit();return serialize(r)
    @api.put('/prompts/{prompt_id}/{version}/{status}')
    def prompt_status(prompt_id:str,version:int,status:Literal['draft','active','archived'],request:Request):
        t=scope(request,True).tenant
        with layer.sessions() as db:
            r=db.get(PromptVersion,f'{t}:{prompt_id}:{version}')
            if not r:raise HTTPException(404,'not_found')
            if status=='active':
                for previous in db.scalars(select(PromptVersion).where(PromptVersion.tenant_id==t,PromptVersion.prompt_id==prompt_id,PromptVersion.status=='active')):previous.status='archived'
            r.status=status;db.commit();return serialize(r)
    @api.post('/comparisons')
    async def compare(request:Request):
        t=scope(request,True).tenant
        # Legacy evaluation data belongs only to the workspace owner.
        if t!='workspace':raise HTTPException(403,'permission_denied')
        body=await request.json()
        if set(body)!={'baseline_id','current_id'}:raise HTTPException(422,'validation_error')
        with layer.sessions() as db:
            baseline=db.get(EvaluationRun,body['baseline_id']);current=db.get(EvaluationRun,body['current_id'])
            if not baseline or not current:raise HTTPException(404,'not_found')
            if baseline.status!='completed' or current.status!='completed' or baseline.dataset_version!=current.dataset_version:raise HTTPException(409,'comparison_incompatible')
            if baseline.provider_metadata.get('generation')!=current.provider_metadata.get('generation'):raise HTTPException(409,'comparison_incompatible')
            result={'dataset_version':current.dataset_version,'provider':current.provider_metadata.get('generation'),'small_sample_warning':True,'legacy_metadata_warning':not baseline.provider_metadata.get('prompt_version'),'modes':{}}
            passed=True
            for mode,metrics in current.metrics.items():
                old=baseline.metrics.get(mode,{})
                if not isinstance(metrics,dict) or not isinstance(old,dict):continue
                delta={k:metrics[k]-old[k] for k in metrics if isinstance(metrics[k],(int,float)) and not isinstance(metrics[k],bool) and isinstance(old.get(k),(int,float))}
                for k,v in metrics.get('retrieval',{}).items():
                    if isinstance(v,(int,float)) and isinstance(old.get('retrieval',{}).get(k),(int,float)):delta['retrieval.'+k]=v-old['retrieval'][k]
                failures=[k for k in ('answer_correct','correct_abstention_rate','citation_validity_rate','retrieval.hit_at_1','retrieval.hit_at_5') if delta.get(k,0)<-1e-9]+[k for k in ('false_abstention_rate','unsupported_answer_rate','unsupported_claims') if delta.get(k,0)>1e-9]
                passed=passed and not failures;result['modes'][mode]={'delta':delta,'regressions':failures}
            prior={(r.case_id,r.mode):r.result for r in db.scalars(select(EvaluationCase).where(EvaluationCase.run_id==baseline.id))}
            result['regressed_questions']=[]
            for r in db.scalars(select(EvaluationCase).where(EvaluationCase.run_id==current.id)):
                old=prior.get((r.case_id,r.mode));value=r.result
                if not old:continue
                reasons=[]
                if old.get('answer_correct') and not value.get('answer_correct'):reasons.append('correct_behavior_regressed')
                if not old.get('verification',{}).get('abstained') and value.get('verification',{}).get('abstained') and value.get('expected_behavior')!='abstain':reasons.append('false_abstention')
                for metric in ('hit_at_1','hit_at_5'):
                    if old.get('retrieval_metrics',{}).get(metric)==1 and value.get('retrieval_metrics',{}).get(metric)==0:reasons.append('retrieval_'+metric+'_regressed')
                if reasons:result['regressed_questions'].append({'question_id':r.case_id,'mode':r.mode,'reasons':reasons})
            result['resource_delta']={'duration_ms':(current.duration_ms or 0)-(baseline.duration_ms or 0),'input_tokens':current.provider_metadata.get('input_tokens',0)-baseline.provider_metadata.get('input_tokens',0),'output_tokens':current.provider_metadata.get('output_tokens',0)-baseline.provider_metadata.get('output_tokens',0),'cost_usd':0 if current.provider_metadata.get('generation')=='mock' else None}
            result['thresholds']={'quality_allowed_regression':0,'resource_limits':'informational; live and load thresholds not calibrated'}
            result['baseline_metadata']=baseline.provider_metadata
            result['current_metadata']=current.provider_metadata
            result['passed']=passed
            row=EvaluationComparison(tenant_id=t,baseline_id=baseline.id,current_id=current.id,result=result);db.add(row);db.commit();return serialize(row)
    @api.get('/comparisons')
    def comparisons(request:Request):
        with layer.sessions() as db:return {'items':[serialize(r) for r in db.scalars(select(EvaluationComparison).where(EvaluationComparison.tenant_id==scope(request).tenant).order_by(EvaluationComparison.created_at.desc()).limit(50))]}
    return api
