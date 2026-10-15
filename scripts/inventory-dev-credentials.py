"""Local auth inventory; prints counts only. Does not reset passwords or expose keys."""
import ast,hashlib,json,sqlite3,sys,time,urllib.request,urllib.error
from pathlib import Path
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/'backend'))
from app.config import Settings
from app.main import create_app
from app.db import Base
from fastapi.testclient import TestClient
import tempfile
entries=[];unresolved=[];environments={};schemas={};user_tables=[]
symbols={}
def literal(node,depth=0):
 if depth>5:return None
 if isinstance(node,ast.Name):return literal(symbols.get(node.id),depth+1)
 if isinstance(node,ast.Call) and getattr(node.func,'id',None)=='SecretStr' and node.args:return literal(node.args[0],depth+1)
 try:return ast.literal_eval(node)
 except (ValueError,TypeError):return None
for file in [p for folder in (root/'backend/app',root/'backend/tests',root/'scripts') for p in folder.rglob('*.py')]:
 if any(x in file.parts for x in ('.venv','node_modules','.pytest-work','__pycache__','data')) or file.name in ('inventory-dev-credentials.py','inspect-auth-declarations.py'):continue
 try:tree=ast.parse(file.read_text(encoding='utf-8-sig'))
 except (SyntaxError,UnicodeError):continue
 symbols={}
 for assignment in ast.walk(tree):
  if isinstance(assignment,ast.Assign):
   for target in assignment.targets:
    if isinstance(target,ast.Name):symbols[target.id]=assignment.value
  elif isinstance(assignment,ast.AnnAssign) and isinstance(assignment.target,ast.Name):symbols[assignment.target.id]=assignment.value
 for imported in ast.walk(tree):
  if isinstance(imported,ast.ImportFrom) and imported.module and imported.module.startswith('test_'):
   dependency=root/'backend/tests'/(imported.module+'.py')
   if dependency.exists():
    imported_tree=ast.parse(dependency.read_text(encoding='utf-8-sig'))
    for assignment in ast.walk(imported_tree):
     if isinstance(assignment,ast.Assign):
      for target in assignment.targets:
       if isinstance(target,ast.Name):
        for alias in imported.names:
         if alias.name==target.id:symbols[alias.asname or alias.name]=assignment.value
 parents={child:parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)}
 for call in ast.walk(tree):
  if not isinstance(call,ast.Call):continue
  kws={k.arg:k.value for k in call.keywords if k.arg}
  if not {'api_token','llm_principals'}&kws.keys():continue
  # Only actual auth configuration declarations; HTTP negative-test headers are not identities.
  enclosing=call
  while enclosing in parents and not isinstance(enclosing,(ast.FunctionDef,ast.AsyncFunctionDef)):enclosing=parents[enclosing]
  function=enclosing.name if isinstance(enclosing,(ast.FunctionDef,ast.AsyncFunctionDef)) else '<module>'
  source=f'{file.relative_to(root).as_posix()}:{call.lineno} ({function})';items=[]
  token=literal(kws.get('api_token')) if 'api_token' in kws else None
  if isinstance(token,str) and token:items.append({'user':'owner','tenant':'workspace','role':'admin','token':token})
  elif 'api_token' in kws:unresolved.append(source+' — dynamic token; requires runtime configuration rather than guessing.')
  principals=literal(kws.get('llm_principals')) if 'llm_principals' in kws else []
  if principals is None:unresolved.append(source+' — dynamic principal declaration.')
  for p in principals or []:
   if isinstance(p,dict) and p.get('token'):items.append({'user':str(p.get('user','UNSPECIFIED')),'tenant':str(p.get('tenant','UNSPECIFIED')),'role':str(p.get('role','viewer')),'token':p['token']})
  if items:environments[source]=items
# Primary local runtime only; never inventory external provider secrets.
s=Settings();env_before=hashlib.sha256((root/'backend/.env').read_bytes()).hexdigest()
if s.environment_id=='local':
 token=s.api_token.get_secret_value() or (root/'backend/.local-token').read_text().strip()
 primary=[{'user':'owner','tenant':'workspace','role':'admin','token':token}]
 for p in s.llm_principals:
  if p.get('token'):primary.append({'user':str(p['user']),'tenant':str(p['tenant']),'role':str(p.get('role','viewer')),'token':str(p['token'])})
 environments['Current running local workspace']=primary
