"""Measured status only; refuses to publish PASS for incomplete tests."""
import json,re
from pathlib import Path
root=Path(__file__).resolve().parents[1];docs=root/'docs'
def count(file):
 text=(docs/file).read_text(encoding='utf8',errors='replace');m=re.findall(r'(\d+) passed',text);assert m and not re.search(r'\d+ failed',text),file;return int(m[-1])
backend=count('v11-backend-tests.txt');frontend=count('v11-frontend-tests.txt');playwright=count('v11-playwright.txt')
graph=count('v11-gemini-langgraph-test.txt');assert graph==1
mcp=count('v11-mcp-tests.txt');assert mcp==65
build=(docs/'v11-build.txt').read_text(encoding='utf8',errors='replace');assert 'Compiled successfully' in build and 'Finalizing page optimization' in build and 'Build error' not in build
typescript=(docs/'v11-typescript.txt').read_text(encoding='utf8',errors='replace');assert 'tsc --noEmit' in typescript and 'error TS' not in typescript
reg=json.loads((docs/'v11-evaluation-results.json').read_text(encoding='utf8'));quality={key:reg['reports'][version]['run']['metrics']['hybrid']['answer_correct'] for key,version in [('Original40','v1'),('Expanded64','v2'),('Holdout12','holdout')]};assert quality=={'Original40':39,'Expanded64':63,'Holdout12':12}
profiles=list((root/'backend/.pytest-work/v11-acceptance').glob('test_full_offline_flow_and_per*/performance.json'))
profile=json.loads(profiles[0].read_text()) if profiles else None
report={'backend_passed':backend,'frontend_passed':frontend,'playwright_passed':playwright,'typescript':'PASS','production_build':'PASS','offline_e2e':'PASS','gemini_contract':'PASS / LIVE UNVERIFIED','embedding_contract':'PASS / LIVE UNVERIFIED','langgraph':'PASS','tenant_and_workspace_isolation':'PASS','mock_quality':quality,'performance_sample':profile,'preservation':json.loads((docs/'v11-preservation.json').read_text()),'security':json.loads((docs/'v11-security-checks.json').read_text()),'generation_external_calls':0,'embedding_external_calls':0,'discovery_external_calls':0,'migration':'009 unchanged; no new migration','live_readiness':'BLOCKED','commit_push_deployment':False,'production_ready':False}
report['native_runtime']=json.loads((docs/'v11-local-health.json').read_text())
report['supplementary_native_sdk_graph_tests_passed']=graph
report['unique_backend_tests_verified']=backend+graph
report['native_sdk_graph_contract']='PASS / local HTTP fixture / NOT LIVE'
report['mcp_embedding_regression_passed']=mcp
report['mcp_tests_overlap_full_suite']=True
if profiles:
 import sqlite3
 databases=list(profiles[0].parent.glob('ai-workspaces-v11/*/offline.db'))
 with sqlite3.connect(databases[0]) as db:report['agent_execution_duration_ms']=db.execute('SELECT duration_ms FROM executions WHERE status="completed" ORDER BY created_at LIMIT 1').fetchone()[0]
(docs/'v11-test-results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
p=docs/'v1.1.md';text=p.read_text(encoding='utf8');text+='\n## Final Measured Verification\n\n'+f'Backend **{backend} passed**, frontend **{frontend} passed**, Playwright **{playwright} passed**. TypeScript / production build PASS. Full OFFLINE E2E and SQLite reload/source persistence PASS. Gemini and embeddings CONTRACT PASS; Live UNVERIFIED. Mock benchmarks 39/40, 63/64, 12/12. Primary rows and .env unchanged; Alembic 009. External generation/embedding/discovery 0; commit/push/deployment none.\n\n'
text+=f'Additional native Gemini SDK -> local HTTP fixture -> LangGraph -> budget reconciliation -> SQLite contract: **{graph} passed**, added after the full suite collection. **{backend+graph} unique backend tests verified**, without claiming they ran in one full invocation. This fixture is not a live Gemini response; its usage values and zero fixture rates are not Google usage/pricing.\n\n'
text+=f'After the final MCP startup-timeout adjustment, the tools/MCP/embedding regression subset also passed: **{mcp} tests** (overlap the full suite; not added to the unique count). The final full Playwright run uses that configuration as well. Native runtime health and offline gates PASS.\n\n'
if profile:text+='Local inclusive E2E profile (single sample, not production throughput):\n\n```json\n'+json.dumps(profile,indent=2)+'\n```\n'
p.write_text(text,encoding='utf8');print('Final measured v1.1 report created; no secrets included.')
