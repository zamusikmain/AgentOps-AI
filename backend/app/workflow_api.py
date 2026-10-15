from fastapi import APIRouter, Query
from sqlalchemy import select, func
from .db import Workflow, WorkflowRun, WorkflowStep, WorkflowEvent, serialize
from .repository import Repository
from .services import required
from .workflow_schemas import WorkflowInput, WorkflowRunInput
from .workflow_execution import run_view, step_view

def workflow_router(sessions,service):
    router=APIRouter(prefix='/api',tags=['Workflows'])

    @router.get('/workflows')
    def workflows(offset:int=Query(0,ge=0),limit:int=Query(50,ge=1,le=100)):
        with sessions() as db:
            return Repository(db).page(Workflow,offset,limit)

    @router.get('/workflows/{identifier}')
    def workflow(identifier:str):
        with sessions() as db:
            return serialize(required(Repository(db),Workflow,identifier))

    @router.post('/workflows',status_code=201)
    def create(body:WorkflowInput):
        return service.save(body)

    @router.put('/workflows/{identifier}')
    def update(identifier:str,body:WorkflowInput):
        return service.save(body,identifier)

    @router.delete('/workflows/{identifier}',status_code=204)
    def delete(identifier:str):
        service.delete(identifier)

    @router.post('/workflows/{identifier}/run',status_code=202)
    async def launch(identifier:str,body:WorkflowRunInput):
        return await service.launch(identifier,body)

    @router.get('/workflow-runs')
    def runs(offset:int=Query(0,ge=0),limit:int=Query(50,ge=1,le=100),workflow_id:str|None=None):
        with sessions() as db:
            query=select(WorkflowRun)
            count=select(func.count()).select_from(WorkflowRun)
            if workflow_id:
                query=query.where(WorkflowRun.workflow_id==workflow_id)
                count=count.where(WorkflowRun.workflow_id==workflow_id)
            return {'items':[run_view(r) for r in db.scalars(query.order_by(WorkflowRun.created_at.desc()).offset(offset).limit(limit))],
                    'total':db.scalar(count),'offset':offset,'limit':limit}

    @router.get('/workflow-runs/{identifier}')
    def run(identifier:str):
        with sessions() as db:
            return run_view(required(Repository(db),WorkflowRun,identifier))

    @router.get('/workflow-runs/{identifier}/steps')
    def steps(identifier:str,offset:int=Query(0,ge=0),limit:int=Query(100,ge=1,le=100)):
        with sessions() as db:
            required(Repository(db),WorkflowRun,identifier)
            predicate=WorkflowStep.run_id==identifier
            return {'items':[step_view(r) for r in db.scalars(select(WorkflowStep).where(predicate).order_by(WorkflowStep.created_at,WorkflowStep.id).offset(offset).limit(limit))],
                    'total':Repository(db).count(WorkflowStep,predicate),'offset':offset,'limit':limit}

    @router.get('/workflow-runs/{identifier}/events')
    def events(identifier:str,offset:int=Query(0,ge=0),limit:int=Query(100,ge=1,le=100)):
        with sessions() as db:
            required(Repository(db),WorkflowRun,identifier)
            predicate=WorkflowEvent.run_id==identifier
            return {'items':[serialize(r) for r in db.scalars(select(WorkflowEvent).where(predicate).order_by(WorkflowEvent.id).offset(offset).limit(limit))],
                    'total':Repository(db).count(WorkflowEvent,predicate),'offset':offset,'limit':limit}

    @router.post('/workflow-runs/{identifier}/cancel')
    def cancel(identifier:str):
        return service.cancel(identifier)
    return router
