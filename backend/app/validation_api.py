"""Scoped validation/readiness and content-free exports."""
import json,csv,io
from fastapi import APIRouter,Request,Query
from fastapi.responses import Response
from pydantic import BaseModel,ConfigDict,Field
from sqlalchemy import select
from .llm_reliability import Scope
from .validation import ValidationInput,ApprovalInput
from .validation_datasets import DatasetInput
from .db import ValidationRun,EvaluationCase,EvaluationRun,serialize
from .services import ServiceError
class ComparisonInput(BaseModel):
 model_config=ConfigDict(extra='forbid')
 baseline_id:str=Field(max_length=36)
 current_id:str=Field(max_length=36)
def validation_router(validation):
 api=APIRouter(prefix='/api/validation',tags=['Real LLM Validation'])
 def scope(request,admin=False):
  s=getattr(request.state,'llm_scope',Scope())
  if admin and s.role!='admin':raise ServiceError(403,'permission_denied')
  return s
 @api.get('/datasets')
 def datasets(request:Request):return {'items':validation.datasets.list(scope(request).tenant)}
 @api.post('/datasets',status_code=201)
 def dataset(body:DatasetInput,request:Request):
  s=scope(request,True)
  if s.tenant!='workspace' and any(q.scope for q in body.questions):raise ServiceError(403,'dataset_permission_denied')
  return validation.datasets.save(s.tenant,body.model_dump())
 @api.post('/prepare/{source}',status_code=201)
 async def prepare(source:str,request:Request):
  s=scope(request,True)
  if s.tenant!='workspace':raise ServiceError(403,'dataset_permission_denied')
  if source not in ('v1','v2'):raise ServiceError(422,'validation_dataset_invalid')
  return await validation.evaluator.install(source)
 @api.post('/readiness')
 def readiness(body:ValidationInput,request:Request):return validation.plan(scope(request),body)
 @api.post('/approvals',status_code=201)
 def approve(body:ApprovalInput,request:Request):return validation.approve(scope(request,True),body)
 @api.post('/runs',status_code=202)
 async def start(body:ValidationInput,request:Request):return validation.start(scope(request),body)
 @api.get('/runs')
 def runs(request:Request,offset:int=Query(0,ge=0),limit:int=Query(50,ge=1,le=100)):
  s=scope(request)
  with validation.sessions() as db:rows=list(db.scalars(select(ValidationRun).where(ValidationRun.tenant_id==s.tenant).order_by(ValidationRun.created_at.desc()).offset(offset).limit(limit)))
  visible=[]
  for r in rows:
   try:visible.append(validation.read(s,r.id))
   except ServiceError:continue
  return {'items':visible,'offset':offset,'limit':limit}
 @api.get('/runs/{identifier}')
 def run(identifier:str,request:Request):return validation.read(scope(request),identifier)
 @api.post('/runs/{identifier}/cancel',status_code=202)
 async def cancel(identifier:str,request:Request):
  s=scope(request)
  if s.role not in ('admin','operator'):raise ServiceError(403,'permission_denied')
  return await validation.cancel(s,identifier)
 def safe_report(s,identifier):
  r=validation.read(s,identifier)
  # Dataset questions, Gold text, answers, document excerpts and request content omitted.
  return {'benchmark_id':r['id'],'dataset':r['plan']['dataset'],'provider':r['provider'],'model':r['model'],'mode':r['mode'],'status':r['status'],'verification':r['result'].get('verification','UNVERIFIED'),'quality':r['result'].get('quality',{}),'performance':r['result'].get('performance',{}),'cost':{'estimated_usd':r['result'].get('estimated_cost_usd'),'planned_upper_bound_usd':r['plan'].get('estimated_cost_usd'),'actual_billing':'UNVERIFIED'},'tokens':r['result'].get('tokens',{}),'failure_statistics':r['result'].get('failures',[]),'regression':r['result'].get('comparison',{}),'actual_requests':r['result'].get('actual_requests',0),'external_calls':r['result'].get('external_calls',0),'limitations':r['result'].get('limitations',[]),'created_at':r['created_at']}
 @api.get('/runs/{identifier}/export/{format}')
 def export(identifier:str,format:str,request:Request):
  report=safe_report(scope(request),identifier)
  if format=='json':body=json.dumps(report,ensure_ascii=False,indent=2);mime='application/json'
  elif format=='md':body='# Validation '+identifier+'\n\n'+ '\n\n'.join('## '+k+'\n\n```json\n'+json.dumps(v,ensure_ascii=False,indent=2)+'\n```' for k,v in report.items());mime='text/markdown'
  elif format=='csv':
   buffer=io.StringIO();writer=csv.writer(buffer);writer.writerow(['metric','value'])
   for k,v in report.items():
    value=json.dumps(v,ensure_ascii=False) if isinstance(v,(dict,list)) else str(v)
    if value.startswith(('=','+','-','@')):value="'"+value
    writer.writerow([k,value])
   body=buffer.getvalue();mime='text/csv'
  else:raise ServiceError(422,'export_format_invalid')
  return Response(body,media_type=mime,headers={'Content-Disposition':f'attachment; filename="benchmark-{identifier}.{format}"','Cache-Control':'no-store'})
 @api.post('/comparisons')
 def compare(body:ComparisonInput,request:Request):
  s=scope(request,True);b=validation.read(s,body.baseline_id);c=validation.read(s,body.current_id)
  if b['status']!='completed' or c['status']!='completed':raise ServiceError(409,'comparison_incompatible')
  comparable=b['dataset_hash']==c['dataset_hash'] and b['provider']==c['provider'] and b['model']==c['model'] and b['mode']==c['mode'] and b['plan']['retrieval_modes']==c['plan']['retrieval_modes']
  result={'comparable':comparable,'baseline_id':b['id'],'current_id':c['id'],'quality_delta':{},'regressed_questions':[],'passed':None,'limitations':['Mock and real are separate conditions; no equivalence or significance claim.']}
  if comparable:
   for mode,metrics in c['result'].get('quality',{}).items():
    old=b['result'].get('quality',{}).get(mode,{})
    result['quality_delta'][mode]={k:v-old[k] for k,v in metrics.items() if isinstance(v,(float,int)) and not isinstance(v,bool) and isinstance(old.get(k),(float,int))}
   with validation.sessions() as db:
    previous={(q.case_id,q.mode):q.result for q in db.scalars(select(EvaluationCase).where(EvaluationCase.run_id==b['evaluation_id']))};current=list(db.scalars(select(EvaluationCase).where(EvaluationCase.run_id==c['evaluation_id'])))
    for q in current:
     old=previous.get((q.case_id,q.mode))
     if old and old.get('answer_correct') and not q.result.get('answer_correct'):result['regressed_questions'].append({'question_id':q.case_id,'mode':q.mode,'reason':'correct_behavior_regressed'})
   result['passed']=not result['regressed_questions'] and all(v.get('answer_correct',0)>=0 and v.get('correct_abstention_rate',0)>=0 and v.get('false_abstention_rate',0)<=0 and v.get('unsupported_answer_rate',0)<=0 and v.get('citation_validity_rate',0)>=0 for v in result['quality_delta'].values())
  result['resources']={'baseline':b['result'].get('performance',{}),'current':c['result'].get('performance',{}),'baseline_cost':b['result'].get('estimated_cost_usd'),'current_cost':c['result'].get('estimated_cost_usd')}
  with validation.sessions() as db:r=db.get(ValidationRun,c['id']);r.result={**r.result,'comparison':result};db.commit()
  return result
 return api
