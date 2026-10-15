import asyncio
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
import pytest
from fastapi.testclient import TestClient
from google.genai import types, errors
from app.main import create_app
from app.config import Settings
from app.db import Base, Execution, Task, Agent
from app.providers import MockProvider, ProviderError, Reply, GeminiProvider
from app.tools import invoke

TOKEN = 'test-token-not-a-secret'

@pytest.fixture
def settings(tmp_path):
    return Settings(_env_file=None, database_url=f'sqlite:///{(tmp_path / "test.db").as_posix()}',
                    checkpoint_database_path=tmp_path / 'checkpoints.db',
                    llm_provider='mock', api_token=TOKEN)

@pytest.fixture
def client(settings):
    app = create_app(settings)
    Base.metadata.create_all(app.state.engine)
    with TestClient(app, headers={'Authorization': f'Bearer {TOKEN}'}) as client:
        yield client

def seed(client, **overrides):
    agent = client.post('/api/agents', json={'name':'Planner','role':'planner','instructions':'Make a plan',
                       'model':'gemini-2.5-flash','tools':[], **overrides}).json()
    task = client.post('/api/tasks', json={'title':'Test task','prompt':'Plan the work','agent_id':agent['id']}).json()
    return agent, task

def wait(client, eid):
    deadline=time.monotonic()+min(client.app.state.runner.settings.execution_timeout_seconds,30)+5
    while time.monotonic()<deadline:
        execution = client.get(f'/api/executions/{eid}').json()
        if execution['status'] not in ('queued','running'):
            return execution
        time.sleep(.03)
    pytest.fail('Execution did not finish')

def test_auth(client):
    assert client.get('/health', headers={'Authorization':''}).status_code == 200
    for path in ('/api/agents','/docs','/openapi.json'):
        assert client.get(path, headers={'Authorization':''}).status_code == 401
    assert client.get('/openapi.json').status_code == 200

def test_crud_validation_and_pagination(client):
    assert client.post('/api/agents', json={'name':'x'}).status_code == 422
    assert client.post('/api/agents', json={'name':'x','role':'executor','instructions':'x','model':'x','tools':['shell']}).status_code == 422
    a,t = seed(client)
    assert client.get('/api/agents?limit=1').json()['total'] == 1
    assert client.get('/api/agents?limit=1000').status_code == 422
    assert client.get(f"/api/agents/{a['id']}").json()['name'] == 'Planner'
    assert client.delete(f"/api/agents/{a['id']}").status_code == 409
    data = {k:v for k,v in a.items() if k not in ('id','created_at')}
    data['name'] = 'Updated'
    assert client.put(f"/api/agents/{a['id']}", json=data).json()['name'] == 'Updated'
    assert client.put(f"/api/tasks/{t['id']}", json={'title':'Edited','prompt':'Updated prompt','agent_id':a['id']}).status_code == 200
    assert client.delete(f"/api/tasks/{t['id']}").status_code == 204
    assert client.delete(f"/api/agents/{a['id']}").status_code == 204
    assert client.get('/api/tasks/not-found').status_code == 404

def test_complete_history_and_dashboard(client, settings):
    a,t = seed(client)
    response = client.post(f"/api/tasks/{t['id']}/run")
    assert response.status_code == 202
    e = wait(client, response.json()['id'])
    assert e['status'] == 'completed', e
    assert e['result'].startswith('[MOCK]')
    assert e['input_tokens'] == 12 and e['output_tokens'] == 8
    assert e['estimated_cost_usd'] is None and e['duration_ms'] is not None
    assert 'snapshot' not in e
    kinds = [v['kind'] for v in client.get(f"/api/executions/{e['id']}/events").json()['items']]
    assert kinds == ['started','model_requested','model_completed','completed']
    counts = client.get('/api/dashboard').json()['counts']
    assert counts['completed'] == 1 and counts['tokens'] == 20
    assert client.get(f"/api/executions?agent_id={a['id']}").json()['total'] == 1
    assert client.delete(f"/api/tasks/{t['id']}").status_code == 409
    assert settings.checkpoint_path.exists()
    # Reopen the same database in another application instance.
    reopened = create_app(settings)
    with TestClient(reopened, headers={'Authorization': f'Bearer {TOKEN}'}) as second:
        assert second.get(f"/api/executions/{e['id']}").json()['result'] == e['result']

