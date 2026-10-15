"""Durable workspace grants using the existing configuration ledger.

Conservative shared reservations never refund an ambiguous external dispatch.
No SDK client, key or document content is stored in this ledger.
"""
import hashlib
import json
import time
from decimal import Decimal, ROUND_CEILING
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text
from .db import LLMConfiguration, User, uid, now
from .providers import ProviderError
from .services import ServiceError

GENERATION_MODEL = 'gemini-3.5-flash-lite'
EMBEDDING_MODEL = 'gemini-embedding-2'
VERIFIED_AT = '2026-10-15'
RATES = {GENERATION_MODEL: (.30, 2.50), EMBEDDING_MODEL: (.20, 0)}


class GrantInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    dataset_id: str = Field(min_length=1, max_length=100)
    document_ids: list[str] = Field(min_length=1, max_length=10)
    model: Literal['gemini-3.5-flash-lite'] = GENERATION_MODEL
    embedding_model: Literal['gemini-embedding-2'] = EMBEDDING_MODEL
    max_requests: int = Field(default=64, ge=1, le=100)
    max_tokens: int = Field(default=150000, ge=1, le=500000)
    max_budget_usd: float = Field(default=.40, gt=0, le=1, allow_inf_nan=False)
    expires_in_seconds: int = Field(default=600, ge=1, le=3600)
    confirmation: Literal['AUTHORIZE THIS DATA AND THESE LIMITS']


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


class LiveAuthorizations:
    def __init__(self, sessions):
        self.sessions = sessions

    def create(self, scope, workspace, body, documents):
        if scope.role != 'admin':
            raise ServiceError(403, 'permission_denied')
        if len(set(body.document_ids)) != len(body.document_ids) or set(documents) != set(body.document_ids):
            raise ServiceError(422, 'invalid_document_scope')
        identifier = uid()
        state = {'id': identifier, 'administrator_id': scope.user, 'tenant_id': scope.tenant,
                 'workspace_id': workspace, 'dataset_id': body.dataset_id,
                 'allowed_models': [body.model, body.embedding_model], 'allowed_data': documents,
                 'model': body.model, 'embedding_model': body.embedding_model,
                 'max_requests': body.max_requests, 'max_tokens': body.max_tokens,
                 'max_budget_usd': body.max_budget_usd, 'expires_at': time.time()+body.expires_in_seconds,
                 'revoked': False, 'created_at': now(), 'requests': 0, 'tokens': 0,
                 'reserved_nano_usd': 0, 'reported_input_tokens': 0, 'reported_output_tokens': 0,
                 'reported_thinking_tokens': 0, 'actual_cost_usd': None, 'reservations': {}}
        with self.sessions() as db:
            db.add(LLMConfiguration(id='live_grant:'+identifier, tenant_id=scope.tenant,
                                   kind='live_grant', name=identifier, body=state))
            db.commit()
        return self.public(state)

    def get(self, scope, workspace, identifier):
        with self.sessions() as db:
            row = db.get(LLMConfiguration, 'live_grant:'+identifier)
            if not row or row.body['tenant_id'] != scope.tenant or row.body['workspace_id'] != workspace or row.body['administrator_id'] != scope.user:
                raise ServiceError(404, 'authorization_not_found')
            return dict(row.body)

    def revoke(self, scope, workspace, identifier):
        self.get(scope, workspace, identifier)
        if scope.role != 'admin':
            raise ServiceError(403, 'permission_denied')
        with self.sessions() as db:
            db.execute(text('BEGIN IMMEDIATE'))
            row = db.get(LLMConfiguration, 'live_grant:'+identifier)
            row.body = {**row.body, 'revoked': True, 'revoked_at': now()}
            db.commit()
        return {'revoked': True}

    @staticmethod
    def public(state):
        return {k: v for k, v in state.items() if k != 'reservations'}


