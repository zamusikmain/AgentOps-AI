"""Legacy APIs cannot bypass workspace grants by enabling environment flags.

Only demonstrably in-process test transports can use the old contract path.
The fixture flag alone never permits an SDK network transport.
"""
import httpx
from .providers import ProviderError,MockProvider
from .embeddings import EmbeddingError

class UnscopedDispatch:
    def __init__(self,settings,adapter_for):self.settings,self.adapter_for=settings,adapter_for
    def claim(self,operation,provider,model,tokens=0,cost=None):
        if self.settings.validation_transport_is_stub:
            adapter=self.adapter_for(provider)
            if isinstance(adapter,MockProvider):return 'offline-contract'
            api=getattr(getattr(adapter,'client',None),'_api_client',None)
            sync=getattr(getattr(api,'_httpx_client',None),'_transport',None)
            asynchronous=getattr(getattr(api,'_async_httpx_client',None),'_transport',None)
            if isinstance(sync,httpx.MockTransport) and isinstance(asynchronous,httpx.MockTransport):return 'offline-contract'
        raise ProviderError('live_user_approval_required',403)
    def reported(self,*args):pass

class UnscopedEmbedding:
    def __init__(self,provider):
        self.provider=provider
        for name in ('name','external','model','dimension','parameters'):setattr(self,name,getattr(provider,name))
    def embed(self,*args):raise EmbeddingError('embedding_consent_required')
    def close(self):self.provider.close()
    @property
    def client(self):return self.provider.client
    @property
    def requests(self):return self.provider.requests
