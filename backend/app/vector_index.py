from .profiling import timed
"""Bounded, replaceable vector repository on the existing SQLAlchemy/SQLite layer."""
import asyncio,math
from sqlalchemy import select,delete,func
from .db import KnowledgeDocument,KnowledgeChunk,KnowledgeVector,EmbeddingCache
from .embeddings import EmbeddingError,signature,cache_key,cache_key_signature,pack,unpack

class VectorIndex:
    def __init__(self,sessions,provider,settings,sanitize):
        self.sessions=sessions;self.provider=provider;self.settings=settings;self.sanitize=sanitize;self.lock=asyncio.Lock()
        if settings.embedding_revision:provider.parameters={**getattr(provider,'parameters',{}),'configured_revision':settings.embedding_revision}
    def plan(self,identifier):
        with self.sessions() as db:
            doc=db.get(KnowledgeDocument,identifier)
            if not doc:raise EmbeddingError('document_not_found')
            chunks=list(db.scalars(select(KnowledgeChunk).where(KnowledgeChunk.document_id==identifier)))
            missing=0;characters=0
            for chunk in chunks:
                text=self.sanitize(chunk.text);characters+=len(text)
                if not db.get(EmbeddingCache,cache_key(self.provider,text)):missing+=1
            return {'provider':self.provider.name,'model':self.provider.model,'dimension':self.provider.dimension,'signature':signature(self.provider),'external':self.provider.external,'chunks':len(chunks),'uncached_chunks':missing,'expected_requests':math.ceil(missing/self.settings.embedding_batch_size),'characters':characters,'data':'Sanitized extracted PDF text; no file, API key, paths or other documents.','external_enabled':self.settings.embedding_external_enabled}
    @timed('indexing')
    async def build(self,identifier,consent=False):
        async with self.lock:
            try:
                plan=self.plan(identifier)
                if self.provider.external and (not consent or not self.settings.embedding_external_enabled):raise EmbeddingError('embedding_consent_required')
                if plan['expected_requests']>self.settings.embedding_max_requests:raise EmbeddingError('embedding_request_limit')
                with self.sessions() as db:
                    doc=db.get(KnowledgeDocument,identifier)
                    if doc.status!='ready':raise EmbeddingError('document_not_ready')
                    count=db.scalar(select(func.count()).select_from(KnowledgeVector).join(KnowledgeChunk).where(KnowledgeChunk.document_id==identifier))
                    if doc.embedding_status=='ready' and doc.embedding_signature==plan['signature'] and count==doc.chunks:return {'skipped':True,'requests':0,'chunks':count}
                    doc.embedding_status='indexing';doc.embedding_error=None;db.commit()
                    rows=list(db.scalars(select(KnowledgeChunk).where(KnowledgeChunk.document_id==identifier).order_by(KnowledgeChunk.page,KnowledgeChunk.ordinal)))
                    entries=[(r.id,cache_key(self.provider,self.sanitize(r.text)),self.sanitize(r.text)) for r in rows]
                unique={key:text for _,key,text in entries};missing=[]
                with self.sessions() as db:
                    for key,text in unique.items():
                        cached=db.get(EmbeddingCache,key)
                        if cached:
                            if cached.signature!=plan['signature'] or cached.dimension!=self.provider.dimension:raise EmbeddingError('embedding_dimension_mismatch')
                            unpack(cached.vector,self.provider.dimension)
                        else:missing.append((key,text))
                    if db.scalar(select(func.count()).select_from(EmbeddingCache))+len(missing)>60000:raise EmbeddingError('embedding_index_limit')
                requests=0
                for start in range(0,len(missing),self.settings.embedding_batch_size):
                    if requests>=self.settings.embedding_max_requests:raise EmbeddingError('embedding_request_limit')
                    batch=missing[start:start+self.settings.embedding_batch_size];requests+=1
                    vectors=await asyncio.wait_for(asyncio.to_thread(self.provider.embed,[text for _,text in batch],'document'),self.settings.embedding_timeout_seconds)
                    if len(vectors)!=len(batch):raise EmbeddingError('embedding_invalid_batch')
                    blobs=[pack(vector,self.provider.dimension) for vector in vectors]
                    with self.sessions() as db:
                        for (key,_),blob in zip(batch,blobs):
                            if not db.get(EmbeddingCache,key):db.add(EmbeddingCache(id=key,signature=plan['signature'],dimension=self.provider.dimension,vector=blob))
                        db.commit()
                with self.sessions() as db:
                    doc=db.get(KnowledgeDocument,identifier)
                    if not doc:return
                    ids=[i for i,_,_ in entries]
                    db.execute(delete(KnowledgeVector).where(KnowledgeVector.chunk_id.in_(ids)))
                    for cid,key,_ in entries:db.add(KnowledgeVector(chunk_id=cid,cache_id=key))
                    doc.embedding_status='ready';doc.embedding_signature=plan['signature'];doc.embedded_chunks=len(entries);doc.embedding_error=None;db.commit()
                return {'skipped':False,'requests':requests,'chunks':len(entries)}
            except asyncio.CancelledError:
                self.failed(identifier,'embedding_cancelled');raise
            except Exception as exc:
                code=str(exc) if isinstance(exc,EmbeddingError) else 'embedding_timeout' if isinstance(exc,TimeoutError) else 'embedding_provider_error'
                self.failed(identifier,code);return {'error':code}
    def failed(self,identifier,code):
        with self.sessions() as db:
            doc=db.get(KnowledgeDocument,identifier)
            if doc:doc.embedding_status='needs_consent' if code=='embedding_consent_required' else 'failed';doc.embedding_error=code;db.commit()
    @timed('embedding')
    def query(self,text):
        if self.provider.external and not self.settings.embedding_external_enabled:raise EmbeddingError('embedding_consent_required')
        vectors=self.provider.embed([text],'query')
        if len(vectors)!=1:raise EmbeddingError('embedding_invalid_batch')
        return unpack(pack(vectors[0],self.provider.dimension),self.provider.dimension)
    def candidates(self,db,allowed):
        # Permission predicate is in SQL before vectors are read. No global in-memory matrix.
        query=select(KnowledgeChunk.id,KnowledgeChunk.document_id,EmbeddingCache.dimension,EmbeddingCache.vector).join(KnowledgeVector,KnowledgeVector.chunk_id==KnowledgeChunk.id).join(EmbeddingCache,EmbeddingCache.id==KnowledgeVector.cache_id).where(KnowledgeChunk.document_id.in_(allowed),EmbeddingCache.signature==signature(self.provider)).order_by(KnowledgeChunk.id).execution_options(yield_per=128)
        return db.execute(query)
    def delete_vectors(self,db,identifier):
        ids=select(KnowledgeChunk.id).where(KnowledgeChunk.document_id==identifier)
        affected=list(db.scalars(select(KnowledgeVector.cache_id).where(KnowledgeVector.chunk_id.in_(ids))))
        # Include caches from failed builds and older model versions, without storing PDF text in cache.
        signatures=list(db.scalars(select(EmbeddingCache.signature).distinct()))
        for text in db.scalars(select(KnowledgeChunk.text).where(KnowledgeChunk.document_id==identifier)):
            affected.extend(cache_key_signature(sig,self.sanitize(text)) for sig in signatures)
        db.execute(delete(KnowledgeVector).where(KnowledgeVector.chunk_id.in_(ids)))
        # Cache contains derived document data; delete orphaned entries, retain shared references.
        for start in range(0,len(affected),400):db.execute(delete(EmbeddingCache).where(EmbeddingCache.id.in_(affected[start:start+400]),~EmbeddingCache.id.in_(select(KnowledgeVector.cache_id))))
