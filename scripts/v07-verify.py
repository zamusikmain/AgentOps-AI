"""Explicit offline API runs. Preserves v0.6 artifacts and histories."""
import urllib.request,json,time,sqlite3
from pathlib import Path
root=Path(__file__).resolve().parents[1];token=(root/'backend/.local-token').read_text().strip()
def api(path,body=None):
    req=urllib.request.Request('http://127.0.0.1:8000/api/'+path,data=None if body is None else json.dumps(body).encode(),headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=60) as r:return json.load(r)
reports={}
for version in ('v1','v2'):
    installed=api('evaluation/install?version='+version,{})
    run=api('evaluation/runs',{'agent_id':installed['agent_id'],'provider':'mock','dataset_version':version})
    for _ in range(600):
        run=api('evaluation/runs/'+run['id'])
        if run['status'] not in ('queued','running'):break
        time.sleep(.2)
    assert run['status']=='completed',(version,run.get('error'))
    total=120 if version=='v1' else 192;cases=[]
    for start in range(0,total,50):cases.extend(c['result'] for c in api(f'evaluation/runs/{run["id"]}/cases?offset={start}&limit=50')['items'])
    assert len(cases)==total
    with sqlite3.connect(root/'backend/data/agentops.db') as db:
        saved=json.loads(db.execute('SELECT metrics FROM evaluation_runs WHERE id=?',(run['id'],)).fetchone()[0]);assert saved==run['metrics']
        assert db.execute('SELECT count(*) FROM evaluation_cases WHERE run_id=?',(run['id'],)).fetchone()[0]==total
    reports[version]={'run':run,'cases':cases,'sqlite_reread':True}
    print(version,run['metrics']['hybrid']['answer_correct'],'/',run['metrics']['hybrid']['cases'],'offline cases')
(root/'docs/v07-evaluation-results.json').write_text(json.dumps({'reports':reports,'real_generation_requests':0,'real_embedding_requests':0},ensure_ascii=False,indent=2),encoding='utf8')