class ToolProvider(MockProvider):
    async def generate(self, snapshot, messages, remaining_tokens):
        if len(messages)==1:
            return Reply(calls=[{'name':'calculator','args':{'expression':'2+3'}}],input_tokens=2,output_tokens=3,
                         content={'role':'model','parts':[{'function_call':{'name':'calculator','args':{'expression':'2+3'}}}]})
        assert messages[-1]['parts'][0]['function_response']['response']['untrusted_tool_data']['value'] == 5
        return Reply(text='5',input_tokens=4,output_tokens=1)

@pytest.mark.parametrize('allowed,expected', [(True,'completed'),(False,'failed')])
def test_tool_permission_and_loop(settings,allowed,expected):
    app=create_app(settings,ToolProvider())
    Base.metadata.create_all(app.state.engine)
    with TestClient(app,headers={'Authorization':f'Bearer {TOKEN}'}) as c:
        _, task=seed(c,tools=['calculator'] if allowed else [])
        e=wait(c,c.post(f"/api/tasks/{task['id']}/run").json()['id'])
        assert e['status']==expected,e
        if allowed:
            assert e['result']=='5' and e['output_tokens']==4
        else:
            assert e['error']=='tool_denied'

def test_step_limit(settings):
    app=create_app(settings,ToolProvider())
    Base.metadata.create_all(app.state.engine)
    with TestClient(app,headers={'Authorization':f'Bearer {TOKEN}'}) as c:
        _,task=seed(c,tools=['calculator'],max_steps=1)
        e=wait(c,c.post(f"/api/tasks/{task['id']}/run").json()['id'])
        assert e['error']=='step_limit'

class SlowProvider(MockProvider):
    async def generate(self,*args):
        await asyncio.sleep(20)
        return Reply(text='late')

def test_cancel_and_duplicate(settings):
    app=create_app(settings,SlowProvider())
    Base.metadata.create_all(app.state.engine)
    with TestClient(app,headers={'Authorization':f'Bearer {TOKEN}'}) as c:
        _,task=seed(c)
        eid=c.post(f"/api/tasks/{task['id']}/run").json()['id']
        assert c.post(f"/api/tasks/{task['id']}/run").status_code==409
        assert c.post(f'/api/executions/{eid}/cancel').status_code==200
        assert wait(c,eid)['status']=='cancelled'
        assert c.post(f'/api/executions/{eid}/cancel').status_code==409

def test_timeout(settings):
    settings.execution_timeout_seconds=1
    app=create_app(settings,SlowProvider())
    Base.metadata.create_all(app.state.engine)
    with TestClient(app,headers={'Authorization':f'Bearer {TOKEN}'}) as c:
        _,task=seed(c)
        e=wait(c,c.post(f"/api/tasks/{task['id']}/run").json()['id'])
        assert e['error']=='execution_timeout'

class BrokenProvider(MockProvider):
    async def generate(self,*args):
        raise ProviderError('rate_limit', http_status=429)

def test_provider_failure(settings):
    app=create_app(settings,BrokenProvider())
    Base.metadata.create_all(app.state.engine)
    with TestClient(app,headers={'Authorization':f'Bearer {TOKEN}'}) as c:
        _,task=seed(c)
        e=wait(c,c.post(f"/api/tasks/{task['id']}/run").json()['id'])
        assert e['error']=='rate_limit'
        events=c.get(f"/api/executions/{e['id']}/events").json()['items']
        assert events[-1]['payload']['provider_http_status']==429

def test_missing_key(settings):
    settings.llm_provider='gemini'
    settings.gemini_api_key=''
    # Pydantic validate_assignment is off; build a correctly typed fresh settings object.
    settings=Settings(_env_file=None, database_url=settings.database_url,api_token=TOKEN,llm_provider='gemini')
    app=create_app(settings)
    Base.metadata.create_all(app.state.engine)
    with TestClient(app,headers={'Authorization':f'Bearer {TOKEN}'}) as c:
        _,task=seed(c)
        assert c.post(f"/api/tasks/{task['id']}/run").status_code==503
        assert c.get('/api/providers').json()['configured'] is False

def test_restart_recovery(settings):
    app=create_app(settings)
    Base.metadata.create_all(app.state.engine)
    with app.state.sessions() as db:
        a=Agent(name='a',role='planner',instructions='x',model='x');db.add(a);db.flush()
        t=Task(title='t',prompt='x',agent_id=a.id,status='running');db.add(t);db.flush()
        e=Execution(task_id=t.id,agent_id=a.id,snapshot={},status='running');db.add(e);db.commit();eid=e.id
    with TestClient(app,headers={'Authorization':f'Bearer {TOKEN}'}) as c:
        assert c.get(f'/api/executions/{eid}').json()['error']=='server_restarted'

