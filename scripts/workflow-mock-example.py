"""Generate a concrete four-agent example against isolated SQLite and mock only."""
import json
import sys
import tempfile
import time
from pathlib import Path
from fastapi.testclient import TestClient

root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'backend'))
from app.config import Settings
from app.main import create_app
from app.db import Base

parent=root/'backend/.pytest-work'
parent.mkdir(exist_ok=True)
with tempfile.TemporaryDirectory(prefix='workflow-example-',dir=parent) as folder:
    path=Path(folder)
    settings=Settings(_env_file=None,llm_provider='mock',api_token='example-token',
        database_url=f'sqlite:///{(path/"example.db").as_posix()}',checkpoint_database_path=path/'checkpoints.db')
    app=create_app(settings)
    Base.metadata.create_all(app.state.engine)
    with TestClient(app,headers={'Authorization':'Bearer example-token'}) as client:
        agents=[]
        for role in ('planner','researcher','executor','reviewer'):
            response=client.post('/api/agents',json={'name':role.title(),'role':role,'instructions':f'Perform {role} duties using supplied context.',
                'model':'gemini-3.5-flash-lite','tools':[],'max_steps':2,'max_tokens':2048})
            response.raise_for_status();agents.append(response.json())
        response=client.post('/api/workflows',json={'name':'Customer portal release','agent_ids':[a['id'] for a in agents],'retry_from':2})
        response.raise_for_status();workflow=response.json()
        response=client.post(f"/api/workflows/{workflow['id']}/run",json={'title':'Release a customer portal',
            'prompt':'Prepare a safe customer portal release checklist from the supplied context.'})
        response.raise_for_status();rid=response.json()['id']
        for _ in range(150):
            run=client.get(f'/api/workflow-runs/{rid}').json()
            if run['status'] not in ('queued','running'):break
            time.sleep(.02)
        steps=client.get(f'/api/workflow-runs/{rid}/steps').json()['items']
        events=client.get(f'/api/workflow-runs/{rid}/events').json()['items']
        assert run['status']=='completed',run
        assert len(steps)==4
        for index in range(1,4):
            assert steps[index]['input']['artifacts'][-1]['output']==steps[index-1]['output']
        report={'provider':'mock','real_gemini_requests':0,'run':run,'steps':steps,'events':events,'handoffs_verified':True}
        (root/'docs/workflow-mock-example.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps({'status':run['status'],'roles':[s['role'] for s in steps],'calls':run['calls'],
            'input_tokens':run['input_tokens'],'output_tokens':run['output_tokens'],'handoffs_verified':True,'real_gemini_requests':0}))
