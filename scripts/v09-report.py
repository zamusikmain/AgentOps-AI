"""Build v0.9 documentation from measured local artifacts only."""
from pathlib import Path
import json
root=Path(__file__).resolve().parents[1]
a=json.loads((root/'docs/v09-performance-baseline.json').read_text());b=json.loads((root/'docs/v09-performance-current.json').read_text());assert a['config_hash']==b['config_hash']
comparison={'config_hash':a['config_hash'],'environment_before':a['environment'],'environment_after':b['environment'],'workloads':{},'limitations':b['limitations'],'real_api_calls':0}
rows=[]
for name in ('sequential','concurrent','trace-heavy'):
 old=a['workloads'][name];new=b['workloads'][name];before=old['median_elapsed_ms'];after=new['median_elapsed_ms'];delta=(after-before)/before*100
 comparison['workloads'][name]={'before_ms':before,'after_ms':after,'delta_percent':delta,'commits_before':old['median_commits'],'commits_after':new['median_commits'],'runs':3,'samples_per_run':30}
 rows.append(f"| {name} | {before:.2f} | {after:.2f} | {delta:+.1f}% | {old['median_commits']:.0f} → {new['median_commits']:.0f} |")
for name in ('evaluation-heavy','retrieval-heavy','sqlite-contention','retry-overhead','circuit-open'):comparison['workloads'][name]={'before':a['workloads'][name],'after':b['workloads'][name]}
(root/'docs/v09-performance-comparison.json').write_text(json.dumps(comparison,indent=2),encoding='utf8')
quality=json.loads((root/'docs/v09-evaluation-results.json').read_text(encoding='utf8'));qrows=[]
for name,report in quality['reports'].items():
 m=report['run']['metrics']['hybrid'];qrows.append(f"| {name} | {m['answer_correct']}/{m['cases']} | {m['correct_abstention_rate']:.0%} | {m['false_abstention_rate']:.0%} | {m['unsupported_answer_rate']:.0%} | {m['citation_validity_rate']:.0%} | {m['retrieval']['hit_at_1']:.2%} / {m['retrieval']['hit_at_5']:.2%} |")
