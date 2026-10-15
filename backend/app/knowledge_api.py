from fastapi import APIRouter,Request,Query
from typing import Literal
from pydantic import BaseModel,Field,ConfigDict
from sqlalchemy import select
from .db import KnowledgeDocument,KnowledgeChunk,Agent,Task,Execution,serialize
from .services import required,ServiceError
from .repository import Repository
from .knowledge_store import MAX_UPLOAD
class QueryInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    agent_id:str=Field(min_length=1,max_length=36)
    question:str=Field(min_length=2,max_length=200)
    document_ids:list[str]|None=Field(default=None,max_length=50)
    provider: str|None=None
    search_mode:Literal['lexical','semantic','hybrid']='hybrid'
    rerank:bool=True
class ReindexInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    external_consent:bool=False

def knowledge_router(sessions,store,service,settings):
    router=APIRouter(prefix='/api/knowledge',tags=['Knowledge'])
    def agent_scope(db,body):
        agent=required(Repository(db),Agent,body.agent_id)
        if agent.status!='active':raise ServiceError(409,'agent_disabled')
        if 'knowledge_search' not in agent.tools:raise ServiceError(403,'tool_denied')
        selected=agent.document_ids if body.document_ids is None else body.document_ids
        if not selected or any(i not in agent.document_ids for i in selected):raise ServiceError(403,'document_denied')
        store.validate_scope(selected)
        return agent,selected
    @router.get('/documents')
    def documents(offset:int=Query(0,ge=0),limit:int=Query(50,ge=1,le=100)):
        with sessions() as db:return Repository(db).page(KnowledgeDocument,offset,limit)
    @router.get('/runs')
    def runs(offset:int=Query(0,ge=0),limit:int=Query(50,ge=1,le=100)):
        with sessions() as db:
            predicate=Execution.snapshot['rag'].as_boolean()==True
            rows=db.execute(select(Execution,Task.title).join(Task,Execution.task_id==Task.id).where(predicate).order_by(Execution.created_at.desc()).offset(offset).limit(limit))
            return {'items':[{**{k:v for k,v in serialize(e).items() if k!='snapshot'},'task_title':title} for e,title in rows],'total':Repository(db).count(Execution,predicate),'offset':offset,'limit':limit}
    @router.post('/documents',status_code=202)
    async def upload(request:Request,name:str=Query(...,min_length=1,max_length=200)):
        content=bytearray()
        async for piece in request.stream():
            content.extend(piece)
            if len(content)>MAX_UPLOAD:raise ServiceError(413,'pdf_too_large')
        return store.create(name,bytes(content))
    @router.get('/documents/{identifier}')
    def document(identifier:str):
        with sessions() as db:return serialize(required(Repository(db),KnowledgeDocument,identifier))
    @router.get('/documents/{identifier}/chunks')
    def chunks(identifier:str,offset:int=Query(0,ge=0),limit:int=Query(50,ge=1,le=100)):
        with sessions() as db:
            required(Repository(db),KnowledgeDocument,identifier)
            predicate=KnowledgeChunk.document_id==identifier
            return {'items':[{k:v for k,v in serialize(c).items() if k!='terms'} for c in db.scalars(select(KnowledgeChunk).where(predicate).order_by(KnowledgeChunk.page,KnowledgeChunk.ordinal).offset(offset).limit(limit))],'total':Repository(db).count(KnowledgeChunk,predicate),'offset':offset,'limit':limit}
    @router.delete('/documents/{identifier}',status_code=204)
    async def remove(identifier:str):await store.remove(identifier)
    @router.get('/documents/{identifier}/embedding-plan')
    def plan(identifier:str):
        store.validate_scope([identifier]);return store.vectors.plan(identifier)
    @router.post('/documents/{identifier}/reindex',status_code=202)
    async def reindex(identifier:str,body:ReindexInput):
        return store.reindex(identifier,body.external_consent)
    @router.post('/search')
    async def search(body:QueryInput):
        import asyncio
        with sessions() as db:
            _,scope=agent_scope(db,body)
        try:return await asyncio.wait_for(asyncio.to_thread(store.search,body.question,scope,None,5,body.search_mode,body.rerank),store.vectors.settings.embedding_timeout_seconds+5)
        except ValueError as exc:raise ServiceError(409,str(exc)) from None
        except TimeoutError:raise ServiceError(504,'embedding_timeout') from None
    @router.post('/ask',status_code=202)
    async def ask(body:QueryInput):
        if body.provider not in (None,'mock'):raise ServiceError(422,'invalid_provider')
        if body.provider=='mock' and store.vectors.provider.external:raise ServiceError(403,'evaluation_offline_only')
        async with service.launch_lock:
            with sessions() as db:
                repo=Repository(db);agent,scope=agent_scope(db,body)
                if service.job_count()>=10:raise ServiceError(429,'queue_full')
                if body.provider!='mock' and settings.llm_provider=='gemini' and not settings.gemini_api_key.get_secret_value():raise ServiceError(503,'missing_api_key')
                task=Task(title='RAG: '+body.question[:195],prompt=body.question.strip(),agent_id=agent.id,status='running');db.add(task);db.flush()
                snapshot={**serialize(agent),'prompt':task.prompt,'document_ids':scope,'document_versions':{i:db.get(KnowledgeDocument,i).sha256 for i in scope},'rag':True,'rag_provider':'mock' if body.provider=='mock' else settings.llm_provider,'search_mode':body.search_mode,'rerank':body.rerank,'max_steps':1,'max_tokens':min(agent.max_tokens,2048)}
                execution=Execution(task_id=task.id,agent_id=agent.id,snapshot=snapshot);db.add(execution);db.commit();service.runner.start(execution.id)
                return {k:v for k,v in serialize(execution).items() if k!='snapshot'}
    return router
