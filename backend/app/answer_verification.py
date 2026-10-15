"""Conservative deterministic grounding. Lexical relevance is not semantic proof."""
import re
from .knowledge_store import words,ABSENCE,DANGEROUS
ABSTENTION='В доступных документах недостаточно информации для ответа. / Insufficient information in the accessible documents.'
STATUSES=('supported','unsupported','insufficient_evidence','conflicting_evidence','not_applicable')

def sentences(text):
    return [s.strip() for s in re.split(r'(?<=[.!?])\s+|\n+',text) if s.strip()][:40]

def facts(text):
    # General key/value extraction, never a corporate fact table. Units remain part of the value.
    rows=[]
    for line in text.splitlines():
        for m in re.finditer(r'([\w][\w /-]{1,70}?)\s*(?:[:=]| - )\s*(\d+(?:[.,]\d+)?\s*[\w-]+|[A-Z][A-Z0-9]+-\d+)\b',line):
            rows.append((' '.join(words(m[1])),m[2].casefold()))
        for m in re.finditer(r'\b([A-Z]{2,8})\s+(\d+\s+[\w]+)',line):rows.append((m[1].casefold(),m[2].casefold()))
    return rows

def verify_answer(query,answer,citations,matches,claims=None):
    terms=set(words(query));byid={m['chunk_id']:m for m in matches};checks=[]
    for index,c in enumerate(citations):
        m=byid.get(c['chunk_id']);valid=bool(m and c['document_id']==m['document_id'] and c['page']==m['page'] and c['quote'] in m['excerpt'])
        checks.append({'citation_index':index,'exists_and_matches':valid,'document_id':c['document_id'],'chunk_id':c['chunk_id'],'page':c['page'],'document_sha256':m.get('document_sha256') if m else None})
    supplied=claims if claims is not None else [{'text':s,'chunk_ids':[c['chunk_id'] for c in citations if s in c['quote']]} for s in sentences(answer)]
    checked=[]
    for item in supplied[:40]:
        text=item['text'];ids=item.get('chunk_ids',[])
        supporting=[c['chunk_id'] for c in citations if c['chunk_id'] in ids and text in c['quote']]
        status='not_applicable' if not text.strip() else 'supported' if supporting else 'unsupported'
        checked.append({'text':text,'status':status,'chunk_ids':supporting,'method':'exact_source_span','reason':None if supporting else 'claim_not_in_cited_span'})
    conflicting=[];values={}
    for m in matches:
        for key,value in facts(m['excerpt']):
            if not terms.intersection(words(key)):continue
            values.setdefault(key,{}).setdefault(value,[]).append(m['chunk_id'])
    for key,variants in values.items():
        if len(variants)>1:conflicting.append({'key':key,'values':variants})
    cited_text=' '.join(c['quote'] for c in citations)
    overlap=terms.intersection(words(cited_text));absence=any(ABSENCE.search(c['quote']) for c in citations)
    # Only establish answer sufficiency for explicit query anchors and a quoted value.
    # Paraphrases without anchors are intentionally refused instead of treating overlap as entailment.
    explicit=set(re.findall(r'\b[A-Z]{2,8}\b',query))
    anchored=bool(explicit and all(re.search(r'\b'+re.escape(t)+r'\b',cited_text) for t in explicit))
    field_question=bool(re.search(r'код|code|retention|хранят|сохраня|хранен|реакци|reaction|сколько дней',query,re.I))
    needed_keys={key for key in values if terms.intersection(words(key))}
    quoted_keys={key for key,value in facts(cited_text)}
    # Section numbers and version headings are not factual values answering a duration question.
    has_value=bool(re.search(r'\b[A-Z][A-Z0-9_]{1,24}-\d{2,}\b|\b\d{4}-\d{2}-\d{2}\b|\b\d+(?:[.,]\d+)?(?:\s+\w+){0,2}\s+(?:минут\w*|час\w*|дн\w*|день|days?|hours?|minutes?|seconds?)\b',cited_text,re.I))
    keyed=bool(needed_keys and needed_keys<=quoted_keys)
    sufficient=bool(citations and overlap and has_value and (anchored or field_question or keyed))
    incomplete=bool(re.search(r'\band\b|\sи\s',query,re.I) and len(needed_keys)>1 and not needed_keys<=quoted_keys)
    reason=None;status='supported'
    if DANGEROUS.search(query):reason='unsafe_question';status='not_applicable'
    elif conflicting:reason='sources_conflict';status='conflicting_evidence'
    elif any(not c['exists_and_matches'] for c in checks):reason='citation_mismatch';status='unsupported'
    elif any(c['status']=='unsupported' for c in checked):reason='unsupported_claim';status='unsupported'
    elif absence:reason='explicit_absence';status='insufficient_evidence'
    elif not citations:reason='no_evidence';status='insufficient_evidence'
    elif incomplete:reason='incomplete_multi_hop';status='insufficient_evidence'
    elif not sufficient:reason='semantic_support_not_established';status='insufficient_evidence'
    return {'version':'grounding-v1','status':status,'verified':reason is None,'abstained':reason is not None,'reason':reason,'safe_answer':answer if reason is None else ABSTENTION,'claims':checked,'citation_checks':checks,'conflicts':conflicting,'sufficiency':{'method':'conservative_anchor_and_value','established':sufficient,'query_anchors':sorted(overlap)},'confidence':None,'limitations':'Exact span support is deterministic; semantic sufficiency is conservative and heuristic, not a guarantee of factual truth.'}
