"""Publish aggregate verification evidence only, never raw private traces or credentials."""
import json,re
from pathlib import Path
root=Path(__file__).resolve().parents[1];docs=root/'docs'
def read(name):return re.sub(r'\x1b\[[0-9;]*m','',(docs/name).read_text(encoding='utf8',errors='replace'))
backend=read('v12-backend-verified-tests.txt');assert 'failed' not in backend.lower()
full=int(re.search(r'(\d+) passed in',backend)[1]);assert full==326
assert '2 passed' in read('v12-score-tests.txt')
frontend=read('v12-frontend-tests.txt');assert re.search(r'Tests\s+15 passed',frontend)
playwright=read('v12-playwright-complete.txt');assert '18 passed' in playwright and not re.search(r'^\s*\d+ failed',playwright,re.M)
assert 'error TS' not in read('v12-typecheck.txt')
assert 'Compiled successfully' in read('v12-build.txt') and 'Route (app)' in read('v12-build.txt')
bench=json.loads((docs/'v12-evaluation-results.json').read_text())
for key,target in [('v1',39),('v2',63),('holdout',12)]:assert bench['reports'][key]['metrics']['hybrid']['answer_correct']>=target
preserved=json.loads((docs/'v12-preservation.json').read_text());assert preserved['all_primary_rows_unchanged'] and preserved['env_unchanged']
migration=json.loads((docs/'v12-migration-check.json').read_text());assert migration['clean_database']==migration['upgrade_009_to_head']=='PASS'
health=json.loads((docs/'v12-local-health.json').read_text());assert health['version']=='1.2.0' and not health['workspace_live_enabled']
smoke=json.loads((docs/'v12-synthetic-smoke.json').read_text());assert smoke['sqlite_history_after_reopen'] and smoke['sdk_construction_forbidden']
assert all(c['citation_valid'] for c in smoke['cases'])
result={'version':'1.2.0','backend_full_suite':{'passed':full,'duration_seconds':float(re.search(r'passed in ([\d.]+)',backend)[1])},
        'post_score_regression':{'passed':2,'new_unique_tests':1,'overlaps_full_suite':1},'backend_unique_tests_verified':full+1,
        'targeted_sdk_budget_embedding_regression':99,'frontend_tests':15,'playwright_tests':18,'typescript':'PASS','production_build':'PASS',
        'mock_benchmarks':{k:bench['reports'][k]['metrics']['hybrid']['answer_correct'] for k in ('v1','v2','holdout')},
        'gold_unchanged':bench['gold_unchanged'],'schema_head':'009','new_migration_required':False,'migration_checks':migration,
        'preservation':preserved,'native_health':health,'synthetic_mock_quality':{'passed':smoke['passed_reference_criteria'],'total':10,
             'failed_reference_cases':[c['case_id'] for c in smoke['cases'] if not c['passed']],'literal_scoped_citations_valid':True},
        'dry_run':smoke['dry_run'],'live_readiness':'BLOCKED / UNVERIFIED','real_generation_requests':0,'real_embedding_requests':0,
        'actual_google_cost_usd':None,'publication':'Separate Git/index/remote verification follows these local checks.'}
(docs/'v12-test-results.json').write_text(json.dumps(result,indent=2),encoding='utf8')
section='''\n## Final measured verification\n\n| Check | Result |\n|---|---|\n| Full backend suite | 326 passed, 993.90 s |\n| Additional scorer regression | 2 passed (one new test, one overlap with the full suite); 327 unique backend tests verified across these runs |\n| Targeted SDK/budget/embedding regression | 99 passed; overlaps the full suite |\n| Frontend / Playwright | 15 / 18 passed |\n| TypeScript / production build | PASS / PASS |\n| Mock Original40 / Expanded64 / Holdout12 | 39/40 / 63/64 / 12/12 |\n| Schema / clean + 009 upgrade | 009 / PASS, no new tables or destructive migration |\n| Primary DB rows + .env | Unchanged, including after native restart |\n| Native UI/API v1.2 / anonymous API | PASS / 401 |\n| New external generation / embeddings | 0 / 0 |\n\nThe initial batch-timeout failure was fixed; the completed full suite passed. The final scorer change has its own two-test regression, including an actual ten-case Mock workflow and a new counterexample test. Counts are not summed as though overlapping runs were additional unique tests.\n\n**New synthetic corpus quality: 5/10 with Mock.** The corrected scorer uses the displayed `safe_answer` and abstention state, not a discarded raw model quotation. Earlier provisional 8/10 counting was too optimistic and is superseded. Failures: `ru-exact`, `ru-paraphrase`, `en-exact`, `en-paraphrase`, `en-access`. Literal citations and document permissions remained valid: the access-negative failure used an irrelevant **allowed** source, not the restricted Change document. False abstentions and question relevance need further work; no special answers, source permission bypass or Gold edits were added to inflate the score. This is not Gemini quality.\n\nThe three-document/five-page synthetic run completed ten actual Mock tasks and reopened identical SQLite history. Its measured end-to-end sample is recorded in `v12-synthetic-smoke.json`; Mock token counts are estimates. No production latency or p95 is inferred from a single local sample.\n\nDry Run: LIVE BLOCKED, 45 maximum planned calls, 150,000 reserved tokens, 512 output tokens per generation, no retries/fallback, conservative cost ceiling $0.375. This is a cap-based upper bound, not a prediction of the provider invoice or a promise that every question fits the token cap. Working Live flags remain false.\n\n[Thinking documentation](https://ai.google.dev/gemini-api/docs/thinking) additionally confirms that the output cap includes thinking tokens; 3.5 Flash-Lite defaults to minimal thinking. A short cap can still truncate JSON, which stops the run without an automatic retry.\n\nAggregate evidence: `v12-test-results.json`, `v12-evaluation-results.json`, `v12-migration-check.json`, `v12-preservation.json`, `v12-local-health.json` and `v12-synthetic-smoke.json`. Raw runtime reports remain local and ignored. Git/index secret scan and remote publication are verified separately before the final release report.\n'''
p=docs/'v1.2.md';body=p.read_text(encoding='utf8');body=body.split('\n## Final measured verification')[0];p.write_text(body+section,encoding='utf8')
print('v1.2 aggregate report: PASS; full 326 + one new scorer test, frontend 15, E2E 18, external AI 0.')
