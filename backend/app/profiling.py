"""Monotonic, content-free phase and SQLite instrumentation."""
import contextvars,time,functools,inspect,math
from contextlib import contextmanager
from sqlalchemy import event
from sqlalchemy.orm import Session
active=contextvars.ContextVar('agentops_profile',default=None)
class Profile:
 def __init__(self):self.started=time.perf_counter();self.phases={};self.counts={};self.metadata={};self.token=None
 def start(self):self.token=active.set(self);return self
 def stop(self):
  result=self.snapshot()
  if self.token is not None:active.reset(self.token);self.token=None
  return result
 def snapshot(self):return {'total_ms':round((time.perf_counter()-self.started)*1000,3),'phases_ms':{k:round(v,3) for k,v in self.phases.items()},'counts':dict(self.counts)}
 def add(self,key,ms):self.phases[key]=self.phases.get(key,0)+ms
@contextmanager
def phase(name):
 start=time.perf_counter()
 try:yield
 finally:
  profile=active.get()
  if profile:profile.add(name,(time.perf_counter()-start)*1000)
def timed(name):
 def decorate(fn):
  if inspect.iscoroutinefunction(fn):
   @functools.wraps(fn)
   async def wrapped(*a,**kw):
    with phase(name):return await fn(*a,**kw)
  else:
   @functools.wraps(fn)
   def wrapped(*a,**kw):
    with phase(name):return fn(*a,**kw)
  return wrapped
 return decorate
def install(engine):
 if getattr(engine,'_profile_installed',False):return
 engine._profile_installed=True
 @event.listens_for(engine,'before_cursor_execute')
 def before(conn,cursor,statement,parameters,context,many):context._profile_start=time.perf_counter()
 @event.listens_for(engine,'after_cursor_execute')
 def after(conn,cursor,statement,parameters,context,many):
  p=active.get()
  if p:
   write=statement.lstrip().split(None,1)[0].upper() in ('INSERT','UPDATE','DELETE','REPLACE')
   key='sqlite_writes' if write else 'sqlite_reads';p.counts[key]=p.counts.get(key,0)+1;p.add('sqlite_write' if write else 'sqlite_read',(time.perf_counter()-context._profile_start)*1000)
@event.listens_for(Session,'before_commit')
def before_commit(session):session.info['_profile_commit_start']=time.perf_counter()
@event.listens_for(Session,'after_commit')
def after_commit(session):
 p=active.get()
 if p:p.counts['commits']=p.counts.get('commits',0)+1;p.add('sqlite_commit',(time.perf_counter()-session.info.get('_profile_commit_start',time.perf_counter()))*1000)
def distribution(values):
 values=sorted(values);n=len(values)
 def percentile(q):return values[max(0,math.ceil(n*q)-1)] if n else None
 return {'samples':n,'p50_ms':percentile(.5),'p95_ms':percentile(.95) if n>=20 else None,'p99_ms':percentile(.99) if n>=100 else None,'small_sample':n<100,'limitations':'Local nearest-rank samples; p95 needs 20, p99 needs 100; no production throughput claim.'}
