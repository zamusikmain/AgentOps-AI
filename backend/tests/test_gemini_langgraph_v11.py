"""Native Gemini SDK -> in-process HTTP fixture -> real LangGraph/SQLite, never Google."""
import json,time
import httpx
from google import genai
from google.genai import types
from fastapi.testclient import TestClient
from sqlalchemy import select
from app.config import Settings
from app.main import create_app
from app.providers import GeminiProvider
from app.db import Base,LLMExecution,BudgetReservation

def test_native_gemini_transport_through_langgraph(tmp_path):
    requests=[]
    def handler(request):
        requests.append(json.loads(request.content))
        return httpx.Response(200,json={'modelVersion':'LOCAL-HTTP-FIXTURE','candidates':[{'content':{'role':'model','parts':[{'text':'LOCAL TRANSPORT CONTRACT ONLY'}]},'finishReason':'STOP'}],'usageMetadata':{'promptTokenCount':4,'candidatesTokenCount':5,'thoughtsTokenCount':2}})
    settings=Settings(_env_file=None,llm_provider='gemini',gemini_model='contract-fixture',gemini_api_key='contract-placeholder',api_token='fixture-only-api',local_mcp_enabled=False,external_api_enabled=True,allowed_external_providers=['gemini'],allowed_external_operations=['generation'],validation_transport_is_stub=True,database_url=f'sqlite:///{tmp_path/"contract.db"}',checkpoint_database_path=tmp_path/'cp.db',knowledge_storage_path=tmp_path/'docs')
    provider=GeminiProvider(settings)
    provider.client=genai.Client(api_key='contract-placeholder',http_options=types.HttpOptions(httpx_async_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),httpx_client=httpx.Client(transport=httpx.MockTransport(handler)),retry_options=types.HttpRetryOptions(attempts=1)))
    app=create_app(settings,provider);Base.metadata.create_all(app.state.engine)
    with TestClient(app,headers={'Authorization':'Bearer fixture-only-api'}) as client:
        assert client.put('/api/llm/models',json={'provider':'gemini','model':'contract-fixture','display_name':'LOCAL TRANSPORT FIXTURE','availability':'available','compatible':True,'last_verified':'LOCAL CONTRACT ONLY','capabilities':[],'pricing_version':'fixture-zero-not-google-pricing','input_rate':0,'output_rate':0}).status_code==200
        assert client.put('/api/llm/budget',json={'request_usd':0,'day_usd':0,'month_usd':0}).status_code==200
        agent=client.post('/api/agents',json={'name':'Local transport contract','role':'executor','instructions':'This is an offline transport fixture.','model':'contract-fixture','tools':[],'max_steps':1,'max_tokens':128}).json()
        task=client.post('/api/tasks',json={'agent_id':agent['id'],'title':'Native SDK through LangGraph','prompt':'LOCAL_CONTEXT_TRANSFER_1182'}).json()
        run=client.post('/api/tasks/'+task['id']+'/run').json();deadline=time.monotonic()+35
        while time.monotonic()<deadline:
            run=client.get('/api/executions/'+run['id']).json()
            if run['status'] not in ('queued','running'):break
            time.sleep(.05)
        assert run['status']=='completed',run
        assert run['result']=='LOCAL TRANSPORT CONTRACT ONLY' and run['input_tokens']==4 and run['output_tokens']==7
        assert len(requests)==1 and requests[0]['contents'][0]['parts'][0]['text']=='LOCAL_CONTEXT_TRANSFER_1182'
        assert requests[0]['generationConfig']['maxOutputTokens']==128
        with app.state.sessions() as db:
            trace=db.scalar(select(LLMExecution));assert trace.provider=='gemini' and trace.status=='success' and trace.metadata_json['model_registry_version']=='LOCAL CONTRACT ONLY'
            assert db.scalar(select(BudgetReservation)).status=='settled'
        assert client.get('/api/executions/'+run['id']+'/events').json()['total']>=3
