"""Prepared embedding boundary, never wired to Stage A execution.
Uses the same monetary reservation ledger as generation; missing usage stays uncertain.
"""
import re,time
from .db import LLMExecution,BudgetReservation,uid,now
from .providers import ProviderError
from .embeddings import GoogleEmbeddingProvider,EmbeddingError
from .live_envelope import active_envelope
class BudgetedGoogleEmbedding:
 name='google';external=True
 def __init__(self,settings,layer,provider=None,guard=None):
  self.guard=guard
  self.settings=settings;self.layer=layer;self.provider=provider or GoogleEmbeddingProvider(settings)
  self.model=self.provider.model;self.dimension=self.provider.dimension;self.parameters=self.provider.parameters
 def embed(self,texts,task):
  guard=self.guard or active_envelope.get();s=self.settings
  if not guard or not (s.real_validation_enabled and s.external_api_enabled and s.embedding_external_enabled and 'google' in s.allowed_external_providers and 'embedding' in s.allowed_external_operations):raise EmbeddingError('embedding_consent_required')
  registry=self.layer.configuration('model',self.model,{'availability':'unverified'})
  if registry.get('provider')!='google' or registry.get('availability')!='available' or not registry.get('compatible'):raise EmbeddingError('model_unverified')
  if registry.get('input_rate') is None or registry.get('output_rate') is None or not registry.get('pricing_version'):raise EmbeddingError('pricing_unverified')
  if registry['input_rate']<0 or registry['output_rate']<0:raise EmbeddingError('pricing_unverified')
  if (registry['input_rate'] or registry['output_rate']) and not s.paid_operations_enabled:raise EmbeddingError('paid_operations_disabled')
  if task not in ('document','query') or not texts or any(not isinstance(t,str) for t in texts):raise EmbeddingError('embedding_invalid_batch')
  if registry.get('context_limit') and any(len(t.encode())+2048>registry['context_limit'] for t in texts):raise EmbeddingError('embedding_context_limit')
  tokens=sum(len(t.encode())+2048 for t in texts);estimate=tokens*registry['input_rate']/1e6
  try:guard.claim('embedding','google',self.model,tokens,estimate)
  except ProviderError as exc:raise EmbeddingError(str(exc)) from None
  started=time.monotonic();identifier=uid();status='failed';code=None;reserved=False;http_status=None
  with self.layer.sessions() as db:
   db.add(LLMExecution(id=identifier,trace_id=guard.key.removeprefix('workspace:smoke_envelope:'),tenant_id=self.layer.scope.tenant,user_id=self.layer.scope.user,provider='google',model=self.model,operation='embedding',status='queued',metadata_json={**getattr(self.layer,'execution_context',{}),'content_retained':False,'pricing_version':registry['pricing_version'],'estimated_input_bound':tokens,'task':task}));self.layer.commit(db)
  try:
   self.layer.reserve(identifier,1,registry,estimate);reserved=True
   with self.layer.sessions() as db:r=db.get(LLMExecution,identifier);r.status='running';self.layer.commit(db)
   result=self.provider.embed(texts,task);status='success';return result
  except Exception as exc:
   http_status=getattr(exc,'http_status',None)
   code=str(exc) if re.fullmatch(r'[a-z0-9_]{1,80}',str(exc)) else 'embedding_provider_error'
   raise EmbeddingError(code,http_status=http_status) from None
  finally:
   with self.layer.sessions() as db:
    r=db.get(LLMExecution,identifier);r.status=status;r.latency_ms=int((time.monotonic()-started)*1000);r.error_code=code;r.finished_at=now();r.usage={'source':'unknown','input_tokens':None,'output_tokens':None};r.estimated_cost_usd=None;r.attempts=[{'attempt':1,'status':status,'dispatch':'possibly_sent'}] if reserved else []
    reservation=db.get(BudgetReservation,identifier+':1')
    if code:
     r.error_category='rate_limit' if http_status==429 else 'authentication' if http_status in (401,403) else 'timeout' if 'timeout' in code else 'budget' if 'budget' in code else 'provider_unavailable' if http_status==404 or http_status and http_status>=500 else 'configuration'
     r.metadata_json={**r.metadata_json,'http_status':http_status}
    if reservation:reservation.status='uncertain'
    self.layer.commit(db)
 def close(self):self.provider.close()
