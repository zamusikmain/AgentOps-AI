from fastapi import APIRouter,Query
from pydantic import BaseModel,ConfigDict,Field
from typing import Literal
from sqlalchemy import select
from .db import EvaluationRun,EvaluationCase,serialize
from .services import ServiceError
from .evaluation import dataset
class EvaluationInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    agent_id:str=Field(min_length=1,max_length=36)
    provider:Literal['mock','live']='mock'
    external_document_consent:bool=False
    dataset_version:Literal['v1','v2']='v1'
def evaluation_router(evaluator,sessions):
    router=APIRouter(prefix='/api/evaluation',tags=['RAG Evaluation'])
    @router.get('/dataset')
    def info():
        data,version=dataset();return {'name':data['name'],'version':version,'cases':len(data['cases']),'categories':{key:sum(c['category']==key for c in data['cases']) for key in ('exact','paraphrased','multi-hop','unanswerable','conflicting','adversarial')},'offline_only':True}
    @router.post('/install',status_code=201)
    async def install(version:Literal['v1','v2']='v1'):return await evaluator.install(version)
    @router.post('/runs',status_code=202)
    async def start(body:EvaluationInput):
        if body.provider!='mock':raise ServiceError(403,'evaluation_live_disabled')
        return evaluator.start(body.agent_id,body.dataset_version)
    @router.get('/runs')
    def runs(offset:int=Query(0,ge=0),limit:int=Query(50,ge=1,le=100)):
        # History never exposes results from an agent whose current document scope was revoked.
        visible=[]
        with sessions() as db:
            for r in db.scalars(select(EvaluationRun).order_by(EvaluationRun.created_at.desc())):
                try:evaluator.scope(r)
                except ServiceError:continue
                visible.append(serialize(r))
        return {'items':visible[offset:offset+limit],'total':len(visible),'offset':offset,'limit':limit}
    @router.get('/runs/{identifier}')
    def run(identifier:str):return evaluator.read(identifier)
    @router.get('/runs/{identifier}/cases')
    def cases(identifier:str,offset:int=Query(0,ge=0),limit:int=Query(20,ge=1,le=50),error:Literal['all','false_abstention','unsupported','conflicting','partial','repaired']='all'):
        evaluator.read(identifier)
        with sessions() as db:
            from sqlalchemy import func
            where=EvaluationCase.run_id==identifier
            value=EvaluationCase.result
            if error=='false_abstention':where=where & (value['expected_behavior'].as_string()!='abstain') & (value['verification']['abstained'].as_boolean()==True)
            elif error=='unsupported':where=where & (value['verification']['status'].as_string()=='unsupported')
            elif error=='conflicting':where=where & (value['verification']['status'].as_string()=='conflicting_evidence')
            elif error=='partial':where=where & (value['verification']['status'].as_string()=='partial')
            elif error=='repaired':where=where & (func.json_array_length(value['verification']['repair_attempts'])>0)
            return {'items':[serialize(c) for c in db.scalars(select(EvaluationCase).where(where).order_by(EvaluationCase.case_id,EvaluationCase.mode).offset(offset).limit(limit))],'total':db.scalar(select(func.count()).select_from(EvaluationCase).where(where)),'offset':offset,'limit':limit}
    @router.post('/runs/{identifier}/cancel',status_code=202)
    async def cancel(identifier:str):
        evaluator.read(identifier);job=evaluator.jobs.get(identifier)
        if not job:raise ServiceError(409,'execution_finished')
        job.cancel();await __import__('asyncio').gather(job,return_exceptions=True)
        with sessions() as db:
            r=db.get(EvaluationRun,identifier)
            if r.status in ('queued','running'):
                from .db import now
                r.status='cancelled';r.error='evaluation_cancelled';r.finished_at=now();db.commit()
        return evaluator.read(identifier)
    @router.get('/live-preflight')
    def live_plan():return {'enabled':False,'reason':'evaluation_live_disabled','generation_model':'gemini-3.5-flash-lite','embedding_model':'gemini-embedding-2','maximum_generation_calls':120,'maximum_query_embedding_calls':120,'max_output_tokens_per_answer':2048,'maximum_output_tokens':245760,'estimated_cost':None,'paid_calls_allowed':False,'document_consent_required':True,'data_sent_if_authorized':'Questions and permitted extracted PDF passages. No secrets or filesystem paths.','requirements':['Separate explicit user approval','Project Free Tier and model availability check','New smaller call and token budget agreed before launch','Separate document transfer consent']}
    return router
