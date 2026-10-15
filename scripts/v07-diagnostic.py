import sys,json
from pathlib import Path
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/'backend'))
from app.evidence import EvidenceSufficiencyService
from app.rag_answers import grounded_result,mock_selection
data=json.loads((root/'docs/v06-evaluation-results.json').read_text(encoding='utf8'))
for c in data['cases']:
    if c['mode']!='hybrid':continue
    context={'query':c['question'],'matches':c['retrieval']['matches'],'evidence_pipeline':True}
    a=json.loads(grounded_result(json.dumps(mock_selection(context)),context,'mock'));v=a['verification']
    correct=v['abstained'] if c['expected_behavior']=='abstain' else not v['abstained'] and all(s in v['safe_answer'] for s in c['expected_answer'])
    print(c['id'],correct,v['status'],[(f['key'],f['value']) for f in v['sufficiency']['facts']],v['reason'])
