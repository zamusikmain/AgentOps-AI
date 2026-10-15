import asyncio,json,socket,time
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select,func
from app.config import Settings
from app.main import create_app
from app.db import Base,ToolNote
from app.providers import MockProvider,Reply
from app.tools import invoke,declarations
from app.http_tool import validate_url,public_addresses,fetch,FetchError
from app.tool_execution import mask
from app.mcp_client import LocalMCP,MCPError
TOKEN='v03-test-token'
@pytest.fixture
def settings(tmp_path):
 return Settings(_env_file=None,database_url=f'sqlite:///{(tmp_path/"tools.db").as_posix()}',checkpoint_database_path=tmp_path/'checkpoints.db',api_token=TOKEN,llm_provider='mock',local_mcp_enabled=False)
def client(settings,provider=None):
 app=create_app(settings,provider);Base.metadata.create_all(app.state.engine)
 return TestClient(app,headers={'Authorization':'Bearer '+TOKEN})
def task(c,name='calculator',args=None,allowed=None):
 if args is None:args={'expression':'(10+2)/3'}
 a=c.post('/api/agents',json={'name':'Tool tester','role':'executor','instructions':'Use permitted tools only.','model':'gemini-3.5-flash-lite','tools':[name] if allowed is None else allowed,'max_steps':4,'max_tokens':2048}).json()
 t=c.post('/api/tasks',json={'title':'Tool test '+name,'prompt':'[MOCK_TOOL:'+name+'] '+json.dumps(args),'agent_id':a['id']}).json()
 return c.post('/api/tasks/'+t['id']+'/run').json()['id']
def wait(c,rid):
 for _ in range(250):
  r=c.get('/api/executions/'+rid).json()
  if r['status'] not in ('queued','running'):return r
  time.sleep(.015)
 pytest.fail('Run did not finish')
def calls(c,rid):return c.get('/api/tool-calls?run_kind=single&run_id='+rid).json()['items']
def pending(c,rid):
 for _ in range(250):
  rows=calls(c,rid)
  if rows and rows[0]['status']=='awaiting_approval':return rows[0]
  time.sleep(.01)
 pytest.fail('Approval not requested')
@pytest.mark.parametrize('name,args,expected',[
 ('calculator',{'expression':'(10+2)/3'},{'value':4}),
 ('datetime',{'operation':'add_days','date':'2026-10-11','days':2},{'date':'2026-10-13T00:00:00+00:00'}),
 ('datetime',{'operation':'difference_days','date':'2026-10-11','other_date':'2026-10-13'},{'days':2}),
 ('json_validator',{'document':'{"x":3}','schema':{'type':'object','properties':{'x':{'type':'integer'}},'required':['x'],'additionalProperties':False}},{'valid':True,'errors':[]}),
 ('json_validator',{'document':'bad'},{'valid':False,'errors':['invalid_json']})])
def test_real_builtin(name,args,expected):assert invoke(name,args,[name])==expected
@pytest.mark.parametrize('args',[{}, {'expression':2},{'expression':'1','extra':'x'}])
def test_strict_parameters(args):
 with pytest.raises(ValueError,match='tool_invalid_arguments'):invoke('calculator',args,['calculator'])
def test_json_schema_never_fetches_refs():
 with pytest.raises(ValueError):invoke('json_validator',{'document':'{}','schema':{'$ref':'https://example.com/schema'}},['json_validator'])
def test_search_scope():
 r=invoke('knowledge_search',{'query':'RBAC'},['knowledge_search']);assert r['matches'] and r['scope']=='bundled-test-documents'
 with pytest.raises(ValueError):invoke('knowledge_search',{'query':'x','path':'../../.env'},['knowledge_search'])
def test_declarations_and_mask():
 assert [d['name'] for d in declarations(['calculator'])]==['calculator']
 assert mask({'password':'test','text':'Bearer abc.def secret=hello'})=={'password':'[REDACTED]','text':'[REDACTED] [REDACTED]'}
 assert mask('known-key',('known-key',))=='[REDACTED]'
@pytest.mark.parametrize('url',['http://example.com/','https://example.com/other','https://user:password@example.com/','https://127.0.0.1/','https://169.254.169.254/','https://example.com:444/','file:///etc/passwd'])
def test_exact_url_allowlist(url):
 with pytest.raises(ValueError):validate_url(url,['https://example.com/'])
@pytest.mark.parametrize('ip',['127.0.0.1','10.0.0.1','192.168.1.1','169.254.169.254','::1','fc00::1','::ffff:127.0.0.1','100.64.0.1','0.0.0.0'])
def test_ssrf_dns(monkeypatch,ip):
 monkeypatch.setattr(socket,'getaddrinfo',lambda *a,**k:[(socket.AF_INET,socket.SOCK_STREAM,6,'',(ip,443))])
 with pytest.raises(FetchError,match='http_address_denied'):public_addresses('example.com')
