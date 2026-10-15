"""Offline configuration calibration, never reads holdout examples."""
import hashlib,json
from .evidence import EvidencePolicy
def validate_splits(data):
    groups={s:[c for c in data['cases'] if c.get('split','development')==s] for s in ('development','calibration','holdout')}
    docs={s:{d for c in rows for d in c['scope']} for s,rows in groups.items()}
    contents={s:{hashlib.sha256(json.dumps(data.get('documents',{}).get(d,[d]),ensure_ascii=False).encode()).hexdigest() for d in names} for s,names in docs.items()}
    questions={s:{' '.join(c['question'].casefold().split()) for c in rows} for s,rows in groups.items()}
    for a,b in [('development','calibration'),('development','holdout'),('calibration','holdout')]:
        if docs[a]&docs[b] or contents[a]&contents[b] or questions[a]&questions[b]:raise ValueError('evaluation_split_leakage')
        for x in questions[a]:
            for y in questions[b]:
                # Exclude almost identical word order/paraphrase templates as well.
                sx=set(x.split());sy=set(y.split())
                if len(sx&sy)/max(1,len(sx|sy))>.8:raise ValueError('evaluation_near_duplicate')
    return groups
class CalibrationService:
    def calibrate(self,data,evaluate):
        groups=validate_splits(data);rows=groups['calibration']
        if not rows:raise ValueError('missing_calibration_set')
        candidates=[]
        for chunks in (5,8,12):
            policy=EvidencePolicy(max_chunks=chunks);metrics=evaluate(rows,policy)
            candidates.append({'policy':policy.__dict__,'metrics':metrics})
        safe=[c for c in candidates if c['metrics']['unsupported_answer_rate']==0 and c['metrics']['correct_abstention_rate']==1]
        if not safe:raise ValueError('no_safe_calibration')
        best=min(safe,key=lambda c:(c['metrics']['false_abstention_rate'],c['policy']['max_chunks']))
        return {'version':'calibration-v1','dataset_version':hashlib.sha256(json.dumps(data,sort_keys=True,ensure_ascii=False).encode()).hexdigest(),'split':'calibration','case_ids':[c['id'] for c in rows],'candidates':candidates,'selected_policy':best['policy'],'holdout_used':False,'objective':'zero unsupported, preserve correct refusals; then minimize false refusal and context size','immutable_checks':['exact_citation','numeric_values','permissions','document_version','conflict'],'completeness_threshold':1.0}
