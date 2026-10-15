"""Owner-scoped offline workspaces. No external transport is enabled by this module."""
import asyncio, hashlib, json, secrets, re
from pathlib import Path
from contextlib import AsyncExitStack
import httpx
from fastapi import APIRouter, Request, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select, text
from .db import Base, LLMConfiguration, KnowledgeDocument, uid, now
from .services import ServiceError
from .embeddings import signature, GoogleEmbeddingProvider, EmbeddingError

class WorkspaceInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    name: str = Field(min_length=1,max_length=80)

class Workspaces:
    def __init__(self, sessions, settings):
        self.sessions,self.settings=sessions,settings
        self.root=Path(settings.knowledge_storage_path).parent/'ai-workspaces-v11'
        self.apps={};self.lock=asyncio.Lock();self.stack=AsyncExitStack()
        self.adapter_factory=None # In-process test injection only; no API/configuration switch.
        from .workspace_live import WorkspaceLive
        self.live=WorkspaceLive(self)
        from .workspace_smoke import WorkspaceSmoke
        self.smoke=WorkspaceSmoke(self)

    def rows(self,scope):
        with self.sessions() as db:
            rows=db.scalars(select(LLMConfiguration).where(LLMConfiguration.tenant_id==scope.tenant,LLMConfiguration.kind=='ai_workspace'))
            return [dict(r.body) for r in rows if r.body['owner_id']==scope.user]

    def get(self,scope,identifier):
        row=next((r for r in self.rows(scope) if r['id']==identifier),None)
        if not row:raise ServiceError(404,'workspace_not_found')
        return row

    def create(self,scope,body):
        if scope.role not in ('admin','operator'):raise ServiceError(403,'permission_denied')
        if re.search(r'AIza[\w-]{20,}|(?:api[_-]?key|password)\s*[:=]',body.name,re.I):raise ServiceError(422,'workspace_name_invalid')
        identifier=uid();row={'id':identifier,'name':body.name.strip(),'owner_id':scope.user,'tenant_id':scope.tenant,'created_at':now(),'mode':'OFFLINE_E2E','live_enabled':False}
        if not row['name']:raise ServiceError(422,'workspace_name_invalid')
        with self.sessions() as db:
            db.execute(text('BEGIN IMMEDIATE'))
            if len(self.rows(scope))>=10:raise ServiceError(409,'workspace_limit')
            db.add(LLMConfiguration(id=f'{scope.tenant}:ai_workspace:{identifier}',tenant_id=scope.tenant,kind='ai_workspace',name=identifier,body=row));db.commit()
        return row

    async def runtime(self,scope,identifier):
        self.get(scope,identifier)
        key=hashlib.sha256(json.dumps([scope.tenant,scope.user,identifier]).encode()).hexdigest()
        async with self.lock:
            if key not in self.apps:
                from .main import create_app
                directory=self.root/key;directory.mkdir(parents=True,exist_ok=True)
                # Independent future Google namespace: directory only, no API/index creation.
                (directory/'google-index-unverified').mkdir(exist_ok=True)
                settings=self.settings.model_copy(update={'database_url':f'sqlite:///{(directory/"offline.db").as_posix()}',
                    'checkpoint_database_path':directory/'checkpoints.db','knowledge_storage_path':directory/'documents',
                    'api_token':secrets.token_urlsafe(32),'gemini_api_key':'','llm_provider':'mock','embedding_provider':'mock',
                    'input_price_per_million':0,'output_price_per_million':0,
                    'embedding_revision':'AIWorkspace-v11-offline','external_api_enabled':False,'embedding_external_enabled':False,
                    'real_validation_enabled':False,'paid_operations_enabled':False,'allowed_external_providers':[],
                    'allowed_external_operations':[],'allowed_fallback_models':[],'fallback_data_allowed':False,
                    'mock_degradation_allowed':False,'llm_principals':[],'local_mcp_enabled':False})
                # model_copy preserves SecretStr types only when typed values are supplied.
                from pydantic import SecretStr
                settings.api_token=SecretStr(settings.api_token);settings.gemini_api_key=SecretStr('')
                app=create_app(settings,provider=self.adapter_factory() if self.adapter_factory else None,workspace_routes=False)
                Base.metadata.create_all(app.state.engine) # New independent database only.
                await self.stack.enter_async_context(app.router.lifespan_context(app))
                self.apps[key]=app
            return self.apps[key]

    async def readiness(self,scope,identifier):
        app=await self.runtime(scope,identifier)
        store=app.state.knowledge
        with store.sessions() as db:documents=list(db.scalars(select(KnowledgeDocument)))
        settings=self.settings
        try:google_signature=signature(GoogleEmbeddingProvider(settings))
        except EmbeddingError:google_signature=None
        checks={
            'user_authorization':'READY','tenant_workspace_access':'READY',
            'api_key_availability':'READY' if settings.gemini_api_key.get_secret_value() else 'BLOCKED',
            'provider_configuration':'BLOCKED','model_compatibility':'UNVERIFIED','embedding_compatibility':'UNVERIFIED',
            'dataset_availability':'READY' if any(d.status=='ready' and d.embedding_status=='ready' for d in documents) else 'BLOCKED',
            'budget_limits':'BLOCKED','request_limits':'READY','token_limits':'READY','retry_limits':'READY',
            'data_transmission_permission':'BLOCKED','live_user_approval':'BLOCKED','logging_redaction':'READY',
            'pricing':'UNVERIFIED','google_index':'UNVERIFIED'}
        return {'status':'BLOCKED','mode':'OFFLINE_E2E','live_status':'UNVERIFIED','live_enabled':False,
            'model':settings.gemini_model,'embedding_model':settings.embedding_model,'checks':checks,
            'offline_index_signature':signature(store.vectors.provider),'future_google_signature':google_signature,
            'index_namespaces_separate':True,'external_calls':0,'fallback_enabled':False,
            'plan':{'documents':3,'questions':6,'index_embedding_calls_upper':3,'query_embedding_calls_upper':18,
                'generation_calls_upper':6,'retries':0,'verification_calls':0,'repair_calls':0,
                'total_calls_upper':27,'max_output_tokens_per_call':512,'max_total_tokens':150000,
                'timeout_seconds':120,'estimated_cost_usd':None,'cost_status':'UNVERIFIED'},
            'blockers':['live_user_approval_required','data_transmission_permission_required','pricing_unverified','model_unverified','google_index_not_built']}

    async def forward(self,scope,identifier,path,request):
        self.get(scope,identifier)
        # Fixed local routes only. No arbitrary URLs, auth routes, API-key/provider discovery or smoke recursion.
        allowed=re.fullmatch(r'(?:agents(?:/[a-zA-Z0-9_-]+)?|knowledge/(?:documents(?:/[a-zA-Z0-9_-]+(?:/(?:chunks|embedding-plan|reindex))?)?|ask|search|runs)|executions/[a-zA-Z0-9_-]+(?:/(?:events|cancel))?|tool-calls|llm/(?:requests(?:/[a-zA-Z0-9_-]+)?|stats|models|budgets|policy))',path)
        if not allowed:raise ServiceError(404,'not_found')
        if request.method not in ('GET','HEAD') and scope.role not in ('admin','operator'):raise ServiceError(403,'permission_denied')
        if request.method not in ('GET','HEAD') and path.startswith('llm/'):raise ServiceError(403,'offline_configuration_locked')
        app=await self.runtime(scope,identifier)
        body=bytearray()
        async for part in request.stream():
            body.extend(part)
            if len(body)>5*1024*1024:raise ServiceError(413,'payload_too_large')
        if path=='knowledge/ask' and body:
            try:data=json.loads(body)
            except (ValueError,UnicodeDecodeError):raise ServiceError(422,'validation_error')
            if not isinstance(data,dict):raise ServiceError(422,'validation_error')
            if data.get('provider') not in (None,'mock'):raise ServiceError(403,'live_user_approval_required')
            data['provider']='mock';body=json.dumps(data).encode()
        if path.startswith('agents') and request.method in ('POST','PUT') and body:
            try:data=json.loads(body)
            except (ValueError,UnicodeDecodeError):raise ServiceError(422,'validation_error')
            if not isinstance(data,dict):raise ServiceError(422,'validation_error')
            if data.get('model')!='mock-v1':raise ServiceError(403,'offline_model_required')
            if not isinstance(data.get('tools',[]),list):raise ServiceError(422,'validation_error')
            if any(t not in ('knowledge_search','calculator','datetime','json_validator','save_note') for t in data.get('tools',[])):
                raise ServiceError(403,'tool_denied')
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://workspace.internal') as client:
            result=await client.request(request.method,'/api/'+path,params=request.query_params,
                content=bytes(body),headers={'Authorization':'Bearer '+app.state.token,'Content-Type':request.headers.get('content-type','application/json')})
        return Response(content=result.content,status_code=result.status_code,media_type='application/json')

    async def close(self):
        await self.smoke.close()
        await self.stack.aclose()

