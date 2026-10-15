"""Isolated local auth development server; no external AI/provider key."""
import sys,json
from pathlib import Path
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/'backend'))
from app.config import Settings
from app.main import create_app
import uvicorn
path=root/'backend/data/auth-dev'
settings=Settings(_env_file=None,database_url=f'sqlite:///{path/"users.db"}',knowledge_storage_path=path/'documents',checkpoint_database_path=path/'cp.db',api_token=json.loads((path/'server.local.json').read_text())['api_token'],local_mcp_enabled=False,llm_provider='mock',embedding_provider='mock',gemini_api_key='',external_api_enabled=False,real_validation_enabled=False,embedding_external_enabled=False,paid_operations_enabled=False,auth_cookie_name='agentops_dev_session',auth_csrf_cookie_name='agentops_dev_csrf',auth_allowed_origins=['http://127.0.0.1:3002','http://127.0.0.1:8002'])
app=create_app(settings)
if __name__=='__main__':uvicorn.run(app,host='127.0.0.1',port=8002,access_log=False)
