import asyncio
import json
import time
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from app.main import create_app
from app.config import Settings
from app.db import Base, WorkflowRun, WorkflowStep, WorkflowEvent
from app.providers import MockProvider, Reply, ProviderError

TOKEN='workflow-test-token'

@pytest.fixture
def settings(tmp_path):
    return Settings(_env_file=None,database_url=f'sqlite:///{(tmp_path/"test.db").as_posix()}',
        checkpoint_database_path=tmp_path/'checkpoints.db',llm_provider='mock',api_token=TOKEN)

def context(settings,provider=None):
    app=create_app(settings,provider)
    Base.metadata.create_all(app.state.engine)
    return TestClient(app,headers={'Authorization':f'Bearer {TOKEN}'})

def seed(c,**limits):
    agents=[]
    for role in ('planner','researcher','executor','reviewer'):
        response=c.post('/api/agents',json={'name':role.title(),'role':role,'instructions':f'Perform {role} role.',
            'model':'gemini-3.5-flash-lite','tools':[],'max_steps':2,'max_tokens':2048})
        assert response.status_code==201,response.text
        agents.append(response.json())
    response=c.post('/api/workflows',json={'name':'Launch workflow','agent_ids':[a['id'] for a in agents],
        'retry_from':2,**limits})
    assert response.status_code==201,response.text
    return agents,response.json()

def launch(c,w):
    response=c.post(f"/api/workflows/{w['id']}/run",json={'title':'Launch a customer portal','prompt':'Plan a safe customer portal release using the supplied context.'})
    assert response.status_code==202,response.text
    return response.json()['id']

def wait(c,rid):
    deadline=time.monotonic()+min(c.app.state.workflow_runner.settings.execution_timeout_seconds,30)+5
    while time.monotonic()<deadline:
        r=c.get(f'/api/workflow-runs/{rid}').json()
        if r['status'] not in ('queued','running'):
            return r
        time.sleep(.025)
    pytest.fail('Workflow did not finish')

def steps(c,rid):
    return c.get(f'/api/workflow-runs/{rid}/steps').json()['items']

def test_four_agents_exchange_and_persistence(settings):
    with context(settings) as c:
        agents,w=seed(c)
        rid=launch(c,w);run=wait(c,rid)
        assert run['status']=='completed',run
        assert run['calls']==4 and run['input_tokens']==110 and run['output_tokens']==160
        history=steps(c,rid)
        assert [s['role'] for s in history]==['planner','researcher','executor','reviewer']
        for index,s in enumerate(history):
            assert s['output']['data']['received_roles']==[a['role'] for a in agents[:index]]
            assert len(s['input']['artifacts'])==index
            assert s['duration_ms'] is not None
            if index:
                assert s['input']['artifacts'][-1]['output']==history[index-1]['output']
        assert run['result']['review']['decision']=='approve'
        assert c.get('/api/dashboard').json()['counts']['workflow_runs']==1
        assert c.get('/api/dashboard').json()['counts']['tokens']==270
        assert c.get('/api/workflow-runs?limit=1').json()['total']==1
        assert c.get(f'/api/workflow-runs/{rid}/steps?limit=2&offset=2').json()['items'][0]['role']=='executor'
        assert c.get(f'/api/workflow-runs/{rid}/events?limit=1').json()['total']==18
        assert c.delete(f"/api/workflows/{w['id']}").status_code==409
        assert c.delete(f"/api/agents/{agents[0]['id']}").status_code==409
        original_instructions=agents[0]['instructions']
        a={k:v for k,v in agents[0].items() if k not in ('id','created_at')};a['instructions']='Changed'
        assert c.put(f"/api/agents/{agents[0]['id']}",json=a).status_code==200
        with c.app.state.sessions() as db:
            assert db.get(WorkflowRun,rid).snapshot['agents'][0]['instructions']==original_instructions
    with context(settings) as reopened:
        assert reopened.get(f'/api/workflow-runs/{rid}').json()['result']==run['result']
        assert len(steps(reopened,rid))==4
    assert settings.checkpoint_path.exists()

class RevisionProvider(MockProvider):
    def __init__(self,always=False):
        self.always=always
        self.requests=[]
    async def generate(self,snapshot,messages,remaining_tokens):
        envelope=json.loads(messages[0]['parts'][0]['text'])
        self.requests.append((snapshot['role'],envelope))
        reply=await super().generate(snapshot,messages,remaining_tokens)
        if snapshot['role']=='reviewer' and (self.always or not envelope['review_feedback']):
            output=json.loads(reply.text)
            output.update(decision='revise',feedback='Add an explicit rollback checklist.')
            reply.text=json.dumps(output)
        return reply

