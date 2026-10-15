"""Pure metrics independently computed from reference labels, not generator judgements."""
import math
def retrieval_metrics(ranked,relevant,k=5):
    relevant=set(relevant);ranked=list(dict.fromkeys(ranked))
    if not relevant:return {'applicable':False}
    ranks=[i+1 for i,c in enumerate(ranked) if c in relevant]
    dcg=sum(1/math.log2(i+2) for i,c in enumerate(ranked[:k]) if c in relevant)
    ideal=sum(1/math.log2(i+2) for i in range(min(k,len(relevant))))
    return {'applicable':True,**{'hit_at_'+str(n):int(any(r<=n for r in ranks)) for n in (1,3,5)},'mrr':1/min(ranks) if ranks else 0,'recall_at_'+str(k):len(set(ranked[:k])&relevant)/len(relevant),'ndcg_at_'+str(k):dcg/ideal if ideal else 0}
def aggregate(results):
    metrics={}
    for mode in ('lexical','semantic','hybrid'):
        cases=[r for r in results if r['mode']==mode];valid=[c['retrieval_metrics'] for c in cases if c['retrieval_metrics']['applicable']]
        answerable=[c for c in cases if c['expected_behavior']!='abstain'];unanswerable=[c for c in cases if c['expected_behavior']=='abstain']
        metrics[mode]={'cases':len(cases),'retrieval_cases':len(valid),'retrieval':{key:sum(v[key] for v in valid)/len(valid) if valid else None for key in ('hit_at_1','hit_at_3','hit_at_5','mrr','recall_at_5','ndcg_at_5')},'retrieval_latency_ms':sum(c['retrieval_latency_ms'] for c in cases)/len(cases) if cases else 0,'answer_correct':sum(c['answer_correct'] for c in cases),'answer_accuracy':sum(c['answer_correct'] for c in cases)/len(cases) if cases else None,'correct_abstentions':sum(c['verification']['abstained'] for c in unanswerable),'incorrect_abstentions':sum(c['verification']['abstained'] for c in answerable),'abstention_denominator':len(unanswerable),'false_abstention_denominator':len(answerable),'unsupported_answers':sum(not c['verification']['abstained'] and not c['answer_correct'] for c in cases),'citation_errors':sum(not check['exists_and_matches'] for c in cases for check in c['verification']['citation_checks']),'supported_claims':sum(cl['status']=='supported' for c in cases for cl in c['verification']['claims']),'unsupported_claims':sum(cl['status']=='unsupported' for c in cases for cl in c['verification']['claims'])}
        m=metrics[mode]
        # Reference string mismatch is answer quality, not proof of unsupported source claims.
        m['reference_mismatches_nonabstained']=m['unsupported_answers']
        m['unsupported_answers']=sum(not c['verification']['abstained'] and (c['verification']['status']=='unsupported' or any(cl['status']=='unsupported' for cl in c['verification']['claims'])) for c in cases)
        m['correct_abstention_rate']=m['correct_abstentions']/len(unanswerable) if unanswerable else None
        m['false_abstention_rate']=m['incorrect_abstentions']/len(answerable) if answerable else None
        m['unsupported_answer_rate']=m['unsupported_answers']/len(cases) if cases else None
        count=sum(len(c['verification']['citation_checks']) for c in cases)
        m['citation_validity_rate']=1-m['citation_errors']/count if count else None
        attempted=[c for c in cases if c['verification'].get('retrieval_attempts')]
        m['reretrieval_attempted']=len(attempted)
        m['reretrieval_successes']=sum(bool(c['verification'].get('reretrieval_success')) for c in attempted)
        m['reretrieval_success_rate']=m['reretrieval_successes']/len(attempted) if attempted else None
        m['repaired_answers']=sum(bool(c['verification'].get('repair_attempts')) for c in cases)
        m['answer_repair_rate']=m['repaired_answers']/len(cases) if cases else None
        m['evidence_statuses']={s:sum(c['verification'].get('sufficiency',{}).get('status')==s for c in cases) for s in ('sufficient','partial','insufficient','conflicting','inaccessible')}
        m['latency_breakdown_ms']={key:sum(c['verification'].get(key,0) for c in cases)/len(cases) if cases else 0 for key in ('latency_ms','generation_latency_ms','verification_latency_ms')}
        m['latency_breakdown_ms']={'initial_retrieval':m['retrieval_latency_ms'],**m['latency_breakdown_ms']}
    return metrics

def grouped_metrics(results):
    return {field:{value:aggregate([r for r in results if r.get(field,'development')==value]) for value in sorted({r.get(field,'development') for r in results})} for field in ('category','split')}
