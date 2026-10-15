"""SQLite atomic cross-operation envelope. Reservations survive failure/cancellation."""
import time,math
from decimal import Decimal
from contextvars import ContextVar
from sqlalchemy import text
from .db import LLMConfiguration
from .providers import ProviderError
active_envelope=ContextVar('live_smoke_envelope',default=None)
class Envelope:
 def __init__(self,sessions,identifier,limits):
  self.sessions=sessions;self.key='workspace:smoke_envelope:'+identifier
  with sessions() as db:
   db.add(LLMConfiguration(id=self.key,tenant_id='workspace',kind='smoke_envelope',name=identifier,body={'limits':limits,'started':time.time(),'total':0,'generation':0,'embedding':0,'tokens':0,'estimated_usd':0}));db.commit()
 def claim(self,operation,provider,model,tokens=0,cost=None):
  if operation not in ('generation','embedding'):raise ProviderError('operation_denied')
  if cost is None or not math.isfinite(cost) or cost<0:raise ProviderError('pricing_unverified')
  if type(tokens)!=int or tokens<0:raise ProviderError('invalid_usage')
  with self.sessions() as db:
   db.execute(text('BEGIN IMMEDIATE'));row=db.get(LLMConfiguration,self.key);state=dict(row.body);limits=state['limits']
   if provider!=limits[operation+'_provider'] or model!=limits[operation+'_model']:raise ProviderError('model_denied')
   if time.time()-state['started']>=limits['duration_seconds']:raise ProviderError('validation_timeout')
   if state['total']+1>limits['total_requests'] or state[operation]+1>limits[operation+'_calls']:raise ProviderError('validation_request_limit')
   if state['tokens']+tokens>limits['total_tokens']:raise ProviderError('validation_token_limit')
   if Decimal(str(state['estimated_usd']))+Decimal(str(cost))>Decimal(str(limits['cost_usd'])):raise ProviderError('budget_exceeded')
   state['total']+=1;state[operation]+=1;state['tokens']+=tokens;state['estimated_usd']=float(Decimal(str(state['estimated_usd']))+Decimal(str(cost)));row.body=state;db.commit()
 def view(self):
  with self.sessions() as db:state=db.get(LLMConfiguration,self.key).body
  return {**state,'budget_remaining_usd':max(0,state['limits']['cost_usd']-state['estimated_usd']),'billing':'NOT VERIFIED','token_accounting':'conservative_reservations'}
