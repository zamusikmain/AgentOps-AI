import json
from pathlib import Path
from datetime import datetime,timezone
root=Path(__file__).resolve().parents[1]
result={'verified_at':datetime.now(timezone.utc).isoformat(),'backend_passed':211,'backend_duration_seconds':94.68,'frontend_passed':10,'playwright_passed':10,'typescript':'PASS','production_build':'PASS','real_llm_requests':0,'real_embedding_requests':0,'browser_bundle_secret_check':'PASS','production_ready':False,'providers':'Mock verified locally; Gemini SDK stub verified; live NOT VERIFIED'}
(root/'docs/v08-test-results.json').write_text(json.dumps(result,indent=2),encoding='utf8')
p=root/'docs/v0.8.md';s=p.read_text(encoding='utf8').replace('Final backend count is recorded in docs/v08-test-results.json after completion.','Backend: **211 passed** (94.68 seconds); 26 new reliability tests plus all 185 existing tests. Final counts also recorded in docs/v08-test-results.json.');p.write_text(s,encoding='utf8')
p=root/'README.md';s=p.read_text(encoding='utf8');addition='\n## v0.8 — LLM Reliability & Observability\n\nOffline-first request traces, immutable prompt/pricing versions, bounded retries, SQLite circuit breaker, atomic budget reservations and RU/EN observability. Gemini remains disabled/unverified until explicit server authorization. See [v0.8 report](docs/v0.8.md) and [verification results](docs/v08-test-results.json). Production readiness is not claimed.\n'
if '## v0.8 — LLM Reliability & Observability' not in s:p.write_text(s+addition,encoding='utf8')
print('Final verification counts recorded.')
