"""Local, explicit Mock evaluation and same-question v0.5 comparison; no external calls."""
import urllib.request,json,time
from pathlib import Path
root=Path(__file__).resolve().parents[1];token=(root/'backend/.local-token').read_text().strip()
def api(path,body=None):
    req=urllib.request.Request('http://127.0.0.1:8000/api/'+path,data=None if body is None else json.dumps(body).encode(),headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=50) as response:return json.load(response)
installed=api('evaluation/install',{});run=api('evaluation/runs',{'agent_id':installed['agent_id'],'provider':'mock'})
for _ in range(600):
    run=api('evaluation/runs/'+run['id'])
    if run['status'] not in ('queued','running'):break
    time.sleep(.2)
assert run['status']=='completed',run.get('error')
results=[]
for start in range(0,120,50):results.extend(c['result'] for c in api(f'evaluation/runs/{run["id"]}/cases?offset={start}&limit=50')['items'])
assert len(results)==120 and api('evaluation/runs/'+run['id'])['metrics']==run['metrics']
baseline=json.loads((root/'docs/v05-comparison.json').read_text(encoding='utf8'));comparison=[]
for case in baseline['questions']:
    # Scope only the original PDF, matching v0.5, not the synthetic evaluation documents.
    docid=baseline['document']['id'];q=case['question'];body={'agent_id':installed['agent_id'],'document_ids':[docid],'question':q,'provider':'mock','search_mode':'hybrid'}
    execution=api('knowledge/ask',body)
    for _ in range(200):
        execution=api('executions/'+execution['id'])
        if execution['status'] not in ('queued','running'):break
        time.sleep(.05)
    assert execution['status']=='completed',execution.get('error')
    answer=json.loads(execution['result']);comparison.append({'label':case['label'],'question':q,'v05_answer':case['answer'],'v06_answer':answer,'run_id':execution['id']})
report={'evaluation_run':run,'cases':results,'same_five_questions':comparison,'real_generation_requests':0,'real_embedding_requests':0,'sqlite_history_reread':True}
(root/'docs/v06-evaluation-results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
print('Completed',len(results),'Mock cases; metrics and five-question comparison saved. No real API calls.')
