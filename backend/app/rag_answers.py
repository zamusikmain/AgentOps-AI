from .profiling import timed
from typing import Literal
import json,re
from pydantic import BaseModel,Field,ConfigDict
from .knowledge_store import DANGEROUS,ABSENCE,words
from .providers import ProviderError

class Citation(BaseModel):
    model_config=ConfigDict(extra='forbid')
    chunk_id:str=Field(max_length=36)
    quote:str=Field(min_length=1,max_length=1200)
class RagSelection(BaseModel):
    model_config=ConfigDict(extra='forbid')
    found:bool
    citations:list[Citation]=Field(max_length=5)

def mock_selection(context):
    matches=context['matches'];query=context['query'];terms=set(words(query))
    candidates=[]
    for match in matches:
        lines=match['excerpt'].splitlines()
        for i,line in enumerate(lines):
            if DANGEROUS.search(line) or line.strip().endswith('?'):continue
            common=len(terms & set(words(line)))
            if not common and not ABSENCE.search(line):continue
            # Include adjacent lines for table values, not only the query label.
            quote='\n'.join(lines[max(0,i-1):min(len(lines),i+3)]).strip()
            if DANGEROUS.search(quote):continue
            score=len(terms & set(words(quote)))+match['score']/5
            if 'ожидаемый ответ' in quote.casefold() and not ABSENCE.search(quote):score*=.25
            if re.search(r'(?<!\w)\d+(?!\w)',line):score+=.5
            if ABSENCE.search(quote):score+=1
            candidates.append((score,match,quote[:1200]))
    if not candidates:return {'found':False,'citations':[]}
    candidates.sort(key=lambda x:-x[0]);_,match,quote=candidates[0]
    return {'found':not bool(ABSENCE.search(quote)),'citations':[{'chunk_id':match['chunk_id'],'quote':quote}]}

def source_quote(excerpt,quote):
    """Permit PDF line-wrap whitespace only; return the literal source span, never model prose."""
    if not quote.strip():return None
    if quote in excerpt:return quote
    tokens=re.split(r'\s+',quote.strip())
    if not tokens or not all(tokens):return None
    matched=re.search(r'\s+'.join(re.escape(token) for token in tokens),excerpt)
    return matched.group() if matched else None

@timed('verification')
def grounded_result(text,context,provider,evidence_validator=None):
    try:selection=RagSelection.model_validate_json(text)
    except Exception:raise ProviderError('invalid_rag_output') from None
    matches={m['chunk_id']:m for m in context['matches']};citations=[]
    for citation in selection.citations:
        match=matches.get(citation.chunk_id)
        quote=source_quote(match['excerpt'],citation.quote) if match else None
        if not quote or DANGEROUS.search(quote):raise ProviderError('invalid_rag_citation')
        if evidence_validator and not evidence_validator(match,quote):raise ProviderError('invalid_rag_citation')
        citations.append({**{k:match[k] for k in ('chunk_id','document_id','document','page')},'quote':quote})
    if selection.found and not citations:raise ProviderError('invalid_rag_citation')
    # No model-authored factual prose is trusted. The answer is rendered from exact validated PDF quotations.
    if not selection.found and any(not ABSENCE.search(c['quote']) for c in citations):raise ProviderError('invalid_rag_citation')
    answer='\n\n'.join(c['quote'] for c in citations) if selection.found else 'В предоставленных документах информация не найдена. / Information not found in the supplied documents.'
    from .answer_verification import verify_answer
    verification=verify_answer(context['query'],answer if selection.found else '',citations,context['matches'])
    if context.get('evidence_pipeline'):
        from .evidence import AnswerRepairPipeline,EvidencePolicy
        verification=AnswerRepairPipeline(EvidencePolicy(**context['policy']) if context.get('policy') else None).apply(context['query'],answer if selection.found else '',citations,context['matches'],evidence_validator or (lambda m,q:q in m['excerpt']))
        for key in ('retrieval_attempts','initial_evidence','reretrieval_success','policy','latency_ms'):
            if key in context:verification[key]=context[key]
        citations=verification['final_citations'] or citations
    return json.dumps({'mode':'extractive-rag','provider':provider,'mock':provider=='mock','question':context['query'],'found':selection.found,'final_found':verification['verified'],'answer':answer,'citations':citations,'verification':verification},ensure_ascii=False)
