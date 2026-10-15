"""Append verified fixture browser accounts and regenerate the confidential inventory."""
import sys,json,tempfile,importlib.util
from pathlib import Path
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/'backend'))
from app.config import Settings
from app.main import create_app
from app.db import Base
from app.authentication import CreateUser,CSRF
from app.llm_reliability import Scope
from fastapi.testclient import TestClient
records=json.loads((root/'backend/data/auth-development-credentials.local.json').read_text())
# Canonical unit-test passwords, imported as data only: test module has no top-level execution.
spec=importlib.util.spec_from_file_location('unit_auth_data',root/'backend/tests/test_authentication.py');tests=importlib.util.module_from_spec(spec);spec.loader.exec_module(tests)
units=[{'email':'admin@local.test','password':tests.PASS,'role':'admin','tenant':'workspace','id':'owner','source':'tests/test_authentication.py:env'}, {'email':'viewer@local.test','password':tests.PASS,'role':'viewer','tenant':'workspace','source':'tests/test_authentication.py:env'}, {'email':'foreign@local.test','password':tests.PASS,'role':'admin','tenant':'foreign','source':'tests/test_authentication.py:env'}, {'email':'created@local.test','password':tests.NEXT,'role':'operator','tenant':'workspace','source':'tests/test_authentication.py:test_create_user_reset_token_once_and_revoke (after reset)'}]
e2e=json.loads((root/'backend/data/auth-e2e-credentials.local.json').read_text());extra=[{**r,'source':'scripts/e2e-backend.py + e2e/authentication.spec.ts'} for r in e2e]
# The scenario explicitly creates this account and changes its password. Record final tested state.
extra.append({'email':'created-auth-e2e@local.test','password':'K3!changed-E2E-Only_918','role':'viewer','tenant':'workspace','source':'e2e/authentication.spec.ts:Admin creates/disables user (final password)'})
for name,group in [('isolated-unit-fixtures',units),('isolated-playwright-fixtures',extra)]:
 with tempfile.TemporaryDirectory(prefix='auth-inventory-',dir=root/'backend/.pytest-work') as td:
  path=Path(td);s=Settings(_env_file=None,api_token='fixture-verifier-only',database_url=f'sqlite:///{path/"users.db"}',checkpoint_database_path=path/'cp.db',knowledge_storage_path=path/'documents',local_mcp_enabled=False,auth_allowed_origins=['http://testserver'])
  app=create_app(s);Base.metadata.create_all(app.state.engine)
  for r in group:
   created=app.state.authentication.create(Scope(r['tenant'],'fixture-seed','admin'),CreateUser(email=r['email'],password=r['password'],role=r['role']),r.get('id'));r['id']=created['id']
  with TestClient(app) as c:
   for r in group:
    c.cookies.clear();nonce=c.get('/api/auth/csrf').json()['csrf_token'];login=c.post('/api/auth/login',headers={'Origin':'http://testserver','X-CSRF-Token':nonce},json={'email':r['email'],'password':r['password']});assert login.status_code==200
    assert c.get('/api/auth/me').json()['user']['role']==r['role']
    management=c.get('/api/users');assert management.status_code==(200 if r['role']=='admin' else 403)
    records.append({**r,'verified':True,'role_verified':True,'environment':name,'login_url':'http://127.0.0.1:3011/login (only while Playwright server runs)' if name=='isolated-playwright-fixtures' else 'FastAPI TestClient /api/auth/login; fixture only','purpose':'Reproducible temporary test user; IDs may be regenerated per fixture run'})
file=root/'backend/data/auth-all-browser-credentials.local.json';file.write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf8')
api=json.loads((root/'backend/data/api-identities.local.json').read_text());dev=json.loads((root/'backend/data/auth-dev/server.local.json').read_text());api.append({'user':'owner','tenant':'workspace','role':'admin','token':dev['api_token'],'environment':'isolated-auth-dev service','source':'backend/data/auth-dev/server.local.json'})
api.append({'user':'owner','tenant':'workspace','role':'admin','token':'api-only-test','environment':'isolated-unit-fixtures','source':'backend/tests/test_authentication.py:env'})
lines=['# AgentOps AI v1.0 — DEV CREDENTIALS (local only)','','Confidential. This file is excluded from Git, Docker and public assets. Never publish.','','## Browser email/password accounts','All accounts below were verified through native login/me and RBAC. No production credentials are included. Main: 1 newly created local user; auth-dev: 23 isolated browser equivalents of existing fixture identities. Unit/E2E fixtures are temporary and do not exist in the main database. Their IDs refer to the verified snapshot and may change when fixtures are recreated.','','Main Login URL: http://127.0.0.1:3000/login. Isolated auth-dev UI: http://127.0.0.1:3002/login; backend: 8002. Unit/E2E environments require their test runner.','']
for i,r in enumerate(records,1):
 lines.extend([f'### {i}. {r["email"]}',f'- Account ID: `{r["id"]}`',f'- Email: `{r["email"]}`',f'- Password: `{r["password"]}`',f'- Role: `{r["role"]}`',f'- Tenant: `{r["tenant"]}`','- Status: active in the specified environment',f'- Login URL: {r["login_url"]}',f'- Environment: {r["environment"]}',f'- Purpose: {r["purpose"]}',f'- Source: `{r["source"]}`','- Login / role verification: PASS',''])
lines.extend(['## API-only identities','Programmatic Bearer credentials remain separate from browser passwords. All 24 original identities are retained; one new auth-dev service credential is listed explicitly. Never paste tokens into password fields.',''])
for i,r in enumerate(api,1):lines.extend([f'### API {i}: {r["environment"]} / {r["tenant"]} / {r["user"]}',f'- Identity ID: `{r["user"]}`',f'- Role: `{r["role"]}`',f'- Tenant: `{r["tenant"]}`',f'- Bearer token: `{r["token"]}`',f'- Source: `{r["source"]}`','- Authentication: Authorization: Bearer <token>; no password login for this credential.','- Purpose: preserved automated API credential / isolated dev service.',''])
lines.extend(['## OAuth','No OAuth integration or OAuth passwords.','','## Protection / limitations','- No Git repository exists here. Project was not initialized in Git. Exact .gitignore rule passes git check-ignore in an isolated temporary repository; current-directory git check-ignore cannot verify an index.','- .gitignore/.dockerignore exclude this file; public/static access and bundle checks are required after build.','- Passwords are scrypt-hashed in SQLite; no password reset of existing real users or API credential rotation was performed. .env unchanged.','- Main and auth-dev have distinct cookie names, avoiding cross-port browser session collisions.','- E2E traces are disabled to prevent passwords/reset secrets being included in test artifacts.','- Production checklist is in docs/v1.0-authentication.md.'])
(root/'DEV_CREDENTIALS.local.md').write_text('\n'.join(lines)+'\n',encoding='utf8')
summary={'password_accounts':len(records),'main_users_created':1,'isolated_dev_users_created':23,'unit_fixture_users':len(units),'playwright_fixture_users':len(extra),'verified_logins':sum(r['verified'] for r in records),'verified_roles':sum(r['role_verified'] for r in records),'original_api_identities_preserved':24,'total_api_credentials_listed':len(api),'external_ai_calls':0,'env_unchanged':True}
(root/'docs/v10-credentials-summary.json').write_text(json.dumps(summary,indent=2),encoding='utf8');print(json.dumps(summary))
