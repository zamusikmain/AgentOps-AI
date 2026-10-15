import sys,tempfile,time,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from app.main import create_app
from app.config import Settings
from app.db import Base
from fastapi.testclient import TestClient
root=Path(__file__).resolve().parents[1]
questions=['Какой внутренний код проекта Aurora Portal?','Сколько дней хранятся журналы аудита?','Какое время реакции на инцидент P1?','Какие RPO и RTO установлены?','Сколько стоит подписка Aurora Portal?']
with tempfile.TemporaryDirectory(dir=root/'backend/.pytest-work',prefix='rag-') as directory:
 d=Path(directory);s=Settings(_env_file=None,llm_provider='mock',api_token='rag-test',local_mcp_enabled=False,database_url=f'sqlite:///{d.as_posix()}/rag.db',checkpoint_database_path=d/'checkpoints.db',knowledge_storage_path=d/'documents')
 app=create_app(s);Base.metadata.create_all(app.state.engine)
 with TestClient(app,headers={'Authorization':'Bearer rag-test'}) as c:
  doc=c.post('/api/knowledge/documents?name=AgentOps_RAG_Test_Corporate_Policy.pdf',content=(root/'docs/fixtures/AgentOps_RAG_Test_Corporate_Policy.pdf').read_bytes()).json()
  for _ in range(200):
   doc=c.get('/api/knowledge/documents/'+doc['id']).json()
   if doc['status']!='indexing':break
   time.sleep(.05)
  print('DOC',json.dumps(doc))
  a=c.post('/api/agents',json={'name':'RAG tester','role':'researcher','instructions':'Answer only from PDFs.','model':'gemini-3.5-flash-lite','tools':['knowledge_search'],'document_ids':[doc['id']],'max_steps':1,'max_tokens':2048}).json()
  for q in questions:
   body={'agent_id':a['id'],'question':q,'provider':'mock'}
   run=c.post('/api/knowledge/ask',json=body).json()
   for _ in range(100):
    r=c.get('/api/executions/'+run['id']).json()
    if r['status'] not in ('queued','running'):break
    time.sleep(.03)
   print('ANSWER',json.dumps({'question':q,'status':r['status'],'error':r['error'],'result':json.loads(r['result']) if r['result'] else None},ensure_ascii=False))
