from typing import Literal
from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator
from .schemas import TaskInput

class WorkflowInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    name: str = Field(min_length=1, max_length=120)
    agent_ids: list[str] = Field(min_length=2, max_length=8)
    retry_from: int = Field(default=0, ge=0)
    max_revisions: int = Field(default=1, ge=0, le=3)
    max_calls: int = Field(default=12, ge=2, le=64)
    max_total_tokens: int = Field(default=32768, ge=1024, le=262144)
    timeout_seconds: int = Field(default=180, ge=1, le=600)
    status: Literal['active', 'disabled'] = 'active'

    @field_validator('name')
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError('blank_value')
        return value.strip()

    @model_validator(mode='after')
    def limits(self):
        if len(set(self.agent_ids)) != len(self.agent_ids) or self.retry_from >= len(self.agent_ids)-1 or self.max_calls < len(self.agent_ids):
            raise ValueError('invalid_workflow_limits')
        return self

class WorkflowRunInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    title: str = Field(min_length=1, max_length=200)
    prompt: str = Field(min_length=1, max_length=32000)

    @field_validator('title', 'prompt')
    @classmethod
    def nonblank(cls, value):
        return TaskInput.nonblank(value)

class StageOutput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    summary: str = Field(min_length=1, max_length=16000)
    data: dict

class ReviewOutput(StageOutput):
    decision: Literal['approve', 'revise']
    feedback: str = Field(max_length=16000)

    @model_validator(mode='after')
    def feedback_required(self):
        if self.decision == 'revise' and not self.feedback.strip():
            raise ValueError('review_feedback_required')
        return self