def workspace_router(workspaces):
    router=APIRouter(prefix='/api/workspaces',tags=['Offline AI workspaces'])
    @router.get('')
    def listing(request:Request):return {'items':workspaces.rows(request.state.llm_scope)}
    @router.post('',status_code=201)
    def create(body:WorkspaceInput,request:Request):return workspaces.create(request.state.llm_scope,body)
    @router.get('/{identifier}/readiness')
    async def readiness(identifier:str,request:Request):return await workspaces.readiness(request.state.llm_scope,identifier)
    @router.post('/{identifier}/live')
    async def live(identifier:str,body:dict,request:Request):
        workspaces.get(request.state.llm_scope,identifier)
        return await workspaces.live.ask(request.state.llm_scope,identifier,body)
    @router.get('/{identifier}/live-status')
    async def live_status(identifier:str,request:Request,authorization_id:str|None=None):
        return await workspaces.live.status(request.state.llm_scope,identifier,authorization_id)
    @router.post('/{identifier}/smoke/prepare')
    async def smoke_prepare(identifier:str,request:Request):
        return await workspaces.smoke.prepare(request.state.llm_scope,identifier)
    @router.post('/{identifier}/smoke')
    async def smoke_start(identifier:str,body:dict,request:Request):
        return await workspaces.smoke.start(request.state.llm_scope,identifier,body)
    @router.get('/{identifier}/smoke')
    def smoke_list(identifier:str,request:Request):return workspaces.smoke.record(request.state.llm_scope,identifier)
    @router.get('/{identifier}/smoke/{run}')
    def smoke_view(identifier:str,run:str,request:Request):return workspaces.smoke.record(request.state.llm_scope,identifier,run)
    @router.post('/{identifier}/smoke/{run}/cancel')
    async def smoke_cancel(identifier:str,run:str,request:Request):
        scope=request.state.llm_scope
        workspaces.smoke.record(scope,identifier,run)
        if scope.role not in ('admin','operator'):raise ServiceError(403,'permission_denied')
        job=workspaces.smoke.jobs.get(run)
        if not job:raise ServiceError(409,'smoke_not_running')
        job.cancel();await asyncio.gather(job,return_exceptions=True)
        return workspaces.smoke.record(scope,identifier,run)
    from .live_authorization import GrantInput
    @router.post('/{identifier}/authorizations',status_code=201)
    async def authorize(identifier:str,body:GrantInput,request:Request):
        workspaces.get(request.state.llm_scope,identifier)
        return await workspaces.live.authorize(request.state.llm_scope,identifier,body)
    @router.get('/{identifier}/authorizations/{grant}')
    def authorization(identifier:str,grant:str,request:Request):
        workspaces.get(request.state.llm_scope,identifier)
        return workspaces.live.grants.public(workspaces.live.grants.get(request.state.llm_scope,identifier,grant))
    @router.delete('/{identifier}/authorizations/{grant}')
    def revoke(identifier:str,grant:str,request:Request):
        workspaces.get(request.state.llm_scope,identifier)
        return workspaces.live.grants.revoke(request.state.llm_scope,identifier,grant)
    @router.post('/{identifier}/dry-run')
    async def dry(identifier:str,body:dict,request:Request):
        workspaces.get(request.state.llm_scope,identifier)
        if request.state.llm_scope.role not in ('admin','operator'):raise ServiceError(403,'permission_denied')
        return await workspaces.live.plan(request.state.llm_scope,identifier,body)
    @router.get('/{identifier}/dry-runs')
    def dry_runs(identifier:str,request:Request):
        scope=request.state.llm_scope;workspaces.get(scope,identifier)
        with workspaces.sessions() as db:
            return {'items':[r.body for r in db.scalars(select(LLMConfiguration).where(LLMConfiguration.kind=='live_dry',LLMConfiguration.tenant_id==scope.tenant)) if r.body['workspace_id']==identifier and r.body['owner_id']==scope.user]}
    @router.post('/{identifier}/google/{grant}/reindex')
    async def google_index(identifier:str,grant:str,request:Request):
        scope=request.state.llm_scope
        app=await workspaces.live.runtime(scope,identifier,grant)
        if scope.role!='admin':raise ServiceError(403,'permission_denied')
        state=workspaces.live.grants.get(scope,identifier,grant)
        return {'items':[app.state.knowledge.reindex(i,True) for i in state['allowed_data']]}
    async def google_read(identifier:str,grant:str,path:str,request:Request):
        # Read history/source/trace and cancel only. No arbitrary provider/config/API forwarding.
        if not re.fullmatch(r'(?:knowledge/(?:documents(?:/[a-zA-Z0-9_-]+(?:/chunks)?)?|runs)|executions/[a-zA-Z0-9_-]+(?:/(?:events|cancel))?|llm/requests(?:/[a-zA-Z0-9_-]+)?)',path):raise ServiceError(404,'not_found')
        if request.method=='POST' and not path.endswith('/cancel'):raise ServiceError(403,'permission_denied')
        if request.method=='POST' and request.state.llm_scope.role not in ('admin','operator'):raise ServiceError(403,'permission_denied')
        return await workspaces.live.request(request.state.llm_scope,identifier,grant,path,request.method)
    for method in ('GET','POST'):
        router.add_api_route('/{identifier}/google/{grant}/{path:path}',google_read,methods=[method],operation_id='workspace_google_'+method.lower())
    async def forward(identifier:str,path:str,request:Request):return await workspaces.forward(request.state.llm_scope,identifier,path,request)
    for method in ('GET','POST','PUT','PATCH','DELETE'):
        router.add_api_route('/{identifier}/{path:path}',forward,methods=[method],operation_id='workspace_forward_'+method.lower())
    return router
