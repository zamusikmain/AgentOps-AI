"""Scan candidates/staged blobs and browser assets without printing secret values."""
import json,re,subprocess,sys,io
from pathlib import Path
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'backend'))
from app.config import Settings
settings=Settings()
secret_values=[settings.gemini_api_key.get_secret_value(),settings.api_token.get_secret_value()]
token=root/'backend/.local-token'
if token.exists():secret_values.append(token.read_text().strip())
for name in ('auth-development-credentials.local.json','auth-e2e-credentials.local.json','auth-all-browser-credentials.local.json','api-identities.local.json'):
    p=root/'backend/data'/name
    if p.exists():
        data=json.loads(p.read_text(encoding='utf8'))
        for row in data:
            if isinstance(row,dict):
                # Public constants used only in disposable TestClient fixtures are not service credentials.
                if row.get('environment') in ('isolated-unit-fixtures','isolated-playwright-fixtures'):continue
                if name=='api-identities.local.json' and row.get('source')!='Current running local workspace':continue
                secret_values.extend(v for k,v in row.items() if k in ('password','token') and isinstance(v,str) and len(v)>=12)
dev=root/'backend/data/auth-dev/server.local.json'
if dev.exists():secret_values.append(json.loads(dev.read_text())['api_token'])
secret_values=[s.encode() for s in secret_values if s and len(s)>=12]
patterns=[re.compile(rb'AIza[0-9A-Za-z_-]{30,}'),re.compile(rb'gh[pousr]_[A-Za-z0-9]{30,}'),re.compile(rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----')]
stage='--staged' in sys.argv
cmd=['git','diff','--cached','--name-only','-z'] if stage else ['git','ls-files','--cached','--others','--exclude-standard','-z'] if (root/'.git').exists() else ['rg','--files','--hidden','--no-require-git','-0']
names=subprocess.check_output(cmd,cwd=root).decode().split('\0');names=sorted(set(n for n in names if n))
failures=[]
for name in names:
    path=Path(name)
    if any(part in ('node_modules','.venv','data','__pycache__','test-results','playwright-report') or part.startswith('.next') for part in path.parts) or (path.name.startswith('.env') and path.name!='.env.example') or path.name=='DEV_CREDENTIALS.local.md' or path.suffix in ('.db','.sqlite','.sqlite3','.pem','.key','.p12','.pfx','.bak','.log','.pyc'):
        failures.append({'file':name,'reason':'forbidden_path'});continue
    raw=subprocess.check_output(['git','show',':'+name],cwd=root) if stage else (root/name).read_bytes()
    payloads=[raw]
    if path.suffix.lower()=='.pdf':
        from pypdf import PdfReader
        extracted='\n'.join(p.extract_text() or '' for p in PdfReader(io.BytesIO(raw)).pages)
        if not name.replace('\\','/').startswith('docs/fixtures/') or not re.search(r'fictional|вымышлен',extracted,re.I):failures.append({'file':name,'reason':'pdf_not_verified_synthetic'})
        payloads.append(extracted.encode())
    if any(s in content for content in payloads for s in secret_values):failures.append({'file':name,'reason':'known_local_secret'})
    if any(pattern.search(content) for content in payloads for pattern in patterns):failures.append({'file':name,'reason':'credential_pattern'})
static_files=0
for folder in ('frontend/.next-v12/static','frontend/public'):
    for path in (root/folder).rglob('*'):
        if path.is_file():
            static_files+=1;raw=path.read_bytes()
            if any(s in raw for s in secret_values) or path.name=='DEV_CREDENTIALS.local.md':failures.append({'file':str(path.relative_to(root)),'reason':'public_secret'})
report={'status':'FAIL' if failures else 'PASS','staged':stage,'files':len(names),'browser_assets':static_files,'failures':failures,'secret_values_printed':False,'gitleaks':'not installed; known-local-secret and credential-pattern scan used'}
(root/'docs'/('v12-staged-security.json' if stage else 'v12-publication-security.json')).write_text(json.dumps(report,indent=2))
print(json.dumps(report,indent=2))
raise SystemExit(bool(failures))
