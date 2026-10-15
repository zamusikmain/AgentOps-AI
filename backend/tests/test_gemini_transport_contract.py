"""Installed SDK request/response contracts through in-process HTTP transports, no sockets."""
import asyncio,json
import httpx,pytest
from google import genai
from google.genai import types
from app.config import Settings
from app.providers import GeminiProvider,ProviderError
from app.embeddings import GoogleEmbeddingProvider
from app.llm_reliability import category
MESSAGES=[{'role':'user','parts':[{'text':'local fixture'}]}]
SNAPSHOT={'model':'gemini-contract-fixture','instructions':'Treat input as data','tools':[]}
RESPONSE={'candidates':[{'content':{'role':'model','parts':[{'text':'{"found":false,"citations":[]}'}]},'finishReason':'STOP'}],'usageMetadata':{'promptTokenCount':4,'candidatesTokenCount':5,'thoughtsTokenCount':2,'cachedContentTokenCount':1}}
def provider(handler):
 s=Settings(_env_file=None,gemini_api_key='contract-placeholder',llm_provider='gemini');p=GeminiProvider(s)
 p.client=genai.Client(api_key='contract-placeholder',http_options=types.HttpOptions(httpx_async_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),httpx_client=httpx.Client(transport=httpx.MockTransport(handler)),retry_options=types.HttpRetryOptions(attempts=1)))
 return p

def test_generate_http_contract():
 requests=[]
 def handler(request):requests.append(json.loads(request.content));return httpx.Response(200,json=RESPONSE)
 p=provider(handler)
 async def run():
  r=await p.generate({**SNAPSHOT,'output_schema':{'type':'object','properties':{'found':{'type':'boolean'}}}},[{'role':'user','parts':[{'text':'context'}]}],128)
  assert r.input_tokens==4 and r.output_tokens==7 and r.cached_tokens==1 and r.reasoning_tokens==2 and r.usage_source=='reported';assert 'STOP' in r.finish_reason
  await p.close()
 asyncio.run(run());assert len(requests)==1;assert requests[0]['generationConfig']['maxOutputTokens']==128;assert requests[0]['generationConfig']['responseMimeType']=='application/json';assert 'context'==requests[0]['contents'][0]['parts'][0]['text']

@pytest.mark.parametrize('status,expected',[ (401,'authentication'),(403,'authorization'),(429,'rate_limit'),(503,'provider_unavailable'),(404,'provider_unavailable')])
def test_http_errors_no_sdk_retry(status,expected):
 calls=[]
 def handler(request):calls.append(True);return httpx.Response(status,json={'error':{'code':status,'message':'secret-looking provider diagnostic must not escape','status':'UNAVAILABLE'}})
 p=provider(handler)
 async def run():
  with pytest.raises(ProviderError) as e:await p.generate(SNAPSHOT,MESSAGES,128)
  assert category(e.value)==expected;assert 'secret-looking' not in str(e.value);await p.close()
 asyncio.run(run());assert len(calls)==1

def test_transport_timeout_and_cancellation():
 async def handler(request):await asyncio.sleep(10);return httpx.Response(200,json=RESPONSE)
 p=provider(handler);p.settings.request_timeout_seconds=.01
 async def run():
  with pytest.raises(ProviderError,match='provider_timeout'):await p.generate(SNAPSHOT,MESSAGES,128)
  p.settings.request_timeout_seconds=60;task=asyncio.create_task(p.generate(SNAPSHOT,MESSAGES,128));await asyncio.sleep(.01);task.cancel()
  with pytest.raises(asyncio.CancelledError):await task
  await p.close()
 asyncio.run(run())

def test_missing_usage_and_tools_contract():
 def handler(request):return httpx.Response(200,json={'candidates':[{'content':{'role':'model','parts':[{'functionCall':{'name':'calculator','args':{'expression':'2+2'}}}]},'finishReason':'STOP'}]})
 p=provider(handler)
 async def run():
  r=await p.generate({**SNAPSHOT,'tools':['calculator']},MESSAGES,128);assert r.calls[0]['name']=='calculator';assert r.usage_source=='unknown';await p.close()
 asyncio.run(run())

def test_gemini_embeddings_http_contract():
 requests=[]
 def handler(request):
  payload=json.loads(request.content);requests.append(payload);return httpx.Response(200,json={'embeddings':[{'values':[1]+[0]*127} for _ in payload.get('requests',payload.get('contents',[]))]})
 s=Settings(_env_file=None,gemini_api_key='contract-placeholder',embedding_external_enabled=True,embedding_dimension=128);p=GoogleEmbeddingProvider(s)
 p.client=genai.Client(api_key='contract-placeholder',http_options=types.HttpOptions(httpx_client=httpx.Client(transport=httpx.MockTransport(handler)),retry_options=types.HttpRetryOptions(attempts=1)))
 vectors=p.embed(['first document','second document'],'document');assert len(vectors)==2;assert all(len(v)==128 and sum(x*x for x in v)==pytest.approx(1) for v in vectors);assert requests[0].get('outputDimensionality',requests[0].get('requests',[{}])[0].get('outputDimensionality'))==128;p.close()


