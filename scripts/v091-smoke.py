"""Invoke local isolated smoke API; collect real persisted Mock cases, not canned responses."""
import json,time,urllib.request
from pathlib import Path
root=Path(__file__).resolve().parents[1];token=(root/'backend/.local-token').read_text().strip()
def api(path,body=None):
 request=urllib.request.Request('http://127.0.0.1:8000/api/validation/smoke/'+path,data=None if body is None else json.dumps(body).encode(),headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'})
 with urllib.request.urlopen(request,timeout=60) as response:return json.load(response)
p=api('prepare',{});run=api('runs',{})
for _ in range(600):
 run=api('runs/'+run['id'])
 if run['status'] not in ('queued','running'):break
 time.sleep(.1)
assert run['status']=='completed',run['result']
assert len(run['cases'])==12 and run['result']['external_calls']==0
api('runs/'+run['id']+'/reviews',{'case_id':'fact-code','verdict':'correct','notes':'Local review: literal NS-8841 evidence and page checked; Mock only.'})
run=api('runs/'+run['id']);assert run['human_reviews']
readiness=api('readiness',{'mode':'REAL_DRY_RUN'})
report={'run':run,'manifest':p,'readiness':readiness,'external_generation_calls':0,'external_embedding_calls':0,'sqlite_reload':True,'human_review_persisted':True,'billing':'NOT VERIFIED'}
(root/'docs/v091-smoke-results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
print('Offline smoke:',run['result']['quality']['hybrid']['answer_correct'],'/12; external calls: 0')
for c in run['cases']:print(c['case_id'],c['result']['answer_correct'],c['result']['verification']['status'])
