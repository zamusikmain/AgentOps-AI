from .profiling import timed
"""Bounded, offline evidence semantics. No references, fixture values or LLM calls."""
import re,time
from dataclasses import dataclass,asdict
from typing import Protocol
from .knowledge_store import DANGEROUS,ABSENCE

# Domain vocabulary describes relations, never their values. Unknown relations abstain.
PATTERNS={
 'retention':r'retention|records.{0,15}kept|хранен|хранят|сохраня.*(?:журнал|аудит)|удержан',
 'logging':r'logging|stored activity|activity.{0,15}(?:stored|duration)',
 'response':r'response|respond|reaction|реакци|отреаг|реагир',
 'recovery':r'recovery|restoration|restore|восстанов',
 'backup':r'backup|резервн.*коп',
 'rpo':r'\brpo\b|data loss|потер.{0,30}(?:данн|врем)|врем.{0,40}потер',
 'rto':r'\brto\b',
 'project_code':r'(?:project|проек|портал).{0,45}(?:code|код|идентификатор)|(?:code|код|идентификатор).{0,45}(?:project|проек|портал)',
 'review_period':r'review period|срок рассмотр|рассмотрен',
 'founded':r'found(?:ed|ing)|основан',
 'countries':r'countries|странах|стран',
 'deadline':r'deadline|due date|крайний срок',
 'access_approval':r'(?:access|доступ).{0,80}(?:approval|approved|одобрен|согласован)|(?:approval|одобрен|согласован).{0,80}(?:access|доступ)',
}
LABELS={'retention':'Retention хранение аудита','logging':'Logging stored activity','response':'Response reaction реакция','recovery':'Recovery restoration восстановление','backup':'Backup резервная копия','rpo':'RPO data loss','rto':'RTO восстановление','project_code':'project code внутренний код проекта','review_period':'review period срок рассмотрения','founded':'founded основана','countries':'countries страны','deadline':'deadline крайний срок','access_approval':'access approval согласование доступа'}
def concepts(text):
    text=' '.join(text.casefold().split())
    found=[k for k,p in PATTERNS.items() if re.search(p,text)]
    if 'rpo' in found:found=[k for k in found if k!='recovery']
    if 'rto' in found:found=[k for k in found if k!='recovery']
    if 'backup' in found and 'recoverable' in text:found=[k for k in found if k!='recovery']
    return found

VALUE=r'\b\d{4}-\d{2}-\d{2}\b|\b[A-Z][A-Z0-9_]*-\d{2,}\b|\b\d+(?:[.,]\d+)?\s*(?:(?:working|calendar|рабоч\w*|календар\w*)\s+)?(?:minutes?|hours?|days?|минут\w*|час\w*|дней|дня|день|countries|стран\w*)\b|\b(?:19|20)\d{2}\b'
def normalized(value):
    s=value.casefold().replace(',','.');n=re.search(r'\d+(?:\.\d+)?',s)
    if re.fullmatch(r'\d{4}-\d{2}-\d{2}',s) or re.fullmatch(r'[a-z][a-z0-9_]*-\d+',s):return s
    unit='minute' if re.search(r'minut|минут',s) else 'hour' if re.search(r'hour|час',s) else 'day' if re.search(r'day|дн|день',s) else 'country' if re.search(r'countries|стран',s) else 'year'
    qualifier='working' if re.search(r'working|рабоч',s) else 'calendar' if re.search(r'calendar|календар',s) else ''
    # Do not equate working and calendar deadlines, or silently change units.
    return (n.group() if n else s,unit,qualifier)
def negated(text):return bool(re.search(r'\b(?:not|never|no)\b|\bне\b|никогда',text,re.I))
def condition(text):
    m=re.search(r'\b(?:if|unless|если|после|after|requires?|требуется|требует)\b(.+)',text,re.I)
    return m.group().casefold() if m else None

@dataclass
class Fact:
    key:str
    value:str
    quote:str
    chunk_id:str
    negated:bool=False

def extract_facts(matches):
    facts=[]
    for m in matches:
        text=m['excerpt'];lines=text.splitlines()
        if 'ожидаемый ответ' in text.casefold():continue
        # Preserve literal spans across PDF wraps; no reconstructed quotations.
        for span in re.finditer(r'[^.!?\n]+(?:\n[^.!?\n]+){0,2}[.!?]?',text):
            quote=span.group().strip()
            if DANGEROUS.search(quote) or ABSENCE.search(quote):continue
            flat=' '.join(quote.split());keys=concepts(flat)
            for key in keys:
                # Associate each label with the nearest following value, not all numbers in a paragraph.
                anchor=re.search(PATTERNS[key],flat,re.I)
                tail=flat[anchor.end():] if anchor else flat
                v=re.search(VALUE,tail,re.I)
                if not v and key=='founded':v=re.search(r'\b(?:19|20)\d{2}\b',flat)
                if key=='access_approval' and re.search(r'manager|руководител',flat,re.I):value='manager approval'
                elif v:value=v.group()
                else:continue
                facts.append(Fact(key,value,quote,m['chunk_id'],negated(flat)))
        # Row-oriented severity table: explicit P1 row + response/recovery columns.
        table=re.search(r'\bP1\s*\n[^\n]+\n(\d+[^\n]+)\n(\d+[^\n]+)',text)
        if table and re.search(r'Первичная реакция.*Целевое восстановление',text,re.S):
            for key,index in [('response',1),('recovery',2)]:facts.append(Fact(key,table[index].strip(),table.group(),m['chunk_id']))
    return list({(f.key,f.value,f.chunk_id,f.quote):f for f in facts}.values())