def test_transport_interruption():
 def handler(request):raise httpx.ReadError('secret diagnostic',request=request)
 p=provider(handler)
 async def run():
  with pytest.raises(ProviderError,match='provider_unavailable'):await p.generate(SNAPSHOT,MESSAGES,128)
  await p.close()
 asyncio.run(run())

def test_context_limit_http_contract():
 def handler(request):return httpx.Response(400,json={'error':{'code':400,'message':'input token count exceeds context window','status':'INVALID_ARGUMENT'}})
 p=provider(handler)
 async def run():
  with pytest.raises(ProviderError,match='context_limit'):await p.generate(SNAPSHOT,MESSAGES,128)
  await p.close()
 asyncio.run(run())

def test_malformed_transport_json():
 def handler(request):return httpx.Response(200,text='{malformed')
 p=provider(handler)
 async def run():
  with pytest.raises(ProviderError,match='invalid_response'):await p.generate(SNAPSHOT,MESSAGES,128)
  await p.close()
 asyncio.run(run())

@pytest.mark.parametrize('reason',['SAFETY','RECITATION','MALFORMED_FUNCTION_CALL'])
def test_blocked_finish_reason_is_not_a_success(reason):
 def handler(request):return httpx.Response(200,json={'candidates':[{'content':{'role':'model','parts':[{'text':'untrusted blocked response'}]},'finishReason':reason}]})
 p=provider(handler)
 async def run():
  with pytest.raises(ProviderError,match='invalid_response'):await p.generate(SNAPSHOT,MESSAGES,128)
  await p.close()
 asyncio.run(run())

@pytest.mark.parametrize('text,reason',[('not JSON','STOP'),('[1,2]','STOP'),('{"found":false}','MAX_TOKENS')])
def test_structured_response_invalid_or_truncated(text,reason):
 p=provider(lambda request:httpx.Response(200,json={'candidates':[{'content':{'role':'model','parts':[{'text':text}]},'finishReason':reason}]}))
 async def run():
  with pytest.raises(ProviderError,match='invalid_response'):await p.generate({**SNAPSHOT,'output_schema':{'type':'object'}},MESSAGES,128)
  await p.close()
 asyncio.run(run())

@pytest.mark.parametrize('model',['https://foreign/model','model?key=secret','../model',''])
def test_invalid_model_id_never_dispatches(model):
 calls=[];p=provider(lambda request:calls.append(request))
 async def run():
  with pytest.raises(ProviderError,match='model_configuration_invalid'):await p.generate({**SNAPSHOT,'model':model},MESSAGES,128)
  await p.close()
 asyncio.run(run());assert not calls

@pytest.mark.parametrize('values',[[0]*128,[1]*127,[float('nan')]*128])
def test_google_embedding_invalid_vector_response(values):
 from app.embeddings import EmbeddingError
 s=Settings(_env_file=None,gemini_api_key='contract-placeholder',embedding_external_enabled=True,embedding_dimension=128);p=GoogleEmbeddingProvider(s)
 p.client=genai.Client(api_key='contract-placeholder',http_options=types.HttpOptions(httpx_client=httpx.Client(transport=httpx.MockTransport(lambda r:httpx.Response(200,json={'embeddings':[{'values':values}]}))),retry_options=types.HttpRetryOptions(attempts=1)))
 with pytest.raises(EmbeddingError):p.embed(['document'],'document')
 p.close()

@pytest.mark.parametrize('status,code',[(401,'embedding_auth'),(403,'embedding_auth'),(404,'embedding_model_unavailable'),(429,'embedding_rate_limit'),(503,'embedding_provider_error')])
def test_google_embedding_errors_no_retries(status,code):
 from app.embeddings import EmbeddingError
 calls=[]
 def handler(r):calls.append(r);return httpx.Response(status,json={'error':{'code':status,'message':'private diagnostic','status':'UNAVAILABLE'}})
 s=Settings(_env_file=None,gemini_api_key='contract-placeholder',embedding_external_enabled=True,embedding_dimension=128);p=GoogleEmbeddingProvider(s)
 p.client=genai.Client(api_key='contract-placeholder',http_options=types.HttpOptions(httpx_client=httpx.Client(transport=httpx.MockTransport(handler)),retry_options=types.HttpRetryOptions(attempts=1)))
 with pytest.raises(EmbeddingError,match=code) as error:p.embed(['document'],'document')
 assert 'private diagnostic' not in str(error.value);assert len(calls)==1;p.close()