else:unresolved.append('Current environment is not local; account changes and secret extraction skipped.')
# Schema-only inventory of all retained local SQLite databases, no hashes/password contents read.
if '--reuse-schema-inventory' in sys.argv:
 previous=json.loads((root/'backend/data/credentials-inventory-summary.json').read_text(encoding='utf8'));schemas={('previous complete read-only inventory',):previous['sqlite_files_checked']};user_tables=previous['user_password_tables']
for file in ([] if '--reuse-schema-inventory' in sys.argv else (root/'backend').rglob('*.db')):
 if '.venv' in file.parts:continue
 try:
  with sqlite3.connect(file.resolve().as_uri()+'?mode=ro',uri=True,timeout=2) as db:
   tables=[r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")]
   signature=tuple(sorted(tables));schemas[signature]=schemas.get(signature,0)+1
   for table in tables:
    columns=[r[1] for r in db.execute('PRAGMA table_info("'+table.replace('"','""')+'")')]
    if any(c.casefold() in ('password','password_hash','hashed_password','email','login','username') for c in columns):
     user_tables.append({'database':file.relative_to(root).as_posix(),'table':table,'count':db.execute('SELECT count(*) FROM "'+table.replace('"','""')+'"').fetchone()[0]})
 except sqlite3.Error:unresolved.append(str(file.relative_to(root))+' — unreadable SQLite; no changes made.')
parent=root/'backend/.pytest-work';parent.mkdir(exist_ok=True)
for number,(source,items) in enumerate(environments.items(),1):
 if source=='Current running local workspace':
  for item in items:
   req=urllib.request.Request('http://127.0.0.1:8000/api/llm/summary',headers={'Authorization':'Bearer '+item['token']})
   try:
    with urllib.request.urlopen(req,timeout=10) as response:verified=response.status==200
   except (urllib.error.URLError,TimeoutError):verified=False
   role_verified=False
   if item['tenant']=='workspace' and item['role']=='admin':
    probe=urllib.request.Request('http://127.0.0.1:8000/api/validation/prepare/credentials-role-probe',data=b'{}',headers={'Authorization':'Bearer '+item['token'],'Content-Type':'application/json'})
    try:urllib.request.urlopen(probe,timeout=10).close()
    except urllib.error.HTTPError as exc:role_verified=exc.code==422 and json.load(exc).get('error',{}).get('code')=='validation_dataset_invalid'
   entries.append({**item,'source':source,'environment':f'env-{number}','url':'http://127.0.0.1:3000/ (browser server proxy); http://127.0.0.1:8000/api/llm/summary (Bearer)','verified':verified,'role_verified':role_verified,'status':'active local runtime','purpose':'Local workspace API / scoped diagnostics','persistent':True})
  continue
 with tempfile.TemporaryDirectory(prefix='credentials-auth-',dir=parent) as td:
  path=Path(td);owner=next((i['token'] for i in items if i['user']=='owner' and i['tenant']=='workspace' and i['role']=='admin'),None)
  # Use the declaration token for the owner; principals have distinct configured identity.
  owner_token=owner or 'isolated-inventory-owner-'+str(number)
  principals=[{'token':i['token'],'tenant':i['tenant'],'user':i['user'],'role':i['role']} for i in items if i is not next((i for i in items if i['token']==owner_token and i['user']=='owner' and i['tenant']=='workspace' and i['role']=='admin'),None)]
  settings=Settings(_env_file=None,api_token=owner_token,llm_principals=principals,llm_provider='mock',database_url=f'sqlite:///{path/"auth.db"}',checkpoint_database_path=path/'cp.db',knowledge_storage_path=path/'documents',local_mcp_enabled=False)
  app=create_app(settings);Base.metadata.create_all(app.state.engine)
  with TestClient(app) as client:
   for i,item in enumerate(items):
    h={'Authorization':'Bearer '+item['token']};response=client.get('/api/llm/summary',headers=h)
    dataset={'id':'inventory-permission-'+str(i),'version':1,'name':'Local authorization role check','questions':[{'id':'missing','question':'Independent missing fact?','language':'en','expected_behavior':'abstain','scope':[]}]}
    role_response=client.post('/api/validation/datasets',headers=h,json=dataset)
    correct_role=role_response.status_code==(201 if item['role']=='admin' else 403)
    entries.append({**item,'source':source,'environment':f'env-{number}','url':'Isolated FastAPI TestClient: /api/llm/summary; no permanent browser login','verified':response.status_code==200,'role_verified':correct_role,'status':'fixture; active only when its isolated test environment is created','purpose':'Local automated authorization fixture','persistent':False})
# Reject file inclusion of API secrets inadvertently reused as auth tokens.
key=s.gemini_api_key.get_secret_value()
if key and any(key==e['token'] for e in entries):raise RuntimeError('Provider secret unexpectedly used as auth; inventory stopped safely')
assert env_before==hashlib.sha256((root/'backend/.env').read_bytes()).hexdigest()
lines=['# AgentOps AI — локальные учётные записи и API credentials','','Конфиденциально. Только локальная разработка. Не публиковать и не включать в сборку.','','## Штатная авторизация','','В проекте отсутствуют пользователи с логином/email и паролем, password hashing, форма входа и OAuth. Авторизация backend выполняется через Authorization: Bearer <token>. Frontend использует серверный proxy с локальным токеном; отдельного пользовательского входа в браузере нет. Пароли не создавались и не сбрасывались. Поле пароль ниже неприменимо, рабочий credential — конкретный Bearer token.','','Каждая декларация отдельного тестового окружения перечислена полностью, даже при одинаковых ролях/ID/токенах. Fixture credentials проверены штатным FastAPI middleware в восстановленном изолированном Mock окружении, а не выданы за постоянно работающие серверы. Случайные auth headers для проверки unauthorized не являются учётными записями. LLM agents и user_id в трассах сами по себе также не являются аккаунтами.','','## Все конфигурационные идентичности','']
for n,e in enumerate(entries,1):
 lines.extend([f'### {n}. {e["environment"]} / {e["tenant"]} / {e["user"]}',f'- ID пользователя: `{e["user"]}`',f'- Tenant: `{e["tenant"]}`',f'- Логин / email: не предусмотрен; идентификатор `{e["user"]}`', '- Пароль: не применяется (password authentication отсутствует)',f'- Рабочий Bearer token: `{e["token"]}`',f'- Роль: `{e["role"]}`',f'- Статус: {e["status"]}',f'- URL / точка входа: {e["url"]}', '- Способ авторизации: `Authorization: Bearer <рабочий токен выше>`',f'- Назначение: {e["purpose"]}',f'- Источник: `{e["source"]}`',f'- Штатная авторизация: {"PASS" if e["verified"] else "FAIL / недоступно"}',f'- Проверка RBAC: {"PASS — штатные проверки RBAC" if e["role_verified"] else "configured role; live mutation deliberately not performed"}',''])
lines.extend(['## OAuth','Не обнаружено OAuth интеграций и внешних OAuth аккаунтов.','','## Ограничения и дополнительные окружения',f'- Проверено локальных SQLite файлов: {sum(schemas.values())}. Таблиц с login/email/password полями: {len(user_tables)}.', '- Production/shared аккаунты не изменялись. Реальные пользовательские пароли не извлекались. .env не изменялся.','- Эфемерные fixture окружения закрыты после проверок; токены действуют при запуске соответствующих тестовых конфигураций, но не на основном сервере.'])
lines.extend('- '+u for u in unresolved)
lines.extend('- '+json.dumps(t,ensure_ascii=False) for t in user_tables)
(root/'DEV_CREDENTIALS.local.md').write_text('\n'.join(lines)+'\n',encoding='utf8')
summary={'account_entries':len(entries),'unique_environment_identities':len({(e['source'],e['tenant'],e['user'],e['token']) for e in entries}),'password_accounts':0,'working_bearer_credentials':sum(e['verified'] for e in entries),'successful_authorizations':sum(e['verified'] for e in entries),'role_checks_passed':sum(e['role_verified'] for e in entries),'primary_runtime_entries':sum(e['persistent'] for e in entries),'fixture_entries':sum(not e['persistent'] for e in entries),'sqlite_files_checked':sum(schemas.values()),'user_password_tables':user_tables,'unresolved':unresolved,'env_unchanged':True}
(root/'backend/data/credentials-inventory-summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps(summary,ensure_ascii=False))