def test_reviewer_revision_replays_only_downstream(settings):
    p=RevisionProvider()
    with context(settings,p) as c:
        _,w=seed(c,max_revisions=1)
        rid=launch(c,w);r=wait(c,rid)
        assert r['status']=='completed',r
        history=steps(c,rid)
        assert [s['role'] for s in history]==['planner','researcher','executor','reviewer','executor','reviewer']
        assert r['revisions']==1 and r['calls']==6
        revised=history[4]['input']
        assert revised['review_feedback']['feedback']=='Add an explicit rollback checklist.'
        assert [a['role'] for a in revised['artifacts']]==['planner','researcher']
        assert history[4]['attempt']==2
        assert history[5]['input']['artifacts'][-1]['output']==history[4]['output']
        assert r['result']['artifacts'][2]['attempt']==2

def test_revision_limit_no_extra_call(settings):
    with context(settings,RevisionProvider(always=True)) as c:
        _,w=seed(c,max_revisions=1)
        rid=launch(c,w);r=wait(c,rid)
        assert r['error']=='revision_limit' and r['calls']==6
        assert len(steps(c,rid))==6

def test_call_limit(settings):
    with context(settings,RevisionProvider()) as c:
        _,w=seed(c,max_calls=4)
        rid=launch(c,w);r=wait(c,rid)
        assert r['error']=='workflow_call_limit' and r['calls']==4
        assert steps(c,rid)[-1]['status']=='failed'

def test_token_reservation_prevents_request(settings):
    with context(settings) as c:
        _,w=seed(c,max_total_tokens=1024)
        rid=launch(c,w);r=wait(c,rid)
        assert r['error']=='workflow_token_limit' and r['calls']==0

class OverBudget(MockProvider):
    async def generate(self,*args):
        return Reply(text='{}',input_tokens=33000,output_tokens=100)

def test_actual_usage_accounted_on_limit(settings):
    with context(settings,OverBudget()) as c:
        _,w=seed(c)
        rid=launch(c,w);r=wait(c,rid)
        assert r['error']=='workflow_token_limit' and r['input_tokens']==33000
        assert len(steps(c,rid))==1

class FailureAtRole(MockProvider):
    def __init__(self,role):self.role=role
    async def generate(self,snapshot,*args):
        if snapshot['role']==self.role:
            raise ProviderError('rate_limit',http_status=429)
        return await super().generate(snapshot,*args)

@pytest.mark.parametrize('role,index',[('planner',0),('researcher',1),('executor',2),('reviewer',3)])
def test_failure_at_any_stage(settings,role,index):
    with context(settings,FailureAtRole(role)) as c:
        _,w=seed(c);rid=launch(c,w);r=wait(c,rid)
        assert r['error']=='rate_limit' and r['current_stage']==index and r['calls']==index+1
        assert steps(c,rid)[-1]['error']=='rate_limit'
        ev=c.get(f'/api/workflow-runs/{rid}/events').json()['items']
        assert ev[-1]['payload']['provider_http_status']==429

class SlowAtRole(MockProvider):
    def __init__(self,role):self.role=role
    async def generate(self,snapshot,*args):
        if snapshot['role']==self.role:await asyncio.sleep(20)
        return await super().generate(snapshot,*args)

@pytest.mark.parametrize('role,index',[('planner',0),('researcher',1),('executor',2),('reviewer',3)])
def test_cancel_at_any_stage(settings,role,index):
    with context(settings,SlowAtRole(role)) as c:
        _,w=seed(c);rid=launch(c,w)
        for _ in range(100):
            r=c.get(f'/api/workflow-runs/{rid}').json()
            if r['current_stage']==index:break
            time.sleep(.02)
        assert r['current_stage']==index
        assert c.post(f'/api/workflow-runs/{rid}/cancel').status_code==200
        r=wait(c,rid)
        assert r['status']=='cancelled' and r['calls']==index+1
        assert steps(c,rid)[-1]['status']=='cancelled'
        assert c.post(f'/api/workflow-runs/{rid}/cancel').status_code==409

def test_timeout(settings):
    with context(settings,SlowAtRole('researcher')) as c:
        _,w=seed(c,timeout_seconds=1);rid=launch(c,w);r=wait(c,rid)
        assert r['error']=='execution_timeout'
        assert steps(c,rid)[-1]['status']=='failed'
        assert steps(c,rid)[-1]['error']=='execution_timeout'

class InvalidOutput(MockProvider):
    async def generate(self,*args):return Reply(text='not JSON',input_tokens=1,output_tokens=2)

def test_invalid_output_saved_without_automatic_retry(settings):
    with context(settings,InvalidOutput()) as c:
        _,w=seed(c);rid=launch(c,w);r=wait(c,rid)
        assert r['error']=='invalid_stage_output' and r['calls']==1
        assert steps(c,rid)[0]['raw_output']=='not JSON'

