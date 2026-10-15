from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import String, Text, Integer, Float, ForeignKey, JSON, LargeBinary, create_engine, event, Index
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

def now() -> str:
    return datetime.now(timezone.utc).isoformat()

def uid() -> str:
    return str(uuid4())

class Base(DeclarativeBase):
    pass

class Agent(Base):
    __tablename__ = 'agents'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    name: Mapped[str] = mapped_column(String(120))
    role: Mapped[str] = mapped_column(String(30))
    instructions: Mapped[str] = mapped_column(Text)
    model: Mapped[str] = mapped_column(String(120))
    tools: Mapped[list[str]] = mapped_column(JSON, default=list)
    document_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    max_steps: Mapped[int] = mapped_column(Integer, default=4)
    max_tokens: Mapped[int] = mapped_column(Integer, default=2048)
    status: Mapped[str] = mapped_column(String(20), default='active')
    created_at: Mapped[str] = mapped_column(String(40), default=now)

class Task(Base):
    __tablename__ = 'tasks'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    title: Mapped[str] = mapped_column(String(200))
    prompt: Mapped[str] = mapped_column(Text)
    agent_id: Mapped[str] = mapped_column(ForeignKey('agents.id'))
    status: Mapped[str] = mapped_column(String(20), default='draft')
    created_at: Mapped[str] = mapped_column(String(40), default=now)

class Execution(Base):
    __tablename__ = 'executions'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    task_id: Mapped[str] = mapped_column(ForeignKey('tasks.id'))
    agent_id: Mapped[str] = mapped_column(ForeignKey('agents.id'))
    snapshot: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(20), default='queued')
    result: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(String(100), nullable=True)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    estimated_cost_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[str] = mapped_column(String(40), default=now)
    finished_at: Mapped[str | None] = mapped_column(String(40), nullable=True)

class ExecutionEvent(Base):
    __tablename__ = 'execution_events'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    execution_id: Mapped[str] = mapped_column(ForeignKey('executions.id'))
    kind: Mapped[str] = mapped_column(String(40))
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[str] = mapped_column(String(40), default=now)

class Workflow(Base):
    __tablename__ = 'workflows'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    name: Mapped[str] = mapped_column(String(120))
    agent_ids: Mapped[list[str]] = mapped_column(JSON)
    retry_from: Mapped[int] = mapped_column(Integer, default=2)
    max_revisions: Mapped[int] = mapped_column(Integer, default=1)
    max_calls: Mapped[int] = mapped_column(Integer, default=12)
    max_total_tokens: Mapped[int] = mapped_column(Integer, default=32768)
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=180)
    status: Mapped[str] = mapped_column(String(20), default='active')
    created_at: Mapped[str] = mapped_column(String(40), default=now)