class SemanticVerificationAdapter(Protocol):
    def verify(self,claim:str,quotes:list[str])->dict:...
class DeterministicSemanticVerifier:
    def verify(self,claim,quotes):
        if any(claim.strip()==q.strip() for q in quotes):return {'status':'supported','method':'exact_source_span'}
        source=extract_facts([{'chunk_id':str(i),'excerpt':q} for i,q in enumerate(quotes)])
        proposed=extract_facts([{'chunk_id':'claim','excerpt':claim}])
        if not proposed:return {'status':'uncertain','method':'structured_relations','reason':'unknown_semantics'}
        observed={str(normalized(f.value)) for f in source}
        if any(str(normalized(value)) not in observed for value in re.findall(VALUE,claim,re.I)):
            return {'status':'unsupported','method':'structured_relations','reason':'unmatched_quantitative_claim'}
        for f in proposed:
            candidates=[s for s in source if s.key==f.key]
            if not candidates:return {'status':'uncertain','method':'structured_relations','reason':'missing_relation'}
            supported=[s for s in candidates if normalized(s.value)==normalized(f.value) and s.negated==f.negated]
            if not supported:return {'status':'unsupported','method':'structured_relations','reason':'value_or_negation_mismatch'}
            # General conditionals require literal condition; approval has a narrowly recognized prerequisite relation.
            if f.key!='access_approval' and any(condition(s.quote) for s in supported) and not any(condition(s.quote)==condition(claim) for s in supported):return {'status':'uncertain','method':'structured_relations','reason':'condition_not_established'}
        return {'status':'supported','method':'structured_relations'}

class EvidenceSufficiencyService:
    def assess(self,query,matches,accessible=True):
        if not accessible:return {'status':'inaccessible','reason':'document_denied','required':[],'missing':[],'facts':[],'conflicts':[]}
        required=concepts(query);facts=extract_facts(matches);relevant=[f for f in facts if f.key in required]
        if DANGEROUS.search(query):return {'status':'insufficient','reason':'unsafe_question','required':required,'missing':required,'facts':[],'conflicts':[]}
        conflicts=[]
        for key in required:
            variants={str((normalized(f.value),f.negated)) for f in relevant if f.key==key}
            if len(variants)>1:conflicts.append({'key':key,'values':sorted(variants)})
        missing=[k for k in required if not any(f.key==k for f in relevant)]
        parts=re.split(r'\band\b|\sи\s',query,flags=re.I)
        if len(parts)>1 and required and any(not concepts(part) for part in parts):missing.append('unrecognized_part')
        status='conflicting' if conflicts else 'sufficient' if required and not missing else 'partial' if relevant else 'insufficient'
        return {'status':status,'reason':'sources_conflict' if conflicts else 'missing_facts' if missing else 'unknown_question_relation' if not required else 'facts_complete','required':required,'missing':missing,'facts':[asdict(f) for f in relevant],'conflicts':conflicts,'method':'structured-relations-v2','confidence':None}

@dataclass(frozen=True)
class EvidencePolicy:
    max_passes:int=2
    max_chunks:int=12
    timeout_seconds:float=8
    max_repairs:int=1
    version:str='evidence-policy-v1'
    def __post_init__(self):
        if not 0<=self.max_passes<=2 or not 1<=self.max_chunks<=20 or not 0<self.timeout_seconds<=15 or not 0<=self.max_repairs<=1:raise ValueError('invalid_evidence_policy')

