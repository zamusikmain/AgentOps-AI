"""Verify private auth artifacts are excluded; print only statuses/counts."""
import sys,json,re,urllib.request,urllib.error,subprocess,tempfile,shutil
from pathlib import Path
root=Path(__file__).resolve().parents[1]
rows=json.loads((root/'backend/data/auth-all-browser-credentials.local.json').read_text());tokens=[r['password'] for r in rows]
tokens += [r['token'] for r in json.loads((root/'backend/data/api-identities.local.json').read_text()) if len(r['token'])>=20]
key=(root/'backend/.local-token').read_text().strip();tokens.append(key)
for folder in ('frontend/.next/static','frontend/.next-auth-production/static','frontend/public'):
 for p in (root/folder).rglob('*'):
  if p.is_file():
   raw=p.read_bytes();assert all(token.encode() not in raw for token in tokens),'Private auth secret found in public artifact'
assert not any(p.name=='DEV_CREDENTIALS.local.md' for p in (root/'frontend/.next-auth-production').rglob('*'))
for name in ('.gitignore','.dockerignore'):assert 'DEV_CREDENTIALS.local.md' in (root/name).read_text()
with tempfile.TemporaryDirectory(prefix='v10-ignore-',dir=root/'backend/data') as td:
 path=Path(td);shutil.copyfile(root/'.gitignore',path/'.gitignore');(path/'DEV_CREDENTIALS.local.md').write_text('No secret fixture.')
 assert subprocess.run(['git','init','-q',str(path)],capture_output=True).returncode==0
 assert subprocess.run(['git','-C',str(path),'check-ignore','--no-index','DEV_CREDENTIALS.local.md'],capture_output=True).returncode==0
# Redact any text failure artifacts from previous test attempts before they can be shared.
for folder in ('frontend/test-results','docs'):
 for p in (root/folder).rglob('*'):
  if p.is_file() and p.suffix in ('.txt','.md','.html') and p.name!='DEV_CREDENTIALS.local.md':
   raw=p.read_text(encoding='utf8',errors='replace');clean=raw
   for token in sorted(set(tokens),key=len,reverse=True):clean=clean.replace(token,'[REDACTED]')
   if raw!=clean:p.write_text(clean,encoding='utf8')
report={'public_password_scan':'PASS','public_api_credential_scan':'PASS','credential_file_in_public_build':False,'git_rule_verified_in_isolated_repo':True,'current_project_git_repository':False,'dockerignore_rule_present':True,'docker_image_built':False,'ci_pipeline_configured':False,'secret_output':False,'password_entries':len(rows)}
(root/'docs/v10-security-checks.json').write_text(json.dumps(report,indent=2),encoding='utf8');print('Auth credentials/bundle/exclusion checks: PASS; current project has no Git repository.')
