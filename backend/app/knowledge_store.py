from .profiling import timed
"""PDF ingestion and permission-scoped hybrid retrieval; external indexing requires consent."""
import asyncio,hashlib,json,math,re,sys
from collections import Counter
from pathlib import Path
from sqlalchemy import select,delete
from .db import KnowledgeDocument,KnowledgeChunk,Agent,Execution,WorkflowRun,EvaluationRun,serialize
from .services import ServiceError
from .repository import Repository
ROOT=Path(__file__).resolve().parents[1]
MAX_UPLOAD=5*1024*1024
STOP=set('какой какая какие какое сколько как что это время инцидент и в на по для из ли а о с the what how is are of to a an from for document pdf документ aurora portal'.split())
DANGEROUS=re.compile(r'игнориру[йя]|ignore\s+(all|previous|instructions)|раскро[йя]|reveal\s+(secret|key)|system\s+prompt|отправь|вредная\s+строка',re.I)
ABSENCE=re.compile(r'нет\s+(информации|данных|сведений)|не\s+(указан[аоы]?|приведен[аоы]?)|not\s+(specified|provided)|no\s+information',re.I)
def words(text):
    return [w[:4] if re.search(r'[а-яё]',w) and len(w)>4 else w[:6] if len(w)>6 else w for w in re.findall(r'[\w-]+',text.casefold()) if w not in STOP and len(w)>1]