@pytest.mark.parametrize('expression',["__import__('os')",'2**1000000','1/0','x+1','9'*201])
def test_calculator_rejects_unsafe(expression):
    with pytest.raises(Exception):
        invoke('calculator',{'expression':expression},['calculator'])

def test_calculator():
    assert invoke('calculator',{'expression':'(10+2)/3'},['calculator'])=={'value':4}
    with pytest.raises(ValueError):
        invoke('utc_time',{},[])

def test_gemini_sdk_contract(settings):
    # No network: verify SDK types, message round trips, and preserved function-call parts.
    settings=Settings(_env_file=None,gemini_api_key='test-key',api_token=TOKEN)
    p=GeminiProvider(settings)
    p.client=MagicMock()
    p.client.aio.models.generate_content=AsyncMock(return_value=types.GenerateContentResponse(
        candidates=[types.Candidate(content=types.Content(role='model',parts=[types.Part(text='Answer')]))],
        usage_metadata=types.GenerateContentResponseUsageMetadata(prompt_token_count=4,candidates_token_count=3,thoughts_token_count=2)))
    async def run():
        reply=await p.generate({'model':'test-model','instructions':'x','tools':['calculator']},[{'role':'user','parts':[{'text':'task'}]}],128)
        assert reply.text=='Answer' and reply.output_tokens==5 and reply.input_tokens==4
        config=p.client.aio.models.generate_content.call_args.kwargs['config']
        assert config.automatic_function_calling.disable is True
        assert config.max_output_tokens==128
        assert config.tools[0].function_declarations[0].name=='calculator'
        assert len(config.tools[0].function_declarations)==1
        assert config.tools[0].function_declarations[0].parameters_json_schema['additionalProperties'] is False
        p.client.aio.models.generate_content.side_effect=errors.ClientError(429,{'error':{'message':'sensitive provider text'}})
        with pytest.raises(ProviderError,match='rate_limit'):
            await p.generate({'model':'x','instructions':'x','tools':[]},[],128)
    asyncio.run(run())

class OverBudgetProvider(MockProvider):
    async def generate(self, *args):
        return Reply(text='over budget', input_tokens=20, output_tokens=200)

def test_output_budget(settings):
    app=create_app(settings,OverBudgetProvider())
    Base.metadata.create_all(app.state.engine)
    with TestClient(app,headers={'Authorization':f'Bearer {TOKEN}'}) as c:
        _,task=seed(c,max_tokens=128)
        e=wait(c,c.post(f"/api/tasks/{task['id']}/run").json()['id'])
        assert e['error']=='token_limit' and e['output_tokens']==200

def test_snapshot_and_price(settings):
    settings.input_price_per_million=1
    settings.output_price_per_million=2
    app=create_app(settings)
    Base.metadata.create_all(app.state.engine)
    with TestClient(app,headers={'Authorization':f'Bearer {TOKEN}'}) as c:
        agent,task=seed(c,model=settings.gemini_model)
        e=wait(c,c.post(f"/api/tasks/{task['id']}/run").json()['id'])
        assert e['estimated_cost_usd']==pytest.approx(28/1e6)
        original=agent['instructions']
        data={k:v for k,v in agent.items() if k not in ('id','created_at')}
        data['instructions']='Changed after run'
        assert c.put(f"/api/agents/{agent['id']}",json=data).status_code==200
        with app.state.sessions() as db:
            assert db.get(Execution,e['id']).snapshot['instructions']==original

def test_disabled_agent_and_empty_inputs(client):
    _,task=seed(client,status='disabled')
    assert client.post(f"/api/tasks/{task['id']}/run").status_code==409
    assert client.post('/api/agents',json={'name':'  ','role':'planner','instructions':'x','model':'x'}).status_code==422
    assert client.post('/api/tasks',json={'title':'  ','prompt':'x','agent_id':'x'}).status_code==422

def test_openapi_auth_contract(client):
    schema=client.get('/openapi.json').json()
    assert schema['components']['securitySchemes']['LocalBearer']['scheme']=='bearer'
    assert schema['paths']['/api/agents']['post']['security']==[{'LocalBearer':[]}]
