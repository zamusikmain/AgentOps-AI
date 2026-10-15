"""Read-only embedding contract/index compatibility; does not build or mutate vectors."""
from sqlalchemy import select
from .db import KnowledgeDocument
from .embeddings import signature

def compatibility(knowledge,documents=None):
 p=knowledge.vectors.provider;sig=signature(p)
 with knowledge.sessions() as db:
  q=select(KnowledgeDocument).where(KnowledgeDocument.status=='ready')
  if documents is not None:q=q.where(KnowledgeDocument.id.in_(documents))
  docs=list(db.scalars(q))
 mismatched=[d.id for d in docs if d.embedding_status!='ready' or d.embedding_signature!=sig]
 return {'status':'BLOCKED' if mismatched else ('UNVERIFIED' if p.external else 'READY'),'provider':p.name,'model':p.model,'dimension':p.dimension,'embedding_version':getattr(p,'parameters',{}).get('configured_revision',p.model if not p.external else 'UNVERIFIED'),'vector_format':'float32-l2-v1','sanitizer_version':'pdf-data-v1','index_version':sig,'cache_namespace':sig,'reindex_required':mismatched,'verification':'UNVERIFIED' if p.external else 'MOCK','mutated':False}
