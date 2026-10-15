"""Local auth seeds. No existing password is reset; secrets are written only to excluded files."""
import sys,json,secrets,re,sqlite3
from pathlib import Path
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/'backend'))
from app.config import Settings
from app.main import create_app
from app.db import Base,User
from app.authentication import CreateUser
from app.llm_reliability import Scope
from app.password_security import verify_password
DATA=root/'backend/data'
def e2e_seed(app):
 file=DATA/'auth-e2e-credentials.local.json'
 if file.exists():records=json.loads(file.read_text())
 else:
  records=[{'id':'owner','email':'e2e-admin@agentops.local.test','password':secrets.token_urlsafe(24),'role':'admin','tenant':'workspace'},{'id':'e2e-viewer','email':'e2e-viewer@agentops.local.test','password':secrets.token_urlsafe(24),'role':'viewer','tenant':'workspace'}];file.write_text(json.dumps(records),encoding='utf8')
 for r in records:
  with app.state.sessions() as db:user=db.get(User,r['id'])
  if not user:app.state.authentication.create(Scope(r['tenant'],'seed','admin'),CreateUser(email=r['email'],password=r['password'],role=r['role']),r['id'])
 return records
if __name__=='__main__':
 path=root/'DEV_CREDENTIALS.local.md';previous=DATA/'credentials-before-v10.local.md'
 if not previous.exists() and path.exists() and 'Рабочий Bearer token' in path.read_text(encoding='utf8'):previous.write_bytes(path.read_bytes())
 old=previous.read_text(encoding='utf8') if previous.exists() else '';api=[]
 for block in re.split(r'^### \d+\. ',old,flags=re.M)[1:]:
  def field(label):
   m=re.search(r'^- '+re.escape(label)+r': `([^`]+)`',block,re.M);return m.group(1) if m else ''
  token=field('Рабочий Bearer token')
  if token:api.append({'user':field('ID пользователя'),'tenant':field('Tenant'),'role':field('Роль'),'token':token,'source':field('Источник'),'environment':block.split(' / ')[0].splitlines()[0]})
 if not api:
  saved=DATA/'api-identities.local.json'
  if saved.exists():api=json.loads(saved.read_text(encoding='utf8'))
  else:
   import importlib.util
   spec=importlib.util.spec_from_file_location('auth_manifest',root/'scripts/auth-fixture-manifest.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);api=module.resolve(root,json.loads((root/'docs/fixtures/auth-api-identity-manifest.json').read_text(encoding='utf8')))
 assert len(api)==24
 file=DATA/'auth-development-credentials.local.json';stored=json.loads(file.read_text()) if file.exists() else []
 main_settings=Settings()
 if main_settings.environment_id!='local':raise RuntimeError('Development seed is forbidden outside local environment')
 main=create_app(main_settings);dev_path=DATA/'auth-dev';dev_path.mkdir(exist_ok=True)
 dev_settings=Settings(_env_file=None,database_url=f'sqlite:///{dev_path/"users.db"}',knowledge_storage_path=dev_path/'documents',checkpoint_database_path=dev_path/'cp.db',api_token=secrets.token_urlsafe(32),local_mcp_enabled=False,llm_provider='mock',embedding_provider='mock',gemini_api_key='',external_api_enabled=False,real_validation_enabled=False,embedding_external_enabled=False,paid_operations_enabled=False,auth_cookie_name='agentops_dev_session',auth_csrf_cookie_name='agentops_dev_csrf',auth_allowed_origins=['http://127.0.0.1:3002','http://127.0.0.1:8002'])
 # Persist only local service credentials, never provider keys.
 config=dev_path/'server.local.json'
 if config.exists():dev_settings.api_token=__import__('pydantic').SecretStr(json.loads(config.read_text())['api_token'])
 else:config.write_text(json.dumps({'api_token':dev_settings.api_token.get_secret_value()}),encoding='utf8')
 dev=create_app(dev_settings);Base.metadata.create_all(dev.state.engine)
 records=[]
 for index,identity in enumerate(api,1):
  primary=identity['source']=='Current running local workspace';app=main if primary else dev
  environment='main-local' if primary else 'isolated-auth-dev'
  email='owner@agentops.local.test' if primary else f'fixture-{index:02d}@agentops.local.test'
  tenant='workspace' if primary else identity['environment']+'-'+identity['tenant']
  existing=next((r for r in stored if r['email']==email),None)
  password=existing['password'] if existing else secrets.token_urlsafe(24)
  with app.state.sessions() as db:user=db.scalar(__import__('sqlalchemy').select(User).where(User.email==email))
  if user:
   if not existing or not verify_password(password,user.password_hash):raise RuntimeError('Existing user cannot be reset automatically; review local credentials')
   id=user.id
  else:
   result=app.state.authentication.create(Scope(tenant,'development-seed','admin'),CreateUser(email=email,password=password,role=identity['role']),'owner' if primary else None);id=result['id']
  records.append({'id':id,'email':email,'password':password,'role':identity['role'],'tenant':tenant,'environment':environment,'login_url':'http://127.0.0.1:3000/login' if primary else 'http://127.0.0.1:3002/login','api_url':'http://127.0.0.1:8000' if primary else 'http://127.0.0.1:8002','source':identity['source'],'purpose':'Browser equivalent of local API test identity; API credential unchanged','verified':False})
 file.write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf8')
 # Also persist API-only inventory separately, so password and API secrets are never conflated.
 (DATA/'api-identities.local.json').write_text(json.dumps(api,ensure_ascii=False,indent=2),encoding='utf8')
 e2e_file=DATA/'auth-e2e-credentials.local.json'
 if not e2e_file.exists():e2e_file.write_text(json.dumps([{'id':'owner','email':'e2e-admin@agentops.local.test','password':secrets.token_urlsafe(24),'role':'admin','tenant':'workspace'},{'id':'e2e-viewer','email':'e2e-viewer@agentops.local.test','password':secrets.token_urlsafe(24),'role':'viewer','tenant':'workspace'}]),encoding='utf8')
 print('Local browser seed: 1 main user, 23 isolated fixture equivalents; 24 API identities preserved. No passwords printed.')
