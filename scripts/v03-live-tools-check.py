import json,time,sqlite3,hashlib
from pathlib import Path
import httpx
root=Path(__file__).resolve().parents[1]
marker=root/'docs/v03-live-tools-verification.json'
if marker.exists():raise SystemExit('Existing live marker: do not rerun')
env=root/'backend/.env'; before=hashlib.sha256(env.read_bytes()).hexdigest()
token=(root/'backend/.local-token').read_text().strip()
c=httpx.Client(base_url='http://127.0.0.1:8000',headers={'Authorization':'Bearer '+token},timeout=30)
def api(method,path,body=None):
 r=c.request(method,path,json=body);r.raise_for_status();return r.json()
db=sqlite3.connect('file:'+str(root/'backend/data/agentops.db').replace('\\','/')+'?mode=ro',uri=True)
db.row_factory=sqlite3.Row
report={'model':'gemini-3.5-flash-lite','max_new_requests':6,'scenarios':[],'env_unchanged':True}
def save():marker.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
api('GET','/health');report['mcp']=api('GET','/api/mcp-servers');save()
scenarios=[('Calculator','Compute (1250 + 375) / 5 accurately using an appropriate available tool. Report the result in Russian.'),('Local MCP knowledge','Look up the bundled corporate portal documentation through the local MCP server. State the exact audit fields required by that document and cite its document_id. Do not use the internet or invent facts.'),('Human approval','Request saving this exact local test note: AgentOps v0.3 live HITL verification. Use the available note tool. Never bypass human approval.')]
for title,prompt in scenarios:
 used=sum(sum(e['kind']=='model_requested' for e in s.get('events',[])) for s in report['scenarios'])
 if used+2>6:break
 a=api('POST','/api/agents',{'name':'Live v0.3 '+title,'role':'executor','instructions':'Choose the appropriate permitted tool yourself when needed. Make at most one tool call, then give a concise answer based on its returned result. No external search. Do not disclose credentials.','model':report['model'],'tools':['calculator','utc_time','mcp_knowledge_search','save_note'],'max_steps':2,'max_tokens':768})
 t=api('POST','/api/tasks',{'title':'Live v0.3 '+title,'prompt':prompt,'agent_id':a['id']})
 s={'title':title,'task_id':t['id'],'state':'launch_intent'};report['scenarios'].append(s);save()
 r=api('POST','/api/tasks/'+t['id']+'/run');s['run_id']=r['id'];save()
 deadline=time.monotonic()+185
 while time.monotonic()<deadline:
  s['run']=api('GET','/api/executions/'+r['id']);s['calls']=api('GET','/api/tool-calls?run_kind=single&run_id='+r['id'])['items'];s['events']=api('GET','/api/executions/'+r['id']+'/events')['items'];save()
  if any(x['status']=='awaiting_approval' for x in s['calls']):
   cid=s['calls'][0]['id'];s['notes_before_decision']=db.execute('select count(*) from tool_notes where call_id=?',(cid,)).fetchone()[0];s['state']='awaiting_human';save();print(json.dumps({'awaiting':cid,'run_id':r['id'],'notes':s['notes_before_decision']}));raise SystemExit(0)
  if s['run']['status'] not in ('queued','running'):break
  time.sleep(.3)
 s['state']='finished';save();print(json.dumps({'title':title,'status':s['run']['status'],'error':s['run']['error'],'result':s['run']['result'],'calls':s['calls']},ensure_ascii=False))
 if s['run']['status']!='completed':break
report['env_unchanged']=hashlib.sha256(env.read_bytes()).hexdigest()==before;save()
