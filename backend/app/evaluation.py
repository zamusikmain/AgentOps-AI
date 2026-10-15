"""Bounded offline benchmark. Reference fixtures never enter the generator context."""
import asyncio,json,hashlib,time,io,copy,threading
from pathlib import Path
from sqlalchemy import select
from .db import EvaluationRun,EvaluationCase,KnowledgeDocument,Agent,PromptVersion,serialize,now
from .services import ServiceError
from .knowledge_store import safe_evidence
from .rag_answers import grounded_result
from .providers import MockProvider
from .evaluation_metrics import retrieval_metrics,aggregate
DATASET=Path(__file__).resolve().parents[2]/'docs/fixtures/rag-evaluation-v1.json'
def dataset(version='v1'):
    if version not in ('v1','v2'):raise ServiceError(422,'evaluation_dataset_invalid')
    raw=DATASET.with_name('rag-evaluation-'+version+'.json').read_bytes();data=json.loads(raw)
    if len(raw)>200000 or len(data['cases'])!=(40 if version=='v1' else 64):raise ServiceError(409,'evaluation_dataset_invalid')
    return data,hashlib.sha256(raw).hexdigest()

def synthetic_pdf(pages):
    from pypdf import PdfWriter
    from pypdf.generic import DictionaryObject,NameObject,DecodedStreamObject
    writer=PdfWriter()
    for text in pages:
        page=writer.add_blank_page(600,800);font=DictionaryObject({NameObject('/Type'):NameObject('/Font'),NameObject('/Subtype'):NameObject('/Type1'),NameObject('/BaseFont'):NameObject('/Helvetica')})
        page[NameObject('/Resources')]=DictionaryObject({NameObject('/Font'):DictionaryObject({NameObject('/F1'):writer._add_object(font)})})
        stream=DecodedStreamObject();stream.set_data(('BT /F1 12 Tf 30 750 Td ('+text.replace('\\','\\\\').replace('(','\\(').replace(')','\\)')+') Tj ET').encode('ascii'))
        page[NameObject('/Contents')]=writer._add_object(stream)
    output=io.BytesIO();writer.write(output);return output.getvalue()

