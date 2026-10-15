"""Isolated copy of primary DB for reproducible Mock benchmarks; no primary writes or AI network."""
import sys,sqlite3,tempfile,threading,time,json,hashlib
from pathlib import Path
import uvicorn
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/'backend'))
from app.config import Settings
from app.main import create_app
directory=root/'backend/data/v12-regression';directory.mkdir(exist_ok=True)
target=directory/'copy.db'
with sqlite3.connect(root/'backend/data/agentops.db') as source,sqlite3.connect(target) as db:source.backup(db)
settings=Settings(_env_file=None,api_token='v12-isolated-benchmark',llm_provider='mock',gemini_api_key='',database_url=f'sqlite:///{target.as_posix()}',checkpoint_database_path=directory/'cp.db',knowledge_storage_path=directory/'documents',local_mcp_enabled=False)
app=create_app(settings)
server=uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=8021,access_log=False,log_level='error'))
thread=threading.Thread(target=server.run,daemon=True);thread.start()
while not server.started:time.sleep(.1)
text=(root/'scripts/v10-regression.py').read_text().replace("token=(root/'backend/.local-token').read_text().strip()","token='v12-isolated-benchmark'").replace('127.0.0.1:8000','127.0.0.1:8021').replace("root/'backend/data/agentops.db'","root/'backend/data/v12-regression/copy.db'").replace('v10-evaluation-results.json','v12-evaluation-results.json')
text=text.replace(' for _ in range(1000):',' deadline=time.monotonic()+330\n while time.monotonic()<deadline:').replace('\nfor _ in range(1000):','\ndeadline=time.monotonic()+330\nwhile time.monotonic()<deadline:')
gold={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (root/'docs/fixtures').glob('rag-evaluation-*.json')}
started=time.monotonic()
try:
 exec(compile(text,str(root/'scripts/v10-regression.py'),'exec'))
 result=root/'docs/v12-evaluation-results.json';raw=result.read_text(encoding='utf8')
 (directory/'full-results.local.json').write_text(raw,encoding='utf8')
 data=json.loads(raw)
 assert all(hashlib.sha256((root/name).read_bytes()).hexdigest()==digest for name,digest in gold.items())
 summary={'reports':{key:{'metrics':value['run']['metrics'],'sqlite_reread':value['sqlite_reread']} for key,value in data['reports'].items()},'gold_sha256':gold,'gold_unchanged':True,'real_generation_requests':0,'real_embedding_requests':0,'duration_seconds':round(time.monotonic()-started,3),'raw_traces':'excluded local backend/data only'}
 result.write_text(json.dumps(summary,indent=2),encoding='utf8')
finally:server.should_exit=True;thread.join(30)