class ReRetrievalCoordinator:
    def __init__(self,policy=None):self.policy=policy or EvidencePolicy()
    @timed('reretrieval')
    def run(self,query,initial,search,authorize,neighbors=None):
        start=time.monotonic();authorize();matches=initial[:self.policy.max_chunks];service=EvidenceSufficiencyService();attempts=[];before=service.assess(query,matches)
        for index in range(self.policy.max_passes):
            decision=service.assess(query,matches)
            if decision['status'] in ('sufficient','conflicting','inaccessible') or decision['reason']=='unsafe_question':break
            if time.monotonic()-start>=self.policy.timeout_seconds:break
            missing=decision['missing'];refined=(' '.join(LABELS[k] for k in missing if k in LABELS) or query) if missing else query
            if index:refined=' '.join(missing) or query
            authorize() # Fail closed before every search; never retry denial.
            hits=search(refined)['matches'];authorize()
            expanded=neighbors(matches) if neighbors and index==0 else []
            authorize();known={m['chunk_id'] for m in matches};added=[m for m in hits+expanded if m['chunk_id'] not in known and not known.add(m['chunk_id'])]
            matches=(matches+added)[:self.policy.max_chunks]
            attempts.append({'pass':index+1,'query':refined,'new_matches':added[:self.policy.max_chunks],'decision':service.assess(query,matches),'elapsed_ms':round((time.monotonic()-start)*1000,3)})
        authorize();after=service.assess(query,matches)
        return {'matches':matches,'evidence':after,'retrieval_attempts':attempts,'initial_evidence':before,'reretrieval_success':before['status']!='sufficient' and after['status']=='sufficient','policy':asdict(self.policy),'latency_ms':round((time.monotonic()-start)*1000,3)}

class AnswerRepairPipeline:
    def __init__(self,policy=None,verifier=None):self.policy=policy or EvidencePolicy();self.verifier=verifier or DeterministicSemanticVerifier()
    @timed('repair')
    def apply(self,query,original,citations,matches,validate):
        start=time.perf_counter();decision=EvidenceSufficiencyService().assess(query,matches);byid={m['chunk_id']:m for m in matches};selected=[]
        if decision['status'] in ('sufficient','partial'):
            covered=set()
            for f in decision['facts']:
                if f['key'] in covered:continue
                m=byid[f['chunk_id']]
                if not validate(m,f['quote']):
                    from .providers import ProviderError
                    raise ProviderError('document_denied')
                c={**{k:m[k] for k in ('chunk_id','document_id','document','page')},'quote':f['quote']}
                if c not in selected:selected.append(c)
                covered.add(f['key'])
                if len(selected)>=5:break
            omitted=[k for k in decision['required'] if k not in covered and k not in decision['missing']]
            if omitted:decision={**decision,'status':'partial','reason':'answer_context_limit','missing':decision['missing']+omitted}
        original_claims=[{'text':s.strip(),**self.verifier.verify(s.strip(),[c['quote'] for c in citations])} for s in re.split(r'(?<=[.!?])\s+|\n+',original) if s.strip()][:40]
        safe='\n\n'.join(c['quote'] for c in selected)
        missing=decision['missing'];abstained=not bool(selected);partial=bool(selected and missing)
        message='В доступных документах недостаточно информации для ответа. / Insufficient information in the accessible documents.'
        if decision['status']=='conflicting':message='Доступные источники противоречат друг другу. / Accessible sources conflict.'
        if decision['reason']=='unsafe_question':message='Инструкции об обходе правил отклонены. / Instructions to bypass rules were rejected.'
        if partial:safe+='\n\nДанных для полного ответа нет. / Information for a complete answer is missing: '+', '.join(LABELS.get(k,'непроверенная часть вопроса / unverified part of the question') for k in missing)
        if abstained:safe=message
        changed=safe!=original;repairs=[{'attempt':1,'original_answer':original,'repaired_answer':safe,'reason':'evidence_based_reselection','removed_or_replaced':original_claims}] if changed and self.policy.max_repairs else []
        if not self.policy.max_repairs and changed:selected=citations;safe=message;abstained=True;partial=False
        claims=[{'text':c['quote'],'status':'supported','chunk_ids':[c['chunk_id']],'method':'exact_source_span'} for c in selected]
        checks=[{'citation_index':i,'exists_and_matches':validate(byid[c['chunk_id']],c['quote']),'document_id':c['document_id'],'chunk_id':c['chunk_id'],'page':c['page'],'document_sha256':byid[c['chunk_id']].get('document_sha256')} for i,c in enumerate(selected)]
        if any(not c['exists_and_matches'] for c in checks):
            from .providers import ProviderError
            raise ProviderError('document_denied')
        return {'version':'grounding-v2','status':'conflicting_evidence' if decision['status']=='conflicting' else 'insufficient_evidence' if abstained else 'partial' if partial else 'supported','verified':not abstained,'abstained':abstained,'reason':decision['reason'] if abstained or partial else None,'safe_answer':safe,'claims':claims,'citation_checks':checks,'conflicts':decision['conflicts'],'sufficiency':decision,'confidence':None,'original_answer':original,'original_claims':original_claims,'repair_attempts':repairs,'final_citations':selected,'verification_latency_ms':round((time.perf_counter()-start)*1000,3),'limitations':'Offline structured relations cover a bounded vocabulary; unknown semantic claims remain uncertain. Quotes are exact source spans, not model-authored facts.'}