class WorkflowRun(Base):
    __tablename__ = 'workflow_runs'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    workflow_id: Mapped[str] = mapped_column(ForeignKey('workflows.id'))
    title: Mapped[str] = mapped_column(String(200))
    prompt: Mapped[str] = mapped_column(Text)
    snapshot: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(20), default='queued')
    current_stage: Mapped[int | None] = mapped_column(Integer, nullable=True)
    current_agent_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    revisions: Mapped[int] = mapped_column(Integer, default=0)
    calls: Mapped[int] = mapped_column(Integer, default=0)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(String(100), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    started_at: Mapped[str | None] = mapped_column(String(40), nullable=True)
    finished_at: Mapped[str | None] = mapped_column(String(40), nullable=True)
    created_at: Mapped[str] = mapped_column(String(40), default=now)

class WorkflowStep(Base):
    __tablename__ = 'workflow_steps'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    run_id: Mapped[str] = mapped_column(ForeignKey('workflow_runs.id'), index=True)
    stage_index: Mapped[int] = mapped_column(Integer)
    attempt: Mapped[int] = mapped_column(Integer)
    agent_id: Mapped[str] = mapped_column(String(36))
    agent_name: Mapped[str] = mapped_column(String(120))
    role: Mapped[str] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(String(20), default='running')
    input: Mapped[dict] = mapped_column(JSON)
    output: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    raw_output: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(String(100), nullable=True)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    finished_at: Mapped[str | None] = mapped_column(String(40), nullable=True)
    created_at: Mapped[str] = mapped_column(String(40), default=now)

class WorkflowEvent(Base):
    __tablename__ = 'workflow_events'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(ForeignKey('workflow_runs.id'), index=True)
    kind: Mapped[str] = mapped_column(String(40))
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[str] = mapped_column(String(40), default=now)

def database(url: str):
    engine = create_engine(url, connect_args={'check_same_thread': False, 'timeout': 30} if url.startswith('sqlite') else {})
    if url.startswith('sqlite'):
        @event.listens_for(engine, 'connect')
        def configure(connection, _):
            connection.execute('PRAGMA foreign_keys=ON')
            connection.execute('PRAGMA journal_mode=WAL')
    from .profiling import install
    install(engine)
    return engine, sessionmaker(engine, expire_on_commit=False)

def serialize(row):
    return {c.name: getattr(row, c.name) for c in row.__table__.columns}

class ToolCall(Base):
    __tablename__='tool_calls'
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uid)
    run_kind:Mapped[str]=mapped_column(String(20),index=True)
    run_id:Mapped[str]=mapped_column(String(36),index=True)
    stage_id:Mapped[str|None]=mapped_column(String(36),nullable=True)
    tool_id:Mapped[str]=mapped_column(String(80))
    operation_key:Mapped[str]=mapped_column(String(128),unique=True)
    arguments:Mapped[dict]=mapped_column(JSON)
    access:Mapped[str]=mapped_column(String(20))
    status:Mapped[str]=mapped_column(String(30),default='requested')
    result:Mapped[dict|None]=mapped_column(JSON,nullable=True)
    error:Mapped[str|None]=mapped_column(String(80),nullable=True)
    duration_ms:Mapped[int|None]=mapped_column(Integer,nullable=True)
    decision:Mapped[str|None]=mapped_column(String(20),nullable=True)
    decided_at:Mapped[str|None]=mapped_column(String(40),nullable=True)
    created_at:Mapped[str]=mapped_column(String(40),default=now)
    finished_at:Mapped[str|None]=mapped_column(String(40),nullable=True)

class ToolNote(Base):
    __tablename__='tool_notes'
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uid)
    call_id:Mapped[str]=mapped_column(ForeignKey('tool_calls.id'),unique=True)
    text:Mapped[str]=mapped_column(Text)
    created_at:Mapped[str]=mapped_column(String(40),default=now)


class KnowledgeDocument(Base):
    __tablename__='knowledge_documents'
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uid)
    name:Mapped[str]=mapped_column(String(200))
    sha256:Mapped[str]=mapped_column(String(64))
    status:Mapped[str]=mapped_column(String(20),default='indexing')
    error:Mapped[str|None]=mapped_column(String(80),nullable=True)
    pages:Mapped[int]=mapped_column(Integer,default=0)
    chunks:Mapped[int]=mapped_column(Integer,default=0)
    bytes:Mapped[int]=mapped_column(Integer)
    created_at:Mapped[str]=mapped_column(String(40),default=now)
    embedding_status:Mapped[str]=mapped_column(String(30),default='not_indexed')
    embedding_error:Mapped[str|None]=mapped_column(String(80),nullable=True)
    embedding_signature:Mapped[str|None]=mapped_column(String(64),nullable=True)
    embedded_chunks:Mapped[int]=mapped_column(Integer,default=0)

class KnowledgeChunk(Base):
    __tablename__='knowledge_chunks'
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uid)
    document_id:Mapped[str]=mapped_column(ForeignKey('knowledge_documents.id'),index=True)
    page:Mapped[int]=mapped_column(Integer)
    ordinal:Mapped[int]=mapped_column(Integer)
    text:Mapped[str]=mapped_column(Text)
    terms:Mapped[dict]=mapped_column(JSON)

class EmbeddingCache(Base):
    __tablename__='embedding_cache'
    id:Mapped[str]=mapped_column(String(64),primary_key=True)
    signature:Mapped[str]=mapped_column(String(64),index=True)
    dimension:Mapped[int]=mapped_column(Integer)
    vector:Mapped[bytes]=mapped_column(LargeBinary)
    created_at:Mapped[str]=mapped_column(String(40),default=now)

class KnowledgeVector(Base):
    __tablename__='knowledge_vectors'
    chunk_id:Mapped[str]=mapped_column(ForeignKey('knowledge_chunks.id'),primary_key=True)
    cache_id:Mapped[str]=mapped_column(ForeignKey('embedding_cache.id'),index=True)

