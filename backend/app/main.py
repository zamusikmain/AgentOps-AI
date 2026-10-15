import asyncio
import logging
import secrets
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Request, HTTPException, Query
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import select, func
from .config import Settings, ROOT
from .llm_reliability import Reliability, Scope
from .llm_api import router as llm_router
from .validation import Validation
from .validation_api import validation_router
from .authentication import Authentication,auth_router
from .live_smoke import Smoke,smoke_router
from .db import Base, Agent, Task, Execution, ExecutionEvent, WorkflowRun, database, serialize
from .workflow_execution import WorkflowRunner
from .workflow_service import WorkflowService
from .workflow_api import workflow_router
from .schemas import AgentInput, TaskInput
from .providers import GeminiProvider, MockProvider, ProviderError
from .execution import Runner
from .tools import CATALOG
from .tool_execution import ToolExecutor
from .tool_api import tool_router
from .knowledge_store import KnowledgeStore
from .knowledge_api import knowledge_router
from .evaluation import Evaluator
from .evaluation_api import evaluation_router
from .repository import Repository
from .services import WorkspaceService, ServiceError, required

logger = logging.getLogger('agentops')

def create_app(settings: Settings | None = None, provider=None,embedding_provider=None,workspace_routes=True) -> FastAPI:
    settings = settings or Settings()
    (ROOT / 'data').mkdir(exist_ok=True)
    engine, sessions = database(settings.database_url)
    token = settings.api_token.get_secret_value()
    if not token:
        path = ROOT / '.local-token'
        if not path.exists():
            path.write_text(secrets.token_urlsafe(32), encoding='utf-8')
        token = path.read_text(encoding='utf-8').strip()
    if settings.llm_provider not in ('gemini', 'mock'):
        raise ValueError('Invalid LLM_PROVIDER')
    provider = provider or (MockProvider() if settings.llm_provider == 'mock' else GeminiProvider(settings))
    llm=Reliability(sessions,settings,provider)
    provider=llm.bind()
    knowledge=KnowledgeStore(sessions,settings.knowledge_storage_path,settings,embedding_provider)
    if workspace_routes:
        from .unscoped_dispatch import UnscopedDispatch,UnscopedEmbedding
        llm.external_guard=UnscopedDispatch(settings,llm.adapter_for)
        if knowledge.vectors.provider.external:knowledge.vectors.provider=UnscopedEmbedding(knowledge.vectors.provider)
    evaluator=Evaluator(sessions,knowledge)
    evaluator.llm=llm
    validation=Validation(sessions,settings,llm,knowledge,evaluator)
    validation.secrets=(token,settings.gemini_api_key.get_secret_value())
    smoke=Smoke(settings,validation.secrets)
    authentication=Authentication(sessions,settings)
    from .ai_workspaces import Workspaces,workspace_router
    workspaces=Workspaces(sessions,settings) if workspace_routes else None
    tool_executor=ToolExecutor(sessions,settings)
    tool_executor.knowledge=knowledge
    tool_executor.secrets += (token,)
    runner = Runner(sessions, provider, settings)
    runner.tool_executor=tool_executor
    workflow_runner = WorkflowRunner(sessions,provider,settings,runner.lock)

    workflow_runner.tool_executor=tool_executor

    @asynccontextmanager
    async def lifespan(app):
        # Schema is created by Alembic before startup; no implicit production migrations.
        llm.seed()
        llm.recover()
        validation.seed()
        validation.recover()
        if workspaces:workspaces.smoke.recover()
        knowledge.recover()
        evaluator.recover()
        await tool_executor.start()
        tool_executor.recover()
        runner.recover()
        workflow_runner.recover()
        yield
        if workspaces:await workspaces.close()
        await smoke.close()
        await validation.close()
        await evaluator.close()
        await workflow_runner.close()
        await runner.close()
        await llm.close()
        await knowledge.close()
        await tool_executor.close()
        engine.dispose()

    app = FastAPI(title='AgentOps AI', version='1.2.0', lifespan=lifespan)
    app.state.workspaces=workspaces
    if workspaces:app.include_router(workspace_router(workspaces))
    app.state.sessions, app.state.runner, app.state.token = sessions, runner, token
    app.state.engine = engine
    app.state.authentication=authentication
    app.include_router(auth_router(authentication))
    app.state.llm=llm
    app.state.validation=validation
    app.state.smoke=smoke
    app.include_router(smoke_router(smoke))
    app.include_router(validation_router(validation))
    app.include_router(llm_router(llm))
    service = WorkspaceService(sessions, runner, settings)
    app.state.knowledge=knowledge
    app.state.evaluator=evaluator
    app.include_router(evaluation_router(evaluator,sessions))
    app.include_router(knowledge_router(sessions,knowledge,service,settings))
    service.knowledge=knowledge
    service.job_count=lambda:len(runner.jobs)+len(workflow_runner.jobs)
    workflow_service=WorkflowService(sessions,workflow_runner,settings,service.launch_lock,service.job_count)
    app.state.workflow_runner=workflow_runner
    app.state.tool_executor=tool_executor
    app.include_router(tool_router(sessions,tool_executor))
    app.include_router(workflow_router(sessions,workflow_service))

    @app.exception_handler(ServiceError)
    async def service_error(request, exc):
        return JSONResponse({'error': {'code': exc.code}}, status_code=exc.status)

    @app.middleware('http')
    async def protect(request: Request, call_next):
        public_paths={'/health','/api/auth/csrf','/api/auth/login','/api/auth/reset'}
        if request.url.path not in public_paths:
            supplied=request.headers.get('authorization','').removeprefix('Bearer ')
            if supplied and secrets.compare_digest(supplied,token):
                request.state.llm_scope=Scope();request.state.auth_method='bearer'
            elif supplied:
                principal=next((p for p in settings.llm_principals if secrets.compare_digest(supplied,str(p.get('token',''))) and supplied),None)
                if not principal or not request.url.path.startswith(('/api/llm/','/api/validation/','/api/users','/api/workspaces')):
                    return JSONResponse({'error':{'code':'unauthorized'}},status_code=401)
                request.state.llm_scope=Scope(str(principal['tenant']),str(principal['user']),str(principal.get('role','viewer')));request.state.auth_method='bearer'
            else:
                try:
                    user,session=authentication.authenticate(request)
                    if not user:return JSONResponse({'error':{'code':'unauthorized'}},status_code=401)
                    request.state.auth_user=user;request.state.auth_session=session;request.state.auth_method='session'
                    request.state.llm_scope=Scope(user.tenant_id,user.id,user.role)
                    if request.method not in ('GET','HEAD','OPTIONS'):authentication.csrf(request,session)
                    scoped=request.url.path.startswith(('/api/auth/','/api/users','/api/llm/','/api/validation/','/api/workspaces'))
                    if not scoped and user.tenant_id!='workspace':raise ServiceError(403,'permission_denied')
                    if not scoped and request.method not in ('GET','HEAD','OPTIONS') and user.role not in ('admin','operator'):raise ServiceError(403,'permission_denied')
                except ServiceError as error:return JSONResponse({'error':{'code':error.code}},status_code=error.status)
        response = await call_next(request)
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        # Never log body, query, prompt, response, or provider exception.
        logger.info('%s %s', request.method, response.status_code)
        return response

    @app.exception_handler(HTTPException)
    async def http_error(request, exc):
        return JSONResponse({'error': {'code': exc.detail}}, status_code=exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        return JSONResponse({'error': {'code': 'validation_error', 'fields': ['.'.join(map(str, e['loc'][1:])) for e in exc.errors()]}}, status_code=422)

    @app.exception_handler(Exception)
    async def unexpected_error(request, exc):
        return JSONResponse({'error': {'code': 'internal_error'}}, status_code=500)

    def get(db, cls, identifier):
        return required(Repository(db), cls, identifier)

    def page(db, cls, offset, limit):
        return Repository(db).page(cls, offset, limit)

    @app.get('/health')
    def health():
        with sessions() as db:
            db.execute(select(1))
        return {'status': 'ok'}

    @app.get('/api/agents')
    def agents(offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100)):
        with sessions() as db:
            return page(db, Agent, offset, limit)

    @app.get('/api/agents/{identifier}')
    def agent(identifier: str):
        with sessions() as db:
            return serialize(get(db, Agent, identifier))

    @app.post('/api/agents', status_code=201)
    def create_agent(body: AgentInput):
        return service.create_agent(body)

    @app.put('/api/agents/{identifier}')
    def update_agent(identifier: str, body: AgentInput):
        return service.update_agent(identifier, body)

    @app.delete('/api/agents/{identifier}', status_code=204)
    def delete_agent(identifier: str):
        service.delete_agent(identifier)

    @app.get('/api/tasks')
    def tasks(offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100)):
        with sessions() as db:
            return page(db, Task, offset, limit)

    @app.get('/api/tasks/{identifier}')
    def task(identifier: str):
        with sessions() as db:
            return serialize(get(db, Task, identifier))

    @app.post('/api/tasks', status_code=201)
    def create_task(body: TaskInput):
        return service.save_task(body)

    @app.put('/api/tasks/{identifier}')
    def update_task(identifier: str, body: TaskInput):
        return service.save_task(body, identifier)

    @app.delete('/api/tasks/{identifier}', status_code=204)
    def delete_task(identifier: str):
        service.delete_task(identifier)

    @app.post('/api/tasks/{identifier}/run', status_code=202)
    async def run_task(identifier: str):
        return await service.launch(identifier)

    @app.get('/api/executions')
    def executions(offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100), agent_id: str | None = None):
        with sessions() as db:
            query = select(Execution)
            count = select(func.count()).select_from(Execution)
            if agent_id:
                query = query.where(Execution.agent_id == agent_id)
                count = count.where(Execution.agent_id == agent_id)
            rows = db.scalars(query.order_by(Execution.created_at.desc()).offset(offset).limit(limit))
            return {'items': [{k: v for k, v in serialize(r).items() if k != 'snapshot'} for r in rows],
                    'total': db.scalar(count), 'offset': offset, 'limit': limit}

    @app.get('/api/executions/{identifier}')
    def execution(identifier: str):
        with sessions() as db:
            row = get(db, Execution, identifier)
            return {k: v for k, v in serialize(row).items() if k != 'snapshot'}

    @app.get('/api/executions/{identifier}/events')
    def events(identifier: str, offset: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=100)):
        with sessions() as db:
            get(db, Execution, identifier)
            predicate = ExecutionEvent.execution_id == identifier
            return {'items': [serialize(r) for r in db.scalars(select(ExecutionEvent).where(predicate).order_by(ExecutionEvent.id).offset(offset).limit(limit))],
                    'total': db.scalar(select(func.count()).select_from(ExecutionEvent).where(predicate)), 'offset': offset, 'limit': limit}

    @app.post('/api/executions/{identifier}/cancel')
    def cancel(identifier: str):
        return service.cancel(identifier)

    @app.get('/api/dashboard')
    def dashboard():
        with sessions() as db:
            counts = {cls.__tablename__: db.scalar(select(func.count()).select_from(cls)) for cls in (Agent, Task, Execution)}
            counts['completed'] = db.scalar(select(func.count()).select_from(Execution).where(Execution.status == 'completed'))
            counts['running'] = db.scalar(select(func.count()).select_from(Execution).where(Execution.status.in_(['queued', 'running'])))
            counts['tokens'] = db.scalar(select(func.coalesce(func.sum(Execution.input_tokens + Execution.output_tokens), 0)))
            counts['workflow_runs'] = db.scalar(select(func.count()).select_from(WorkflowRun))
            counts['executions'] += counts['workflow_runs']
            counts['completed'] += db.scalar(select(func.count()).select_from(WorkflowRun).where(WorkflowRun.status=='completed'))
            counts['running'] += db.scalar(select(func.count()).select_from(WorkflowRun).where(WorkflowRun.status.in_(['queued','running'])))
            counts['tokens'] += db.scalar(select(func.coalesce(func.sum(WorkflowRun.input_tokens+WorkflowRun.output_tokens),0)))
            return {'counts': counts, 'recent': [{k: v for k, v in serialize(r).items() if k != 'snapshot'} for r in db.scalars(select(Execution).order_by(Execution.created_at.desc()).limit(5))]}

    @app.get('/api/providers')
    def providers():
        return {'provider': settings.llm_provider, 'configured': bool(settings.gemini_api_key.get_secret_value()),
                'model': settings.gemini_model, 'timeout_seconds': settings.execution_timeout_seconds,
                'input_price_per_million': settings.input_price_per_million, 'output_price_per_million': settings.output_price_per_million}

    @app.get('/api/models')
    def models():
        return {'items': [settings.gemini_model], 'verified': False}

    @app.post('/api/models/discover')
    async def discover():
        if settings.llm_provider!='gemini':
            return {'items': [], 'verified': False}
        try:
            if not settings.external_api_enabled:
                raise HTTPException(403,'external_api_disabled')
            raise HTTPException(403,'model_discovery_requires_separate_permission')
        except ProviderError as exc:
            raise HTTPException(503, str(exc)) from None

    @app.get('/api/tools')
    def tools():
        return {'items': tool_executor.catalog()}

    original_openapi = app.openapi
    def secured_openapi():
        schema = original_openapi()
        schema.setdefault('components', {}).setdefault('securitySchemes', {})['LocalBearer'] = {'type': 'http', 'scheme': 'bearer'}
        for path, methods in schema['paths'].items():
            if path != '/health':
                for operation in methods.values():
                    if isinstance(operation, dict):
                        operation['security'] = [{'LocalBearer': []}]
        return schema
    app.openapi = secured_openapi

    return app

app = create_app()