def test_crud_validation_auth(settings):
    with context(settings) as c:
        agents,w=seed(c)
        assert c.get('/api/workflows',headers={'Authorization':''}).status_code==401
        assert c.get('/api/workflows?limit=0').status_code==422
        body={k:v for k,v in w.items() if k not in ('id','created_at')}
        body['name']='Edited'
        assert c.put(f"/api/workflows/{w['id']}",json=body).json()['name']=='Edited'
        bad={**body,'agent_ids':list(reversed(body['agent_ids']))}
        assert c.post('/api/workflows',json=bad).json()['error']['code']=='reviewer_must_be_last'
        assert c.post('/api/workflows',json={**body,'retry_from':3}).status_code==422
        assert c.post('/api/workflows',json={**body,'max_revisions':9}).status_code==422
        assert c.post('/api/workflows',json={**body,'agent_ids':[agents[0]['id']]*4}).status_code==422
        assert c.post(f"/api/workflows/{w['id']}/run",json={'title':' ','prompt':'x'}).status_code==422
        assert c.delete(f"/api/workflows/{w['id']}").status_code==204
        assert c.get(f"/api/workflows/{w['id']}").status_code==404

def test_running_workflow_cannot_edit(settings):
    with context(settings,SlowAtRole('planner')) as c:
        _,w=seed(c);rid=launch(c,w)
        body={k:v for k,v in w.items() if k not in ('id','created_at')}
        assert c.put(f"/api/workflows/{w['id']}",json=body).status_code==409
        c.post(f'/api/workflow-runs/{rid}/cancel')

def test_restart_recovers_run_and_active_step(settings):
    with context(settings) as c:
        _,w=seed(c);rid=launch(c,w);wait(c,rid)
        with c.app.state.sessions() as db:
            run=db.get(WorkflowRun,rid);run.status='running'
            step=db.scalar(select(WorkflowStep).where(WorkflowStep.run_id==rid));step.status='running'
            db.commit()
    with context(settings) as c:
        r=c.get(f'/api/workflow-runs/{rid}').json()
        assert r['error']=='server_restarted'
        assert steps(c,rid)[0]['status']=='failed'

class DeniedTool(MockProvider):
    async def generate(self,*args):return Reply(calls=[{'name':'shell','args':{}}],input_tokens=1,output_tokens=1)

def test_workflow_denies_arbitrary_tools(settings):
    with context(settings,DeniedTool()) as c:
        _,w=seed(c);rid=launch(c,w);r=wait(c,rid)
        assert r['error']=='tool_denied' and r['calls']==1

def test_single_and_workflow_share_worker(settings):
    with context(settings,SlowAtRole('planner')) as c:
        agents,w=seed(c);rid=launch(c,w)
        task=c.post('/api/tasks',json={'title':'Single agent','prompt':'Single prompt','agent_id':agents[2]['id']}).json()
        e=c.post(f"/api/tasks/{task['id']}/run").json()
        time.sleep(.05)
        assert c.get(f"/api/executions/{e['id']}").json()['status']=='queued'
        c.post(f'/api/workflow-runs/{rid}/cancel')
        for _ in range(100):
            single=c.get(f"/api/executions/{e['id']}").json()
            if single['status']=='completed':break
            time.sleep(.02)
        assert single['result']=='[MOCK] Offline test response'

def test_shared_queue_limit(settings):
    with context(settings,SlowAtRole('planner')) as c:
        agents,w=seed(c)
        ids=[launch(c,w) for _ in range(10)]
        assert c.post(f"/api/workflows/{w['id']}/run",json={'title':'overflow','prompt':'x'}).status_code==429
        task=c.post('/api/tasks',json={'title':'Single','prompt':'x','agent_id':agents[2]['id']}).json()
        assert c.post(f"/api/tasks/{task['id']}/run").status_code==429
        for rid in ids:c.post(f'/api/workflow-runs/{rid}/cancel')

def test_workflow_launch_revalidates_changed_roles(settings):
    with context(settings) as c:
        agents,w=seed(c)
        a={k:v for k,v in agents[-1].items() if k not in ('id','created_at')};a['role']='executor'
        c.put(f"/api/agents/{agents[-1]['id']}",json=a)
        response=c.post(f"/api/workflows/{w['id']}/run",json={'title':'test','prompt':'x'})
        assert response.status_code==422 and response.json()['error']['code']=='reviewer_must_be_last'

class PermittedTool(MockProvider):
    async def generate(self,snapshot,messages,remaining_tokens):
        if snapshot['role']=='executor' and len(messages)==1:
            return Reply(calls=[{'name':'calculator','args':{'expression':'2+3'}}],input_tokens=2,output_tokens=3,
                content={'role':'model','parts':[{'function_call':{'name':'calculator','args':{'expression':'2+3'}}}]})
        if snapshot['role']=='executor':
            assert messages[-1]['parts'][0]['function_response']['response']['untrusted_tool_data']['value']==5
        return await super().generate(snapshot,messages,remaining_tokens)

def test_workflow_permitted_tools_and_agent_call_limit(settings):
    with context(settings,PermittedTool()) as c:
        agents,w=seed(c)
        a={k:v for k,v in agents[2].items() if k not in ('id','created_at')};a['tools']=['calculator']
        c.put(f"/api/agents/{agents[2]['id']}",json=a)
        rid=launch(c,w);r=wait(c,rid)
        assert r['status']=='completed' and r['calls']==5
        a['max_steps']=1;c.put(f"/api/agents/{agents[2]['id']}",json=a)
        rid=launch(c,w);r=wait(c,rid)
        assert r['error']=='step_limit' and r['calls']==3
