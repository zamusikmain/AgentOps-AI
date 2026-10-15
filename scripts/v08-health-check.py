import json,urllib.request,sqlite3
from pathlib import Path
root=Path.cwd();token=(root/'backend/.local-token').read_text().strip()
with urllib.request.urlopen('http://127.0.0.1:8000/health') as r:assert r.status==200
request=urllib.request.Request('http://127.0.0.1:8000/api/llm/configuration',headers={'Authorization':'Bearer '+token})
with urllib.request.urlopen(request) as r:config=json.load(r)
assert not config['external_api_enabled'] and not config['paid_operations_enabled'] and not config['fallback_enabled']
with urllib.request.urlopen('http://127.0.0.1:3000/') as r:assert r.status==200
with sqlite3.connect(root/'backend/data/agentops.db') as db:assert db.execute('SELECT version_num FROM alembic_version').fetchone()[0]=='007'
print('Backend and frontend healthy; external/paid/fallback disabled; SQLite head 007.')
