from .profiling import phase
"""Streaming lexical/cosine search, rank fusion and deterministic feature reranking."""
import math,heapq,re
from collections import Counter
from sqlalchemy import select
from .db import KnowledgeDocument,KnowledgeChunk
from .embeddings import EmbeddingError,signature,unpack
POOL=30

def keep(heap,score,identifier):
    item=(score,identifier)
    if len(heap)<POOL:heapq.heappush(heap,item)
    elif item>heap[0]:heapq.heapreplace(heap,item)
def rrf(lexical,semantic,k=60):
    fused={}
    for ranking in (lexical,semantic):
        for rank,identifier in enumerate(ranking,1):fused[identifier]=fused.get(identifier,0)+1/(k+rank)
    return fused

def search(store,query,allowed,requested=None,limit=3,mode='hybrid',rerank=True):
    from .knowledge_store import words,safe_evidence,ABSENCE
    if mode not in ('lexical','semantic','hybrid'):raise ValueError('invalid_search_mode')
    selected=allowed if requested is None else requested
    if not selected or len(selected)!=len(set(selected)) or any(i not in allowed for i in selected):raise ValueError('document_denied')
    terms=words(query);term_set=set(terms);warning=None
    with store.sessions() as db:
        docs={d.id:d for d in db.scalars(select(KnowledgeDocument).where(KnowledgeDocument.id.in_(selected),KnowledgeDocument.status=='ready'))}
        if len(docs)!=len(selected):raise ValueError('document_unavailable')
        usable=[i for i,d in docs.items() if d.embedding_status=='ready' and d.embedding_signature==signature(store.vectors.provider)]
        lexical_heap=[];semantic_heap=[];df=Counter();count=0
        stmt=select(KnowledgeChunk).where(KnowledgeChunk.document_id.in_(selected)).execution_options(yield_per=128)
        if mode!='semantic' and terms:
            for row in db.scalars(stmt):
                count+=1
                df.update(term_set & set(row.terms))
            for row in db.scalars(stmt):
                score=sum(math.log(1+(count-df[t]+.5)/(df[t]+.5))*min(row.terms.get(t,0),2) for t in terms)
                if score:
                    evidence=safe_evidence(row.text)
                    if query.casefold().strip() in evidence.casefold():score*=1.2
                    if re.search(r'ожидаемый ответ|контрольные вопросы',evidence,re.I) and not ABSENCE.search(evidence):score*=.45
                    keep(lexical_heap,score,row.id)
        if mode!='lexical':
            try:
                if len(usable)!=len(selected):raise EmbeddingError('embedding_not_ready')
                q=store.vectors.query(query)
                for cid,did,dimension,blob in store.vectors.candidates(db,usable):
                    if dimension!=store.vectors.provider.dimension:raise EmbeddingError('embedding_dimension_mismatch')
                    vector=unpack(blob,dimension);score=max(-1.0,min(1.0,sum(a*b for a,b in zip(q,vector))))
                    if score>.05:keep(semantic_heap,score,cid)
            except EmbeddingError as exc:
                if mode=='semantic':raise ValueError(str(exc)) from None
                warning=str(exc);semantic_heap=[]
        lex=sorted(lexical_heap,reverse=True);sem=sorted(semantic_heap,reverse=True)
        lex_scores={cid:score for score,cid in lex};sem_scores={cid:score for score,cid in sem}
        base=rrf([cid for _,cid in lex],[cid for _,cid in sem]) if mode=='hybrid' else {cid:score for score,cid in (lex if mode=='lexical' else sem)}
        with phase('reranking'):
            candidates=[];max_base=max(base.values(),default=1)
            for cid,value in base.items():
                row=db.get(KnowledgeChunk,cid);evidence=safe_evidence(row.text)
                coverage=len(term_set & set(row.terms))/max(1,len(term_set))
                phrase=float(bool(query.strip() and query.casefold().strip() in evidence.casefold()))
                quality=.3 if re.search(r'ожидаемый ответ|контрольные вопросы',evidence,re.I) and not ABSENCE.search(evidence) else 1
                rerank_score=(.85*value/max_base+.10*coverage+.05*phrase)*quality if rerank and mode!='lexical' else value
                candidates.append({'chunk_id':cid,'document_id':row.document_id,'document':docs[row.document_id].name,'page':row.page,'ordinal':row.ordinal,'excerpt':evidence,'score':round(rerank_score,6),'lexical_score':round(lex_scores.get(cid,0),6),'semantic_score':round(sem_scores.get(cid,0),6),'fusion_score':round(value,6) if mode=='hybrid' else None,'rerank_score':round(rerank_score,6),'reasons':[name for name,scores in [('lexical',lex_scores),('semantic',sem_scores)] if cid in scores]+(['phrase'] if phrase else [])})
            candidates.sort(key=lambda m:(-m['score'],m['page'],m['ordinal'],m['chunk_id']))
        for rank,match in enumerate(candidates[:limit],1):
            match['rank']=rank;match.pop('ordinal');match['document_sha256']=docs[match['document_id']].sha256
        return {'matches':candidates[:limit],'scope':'uploaded-pdf','documents':selected,'mode':mode,'reranking':rerank,'warning':warning,'embedding_provider':store.vectors.provider.name,'embedding_model':store.vectors.provider.model,'mock_embeddings':not store.vectors.provider.external,'candidate_limit':POOL,'vector_read_batch':128}
