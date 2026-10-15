from typing import Literal
from pydantic import BaseModel, Field, ConfigDict, field_validator
from .tools import CATALOG

class AgentInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    name: str = Field(min_length=1, max_length=120)
    role: Literal['planner', 'researcher', 'executor', 'reviewer']
    instructions: str = Field(min_length=1, max_length=16000)
    model: str = Field(min_length=1, max_length=120, pattern=r'^[a-zA-Z0-9._/-]+$')
    tools: list[str] = Field(default_factory=list, max_length=8)
    document_ids: list[str] = Field(default_factory=list,max_length=50)
    max_steps: int = Field(default=4, ge=1, le=12)
    max_tokens: int = Field(default=2048, ge=128, le=16384)
    status: Literal['active', 'disabled'] = 'active'

    @field_validator('tools')
    @classmethod
    def allowed_tools(cls, value):
        if any(name not in [t['name'] for t in CATALOG] for name in value):
            raise ValueError('unknown_tool')
        return list(dict.fromkeys(value))

    @field_validator('name', 'instructions')
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError('blank_value')
        return value.strip()

class TaskInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    title: str = Field(min_length=1, max_length=200)
    prompt: str = Field(min_length=1, max_length=32000)
    agent_id: str = Field(min_length=1, max_length=36)

    @field_validator('title', 'prompt')
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError('blank_value')
        return value.strip()