def frequencies(text):return dict(Counter(words(text)))
def split_page(text,size=1000,overlap=160):
    text=text.replace('\x00','').strip();start=0
    while start<len(text):
        end=min(len(text),start+size)
        if end<len(text):
            boundary=text.rfind('\n',start+size//2,end)
            if boundary>start:end=boundary
        yield text[start:end].strip()
        if end==len(text):break
        start=max(start+1,end-overlap)
def safe_evidence(text):
    # Never alter archived extracted text. Only remove instruction-looking lines from model context.
    lines=text.splitlines();kept=[]
    for i,line in enumerate(lines):
        if DANGEROUS.search(line):continue
        if i and DANGEROUS.search(lines[i-1]):continue
        kept.append(line)
    return '\n'.join(kept)

class KnowledgeStore:
    def __init__(self,sessions,storage=None,settings=None,embedding_provider=None):
        from .config import Settings
        from .embeddings import MockEmbeddingProvider,GoogleEmbeddingProvider
        from .vector_index import VectorIndex
        settings=settings or Settings(_env_file=None)
        self.settings=settings
        self.sessions=sessions;self.storage=Path(storage or ROOT/'data/documents');self.storage.mkdir(parents=True,exist_ok=True)
        self.jobs={};self.lock=asyncio.Lock()
        provider=embedding_provider or (MockEmbeddingProvider(settings.embedding_dimension) if settings.embedding_provider=='mock' else GoogleEmbeddingProvider(settings))
        self.vectors=VectorIndex(sessions,provider,settings,safe_evidence)
    def view(self,row):return serialize(row)
    def neighbors(self,matches,allowed,limit=8):
        """Read adjacent chunks only after scope and source version validation."""
        self.validate_scope(allowed);out=[]
        with self.sessions() as db:
            for match in matches[:5]:
                if match['document_id'] not in allowed:raise ServiceError(403,'document_denied')
                doc=db.get(KnowledgeDocument,match['document_id']);chunk=db.get(KnowledgeChunk,match['chunk_id'])
                if not doc or not chunk or chunk.document_id!=doc.id or doc.sha256!=match.get('document_sha256'):raise ServiceError(409,'evaluation_source_changed')
                for c in db.scalars(select(KnowledgeChunk).where(KnowledgeChunk.document_id==doc.id,KnowledgeChunk.page==chunk.page,KnowledgeChunk.ordinal.between(max(0,chunk.ordinal-1),chunk.ordinal+1)).order_by(KnowledgeChunk.ordinal)):
                    out.append({'chunk_id':c.id,'document_id':doc.id,'document':doc.name,'page':c.page,'document_sha256':doc.sha256,'excerpt':safe_evidence(c.text),'rank':len(out)+1,'score':0,'reasons':['context_neighbor']})
                    if len(out)>=limit:return out
        return out
    def create(self,name,content):
        name=Path(name.replace('\\','/')).name
        if not name.lower().endswith('.pdf') or not content.startswith(b'%PDF-'):raise ServiceError(422,'invalid_pdf')
        if len(content)>MAX_UPLOAD:raise ServiceError(413,'pdf_too_large')
        with self.sessions() as db:
            digest=hashlib.sha256(content).hexdigest()
            existing=db.scalar(select(KnowledgeDocument).where(KnowledgeDocument.sha256==digest,KnowledgeDocument.status.in_(['ready','indexing'])))
            if existing:return serialize(existing)
            if Repository(db).count(KnowledgeDocument)>=100:raise ServiceError(409,'document_limit')
            row=KnowledgeDocument(name=name[:200],sha256=hashlib.sha256(content).hexdigest(),bytes=len(content))
            db.add(row);db.commit();identifier=row.id
            (self.storage/(identifier+'.pdf')).write_bytes(content)
            self.jobs[identifier]=asyncio.create_task(self.index(identifier))
            self.jobs[identifier].add_done_callback(lambda _:self.jobs.pop(identifier,None))
            return serialize(row)
    @timed('document_processing')
    async def index(self,identifier):
        process=None
        try:
            async with self.lock:
                import os,subprocess
                env={k:v for k,v in os.environ.items() if k in ('SystemRoot','WINDIR','TMP','TEMP')}
                process=await asyncio.create_subprocess_exec(sys.executable,'-I',str(Path(__file__).with_name('pdf_extract.py')),str(self.storage/(identifier+'.pdf')),stdin=asyncio.subprocess.DEVNULL,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.DEVNULL,env=env,**({'creationflags':subprocess.CREATE_NO_WINDOW} if os.name=='nt' else {}))
                async def read_output():
                    output=bytearray()
                    while piece:=await process.stdout.read(65536):
                        output.extend(piece)
                        if len(output)>4000000:raise ValueError('pdf_extraction_failed')
                    await process.wait()
                    return bytes(output)
                output=await asyncio.wait_for(read_output(),self.settings.pdf_processing_timeout_seconds)
                if process.returncode or len(output)>4000000:raise ValueError('pdf_extraction_failed')
                data=json.loads(output)
                if data.get('error'):raise ValueError(data['error'])
                with self.sessions() as db:
                    row=db.get(KnowledgeDocument,identifier)
                    if not row:return
                    self.vectors.delete_vectors(db,identifier)
                    db.execute(delete(KnowledgeChunk).where(KnowledgeChunk.document_id==identifier))
                    count=0
                    for page,text in enumerate(data['pages'],1):
                        for ordinal,chunk in enumerate(split_page(text)):
                            if not chunk:continue
                            db.add(KnowledgeChunk(document_id=identifier,page=page,ordinal=ordinal,text=chunk,terms=frequencies(safe_evidence(chunk))));count+=1
                    if not count:raise ValueError('pdf_no_text')
                    row.status='ready';row.pages=len(data['pages']);row.chunks=count;db.commit()
                await self.vectors.build(identifier)
        except asyncio.CancelledError:raise
        except Exception as exc:
            code=str(exc) if str(exc) in ('pdf_encrypted','pdf_no_text','pdf_page_limit','pdf_text_limit') else 'pdf_index_timeout' if isinstance(exc,TimeoutError) else 'pdf_extraction_failed'
            with self.sessions() as db:
                row=db.get(KnowledgeDocument,identifier)
                if row:row.status='failed';row.error=code;db.commit()
        finally:
            if process and process.returncode is None:process.kill();await process.communicate()
    def recover(self):
        with self.sessions() as db:
            for row in db.scalars(select(KnowledgeDocument).where(KnowledgeDocument.status=='indexing')):row.status='failed';row.error='server_restarted'
            for row in db.scalars(select(KnowledgeDocument).where(KnowledgeDocument.embedding_status=='indexing')):row.embedding_status='failed';row.embedding_error='server_restarted'
            db.commit()
    async def close(self):
        for job in list(self.jobs.values()):job.cancel()
        await asyncio.gather(*list(self.jobs.values()),return_exceptions=True)
        self.vectors.provider.close()
    def validate_scope(self,identifiers):
        with self.sessions() as db:
            if len(identifiers)!=len(set(identifiers)):raise ServiceError(422,'invalid_document_scope')
            for identifier in identifiers:
                row=db.get(KnowledgeDocument,identifier)
                if not row:raise ServiceError(404,'document_not_found')
                if row.status!='ready':raise ServiceError(409,'document_not_ready')
    def verify_citation(self,match,quote,allowed):
        with self.sessions() as db:
            chunk=db.get(KnowledgeChunk,match['chunk_id'])
            doc=db.get(KnowledgeDocument,match['document_id'])
            return bool(chunk and doc and doc.status=='ready' and doc.id in allowed and chunk.document_id==doc.id and chunk.page==match['page'] and doc.name==match['document'] and doc.sha256==match.get('document_sha256',doc.sha256) and quote in chunk.text)
    @timed('retrieval')
    def search(self,query,allowed,requested=None,limit=3,mode='hybrid',rerank=True):
        from .hybrid_search import search
        return search(self,query,allowed,requested,limit,mode,rerank)
    def reindex(self,identifier,consent=False):
        self.validate_scope([identifier])
        if identifier in self.jobs:raise ServiceError(409,'document_in_use')
        if self.vectors.provider.external and (not consent or not self.vectors.settings.embedding_external_enabled):raise ServiceError(403,'embedding_consent_required')
        with self.sessions() as db:
            doc=db.get(KnowledgeDocument,identifier)
            if hashlib.sha256((self.storage/(identifier+'.pdf')).read_bytes()).hexdigest()!=doc.sha256:raise ServiceError(409,'document_changed')
            # Preserve ready state so the worker can skip an unchanged complete index.
            doc.embedding_error=None;db.commit()
        self.jobs[identifier]=asyncio.create_task(self.vectors.build(identifier,consent))
        self.jobs[identifier].add_done_callback(lambda _:self.jobs.pop(identifier,None))
        return {'id':identifier,'status':'indexing'}
    async def remove(self,identifier):
        with self.sessions() as db:
            row=db.get(KnowledgeDocument,identifier)
            if not row:raise ServiceError(404,'document_not_found')
            for evaluation in db.scalars(select(EvaluationRun).where(EvaluationRun.status.in_(['queued','running']))):
                if identifier in evaluation.document_ids:raise ServiceError(409,'document_in_use')
            for cls in (Execution,WorkflowRun):
                for run in db.scalars(select(cls).where(cls.status.in_(['queued','running']))):
                    scope=run.snapshot.get('document_ids',[]) if cls==Execution else [i for a in run.snapshot['agents'] for i in a.get('document_ids',[])]
                    if identifier in scope:raise ServiceError(409,'document_in_use')
        job=self.jobs.get(identifier)
        if job:job.cancel();await asyncio.gather(job,return_exceptions=True)
        async with self.vectors.lock:
            with self.sessions() as db:
                for agent in db.scalars(select(Agent)):
                    if identifier in agent.document_ids:agent.document_ids=[i for i in agent.document_ids if i!=identifier]
                self.vectors.delete_vectors(db,identifier)
                db.execute(delete(KnowledgeChunk).where(KnowledgeChunk.document_id==identifier));db.delete(db.get(KnowledgeDocument,identifier));db.commit()
        (self.storage/(identifier+'.pdf')).unlink(missing_ok=True)