text='''# AgentOps AI v0.9 — Real LLM Validation & Performance

## 1. Version Overview

Локальная реализация и тестирование. Реальные внешние LLM/embedding API-вызовы: **0**. REAL_EXECUTION и внешние API в рабочей конфигурации выключены. Gemini live UNVERIFIED; установка SDK и локальный transport не являются реальным испытанием. .env сохранён. Production readiness не заявляется.

## 2. Architecture Changes

Новая ValidationRun — orchestration/plan над существующими EvaluationRun/EvaluationCase, не заменяет историю качества. Immutable dataset sidecars используют LLMConfiguration с отдельным namespace. Scope/RBAC взяты из существующей серверной модели. Старые Single/Multi/RAG/tool/MCP/approval сценарии сохранены.

```mermaid
flowchart LR
 UI[RU/EN Validation] --> Auth[Server tenant/user/role scope]
 Auth --> Registry[Immutable Dataset + Model + Prompt]
 Registry --> Readiness[Read-only readiness / cost plan]
 Readiness --> Dry[REAL_DRY_RUN: persist plan, zero dispatch]
 Readiness --> Mock[MOCK_ONLY: local evaluator]
 Readiness --> Gate[REAL_EXECUTION: disabled; future dual approval]
 Gate --> LLM[Existing LLM layer + atomic budget]
 Mock --> Eval[EvaluationRun / cases / reference scoring]
 LLM --> Eval
 Eval --> Trace[Metadata-only audit + monotonic profiles]
 Trace --> SQLite[(SQLite WAL / FULL durability)]
 SQLite --> Reports[JSON / Markdown / CSV export]
```

## 3. Real LLM Validation Framework

Scoped plans/runs/cancellation/history/export. User/admin/data approval binds exact plan hash, dataset hash and provider/model; grant consumed atomically once. A key is never consent. Future real path uses existing adapters/budget guard and bounded requests/tokens/timeout, sanitized RAG context and literal verified citations. Mechanism tested only with an isolated injected non-network provider, status CONTRACT_TESTED. Working configuration was never enabled. Provider selection uses distinct lazy Mock/Gemini adapters; selecting Gemini while default is Mock never relabels a Mock answer as Live.

## 4. Execution Modes

MOCK_ONLY strictly selects Mock identity, rejects external embedding dependency. REAL_DRY_RUN checks/records configuration without calling providers, indexing or reindexing. REAL_EXECUTION requires server real_validation_enabled plus external provider/operation policy, model/capabilities/pricing/budget, exact permission/data grant and one attempt/no fallback for the first real benchmark. UI real launch disabled in this delivery. A blocked dry plan is still exportable and persistable.

## 5. Gemini Compatibility

Installed google-genai exercised through httpx.MockTransport: request body, structured schema, max output, native tool calls, usage/cached/thought tokens, finish reasons, HTTP 401/403/404/429/503, context-limit 400, timeout, cancellation, transport interruption and malformed JSON. API diagnostics are mapped to safe codes. SDK retries remain 1; bounded layer retries covered separately. Model ID and optional reported model_version are retained. Status: **CONTRACT_TESTED**, availability/pricing/native live behavior **UNVERIFIED**. No Google endpoint was contacted.

## 6. Embedding Validation

Mock and Google embedding adapters, dimensions, L2 normalization, cache key, cosine primitives and version signatures covered locally; Google request batch format tested through synchronous MockTransport. Read-only compatibility includes provider/model/dimension/revision/vector format/sanitizer/index signature/cache namespace. Optional configured embedding_revision changes the signature only when explicitly set; default preserves every existing signature. Any incompatible index requires explicit reindex and is not silently combined. No existing document was reindexed and no external embedding call performed.

## 7. Dataset Management

Original40, Expanded64 and independent Holdout12 sidecars retain original question IDs, source hash, language, behavior/evidence/citations, category, difficulty and split; source Gold files unchanged. Metadata language/difficulty for existing files is a sidecar annotation, not a changed reference. Custom datasets have explicit language/scope/evidence/version/classification and unique IDs. Canonical content hash and raw built-in source hash checked before execution. Content changes require a new version. UI selects id AND version. Gold expected answers never enter model messages; comparison/scoring is separate.

## 8. Readiness Checks

READY/BLOCKED/UNVERIFIED, per-check reason codes and RU/EN explanations. Checks exact dataset/agent source hashes and current allowlist, provider/model, environment, API key presence without value, pricing/budget, requests, tokens, timeout/retry, prompt version, embedding/index, logging and exact approvals. Legacy documents are workspace-owner-only; foreign principals cannot assign them. Dry-run checks create no LLM traces and make no AI request. Real unknown prices or missing grants block execution.

## 9. Cost Planning

Plan shows generation calls and worst-case attempts, external query embedding upper bound, input/output token upper envelope, output/total/input limits, budget, timeout, data IDs/classification and prompt/retrieval configuration. External embedding cost is UNKNOWN and blocked in this release. Verification/repair are deterministic local operations, so additional verification/repair LLM calls are explicitly zero. Re-retrieval bounded at two passes; no automatic reindex. No unsupported duration estimate is invented. Existing atomic budget handles retries/uncertain billing; missing token metadata charges a conservative token envelope rather than zero. Cost is estimated, not an invoice.

## 10. Performance Profiling

perf_counter/context-local measurement; phase totals for retrieval, embedding, candidate reranking, generation, verification, reretrieval, repair, LLM total, SQLite reads/writes/commits and trace persistence. Validation/evaluation total persisted. Nested timings are inclusive and must not be summed as disjoint phases. SQLite instrumentation logs counts/duration only, never SQL parameters/content. Nearest-rank p50; p95 for >=20 samples, p99 for >=100; smaller samples explicitly limited. Retry sample 12 and one evaluation measurement have no meaningful p95/p99 claims.

## 11. SQLite Optimization

Measured v0.8 baseline: normal warm request had 6 commit boundaries, 4 writes and repeated metadata updates. Optimized: 3 mandatory durable states queued/running/final, 3 writes; pricing/parameters combined with running state, unchanged closed breaker rolls back its read transaction. No audit/security/budget events disabled; WAL and FULL synchronous durability retained. New composite tenant/created and tenant/trace/created indexes eliminate measured temporary ORDER BY B-trees. No asynchronous lossy buffer was introduced. scripts/v09-performance.py baseline-reproduced preserves a runnable legacy strategy only in fresh fixture DBs; original observed v0.8 measurements remain in v09-performance-observed-v08.json. Current implementation hash is recorded. No production endpoint can select legacy tracing. Persist failure fails closed and fsyncs a content-free emergency journal beside the database; if journal also fails, execution fails with audit_unavailable. Repairing an unavailable filesystem is not guaranteed by unit tests.

| Workload / 30 calls | Before median ms | After median ms | Delta | Commit boundaries |
|---|---:|---:|---:|---:|
'''+ '\n'.join(rows)+'''

Three repeats, two warmups, same seed/config hash/dataset, separate new local databases. Sequential/concurrent/trace-heavy differ in scheduling only; workload labels are explicit. Retrieval-heavy, evaluation-heavy, four-thread SQLite contention, retry and circuit-open measurements are in JSON. Variability is visible in raw runs; timing gains are local observations, not statistical significance or production throughput. No retrieval algorithm or relevance threshold changed merely for speed.

## 12. Regression Evaluation

Validation orchestrates quality runs linked to existing cases. v0.7/v0.8/current compare same original and expanded data/provider/modes. Holdout compares only the same 12-case partition, never against 64 totals. Native comparison of different provider/model/mode/dataset is descriptive, comparable=false, no combined PASS claim. Legacy comparisons include regressed Question IDs and reasons for correctness/false abstention/retrieval loss. Quality, CAR/FAR, unsupported/citation, Hit@1/5, repair/reretrieval and token/latency/cost resource changes retained. No live baseline exists.

| Dataset / hybrid | Correct | CAR | FAR | Unsupported | Citations | Hit@1 / Hit@5 |
|---|---:|---:|---:|---:|---:|---:|
'''+ '\n'.join(qrows)+'''

Comparable quality deltas remain zero. The existing reference-string mismatch is retained; Gold not tuned. These are **Mock** results, not real Gemini answers.

## 13. Failure Injection

Local fixtures cover timeout/rate limit/auth/authorization/network interruption/context limit/invalid or empty response/malformed JSON/missing usage/unknown price/breaker/budget/concurrency/cancel/SQLite lock/persistence failure. No unlimited retry or mock/live relabeling. Dispatched cancellation is marked possibly_sent and conservatively counted/reserved. Partial streaming cannot be requested (streaming=True schema rejects); true partial-stream recovery is **NOT VERIFIED / unsupported**, not claimed implemented.

## 14. Security

New routes use trusted authenticated scopes; headers cannot impersonate tenant. Admin-only dataset/approval/comparison writes; operator/admin can run/cancel; viewers scoped reads/exports. Foreign traces/runs/exports return 404. Current source permission is rechecked on read/run/export. Legacy datasets/documents remain owner-only. General LLM configuration excludes dataset bodies and approval records. Report export defaults omit questions, expected answers, generated text/excerpts, secrets and filesystem paths. CSV formula prefix guarded. Credential-like datasets are rejected, and native model context is blocked if it contains the backend access token or Gemini key. Browser host/origin checks retained, bundle secret scan PASS. Prompt injection defenses and MCP/tool approvals are existing bounded controls; no new shell/network tool introduced. This is not a complete enterprise security audit or tenant migration.

## 15. Dashboard

Real LLM Validation: execution mode/provider/model/dataset version, fixture preparation/agent scope, readiness reasons, cost/budget/request/token/timeout plan, quality/performance/failure/comparison, history/cancel and JSON/MD/CSV downloads, custom dataset creation. Static labels use existing RU/EN localization. Technical JSON retains stable protocol names and uppercase verification codes. REAL VERIFIED never displayed without a non-stub authorized completed run. Dark/light/mobile 390px and reload verified. REAL launch stays disabled; dry-run enabled without network.

## 16. Database Changes

Additive Alembic 008 adds only validation_runs and two trace query indexes; existing evaluation/cases/configuration reused. Local excluded SQLite backup created before migration. All pre-existing row hashes, .env, documents and embedding cache preserved; no destructive migration/downgrade, deletion or real reindex. Emergency audit under excluded data/test database location contains no request content.

## 17. Automated Test Results

Full backend **246 passed** at the main complete run; final targeted checks and counts recorded in v09-test-results.json. Frontend **10 passed**, Playwright **11 passed**, TypeScript PASS, production build PASS. Lint is not configured in package scripts (NOT CONFIGURED, not a PASS). SDK transport contracts and all 211 prior tests preserved. Existing tests changed only migration expected head and new version selector in new v0.9 E2E. Prior Gold/quality assertions unchanged.

## 18. v0.8 vs v0.9 Comparison

v0.8 211 backend / 10 frontend / 10 E2E; v0.9 246 / 10 / 11 at complete run. Same Mock quality: 39/40, 63/64, 12/12. Durable warm trace commits 6→3, writes 4→3; query plans use new composite indexes. Measured workload-specific before/after retained, including neutral/slower noisy runs. Native real quality, real embedding quality, price/billing and production load remain UNVERIFIED.

## 19. Known Limitations

- No authorized live test, current model availability/Free Tier/billing proof, or live embedding verification.
- External embedding execution remains blocked; a separate approved embedding experiment/pricing/grant path is required before live reindex. Local Google transport contract does not establish embedding quality.
- Real-mode path prepared and tested on local injected fixtures only. First future run must be small, one attempt/no fallback, with exact data/plan approval.
- Mock/real selection currently evaluates citation selections and deterministic evidence-backed quote answers; it does not claim unconstrained prose quality.
- Streaming unsupported; native stream interruption/recovery not tested.
- SQLite/local worker scope, scan-based statistics/retention and emergency journal management need operational hardening; no distributed throughput claim.
- Metadata-based sensitivity classification requires administrator review; no enterprise DLP/SSO/full tenant-aware legacy RAG.
- Custom datasets use current deterministic grounding verifier and may abstain on unsupported semantic patterns; results are measured, not guaranteed by fixtures.
- Resource thresholds are informational, zero-quality-regression enforced; no significance inference from 12/40/64 samples.

## 20. Real API Test Plan

Without activating now: verify project tier and actual model/capabilities/pricing with separate authorization; choose a tiny public independent dataset and locked prompt/retrieval/index versions; agree max calls/input/output/total/time/USD; retain external embedding disabled first. Explicit user/admin/data approval binds exact non-network plan. Then enable server policy deliberately, run once with no retries/fallback, reconcile actual SDK usage and uncertain billing, preserve citations/events and export a separate real baseline. Any quota/access/context/budget/storage error stops; no paid alternative or silent Mock substitution. Embeddings require a separate approved experiment and explicit reindex decision.

## 21. Recommendations for v1.0

Authorized limited live compatibility/quality and embedding experiments; then provider-side billing ceilings, typed approvals, measured alert/retention/rollup operations, classification/identity and multi-worker audit handling. Add streaming only after cancellation/billing semantics are defined and tested. Keep independent holdout and separate real/Mock baseline. No commit, push or deployment performed.

Artifacts: v09-gap-analysis.md; v09-performance-baseline/current/comparison.json; v09-evaluation-results.json; v09-ui-verification.json and screenshots; v09-preservation.json; v09-test-results.json. Reproduce with scripts/v09-performance.py, v09-verify.py, v09-ui-verify.cjs and normal test/build commands (PLAYWRIGHT_CHROMIUM_EXECUTABLE points to installed Edge). Primary code: validation.py, validation_api.py, validation_datasets.py, embedding_validation.py, profiling.py, migration008, existing LLM/RAG/evaluator integrations, validation-workspace.tsx and validation-i18n.ts, new backend/E2E tests.
'''
(root/'docs/v0.9.md').write_text(text,encoding='utf8');print('v0.9 measured performance comparison and documentation generated.')