class EvaluationRun(Base):
    __tablename__='evaluation_runs'
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uid)
    agent_id:Mapped[str]=mapped_column(String(36),index=True)
    document_ids:Mapped[list]=mapped_column(JSON)
    dataset_version:Mapped[str]=mapped_column(String(64))
    status:Mapped[str]=mapped_column(String(20),default='queued')
    provider_metadata:Mapped[dict]=mapped_column(JSON)
    metrics:Mapped[dict]=mapped_column(JSON,default=dict)
    error:Mapped[str|None]=mapped_column(String(80),nullable=True)
    duration_ms:Mapped[int|None]=mapped_column(Integer,nullable=True)
    created_at:Mapped[str]=mapped_column(String(40),default=now)
    finished_at:Mapped[str|None]=mapped_column(String(40),nullable=True)

class EvaluationCase(Base):
    __tablename__='evaluation_cases'
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uid)
    run_id:Mapped[str]=mapped_column(ForeignKey('evaluation_runs.id'),index=True)
    case_id:Mapped[str]=mapped_column(String(40))
    mode:Mapped[str]=mapped_column(String(20))
    result:Mapped[dict]=mapped_column(JSON)

class LLMConfiguration(Base):
    __tablename__='llm_configurations'
    id:Mapped[str]=mapped_column(String(240),primary_key=True)
    tenant_id:Mapped[str]=mapped_column(String(80),index=True)
    kind:Mapped[str]=mapped_column(String(30),index=True)
    name:Mapped[str]=mapped_column(String(160))
    version:Mapped[int]=mapped_column(Integer,default=1)
    body:Mapped[dict]=mapped_column(JSON)
    updated_at:Mapped[str]=mapped_column(String(40),default=now)

class PromptVersion(Base):
    __tablename__='prompt_versions'
    id:Mapped[str]=mapped_column(String(240),primary_key=True)
    tenant_id:Mapped[str]=mapped_column(String(80),index=True)
    prompt_id:Mapped[str]=mapped_column(String(80))
    version:Mapped[int]=mapped_column(Integer)
    body:Mapped[dict]=mapped_column(JSON)
    digest:Mapped[str]=mapped_column(String(64))
    status:Mapped[str]=mapped_column(String(20),default='draft')
    created_at:Mapped[str]=mapped_column(String(40),default=now)

class LLMExecution(Base):
    __tablename__='llm_executions'
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uid)
    trace_id:Mapped[str]=mapped_column(String(80),index=True)
    tenant_id:Mapped[str]=mapped_column(String(80),index=True)
    user_id:Mapped[str]=mapped_column(String(80))
    provider:Mapped[str]=mapped_column(String(30),index=True)
    model:Mapped[str]=mapped_column(String(120),index=True)
    operation:Mapped[str]=mapped_column(String(30),index=True)
    status:Mapped[str]=mapped_column(String(30),index=True,default='queued')
    metadata_json:Mapped[dict]=mapped_column(JSON,default=dict)
    usage:Mapped[dict]=mapped_column(JSON,default=dict)
    attempts:Mapped[list]=mapped_column(JSON,default=list)
    content:Mapped[dict|None]=mapped_column(JSON,nullable=True)
    estimated_cost_usd:Mapped[float|None]=mapped_column(Float,nullable=True)
    latency_ms:Mapped[int|None]=mapped_column(Integer,nullable=True)
    retry_count:Mapped[int]=mapped_column(Integer,default=0)
    fallback_count:Mapped[int]=mapped_column(Integer,default=0)
    error_category:Mapped[str|None]=mapped_column(String(40),nullable=True)
    error_code:Mapped[str|None]=mapped_column(String(80),nullable=True)
    created_at:Mapped[str]=mapped_column(String(40),index=True,default=now)
    finished_at:Mapped[str|None]=mapped_column(String(40),nullable=True)

class BudgetReservation(Base):
    __tablename__='budget_reservations'
    id:Mapped[str]=mapped_column(String(80),primary_key=True)
    request_id:Mapped[str]=mapped_column(ForeignKey('llm_executions.id'),index=True)
    tenant_id:Mapped[str]=mapped_column(String(80),index=True)
    provider:Mapped[str]=mapped_column(String(30))
    model:Mapped[str]=mapped_column(String(120))
    reserved_usd:Mapped[float]=mapped_column(Float)
    charged_usd:Mapped[float|None]=mapped_column(Float,nullable=True)
    status:Mapped[str]=mapped_column(String(30),default='reserved')
    created_at:Mapped[str]=mapped_column(String(40),index=True,default=now)

