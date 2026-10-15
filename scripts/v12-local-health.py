"""Read-only native runtime checks; no Google/model discovery or user-data transmission."""
import urllib.request,urllib.error,json,sys
from pathlib import Path
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/'backend'))
from app.config import Settings
settings=Settings();token=settings.api_token.get_secret_value() or (root/'backend/.local-token').read_text().strip()
def get(url,authorized=False):
 request=urllib.request.Request(url,headers={'Authorization':'Bearer '+token} if authorized else {})
 try:
  with urllib.request.urlopen(request,timeout=15) as response:return response.status,response.read()
 except urllib.error.HTTPError as error:return error.code,b''
status,data=get('http://127.0.0.1:8000/openapi.json',True);assert status==200 and json.loads(data)['info']['version']=='1.2.0'
status,_=get('http://127.0.0.1:8000/api/workspaces',True);assert status==200
status,_=get('http://127.0.0.1:3000/ai');assert status==200
status,_=get('http://127.0.0.1:3000/api/workspaces');assert status==401
assert not settings.external_api_enabled and not settings.embedding_external_enabled and not settings.real_validation_enabled and not settings.workspace_live_enabled
result={'version':'1.2.0','native_backend':'PASS','native_ui_route':'PASS','unauthenticated_proxy_status':401,'existing_bearer_api':'PASS','external_generation_enabled':False,'external_embedding_enabled':False,'real_validation_enabled':False,'workspace_live_enabled':False,'google_calls':0,'live_verification':'UNVERIFIED'}
(root/'docs/v12-local-health.json').write_text(json.dumps(result,indent=2));print('Native v1.2 UI/API, Bearer compatibility and offline gates: PASS')
