"""Print diagnostics only after replacing known local passwords and long credentials."""
import json,sys,re
from pathlib import Path
root=Path(__file__).resolve().parents[1];secrets=[]
for name in ('auth-development-credentials.local.json','auth-e2e-credentials.local.json','auth-all-browser-credentials.local.json','api-identities.local.json'):
 path=root/'backend/data'/name
 if path.exists():
  for r in json.loads(path.read_text(encoding='utf8')):
   for key in ('password','token'):
    if isinstance(r.get(key),str) and len(r[key])>=12:secrets.append(r[key])
secrets+=['V7!secure-test.Raven_984','Q9!different-test.Oak_761','R8!generated-E2E-Only_742','K3!changed-E2E-Only_918']
path=root/(sys.argv[1] if len(sys.argv)>1 else 'docs/v10-playwright.txt');raw=path.read_text(encoding='utf8',errors='replace')
for value in sorted(set(secrets),key=len,reverse=True):raw=raw.replace(value,'[REDACTED]')
raw=re.sub(r'Bearer\s+[A-Za-z0-9_-]+','Bearer [REDACTED]',raw)
print('\n'.join(raw.splitlines()[-100:]))
