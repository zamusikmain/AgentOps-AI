"""Isolated offline backend for Playwright. Never uses the real key or application DB."""
import sys
import tempfile
from pathlib import Path
import uvicorn

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / 'backend'))
from app.config import Settings
from app.db import Base
from app.main import create_app

parent = root / 'backend/.pytest-work'
parent.mkdir(exist_ok=True)
with tempfile.TemporaryDirectory(prefix='e2e-', dir=parent) as directory:
    directory = Path(directory)
    settings = Settings(_env_file=None, llm_provider='mock', api_token='e2e-test-token',auth_allowed_origins=['http://127.0.0.1:3011'],
                        llm_principals=[{'token':'e2e-v11-foreign-fixture','tenant':'foreign-e2e','user':'foreign-e2e','role':'admin'}],
                        database_url=f'sqlite:///{(directory / "test.db").as_posix()}',
                        checkpoint_database_path=directory / 'checkpoints.db',knowledge_storage_path=directory / 'documents')
    app = create_app(settings)
    from app.providers import MockProvider,ProviderError,Reply
    import asyncio,json
    class OfflineFailures(MockProvider):
        async def generate(self,snapshot,messages,remaining):
            query=snapshot.get('rag_context',{}).get('query','')
            if '[FIXTURE_UNAVAILABLE]' in query:raise ProviderError('provider_unavailable',503)
            if '[FIXTURE_TOKEN_OVERRUN]' in query:return Reply(text='Offline overrun fixture',input_tokens=20,output_tokens=999999)
            if '[FIXTURE_SLOW]' in query:await asyncio.sleep(10)
            return await super().generate(snapshot,messages,remaining)
    app.state.workspaces.adapter_factory=OfflineFailures
    Base.metadata.create_all(app.state.engine)
    import importlib.util
    spec=importlib.util.spec_from_file_location('auth_seed',root/'scripts/auth-development-seed.py');seed=importlib.util.module_from_spec(spec);spec.loader.exec_module(seed);seed.e2e_seed(app)
    import json
    (root/'backend/data/auth-e2e-runtime.local.json').write_text(json.dumps({'database':str(directory/'test.db')}),encoding='utf8')
    uvicorn.run(app, host='127.0.0.1', port=8011, access_log=False)
