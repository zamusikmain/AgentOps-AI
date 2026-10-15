"""Identical local fixtures; separate disposable database per invocation; never reindex workspace."""
import sys,asyncio,json,time,tempfile,platform,random,hashlib,statistics
from pathlib import Path
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/'backend'))
from app.db import Base,database,LLMConfiguration,LLMExecution
from app.config import Settings
from app.providers import MockProvider,ProviderError
from app.llm_reliability import Reliability
from app.profiling import Profile,distribution
from app.knowledge_store import KnowledgeStore
from app.evaluation import Evaluator
from sqlalchemy import text,select
from concurrent.futures import ThreadPoolExecutor
config={'requests':30,'repetitions':3,'warmup':2,'seed':7429,'concurrency':2,'embedding_dimension':768,'synchronous':'SQLite default FULL; WAL','fixtures':'original-v1-pdf','retry_attempts':2}
async def benchmark():
 random.seed(config['seed']);directory=Path(tempfile.mkdtemp(prefix='v09-perf-',dir=root/'backend/data'));s=Settings(_env_file=None,database_url=f'sqlite:///{directory/"perf.db"}',knowledge_storage_path=directory/'docs',checkpoint_database_path=directory/'cp.db',llm_provider='mock')
 engine,sessions=database(s.database_url);Base.metadata.create_all(engine)
 legacy=len(sys.argv)>1 and sys.argv[1]=='baseline-reproduced'
 if legacy:
  assert Path(engine.url.database).resolve().is_relative_to(directory.resolve())
  with engine.begin() as db:
   for name in ('ix_llm_tenant_created','ix_llm_tenant_trace_created'):db.execute(text('DROP INDEX '+name))
 layer=Reliability(sessions,s,MockProvider());layer.legacy_trace_benchmark=legacy;layer.seed();knowledge=KnowledgeStore(sessions,s.knowledge_storage_path,s);doc=knowledge.create('fixture.pdf',(root/'docs/fixtures/AgentOps_RAG_Test_Corporate_Policy.pdf').read_bytes());await knowledge.jobs[doc['id']]
 output={};messages=[{'role':'user','parts':[{'text':'Local performance measurement'}]}];snapshot={'model':'mock','instructions':'Read supplied context only','tools':[]}
 async def one():
  profile=Profile().start()
  try:await layer.execute(snapshot,messages,128);return profile.snapshot()
  finally:profile.stop()
 for workload in ('sequential','concurrent','trace-heavy'):
  for _ in range(config['warmup']):await one()
  runs=[]
  for _ in range(config['repetitions']):
   start=time.perf_counter();records=await asyncio.gather(*[one() for _ in range(config['requests'])]) if workload=='concurrent' else [await one() for _ in range(config['requests'])]
   elapsed=(time.perf_counter()-start)*1000;runs.append({'elapsed_ms':elapsed,'throughput_per_second':len(records)/(elapsed/1000),'latency':distribution([r['total_ms'] for r in records]),'counts':{k:sum(r['counts'].get(k,0) for r in records) for k in ('commits','sqlite_writes','sqlite_reads')},'commit_ms':sum(r['phases_ms'].get('sqlite_commit',0) for r in records)})
  output[workload]={'runs':runs,'median_elapsed_ms':statistics.median(r['elapsed_ms'] for r in runs),'median_commits':statistics.median(r['counts']['commits'] for r in runs)}
 samples=[]
 for _ in range(90):
  profile=Profile().start()
  try:knowledge.search('audit retention policy',[doc['id']],[doc['id']],5,'hybrid',True);samples.append(profile.snapshot())
  finally:profile.stop()
 output['retrieval-heavy']={'latency':distribution([r['total_ms'] for r in samples]),'sqlite_reads':sum(r['counts'].get('sqlite_reads',0) for r in samples)}
 evaluator=Evaluator(sessions,knowledge);evaluator.llm=layer;installed=await evaluator.install('v1');profile=Profile().start();start=time.perf_counter();run=evaluator.start(installed['agent_id']);await evaluator.jobs[run['id']];record=profile.stop();saved=evaluator.read(run['id']);assert saved['status']=='completed'
 output['evaluation-heavy']={'elapsed_ms':(time.perf_counter()-start)*1000,'counts':record['counts'],'quality_correct':saved['metrics']['hybrid']['answer_correct'],'cases':40,'repetitions':1,'small_sample':True}
 class Flaky(MockProvider):
  calls=0
  async def generate(self,*a):
   self.calls+=1
   if self.calls%2:raise ProviderError('rate_limit',429)
   return await super().generate(*a)
 layer.adapter=Flaky()
 with sessions() as db:r=db.get(LLMConfiguration,'workspace:policy:execution');r.body={**r.body,'max_attempts':2,'backoff_seconds':.01};db.commit()
 retry=[await one() for _ in range(12)];output['retry-overhead']={'latency':distribution([r['total_ms'] for r in retry]),'attempts':layer.adapter.calls,'small_sample':True}
 p={'breaker_threshold':1,'breaker_cooldown_seconds':30};layer.circuit('mock','mock-v1',p,'failure');latencies=[]
 for _ in range(30):
  start=time.perf_counter()
  try:await one()
  except ProviderError:pass
  latencies.append((time.perf_counter()-start)*1000)
 output['circuit-open']={'latency':distribution(latencies)}
 # Concurrent SQL writes on a controlled table, not provider dispatch or user data.
 def writer(i):
  profile=Profile().start()
  try:
   with sessions() as db:db.add(LLMConfiguration(id='contention-'+str(i),tenant_id='performance',kind='measurement',name=str(i),body={'sample':i}));db.commit()
   return profile.snapshot()
  finally:profile.stop()
 with ThreadPoolExecutor(4) as executor:records=list(executor.map(writer,range(30)))
 output['sqlite-contention']={'latency':distribution([r['total_ms'] for r in records]),'commits':sum(r['counts'].get('commits',0) for r in records)}
 with engine.connect() as connection:plans={name:[tuple(r) for r in connection.execute(text(sql))] for name,sql in {'trace_lookup':"EXPLAIN QUERY PLAN SELECT * FROM llm_executions WHERE tenant_id='workspace' AND trace_id='fixture' ORDER BY created_at",'request_history':"EXPLAIN QUERY PLAN SELECT * FROM llm_executions WHERE tenant_id='workspace' ORDER BY created_at DESC LIMIT 50"}.items()}
 await evaluator.close();await layer.close();await knowledge.close();engine.dispose()
 return {'implementation_hash':hashlib.sha256((root/'backend/app/llm_reliability.py').read_bytes()).hexdigest(),'trace_variant':'legacy-reproducer' if legacy else 'optimized','config':config,'config_hash':hashlib.sha256(json.dumps(config,sort_keys=True).encode()).hexdigest(),'environment':{'python':platform.python_version(),'platform':platform.system(),'sqlite':__import__('sqlite3').sqlite_version,'cpu_count':__import__('os').cpu_count()},'workloads':output,'query_plans':plans,'real_api_calls':0,'limitations':['Local filesystem/CPU noise; no production-scale claims','Evaluation-heavy has one repetition; quality datasets unchanged','Trace-heavy uses full default audit detail, not disabled observability']}
report=asyncio.run(benchmark());label=sys.argv[1] if len(sys.argv)>1 else 'current';(root/f'docs/v09-performance-{label}.json').write_text(json.dumps(report,indent=2),encoding='utf8');print('Local performance '+label+' recorded; no external AI calls.')
