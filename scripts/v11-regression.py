"""Isolated copy of primary DB for reproducible Mock benchmarks; no primary writes or AI network."""
import sys,sqlite3,tempfile,threading,time
from pathlib import Path
import uvicorn
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/'backend'))
from app.config import Settings
from app.main import create_app
directory=root/'backend/data/v11-regression';directory.mkdir(exist_ok=True)
target=directory/'copy.db'
with sqlite3.connect(root/'backend/data/agentops.db') as source,sqlite3.connect(target) as db:source.backup(db)
settings=Settings(_env_file=None,api_token='v11-isolated-benchmark',llm_provider='mock',gemini_api_key='',database_url=f'sqlite:///{target.as_posix()}',checkpoint_database_path=directory/'cp.db',knowledge_storage_path=directory/'documents',local_mcp_enabled=False)
app=create_app(settings)
server=uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=8021,access_log=False,log_level='error'))
thread=threading.Thread(target=server.run,daemon=True);thread.start()
while not server.started:time.sleep(.1)
text=(root/'scripts/v10-regression.py').read_text().replace("token=(root/'backend/.local-token').read_text().strip()","token='v11-isolated-benchmark'").replace('127.0.0.1:8000','127.0.0.1:8021').replace("root/'backend/data/agentops.db'","root/'backend/data/v11-regression/copy.db'").replace('v10-evaluation-results.json','v11-evaluation-results.json')
try:exec(compile(text,str(root/'scripts/v10-regression.py'),'exec'))
finally:server.should_exit=True;thread.join(30)
