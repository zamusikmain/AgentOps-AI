"""Local status only; never discovers or calls an AI model."""
import urllib.request,json,sqlite3
from pathlib import Path
root=Path(__file__).resolve().parents[1];token=(root/'backend/.local-token').read_text().strip()
def get(path):
 request=urllib.request.Request('http://127.0.0.1:8000'+path,headers={'Authorization':'Bearer '+token})
 with urllib.request.urlopen(request) as r:return json.load(r)
assert get('/health')['status']=='ok';assert get('/openapi.json')['info']['version']=='0.9.1'
c=get('/api/llm/configuration');assert not c['external_api_enabled'] and not c['paid_operations_enabled']
with sqlite3.connect(root/'backend/data/agentops.db') as db:assert db.execute('SELECT version_num FROM alembic_version').fetchone()[0]=='008'
with urllib.request.urlopen('http://127.0.0.1:3000/') as r:assert r.status==200
body={'mode':'REAL_EXECUTION','provider':'gemini','model':'gemini-3.5-flash-lite','dataset_id':'original40'}
request=urllib.request.Request('http://127.0.0.1:8000/api/validation/readiness',data=json.dumps(body).encode(),headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'})
with urllib.request.urlopen(request) as r:plan=json.load(r)
assert plan['status']=='BLOCKED' and any(x['code']=='real_execution_disabled' for x in plan['blockers'])
print('Local v0.9.1 healthy; real/external/paid execution disabled; SQLite 008.')
