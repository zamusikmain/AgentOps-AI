import sys,json,tempfile,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from fastapi.testclient import TestClient
from sqlalchemy import select,func
from app.config import Settings
from app.main import create_app
from app.db import Base,ToolNote
root=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(dir=root/'backend/.pytest-work',prefix='v03-example-') as folder:
 settings=Settings(_env_file=None,llm_provider='mock',api_token='example-local-token',database_url=f'sqlite:///{Path(folder).as_posix()}/example.db',checkpoint_database_path=Path(folder)/'checkpoints.db')
 app=create_app(settings);Base.metadata.create_all(app.state.engine)
 with TestClient(app,headers={'Authorization':'Bearer example-local-token'}) as c:
  results=[]
  for tool,args,decision in [('calculator',{'expression':'(10+2)/3'},None),('mcp_knowledge_search',{'query':'RBAC'},None),('save_note',{'text':'Approved v0.3 example note'},'approve'),('save_note',{'text':'Rejected note'},'reject'),('http_fetch',{'url':'https://example.com/'},None)]:
   a=c.post('/api/agents',json={'name':tool,'role':'executor','instructions':'Use only permitted tools.','model':'gemini-3.5-flash-lite','tools':[tool],'max_steps':4,'max_tokens':2048}).json()
   t=c.post('/api/tasks',json={'title':tool,'prompt':'[MOCK_TOOL:'+tool+'] '+json.dumps(args),'agent_id':a['id']}).json()
   rid=c.post('/api/tasks/'+t['id']+'/run').json()['id'];decided=False
   for _ in range(300):
    calls=c.get('/api/tool-calls?run_kind=single&run_id='+rid).json()['items']
    if decision and calls and calls[0]['status']=='awaiting_approval' and not decided:
     with app.state.sessions() as db:assert db.scalar(select(func.count()).select_from(ToolNote))==(1 if decision=='reject' else 0)
     assert c.post('/api/tool-calls/'+calls[0]['id']+'/decision',json={'decision':decision}).status_code==200;decided=True
    run=c.get('/api/executions/'+rid).json()
    if run['status'] not in ('queued','running'):break
    time.sleep(.05)
   results.append({'tool':tool,'run':run,'calls':c.get('/api/tool-calls?run_kind=single&run_id='+rid).json()['items'],'events':c.get('/api/executions/'+rid+'/events').json()['items']})
  report={'provider':'mock','real_gemini_requests':0,'mcp':c.get('/api/mcp-servers').json(),'examples':results}
  (root/'docs/v03-tool-examples.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
  print(json.dumps([{'tool':r['tool'],'status':r['run']['status'],'error':r['run']['error'],'result':r['calls'][0]['result'] if r['tool']!='http_fetch' else {'http_status':(r['calls'][0]['result'] or {}).get('http_status'),'response_bytes':len((r['calls'][0]['result'] or {}).get('body','').encode())}} for r in results],ensure_ascii=True))
