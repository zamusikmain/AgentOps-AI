"""Non-generative embedding adapters. Mock hashes text; no facts, answer bank or synonym fixture."""
import hashlib,json,math,re,struct,asyncio,httpx
from typing import Protocol
from google import genai
from google.genai import types,errors

class EmbeddingError(ValueError):
    def __init__(self,code,http_status=None):super().__init__(code);self.http_status=http_status
class EmbeddingProvider(Protocol):
    name:str;model:str;dimension:int;external:bool
    def embed(self,texts:list[str],task:str)->list[list[float]]:...
    def close(self):...

def normalize(vector,dimension):
    if not isinstance(vector,(list,tuple)) or len(vector)!=dimension:raise EmbeddingError('embedding_dimension_mismatch')
    if any(type(v) not in (float,int) or not math.isfinite(v) or abs(v)>1e12 for v in vector):raise EmbeddingError('embedding_invalid_vector')
    norm=math.sqrt(sum(v*v for v in vector))
    if norm<1e-12:raise EmbeddingError('embedding_invalid_vector')
    return [v/norm for v in vector]
def pack(vector,dimension):return struct.pack('<'+'f'*dimension,*normalize(vector,dimension))
def unpack(blob,dimension):
    if len(blob)!=dimension*4:raise EmbeddingError('embedding_dimension_mismatch')
    return normalize(struct.unpack('<'+'f'*dimension,blob),dimension)
def signature(provider):
    return hashlib.sha256(json.dumps({'provider':provider.name,'model':provider.model,'dimension':provider.dimension,'parameters':getattr(provider,'parameters',{}),'format':'float32-l2-v1','sanitizer':'pdf-data-v1'},sort_keys=True).encode()).hexdigest()
def cache_key(provider,text,task='document'):
    return cache_key_signature(signature(provider),text,task)
def cache_key_signature(model_signature,text,task='document'):
    return hashlib.sha256((model_signature+'\0'+task+'\0'+hashlib.sha256(text.encode()).hexdigest()).encode()).hexdigest()

class MockEmbeddingProvider:
    name='mock';model='mock-hash-ngram-v1';external=False;parameters={'token_prefix':4,'char_ngrams':3}
    def __init__(self,dimension=768):self.dimension=dimension;self.requests=0
    def embed(self,texts,task):
        self.requests+=1;vectors=[]
        for text in texts:
            vector=[0.0]*self.dimension
            tokens=re.findall(r'[\w-]+',text.casefold())
            features=[]
            for token in tokens:
                if len(token)<3:continue
                features.append(('word:'+token[:4],1.0))
                features.extend(('gram:'+token[i:i+3],.15) for i in range(len(token)-2))
            if not features:features=[('empty',1.0)]
            for feature,weight in features:
                value=int.from_bytes(hashlib.sha256(feature.encode()).digest()[:8],'little')
                vector[value%self.dimension]+=weight
            vectors.append(normalize(vector,self.dimension))
        return vectors
    def close(self):pass

class GoogleEmbeddingProvider:
    name='google';external=True
    def __init__(self,settings):
        if settings.embedding_model!='gemini-embedding-2':raise EmbeddingError('embedding_model_denied')
        self.settings=settings;self.model=settings.embedding_model;self.dimension=settings.embedding_dimension
        self.parameters={'document_prefix':'Represent this document for retrieval: ','query_prefix':'Represent this question for retrieval: '};self.client=None;self.requests=0
    def embed(self,texts,task):
        if task not in ('document','query'):raise EmbeddingError('embedding_invalid_task')
        if not isinstance(texts,list) or not 1<=len(texts)<=32 or any(not isinstance(t,str) or not t.strip() or len(t)>100000 for t in texts):raise EmbeddingError('embedding_invalid_input')
        if not self.settings.embedding_external_enabled:raise EmbeddingError('embedding_consent_required')
        if not self.settings.gemini_api_key.get_secret_value():raise EmbeddingError('missing_api_key')
        from .sensitive_context import contains_secret
        if any(contains_secret(self.settings,t) for t in texts):raise EmbeddingError('sensitive_context_denied')
        if self.client is None:self.client=genai.Client(api_key=self.settings.gemini_api_key.get_secret_value(),http_options=types.HttpOptions(timeout=self.settings.embedding_timeout_seconds*1000,retry_options=types.HttpRetryOptions(attempts=1)))
        try:
            self.requests+=1
            prefix=self.parameters['document_prefix' if task=='document' else 'query_prefix']
            # Each Content is a separate input. A flat list of parts would aggregate Embedding 2 inputs.
            response=self.client.models.embed_content(model=self.model,contents=[types.Content(parts=[types.Part(text=prefix+text)]) for text in texts],config=types.EmbedContentConfig(output_dimensionality=self.dimension))
            vectors=[e.values for e in response.embeddings or []]
            if len(vectors)!=len(texts):raise EmbeddingError('embedding_invalid_batch')
            return [normalize(v,self.dimension) for v in vectors]
        except errors.APIError as exc:raise EmbeddingError('embedding_rate_limit' if exc.code==429 else 'embedding_auth' if exc.code in (401,403) else 'embedding_model_unavailable' if exc.code==404 else 'embedding_provider_error',http_status=exc.code) from None
        except (TimeoutError,httpx.TimeoutException):raise EmbeddingError('embedding_timeout') from None
        except EmbeddingError:raise
        except Exception:raise EmbeddingError('embedding_provider_error') from None
    def close(self):
        if self.client:self.client.close();self.client=None
