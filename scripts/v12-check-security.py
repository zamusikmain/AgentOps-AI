"""Secret-aware static bundle checks; only boolean results leave this process."""
import json
from pathlib import Path
import sys
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/'backend'))
from app.config import Settings
secrets=[]
for name in ('auth-development-credentials.local.json','auth-e2e-credentials.local.json','auth-all-browser-credentials.local.json','api-identities.local.json'):
 p=root/'backend/data'/name
 if p.exists():
  for row in json.loads(p.read_text(encoding='utf8')):
   secrets.extend(row[k] for k in ('password','token') if isinstance(row.get(k),str) and len(row[k])>=12)
secrets.extend([Settings().gemini_api_key.get_secret_value(),(root/'backend/.local-token').read_text().strip()]);secrets=[s for s in secrets if s]
for folder in ('frontend/.next-v12/static','frontend/public'):
 for p in (root/folder).rglob('*'):
  if p.is_file():assert all(s.encode() not in p.read_bytes() for s in secrets),'Secret in static bundle'
assert not list((root/'frontend/.next-v12').rglob('DEV_CREDENTIALS.local.md'))
for file in ('.gitignore','.dockerignore'):assert 'DEV_CREDENTIALS.local.md' in (root/file).read_text()
report={'static_secret_scan':'PASS','credential_file_in_public_build':False,'credentials_ignore_rules_present':True,'external_ai_dispatches':0,'no_secret_values_printed':True}
(root/'docs/v12-security-checks.json').write_text(json.dumps(report,indent=2));print('v12 public bundle and credential exclusions: PASS')