class DispatchGrant:
    def __init__(self, ledger, scope, workspace, identifier, dataset, documents, enabled):
        self.ledger, self.scope, self.workspace = ledger, scope, workspace
        self.identifier, self.dataset, self.documents, self.enabled = identifier, dataset, documents, enabled
        self.key = identifier

    def validate(self, state, transaction=None):
        if not self.enabled():
            raise ProviderError('live_execution_disabled', 403)
        if self.scope.role != 'admin' or state['administrator_id'] != self.scope.user or state['tenant_id'] != self.scope.tenant or state['workspace_id'] != self.workspace:
            raise ProviderError('live_authorization_denied', 403)
        def check_user(db):
            user=db.get(User,self.scope.user)
            if user and (user.role!='admin' or user.status!='active' or user.tenant_id!=self.scope.tenant):raise ProviderError('live_authorization_denied',403)
        if transaction is not None:check_user(transaction)
        else:
            with self.ledger.sessions() as db:check_user(db)
        if state['revoked']:
            raise ProviderError('live_authorization_revoked', 403)
        if time.time() >= state['expires_at']:
            raise ProviderError('live_authorization_expired', 403)
        try:documents=self.documents()
        except ServiceError:raise ProviderError('live_data_changed',403) from None
        if state['dataset_id'] != self.dataset or state['allowed_data'] != documents:
            raise ProviderError('live_data_changed', 403)

    def check(self):
        state = self.ledger.get(self.scope, self.workspace, self.identifier)
        self.validate(state)
        return state

    def claim(self, operation, provider, model, tokens=0, cost=None):
        if type(tokens) != int or tokens <= 0 or model not in RATES:
            raise ProviderError('pricing_unverified')
        if cost is None or not Decimal(str(cost)).is_finite() or cost < 0:
            raise ProviderError('pricing_unverified')
        with self.ledger.sessions() as db:
            db.execute(text('BEGIN IMMEDIATE'))
            row = db.get(LLMConfiguration, 'live_grant:'+self.identifier)
            if not row:
                raise ProviderError('live_authorization_denied', 403)
            state = dict(row.body)
            self.validate(state,db)
            expected = ('gemini', state['model']) if operation == 'generation' else ('google', state['embedding_model']) if operation == 'embedding' else None
            if (provider, model) != expected or model not in state['allowed_models']:
                raise ProviderError('model_denied', 403)
            nanos = int((Decimal(str(cost))*10**9).to_integral_value(rounding=ROUND_CEILING))
            if state['requests']+1 > state['max_requests']:
                raise ProviderError('live_request_limit')
            if state['tokens']+tokens > state['max_tokens']:
                raise ProviderError('live_token_limit')
            if Decimal(state['reserved_nano_usd']+nanos) > Decimal(str(state['max_budget_usd']))*10**9:
                raise ProviderError('budget_exceeded')
            rid = uid()
            state['requests'] += 1
            state['tokens'] += tokens
            state['reserved_nano_usd'] += nanos
            state['reservations'] = {**state['reservations'], rid: {'operation': operation, 'model': model, 'tokens': tokens, 'nano_usd': nanos, 'status': 'uncertain'}}
            row.body = state
            db.commit()
        return rid

    def reported(self, rid, reply):
        # Actual provider invoice remains unknown. Token-derived cost is an estimate.
        if reply.usage_source != 'reported':
            return
        with self.ledger.sessions() as db:
            db.execute(text('BEGIN IMMEDIATE'))
            row = db.get(LLMConfiguration, 'live_grant:'+self.identifier)
            state = dict(row.body)
            reservations = dict(state['reservations'])
            item = reservations[rid]
            if item['status'] == 'reported':
                return
            item = {**item, 'status': 'reported', 'input_tokens': reply.input_tokens, 'output_tokens': reply.output_tokens, 'thinking_tokens': reply.reasoning_tokens}
            reservations[rid] = item
            state['reservations'] = reservations
            state['reported_input_tokens'] += reply.input_tokens
            state['reported_output_tokens'] += reply.output_tokens
            state['reported_thinking_tokens'] += reply.reasoning_tokens or 0
            if reply.input_tokens+reply.output_tokens > item['tokens']:
                state['revoked'] = True
            row.body = state
            db.commit()
        if reply.input_tokens+reply.output_tokens>item['tokens']:
            raise ProviderError('budget_overrun')