def test_mixed_dns_denied(monkeypatch):
 monkeypatch.setattr(socket,'getaddrinfo',lambda *a,**k:[(2,1,6,'',('93.184.216.34',443)),(2,1,6,'',('10.0.0.1',443))])
 with pytest.raises(FetchError):public_addresses('example.com')
def test_fetch_pinning_redirect_size(monkeypatch):
 import app.http_tool as http
 monkeypatch.setattr(http,'public_addresses',lambda host:['93.184.216.34'])
 class Response:
  status=200
  def getheader(self,name,default=None):return {'Content-Type':'text/plain'}.get(name,default)
  def read(self,n):return b'hello'
 class Connection:
  def __init__(self,host,address):assert host=='example.com' and address=='93.184.216.34'
  def request(self,*a,**k):pass
  def getresponse(self):return Response()
  def close(self):pass
 monkeypatch.setattr(http,'PinnedHTTPS',Connection)
 assert fetch('https://example.com/',['https://example.com/'])['body']=='hello'
 Response.status=302;Response.getheader=lambda self,name,default=None:'https://127.0.0.1/' if name=='Location' else default
 with pytest.raises(FetchError,match='http_url_denied'):fetch('https://example.com/',['https://example.com/'])
 Response.status=200;Response.getheader=lambda self,name,default=None:'text/plain' if name=='Content-Type' else default;Response.read=lambda self,n:b'x'*n
 with pytest.raises(FetchError,match='tool_result_limit'):fetch('https://example.com/',['https://example.com/'])
def test_single_history(settings):
 with client(settings) as c:
  rid=task(c);r=wait(c,rid);assert r['status']=='completed',r
  rows=calls(c,rid);assert rows[0]['result']=={'value':4} and rows[0]['arguments']=={'expression':'(10+2)/3'} and rows[0]['duration_ms']>=0
  assert 'untrusted_tool_data' in r['result']
 with client(settings) as c:assert calls(c,rid)==rows
@pytest.mark.parametrize('name,args,allowed,error',[
 ('calculator',{'expression':'2'},[],'tool_denied'),('calculator',{'expression':'1','extra':1},['calculator'],'tool_invalid_arguments'),
 ('calculator',{'expression':'1/0'},['calculator'],'tool_execution_error'),('http_fetch',{'url':'https://127.0.0.1/'},['http_fetch'],'http_url_denied')])
def test_saved_errors(settings,name,args,allowed,error):
 with client(settings) as c:
  rid=task(c,name,args,allowed);assert wait(c,rid)['error']==error
  row=calls(c,rid)[0];assert row['status']=='failed' and row['error']==error
@pytest.mark.parametrize('decision,status',[('approve','completed'),('reject','failed')])
def test_approve_reject(settings,decision,status):
 with client(settings) as c:
  rid=task(c,'save_note',{'text':'A reviewed note'});row=pending(c,rid)
  with c.app.state.sessions() as db:assert db.scalar(select(func.count()).select_from(ToolNote))==0
  assert c.post('/api/tool-calls/'+row['id']+'/decision',json={'decision':decision}).status_code==200
  r=wait(c,rid);assert r['status']==status,r
  assert c.post('/api/tool-calls/'+row['id']+'/decision',json={'decision':'approve'}).status_code==409
  with c.app.state.sessions() as db:assert db.scalar(select(func.count()).select_from(ToolNote))==(1 if decision=='approve' else 0)
  assert calls(c,rid)[0]['decision']==decision
class RepeatWrite(MockProvider):
 async def generate(self,snapshot,messages,remaining_tokens):
  if len(messages)<5:
   args={'text':'Only once'}
   return Reply(calls=[{'name':'save_note','args':args}],content={'role':'model','parts':[{'function_call':{'name':'save_note','args':args}}]},input_tokens=2,output_tokens=2)
  return Reply(text='Done',input_tokens=2,output_tokens=2)
def test_write_replay(settings):
 with client(settings,RepeatWrite()) as c:
  rid=task(c,'save_note',{'text':'ignored'});row=pending(c,rid);c.post('/api/tool-calls/'+row['id']+'/decision',json={'decision':'approve'})
  assert wait(c,rid)['status']=='completed';assert len(calls(c,rid))==1
  with c.app.state.sessions() as db:assert db.scalar(select(func.count()).select_from(ToolNote))==1
  assert any(e['kind']=='tool_reused' for e in c.get('/api/executions/'+rid+'/events').json()['items'])
def test_cancel_pending(settings):
 with client(settings) as c:
  rid=task(c,'save_note',{'text':'Must not save'});row=pending(c,rid);c.post('/api/executions/'+rid+'/cancel')
  assert wait(c,rid)['status']=='cancelled';assert c.post('/api/tool-calls/'+row['id']+'/decision',json={'decision':'approve'}).status_code==409
  assert calls(c,rid)[0]['status']=='cancelled'
  with c.app.state.sessions() as db:assert db.scalar(select(func.count()).select_from(ToolNote))==0
