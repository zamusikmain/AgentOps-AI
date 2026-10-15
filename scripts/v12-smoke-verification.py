"""Actual local synthetic orchestration and reopen; SDK construction is forbidden."""
import json,sys,time,tempfile
from pathlib import Path
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/'backend'))
from google import genai
from fastapi.testclient import TestClient
from app.main import create_app
from app.config import Settings
from app.db import Base

def forbidden(*args,**kwargs):raise AssertionError('External SDK construction forbidden in offline verification')
genai.Client=forbidden
work=root/'backend/.pytest-work';work.mkdir(exist_ok=True)
assert work.resolve().is_relative_to(root)
started=time.monotonic()
with tempfile.TemporaryDirectory(prefix='v12-synthetic-',dir=work) as directory:
    path=Path(directory)
    settings=Settings(_env_file=None,api_token='v12-verification-fixture',database_url=f'sqlite:///{path/"main.db"}',checkpoint_database_path=path/'cp.db',knowledge_storage_path=path/'documents',local_mcp_enabled=False)
    app=create_app(settings);Base.metadata.create_all(app.state.engine)
    with TestClient(app,headers={'Authorization':'Bearer v12-verification-fixture'}) as client:
        r=client.post('/api/workspaces',json={'name':'Synthetic release verification'});assert r.status_code==201
        workspace=r.json()['id'];prefix=f'/api/workspaces/{workspace}/'
        dry=client.post(prefix+'smoke',json={'mode':'REAL_DRY_RUN'});assert dry.status_code==200,dry.status_code
        plan=dry.json()['plan'];assert plan['external_calls']==0
        response=client.post(prefix+'smoke',json={'mode':'MOCK_ONLY'});assert response.status_code==200
        identifier=response.json()['id'];deadline=time.monotonic()+150
        while time.monotonic()<deadline:
            run=client.get(prefix+'smoke/'+identifier).json()
            if run['status'] not in ('queued','running'):break
            time.sleep(.1)
        assert run['status']=='completed',run.get('error')
        assert len(run['cases'])==10 and run['external_calls']==0
        history=client.get(prefix+'knowledge/runs').json();assert history['total']==10
        results={row['id']:row['result'] for row in history['items']}
    reopened=create_app(settings)
    with TestClient(reopened,headers={'Authorization':'Bearer v12-verification-fixture'}) as client:
        saved=client.get(prefix+'smoke/'+identifier).json()
        assert saved['cases']==run['cases']
        history=client.get(prefix+'knowledge/runs').json()
        assert results=={row['id']:row['result'] for row in history['items']}
    report={'mode':'MOCK_ONLY','live_verification':'UNVERIFIED','dataset':run['prepared']['dataset_id'],
            'documents':3,'questions':10,'passed_reference_criteria':run['passed'],
            'cases':run['cases'],'dry_run':{'status':plan['status'],'plan':plan['plan'],'blockers':plan['blockers']},
            'sqlite_history_after_reopen':True,'mock_estimated_tokens':{'input':sum(c['input_tokens'] for c in run['cases']),'output':sum(c['output_tokens'] for c in run['cases'])},
            'duration_seconds':round(time.monotonic()-started,3),'real_generation_requests':0,'real_embedding_requests':0,
            'sdk_construction_forbidden':True}
(root/'docs/v12-synthetic-smoke.json').write_text(json.dumps(report,indent=2),encoding='utf8')
print(json.dumps({k:v for k,v in report.items() if k not in ('cases',)}))
