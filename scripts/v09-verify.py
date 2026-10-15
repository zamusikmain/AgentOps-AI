"""Quality validation via v0.9 orchestration, old fixtures and baselines immutable."""
import urllib.request,json,time,sqlite3
from pathlib import Path
root=Path(__file__).resolve().parents[1];token=(root/'backend/.local-token').read_text().strip()
def api(path,body=None):
 req=urllib.request.Request('http://127.0.0.1:8000/api/'+path,data=None if body is None else json.dumps(body).encode(),headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'})
 with urllib.request.urlopen(req,timeout=60) as r:return json.load(r)
reports={}
for version,identifier,total in [('v1','original40',120),('v2','expanded64',192)]:
 installed=api('validation/prepare/'+version,{})
 validation=api('validation/runs',{'mode':'MOCK_ONLY','provider':'mock','model':'mock-v1','agent_id':installed['agent_id'],'dataset_id':identifier,'retrieval_modes':['lexical','semantic','hybrid'],'max_requests':total})
 for _ in range(1000):
  validation=api('validation/runs/'+validation['id'])
  if validation['status'] not in ('queued','running'):break
  time.sleep(.2)
 assert validation['status']=='completed',validation['result']
 run=api('evaluation/runs/'+validation['evaluation_id']);cases=[]
 for offset in range(0,total,50):cases.extend(c['result'] for c in api(f'evaluation/runs/{run["id"]}/cases?offset={offset}&limit=50')['items'])
 assert len(cases)==total
 comparisons={}
 for baseline in ('v07','v08'):
  previous=json.loads((root/f'docs/{baseline}-evaluation-results.json').read_text(encoding='utf8'))['reports'][version]['run']
  comparisons[baseline]=api('llm/comparisons',{'baseline_id':previous['id'],'current_id':run['id']});assert comparisons[baseline]['result']['passed']
 with sqlite3.connect(root/'backend/data/agentops.db') as db:
  assert json.loads(db.execute('SELECT metrics FROM evaluation_runs WHERE id=?',(run['id'],)).fetchone()[0])==run['metrics']
  assert db.execute('SELECT count(*) FROM evaluation_cases WHERE run_id=?',(run['id'],)).fetchone()[0]==total
 reports[version]={'run':run,'cases':cases,'validation':validation,'comparisons':comparisons,'sqlite_reread':True}
 print(version,run['metrics']['hybrid']['answer_correct'],'/',run['metrics']['hybrid']['cases'],'offline quality')
validation=api('validation/runs',{'mode':'MOCK_ONLY','provider':'mock','model':'mock-v1','agent_id':installed['agent_id'],'dataset_id':'holdout12','retrieval_modes':['lexical','semantic','hybrid'],'max_requests':36})
for _ in range(1000):
 validation=api('validation/runs/'+validation['id'])
 if validation['status'] not in ('queued','running'):break
 time.sleep(.2)
assert validation['status']=='completed',validation['result']
run=api('evaluation/runs/'+validation['evaluation_id']);cases=[c['result'] for c in api(f'evaluation/runs/{run["id"]}/cases?limit=50')['items']];assert len(cases)==36
from sys import path
path.insert(0,str(root/'backend'))
from app.evaluation_metrics import aggregate
holdout_baselines={}
for baseline in ('v07','v08'):
 old=json.loads((root/f'docs/{baseline}-evaluation-results.json').read_text(encoding='utf8'))['reports']['v2']['cases']
 measured=aggregate([c for c in old if c.get('split')=='holdout']);holdout_baselines[baseline]=measured
 for mode in ('lexical','semantic','hybrid'):
  for metric in ('answer_correct','correct_abstention_rate','false_abstention_rate','unsupported_answer_rate','citation_validity_rate'):
   assert run['metrics'][mode][metric]==measured[mode][metric],(baseline,mode,metric)
reports['holdout']={'run':run,'cases':cases,'validation':validation,'baseline_quality':holdout_baselines,'quality_regression':False,'sqlite_reread':True}
print('holdout',run['metrics']['hybrid']['answer_correct'],'/',12,'offline quality')
(root/'docs/v09-evaluation-results.json').write_text(json.dumps({'reports':reports,'real_generation_requests':0,'real_embedding_requests':0},ensure_ascii=False,indent=2),encoding='utf8')