class Evaluator:
    def __init__(self,sessions,knowledge):self.sessions=sessions;self.knowledge=knowledge;self.jobs={};self.install_lock=asyncio.Lock()
    def scope(self,run):
        with self.sessions() as db:
            a=db.get(Agent,run.agent_id)
            if not a or a.status!='active' or 'knowledge_search' not in a.tools or any(i not in a.document_ids for i in run.document_ids):raise ServiceError(403,'document_denied')
            for identifier,version in run.provider_metadata.get('document_versions',{}).items():
                d=db.get(KnowledgeDocument,identifier)
                if not d or d.sha256!=version:raise ServiceError(409,'evaluation_source_changed')
        self.knowledge.validate_scope(run.document_ids)
    async def install(self,version='v1'):
        if self.knowledge.vectors.provider.external:raise ServiceError(403,'evaluation_offline_only')
        async with self.install_lock:
            data,version=dataset(version);ids=[]
            supplied=[('AgentOps_RAG_Test_Corporate_Policy.pdf',(DATASET.parent/'AgentOps_RAG_Test_Corporate_Policy.pdf').read_bytes())]+[(name,synthetic_pdf(pages)) for name,pages in data['documents'].items()]
            for name,pdf in supplied:
                doc=self.knowledge.create(name,pdf);ids.append(doc['id'])
                job=self.knowledge.jobs.get(doc['id'])
                if job:await asyncio.wait_for(asyncio.shield(job),40)
            with self.sessions() as db:
                a=Agent(name='RAG Evaluation v1',role='researcher',instructions='Read-only evaluation on explicitly assigned test documents.',model='mock',tools=['knowledge_search'],document_ids=ids,max_steps=1,max_tokens=2048,status='active');db.add(a);db.commit();return {'agent_id':a.id,'document_ids':ids,'dataset_version':version,'cases':len(data['cases'])}
    def start(self,agent_id,dataset_name='v1',options=None):
        if self.jobs:raise ServiceError(429,'evaluation_busy')
        if self.knowledge.vectors.provider.external:raise ServiceError(403,'evaluation_offline_only')
        data,version=dataset(dataset_name)
        with self.sessions() as db:
            from sqlalchemy import func
            if db.scalar(select(func.count()).select_from(EvaluationRun))>=500:raise ServiceError(409,'evaluation_result_limit')
            a=db.get(Agent,agent_id)
            if not a:raise ServiceError(404,'not_found')
            docs=list(db.scalars(select(KnowledgeDocument).where(KnowledgeDocument.id.in_(a.document_ids))))
            names={d.name:d.id for d in docs}
            # Bind references by trusted fixture content, not by a user-controlled filename.
            fixtures=[('AgentOps_RAG_Test_Corporate_Policy.pdf',(DATASET.parent/'AgentOps_RAG_Test_Corporate_Policy.pdf').read_bytes())]+[(name,synthetic_pdf(pages)) for name,pages in data['documents'].items()]
            for alias,pdf in fixtures:
                matches=[d for d in docs if d.sha256==hashlib.sha256(pdf).hexdigest()]
                if len(matches)!=1:raise ServiceError(403,'document_denied')
                names[alias]=matches[0].id
            required={n for c in data['cases'] for n in c['scope']}
            if not required<=set(names):raise ServiceError(403,'document_denied')
            ids=[names[n] for n in sorted(required)]
            run=EvaluationRun(agent_id=a.id,document_ids=ids,dataset_version=version,provider_metadata={'generation':'mock','model':'mock-v1','prompt_id':'evaluation','prompt_version':1,'environment':'local','permission':'offline-mock','evaluation_version':'grounding-v2','embedding':self.knowledge.vectors.provider.model,'real_requests':0,'generation_calls_limit':len(data['cases'])*3,'per_answer_output_limit':2048,'total_timeout_seconds':120,'reference_judge':'deterministic-reference-v1','dataset_name':dataset_name,'evidence_pipeline':'grounding-v2','validation_options':options or {}});self.scope(run);db.add(run);db.commit();rid=run.id
            prompt=db.scalar(select(PromptVersion).where(PromptVersion.tenant_id=='workspace',PromptVersion.prompt_id=='evaluation',PromptVersion.status=='active').order_by(PromptVersion.version.desc()))
            run.provider_metadata={**run.provider_metadata,'prompt_version':prompt.version if prompt else None,'document_versions':{d.id:d.sha256 for d in docs if d.id in ids}};db.commit()
        self.jobs[rid]=asyncio.create_task(self.execute(rid,data,names));self.jobs[rid].add_done_callback(lambda _:self.jobs.pop(rid,None));return self.read(rid)
    def read(self,rid):
        with self.sessions() as db:
            run=db.get(EvaluationRun,rid)
            if not run:raise ServiceError(404,'not_found')
            self.scope(run);return serialize(run)
    async def execute(self,rid,data,names):
        started=time.monotonic();results=[];provider=MockProvider();calls=0;input_tokens=0;output_tokens=0
        try:
            with self.sessions() as db:run=db.get(EvaluationRun,rid);run.status='running';db.commit()
            if hasattr(self,'llm'):provider=self.llm.bind('mock','evaluation',rid,run.provider_metadata.get('prompt_version'))
            options=run.provider_metadata.get('validation_options',{})
            # Per-run offline read cache. Fresh allowlist/version checks precede every lookup;
            # citations are still checked against SQLite, and no Gold/model response is cached.
            search_cache={};cache_lock=threading.RLock()
            def scoped_search(query,scope,mode='hybrid'):
                key=(query,tuple(scope),mode)
                with cache_lock:
                    if key in search_cache:
                        self.scope(run)
                        return copy.deepcopy(search_cache[key])
                found=self.knowledge.search(query,run.document_ids,scope,5,mode,True)
                with cache_lock:
                    if len(search_cache)<1024:search_cache[key]=copy.deepcopy(found)
                return found
            async with asyncio.timeout(options.get('timeout_seconds',self.knowledge.vectors.settings.evaluation_timeout_seconds)):
                from .evidence import EvidencePolicy,ReRetrievalCoordinator,AnswerRepairPipeline
                policy=EvidencePolicy()
                if run.provider_metadata.get('dataset_name')=='v2':
                    from .calibration import CalibrationService
                    def calibrate_rows(rows,p):
                        measured=[]
                        for case in rows:
                            self.scope(run)
                            if case.get('access')=='denied':
                                # Exercise the same allowlist rejection used by retrieval, before reading passages.
                                try:self.knowledge.search(case['question'],[],[names[n] for n in case['scope']],5,'hybrid',True)
                                except (ServiceError,ValueError) as e:
                                    if (e.code if isinstance(e,ServiceError) else str(e))!='document_denied':raise
                                else:raise ServiceError(409,'permission_check_failed')
                                measured.append({'abstained':True,'correct':True,'expected':case['expected_behavior']});continue
                            scope=[names[n] for n in case['scope']]
                            initial=scoped_search(case['question'],scope)
                            refined=ReRetrievalCoordinator(p).run(case['question'],initial['matches'],lambda q:scoped_search(q,scope),lambda:self.scope(run),lambda m:self.knowledge.neighbors(m,scope))
                            v=AnswerRepairPipeline(p).apply(case['question'],'',[],refined['matches'],lambda m,q:self.knowledge.verify_citation(m,q,run.document_ids))
                            correct=v['abstained'] if case['expected_behavior']=='abstain' else not v['abstained'] and all(s in v['safe_answer'] for s in case['expected_answer']) and (case['expected_behavior']!='partial' or v['status']=='partial')
                            measured.append({'abstained':v['abstained'],'correct':correct,'expected':case['expected_behavior'],'unsupported':any(c['status']!='supported' for c in v['claims']) and not v['abstained']})
                        negative=[r for r in measured if r['expected']=='abstain'];positive=[r for r in measured if r['expected']!='abstain']
                        return {'correct_abstention_rate':sum(r['abstained'] for r in negative)/len(negative),'false_abstention_rate':sum(r['abstained'] for r in positive)/len(positive),'unsupported_answer_rate':sum(r.get('unsupported',False) for r in measured)/len(measured),'answer_accuracy':sum(r['correct'] for r in measured)/len(measured)}
                    calibration=await asyncio.wait_for(asyncio.to_thread(CalibrationService().calibrate,data,calibrate_rows),min(self.knowledge.vectors.settings.evaluation_calibration_timeout_seconds,options.get('timeout_seconds',self.knowledge.vectors.settings.evaluation_timeout_seconds)))
                    policy=EvidencePolicy(**calibration['selected_policy'])
                    with self.sessions() as db:r=db.get(EvaluationRun,rid);r.provider_metadata={**r.provider_metadata,'calibration':calibration};db.commit()
                for case in data['cases']:
                    if options.get('case_ids') and case['id'] not in options['case_ids']:continue
                    for mode in options.get('modes',('lexical','semantic','hybrid')):
                        self.scope(run);scope=[names[n] for n in case['scope']];tick=time.perf_counter()
                        if case.get('access')=='denied':
                            try:await asyncio.to_thread(self.knowledge.search,case['question'],[],scope,5,mode,True)
                            except (ServiceError,ValueError) as e:
                                if (e.code if isinstance(e,ServiceError) else str(e))!='document_denied':raise
                            else:raise ServiceError(409,'permission_check_failed')
                            denied={'status':'inaccessible','safe_answer':'Нет разрешения на источники. / Source access denied.','verified':False,'abstained':True,'reason':'document_denied','claims':[],'citation_checks':[],'sufficiency':{'status':'inaccessible'},'retrieval_attempts':[],'repair_attempts':[]}
                            result={**case,'mode':mode,'retrieval':{'matches':[]},'retrieval_latency_ms':0,'retrieval_metrics':{'applicable':False},'actual_answer':{'answer':denied['safe_answer'],'citations':[]},'verification':denied,'answer_correct':True,'input_tokens':0,'output_tokens':0,'mock_tokens':True}
                            with self.sessions() as db:db.add(EvaluationCase(run_id=rid,case_id=case['id'],mode=mode,result=result));db.commit()
                            results.append(result);continue
                        hits=await asyncio.wait_for(asyncio.to_thread(scoped_search,case['question'],scope,mode),8)
                        latency=(time.perf_counter()-tick)*1000
                        context={'query':case['question'],'matches':hits['matches']}
                        refined=await asyncio.wait_for(asyncio.to_thread(ReRetrievalCoordinator(policy).run,case['question'],hits['matches'],lambda q:scoped_search(q,scope,mode),lambda:self.scope(run),lambda m:self.knowledge.neighbors(m,scope)),10)
                        context.update(refined);context['evidence_pipeline']=True
                        if calls>=len(data['cases'])*3:raise ServiceError(409,'evaluation_call_limit')
                        if calls>=options.get('max_requests',10000):raise ServiceError(409,'validation_request_limit')
                        if input_tokens+output_tokens>=options.get('max_total_tokens',100000000):raise ServiceError(409,'validation_token_limit')
                        calls+=1;generation_started=time.perf_counter();reply=await provider.generate({'rag_context':context},[],options.get('max_output_tokens',2048));generation_latency=(time.perf_counter()-generation_started)*1000
                        input_tokens+=reply.input_tokens;output_tokens+=reply.output_tokens
                        if input_tokens+output_tokens>options.get('max_total_tokens',100000000):raise ServiceError(409,'validation_token_limit')
                        if reply.output_tokens>2048 or output_tokens>len(data['cases'])*3*2048 or input_tokens>2000000:raise ServiceError(409,'evaluation_token_limit')
                        answer=json.loads(grounded_result(reply.text,context,'mock',lambda m,q:self.knowledge.verify_citation(m,q,run.document_ids)))
                        relevant=[f'{s["document"]}:{s["page"]}:{i}' for i,s in enumerate(case['expected_sources'])]
                        ranking=[]
                        for m in hits['matches']:
                            labels=[relevant[i] for i,s in enumerate(case['expected_sources']) if m['document_id']==names[s['document']] and m['page']==s['page'] and s['contains'] in m['excerpt']]
                            ranking.append(labels[0] if labels else 'irrelevant:'+m['chunk_id'])
                        verification=answer['verification'];correct=(verification['abstained'] if case['expected_behavior']=='abstain' else not verification['abstained'] and all(v in verification['safe_answer'] for v in case['expected_answer']) and (case['expected_behavior']!='partial' or verification['status']=='partial'))
                        verification['generation_latency_ms']=round(generation_latency,3)
                        result={**case,'mode':mode,'retrieval':hits,'retrieval_latency_ms':round(latency,3),'retrieval_metrics':retrieval_metrics(ranking,relevant),'actual_answer':answer,'verification':verification,'answer_correct':bool(correct),'input_tokens':reply.input_tokens,'output_tokens':reply.output_tokens,'mock_tokens':True}
                        if len(json.dumps(result).encode())>100000:raise ServiceError(409,'evaluation_result_limit')
                        self.scope(run)
                        with self.sessions() as db:db.add(EvaluationCase(run_id=rid,case_id=case['id'],mode=mode,result=result));db.commit()
                        results.append(result);await asyncio.sleep(0)
            from .evaluation_metrics import grouped_metrics
            with self.sessions() as db:r=db.get(EvaluationRun,rid);r.status='completed';r.metrics=aggregate(results);r.duration_ms=int((time.monotonic()-started)*1000);r.finished_at=now();r.provider_metadata={**r.provider_metadata,'actual_mock_calls':calls,'input_tokens':input_tokens,'output_tokens':output_tokens,'mock_tokens':True,'grouped_metrics':grouped_metrics(results)};db.commit()
        except BaseException as exc:
            code='evaluation_cancelled' if isinstance(exc,asyncio.CancelledError) else 'evaluation_timeout' if isinstance(exc,TimeoutError) else 'document_denied' if isinstance(exc,ServiceError) and exc.code=='document_denied' else 'evaluation_failed'
            with self.sessions() as db:r=db.get(EvaluationRun,rid);r.status='cancelled' if isinstance(exc,asyncio.CancelledError) else 'failed';r.error=code;r.metrics=aggregate(results);r.duration_ms=int((time.monotonic()-started)*1000);r.finished_at=now();db.commit()
    def recover(self):
        with self.sessions() as db:
            for r in db.scalars(select(EvaluationRun).where(EvaluationRun.status.in_(['queued','running']))):r.status='failed';r.error='server_restarted';r.finished_at=now()
            db.commit()
    async def close(self):
        for j in list(self.jobs.values()):j.cancel()
        await asyncio.gather(*list(self.jobs.values()),return_exceptions=True)
