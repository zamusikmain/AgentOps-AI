"""Audit/replay frozen v0.6 results before implementation; no provider/network."""
import json,sys,hashlib
from pathlib import Path
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/'backend'))
from app.rag_answers import grounded_result,mock_selection
from app.evaluation_metrics import aggregate
source=root/'docs/v06-evaluation-results.json';raw=source.read_bytes();data=json.loads(raw)
cases=data['cases'];metrics=aggregate(cases);replay=[]
for c in cases:
    context={'query':c['question'],'matches':c['retrieval']['matches']}
    a=json.loads(grounded_result(json.dumps(mock_selection(context)),context,'mock'))
    replay.append(a['verification']==c['verification'])
assert all(replay), 'Frozen v0.6 replay differs'
hybrid=[c for c in cases if c['mode']=='hybrid'];false=[c for c in hybrid if c['expected_behavior']=='answer' and c['verification']['abstained']]
assert len(false)==13 and metrics['hybrid']['answer_correct']==26
causes={'exact-05':'Mock window ends at «Срок» before value; chunk has full value. Citation selection/window error, not retrieval.',
'paraphrased-01':'Mock chooses postmortem/40-minute scenario instead of RPO; relevant source rank 1. No semantic intent mapping.',
'paraphrased-02':'Mock chooses outage scenario rather than P1 reaction value; source rank 1. Requires condition-to-severity relation.',
'paraphrased-04':'Mock chooses document identifier instead of project identifier; source rank 1. Entity/field confusion.',
'paraphrased-06':'No lexical synonym records kept→Retention; mock hash vectors not semantic. Relevant source absent from top 5.',
'paraphrased-08':'No lexical synonym restoration→Recovery; relevant source absent from top 5.',
'paraphrased-09':'Recovery ranked above Backup; Mock picks Recovery. Relevant Backup rank 2; key completeness fails correctly.',
'paraphrased-10':'No lexical synonym stored activity→Logging; relevant source absent from top 5.'}
rows=[]
for c in false:
    cause=causes.get(c['id'],'Mock returns one citation although both source pages are retrieved. Verifier correctly rejects incomplete multi-hop.')
    rows.append({'id':c['id'],'question':c['question'],'reason':c['verification']['reason'],'cause':cause,'retrieval':c['retrieval_metrics'],'original_answer':c['actual_answer']['answer']})
report={'baseline_sha256':hashlib.sha256(raw).hexdigest(),'dataset_sha256':hashlib.sha256((root/'docs/fixtures/rag-evaluation-v1.json').read_bytes()).hexdigest(),'replayed_cases':len(replay),'identical_verifications':sum(replay),'metrics':metrics,'false_abstentions':rows,'extra_error':'paraphrased-05: source says recovery target 2 hours; gold literal RTO 2 часа is absent. Strict reference mismatch, not unsupported fact.'}
(root/'docs/v07-root-cause.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
lines=['# v0.7 — pre-change v0.6 audit','',f'Frozen replay: {sum(replay)}/{len(replay)} identical verification decisions. No external calls.','', '26/40 = 11 correct answers + 15 correct refusals. 25 answerable = 11 correct + 13 false refusals + 1 literal reference mismatch. CAR 15/15; FAR 13/25. No denominator bug found; strict literal judge limitation retained.','', '| Case | Refusal | Root cause |','|---|---|---|']
lines += [f"| {r['id']} | {r['reason']} | {r['cause']} |" for r in rows]
lines += ['', '## Implementation plan', '', 'Separate structured fact semantics and sufficiency from citation existence; bounded query refinement with permission/version checks; extractive repair using only validated source spans; frozen v1 comparison plus disjoint calibration/holdout fixtures; persist diagnostics in existing JSON histories; extend localized dashboard and run all regression checks.', '', 'Retrieval baseline remains primary-pass metrics; re-retrieval success is measured separately. Keep literal reference scoring unchanged for comparable v1 results.']
(root/'docs/v07-root-cause.md').write_text('\n'.join(lines),encoding='utf-8')
print(json.dumps({'replayed':sum(replay),'false_abstentions':len(rows),'hybrid':metrics['hybrid']}))