class EvaluationComparison(Base):
    __tablename__='evaluation_comparisons'
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uid)
    tenant_id:Mapped[str]=mapped_column(String(80),index=True)
    baseline_id:Mapped[str]=mapped_column(ForeignKey('evaluation_runs.id'))
    current_id:Mapped[str]=mapped_column(ForeignKey('evaluation_runs.id'))
    result:Mapped[dict]=mapped_column(JSON)
    created_at:Mapped[str]=mapped_column(String(40),default=now)

class ValidationRun(Base):
    __tablename__='validation_runs'
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uid)
    tenant_id:Mapped[str]=mapped_column(String(80),index=True)
    user_id:Mapped[str]=mapped_column(String(80))
    mode:Mapped[str]=mapped_column(String(30),index=True)
    dataset_id:Mapped[str]=mapped_column(String(80))
    dataset_version:Mapped[int]=mapped_column(Integer)
    dataset_hash:Mapped[str]=mapped_column(String(64))
    provider:Mapped[str]=mapped_column(String(30))
    model:Mapped[str]=mapped_column(String(120))
    status:Mapped[str]=mapped_column(String(30),index=True,default='queued')
    plan:Mapped[dict]=mapped_column(JSON)
    result:Mapped[dict]=mapped_column(JSON,default=dict)
    evaluation_id:Mapped[str|None]=mapped_column(ForeignKey('evaluation_runs.id'),nullable=True)
    created_at:Mapped[str]=mapped_column(String(40),default=now,index=True)
    finished_at:Mapped[str|None]=mapped_column(String(40),nullable=True)

Index('ix_llm_tenant_created',LLMExecution.tenant_id,LLMExecution.created_at)
Index('ix_llm_tenant_trace_created',LLMExecution.tenant_id,LLMExecution.trace_id,LLMExecution.created_at)

class User(Base):
    __tablename__='users'
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uid)
    email:Mapped[str]=mapped_column(String(254),unique=True,index=True)
    tenant_id:Mapped[str]=mapped_column(String(80),index=True)
    role:Mapped[str]=mapped_column(String(20))
    status:Mapped[str]=mapped_column(String(20),default='active')
    password_hash:Mapped[str]=mapped_column(Text)
    password_changed_at:Mapped[str]=mapped_column(String(40),default=now)
    created_at:Mapped[str]=mapped_column(String(40),default=now)

class UserSession(Base):
    __tablename__='user_sessions'
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uid)
    user_id:Mapped[str]=mapped_column(ForeignKey('users.id'),index=True)
    token_hash:Mapped[str]=mapped_column(String(64),unique=True,index=True)
    csrf_hash:Mapped[str]=mapped_column(String(64))
    expires_at:Mapped[float]=mapped_column(Float)
    revoked_at:Mapped[str|None]=mapped_column(String(40),nullable=True)
    created_at:Mapped[str]=mapped_column(String(40),default=now)

class LoginAttempt(Base):
    __tablename__='login_attempts'
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uid)
    account_key:Mapped[str]=mapped_column(String(64),index=True)
    client_key:Mapped[str]=mapped_column(String(64),index=True)
    occurred_at:Mapped[float]=mapped_column(Float,index=True)

class AuthAudit(Base):
    __tablename__='auth_audit'
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uid)
    tenant_id:Mapped[str]=mapped_column(String(80),index=True)
    actor_id:Mapped[str|None]=mapped_column(String(36),nullable=True)
    target_id:Mapped[str|None]=mapped_column(String(36),nullable=True)
    action:Mapped[str]=mapped_column(String(40))
    created_at:Mapped[str]=mapped_column(String(40),default=now)

class PasswordReset(Base):
    __tablename__='password_resets'
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uid)
    user_id:Mapped[str]=mapped_column(ForeignKey('users.id'),index=True)
    token_hash:Mapped[str]=mapped_column(String(64),unique=True)
    expires_at:Mapped[float]=mapped_column(Float)
    used_at:Mapped[str|None]=mapped_column(String(40),nullable=True)
