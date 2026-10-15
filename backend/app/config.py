from pathlib import Path
import os
from pydantic import SecretStr,Field
from typing import Literal
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[1]
os.environ['LANGGRAPH_STRICT_MSGPACK'] = 'true'
os.environ['LANGCHAIN_TRACING_V2'] = 'false'

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / '.env', extra='ignore')
    gemini_api_key: SecretStr = SecretStr('')
    gemini_model: str = 'gemini-3.5-flash-lite'
    database_url: str = f'sqlite:///{(ROOT / "data/agentops.db").as_posix()}'
    llm_provider: str = 'mock'
    real_validation_enabled: bool = False
    workspace_live_enabled: bool = False
    validation_transport_is_stub: bool = False
    external_api_enabled: bool = False
    paid_operations_enabled: bool = False
    allowed_external_providers: list[str] = []
    allowed_external_operations: list[str] = []
    environment_id: str = 'local'
    allowed_fallback_models: list[str] = []
    fallback_data_allowed: bool = False
    mock_degradation_allowed: bool = False
    llm_concurrency: int = Field(default=2,ge=1,le=8)
    llm_principals: list[dict] = []
    api_token: SecretStr = SecretStr('')
    request_timeout_seconds: int = 60
    execution_timeout_seconds: int = 180
    input_price_per_million: float | None = None
    output_price_per_million: float | None = None
    checkpoint_database_path: Path = ROOT / 'data/checkpoints.db'

    knowledge_storage_path: Path = ROOT / 'data/documents'
    embedding_provider: Literal['mock','google'] = 'mock'
    embedding_revision: str | None = None
    embedding_model: str = 'gemini-embedding-2'
    embedding_dimension: int = Field(default=768,ge=128,le=3072)
    embedding_batch_size: int = Field(default=32,ge=1,le=32)
    embedding_timeout_seconds: int = Field(default=30,ge=1,le=120)
    embedding_max_requests: int = Field(default=32,ge=1,le=32)
    embedding_external_enabled: bool = False
    evidence_max_passes: int = Field(default=2,ge=0,le=2)
    evidence_max_chunks: int = Field(default=12,ge=1,le=20)
    evidence_timeout_seconds: int = Field(default=8,ge=1,le=15)
    evidence_max_repairs: int = Field(default=1,ge=0,le=1)
    local_mcp_enabled: bool = True
    local_mcp_startup_timeout_seconds: int = Field(default=20,ge=1,le=30)
    http_fetch_allowed_urls: list[str] = ['https://example.com/']
    approval_timeout_seconds: int = 60

    @property
    def checkpoint_path(self) -> Path:
        return self.checkpoint_database_path

    auth_session_seconds: int = Field(default=28800,ge=60,le=86400)
    auth_cookie_secure: bool = False
    auth_allowed_origins: list[str] = ['http://127.0.0.1:3000','http://localhost:3000','http://127.0.0.1:8000']
    auth_login_window_seconds: int = Field(default=900,ge=60,le=3600)
    auth_login_account_limit: int = Field(default=5,ge=1,le=20)
    auth_login_client_limit: int = Field(default=30,ge=5,le=100)
    auth_cookie_name: str = Field(default='agentops_session',pattern=r'^[a-zA-Z0-9_-]{1,40}$')
    auth_csrf_cookie_name: str = Field(default='agentops_csrf',pattern=r'^[a-zA-Z0-9_-]{1,40}$')
    evaluation_calibration_timeout_seconds: int = Field(default=60,ge=1,le=60)
    evaluation_timeout_seconds: int = Field(default=300,ge=1,le=300)
    pdf_processing_timeout_seconds: int = Field(default=30,ge=1,le=60)