def test_approval_timeout(settings):
 settings.approval_timeout_seconds=1
 with client(settings) as c:
  rid=task(c,'save_note',{'text':'never approved'});assert wait(c,rid)['error']=='tool_timeout'
def test_tool_timeout(settings):
 with client(settings) as c:
  executor=c.app.state.tool_executor;executor.mcp.status='available'
  async def slow(*args):await asyncio.sleep(10)
  executor.mcp.call=slow;executor.definitions['mcp_local_time']={**executor.definitions['mcp_local_time'],'timeout_seconds':.05}
  rid=task(c,'mcp_local_time',{});assert wait(c,rid)['error']=='tool_timeout'
def test_real_mcp():
 async def scenario():
  mcp=LocalMCP()
  try:
   tools=await mcp.discover();assert {t['name'] for t in tools}=={'local_time','knowledge_search'}
   assert 'utc' in await mcp.call('mcp_local_time',{})
   assert (await mcp.call('mcp_knowledge_search',{'query':'RBAC','limit':2}))['matches']
   with pytest.raises(MCPError):await mcp.call('unknown',{})
   mcp.process.kill();await mcp.process.wait()
   with pytest.raises(MCPError):await mcp.call('mcp_local_time',{})
   assert mcp.status=='unavailable'
  finally:await mcp.close()
 asyncio.run(scenario())
def test_mcp_api_runner(settings):
 settings.local_mcp_enabled=True
 with client(settings) as c:
  assert c.get('/api/mcp-servers').json()['items'][0]['status']=='available'
  assert c.post('/api/mcp-servers/unknown/discover').status_code==404
  rid=task(c,'mcp_knowledge_search',{'query':'RBAC'});assert wait(c,rid)['status']=='completed';assert calls(c,rid)[0]['result']['matches']

def test_workflow_real_tool_and_approval(settings):
 from test_workflows import seed,launch,wait as wait_workflow
 from app.db import WorkflowStep
 with client(settings) as c:
  agents,w=seed(c)
  body={k:v for k,v in agents[2].items() if k not in ('id','created_at')};body['tools']=['save_note'];c.put('/api/agents/'+agents[2]['id'],json=body)
  r=c.post('/api/workflows/'+w['id']+'/run',json={'title':'Workflow tool','prompt':'[MOCK_TOOL:save_note] {"text":"Reviewed workflow note"}'}).json();rid=r['id']
  row=None
  for _ in range(250):
   rows=c.get('/api/tool-calls?run_kind=workflow&run_id='+rid).json()['items']
   if rows and rows[0]['status']=='awaiting_approval':row=rows[0];break
   time.sleep(.01)
  assert row and row['stage_id']
  c.post('/api/tool-calls/'+row['id']+'/decision',json={'decision':'approve'})
  assert wait_workflow(c,rid)['status']=='completed'
  with c.app.state.sessions() as db:
   assert db.scalar(select(func.count()).select_from(ToolNote))==1
   assert db.get(WorkflowStep,row['stage_id']).status=='completed'

def test_tool_call_limits(settings):
 class RepeatCalculator(MockProvider):
  async def generate(self,*a):return Reply(calls=[{'name':'calculator','args':{'expression':'2+3'}}],content={'role':'model','parts':[{'function_call':{'name':'calculator','args':{'expression':'2+3'}}}]},input_tokens=2,output_tokens=2)
 with client(settings,RepeatCalculator()) as c:
  a=c.post('/api/agents',json={'name':'Repeater','role':'executor','instructions':'x','model':'x','tools':['calculator'],'max_steps':12}).json()
  t=c.post('/api/tasks',json={'title':'bounded','prompt':'x','agent_id':a['id']}).json();rid=c.post('/api/tasks/'+t['id']+'/run').json()['id']
  assert wait(c,rid)['error']=='tool_limit'
  rows=calls(c,rid);assert len(rows)==5 and sum(r['status']=='completed' for r in rows)==4

def test_restart_does_not_execute_pending_write(settings):
 with client(settings) as c:
  rid=task(c,'save_note',{'text':'never save'});pending(c,rid)
 # Shutdown cancels pending action. Reopening must not execute it.
 with client(settings) as c:
  assert calls(c,rid)[0]['status']=='cancelled'
  with c.app.state.sessions() as db:assert db.scalar(select(func.count()).select_from(ToolNote))==0

def test_live_http_fetch_public_only():
 # This is covered separately by an explicit local verification script, not by CI network tests.
 assert validate_url('https://example.com/',['https://example.com/']).hostname=='example.com'
