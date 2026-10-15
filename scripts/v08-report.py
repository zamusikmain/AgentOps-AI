"""Write local verification documentation from persisted artifacts. No network calls."""
from pathlib import Path
import json
root=Path(__file__).resolve().parents[1]
data=json.loads((root/'docs/v08-evaluation-results.json').read_text(encoding='utf8'))
ui=json.loads((root/'docs/v08-ui-verification.json').read_text(encoding='utf8'))
preserve=json.loads((root/'docs/v08-preservation.json').read_text(encoding='utf8'))
lines=[];notes=[]
for version,report in data['reports'].items():
 m=report['run']['metrics']['hybrid'];baseline=json.loads((root/'docs/v07-evaluation-results.json').read_text(encoding='utf8'))['reports'][version]['run']
 lines.append(f"| {version} / hybrid | {m['answer_correct']}/{m['cases']} | {m['correct_abstention_rate']:.1%} | {m['false_abstention_rate']:.1%} | {m['unsupported_answer_rate']:.1%} | {m['citation_validity_rate']:.1%} | {m['retrieval']['hit_at_1']:.2%} / {m['retrieval']['hit_at_5']:.2%} |")
 notes.append(f"\n{version}: baseline run `{baseline['id']}`, current `{report['run']['id']}`; baseline duration {baseline['duration_ms']} ms, current {report['run']['duration_ms']} ms. Quality comparison: {'PASS' if report['comparison']['result']['passed'] else 'FAIL'}. Input/output Mock tokens: {report['run']['provider_metadata'].get('input_tokens')} / {report['run']['provider_metadata'].get('output_tokens')}.\n")
text='''# AgentOps AI v0.8 — Production LLM Reliability & Observability

## 1. Обзор версии

Реализован локальный слой над Mock и Gemini, единая трассировка Single-Agent, Multi-Agent и offline Evaluation. Проверки выполнялись с Mock и SDK-заглушками. Production readiness **не заявляется**. Настоящий Gemini в v0.8: **NOT VERIFIED**, новых реальных LLM/embedding-запросов: **0**.

## 2. Архитектура провайдеров

`LLMProvider` сохраняет совместимый generate-контракт. Reply дополнен actual provider/model/request/trace, latency, finish_reason, cached/reasoning tokens и provenance reported/estimated/unknown. Существующий google-genai adapter и native function calling сохранены; SDK retry attempts=1. OpenAI/Anthropic/local integrations не выдаются за реализованные.

```mermaid
flowchart LR
  UI[RU/EN UI] --> Auth[Owner / scoped LLM RBAC]
  Auth --> Runners[Single / LangGraph Workflow / Offline Eval]
  Runners --> Bound[Version-bound execution facade]
  Bound --> Gate[Environment + operation + model policy]
  Gate --> Limits[Concurrency / rate / timeout / breaker]
  Limits --> Budget[Atomic budget reservation]
  Budget --> Mock[Offline Mock]
  Budget --> Gemini[Gemini adapter: disabled by default]
  Mock --> Trace[Metadata-only trace / usage / reconciliation]
  Gemini --> Trace
  Trace --> DB[(SQLite)]
  DB --> Dashboard[Requests / stats / budgets / comparison]
```

## 3. Model Registry

SQLite stores names, provider, capability list, availability, compatibility, context/output limits, streaming, pricing version and last verification. Mock `mock-v1` is explicitly local; Gemini default model remains **unverified**, with unknown limits/prices, no invented specifications. Registry PUT is admin-only, validates values, and does not enable the environment gate. Compatible entries require availability and last_verified. Verification entered by an administrator is a declaration, not proof of a live smoke test.

## 4. Execution Layer

Bound facade handles selection, prompt binding, operation/trace provenance, validation, timeouts, bounded attempts and safe errors. All application LLM paths use it; low-level SDK adapter remains independently testable with stubs. Each generation call creates a request; attempts are retained within it. Parent trace is execution/workflow/evaluation ID. No arbitrary code or new shell/network tools were added.

## 5. Offline Policy

Defaults: Mock, external API false, paid operations false, fallback false. Key presence grants no permission. Gemini additionally requires server provider/operation allowlists, approved model, known pricing and configured request/day/month budget. Model discovery is blocked without separate permission. Offline evaluation binds Mock even if workspace provider settings differ; it never sends evaluation fixtures to Gemini. `.env` was not modified.

## 6. Reliability Mechanisms

Concurrency semaphore; external per-minute admission limit; configurable 1–3 attempts; bounded exponential delay with jitter only for rate_limit/provider_unavailable. Authentication, authorization, configuration, budget and invalid responses do not retry. Timeouts may have been billed and never auto-retry. SQLite circuit breaker has closed/open/half_open with atomic single probe and restart recovery. Cancellation records cancelled status and conservatively retains dispatched reservations. Tool execution is outside the LLM retry loop, preserving existing approval/idempotency controls.

Optional fallback has a single explicit target and requires server model allowlist plus data-transfer permission; it is disabled by default. Mock degradation additionally requires local environment and explicit mock_degradation_allowed. Authentication/access/budget/ambiguous timeout never fall back. Source failure and actual target provider/model remain visible in linked traces and runner events.

## 7. Observability

Request/Trace IDs, tenant/user, timestamps, provider/model/operation/status, attempts, retry/fallback, latency, safe error category/code, usage, finish reason, pricing snapshot/version, prompt version, environment and permission provenance persist in SQLite. Diagnostic records retain **neither full prompt nor full response**. Legacy user-owned execution content remains in its existing protected history; this is distinct from diagnostics. API exposes scoped list/detail/summary and evaluation status for evaluation traces. Categories: authentication, authorization, rate_limit, timeout, provider_unavailable, invalid_response, context_limit, configuration, budget, cancelled.

## 8. Token & Cost Tracking

Gemini usage is reported when SDK metadata exists; Mock usage is estimated; absent metadata is unknown. Cached/reasoning tokens may be null. No unknown count is presented as measured usage. Offline Mock has zero external billing cost. Real prices remain unknown until explicitly configured. Pricing versions are immutable; changing rates requires a new version. Traces retain rates/version so historical cost is not recalculated against current config. Cost is an estimate in USD, not an invoice. Daily provider/model/operation grouping, monthly known cost, unknown usage/cost counters and held reserves are available.

## 9. Budget Guardrails

External dispatch reserves before SDK call under SQLite BEGIN IMMEDIATE. Checks request/trace, UTC day/month, optional provider/model monthly caps. A workflow trace shares a conservative request envelope; retries/fallback cannot reset it. Decimal comparisons and upward nanodollar rounding prevent floating tolerance bypass. Input estimate includes UTF-8 message/instruction/schema bytes, tool declarations and protocol margin, plus bounded output.

Reported usage settles actual estimated cost. Missing usage, timeout/cancel and possibly billed failures retain an uncertain reserve; restart does not erase it. An unexpected SDK overrun is saved as overdrawn, blocks the answer and subsequent budget admission, and does not retry. Already billed provider overrun cannot be undone; true hard billing ceilings require provider-side controls. Unknown pricing blocks external paid dispatch.

## 10. Evaluation Comparison

Completed runs of matching dataset hash and generation provider can be compared. Baseline/current IDs, metadata, per-mode deltas, quality regression list, token/duration/cost resource delta persist separately. Quality threshold allows zero regression in correctness, CAR, FAR, unsupported claims/answers, citation validity and Hit@1/5. Resource changes are informational; real-load latency/cost thresholds are not calibrated. Legacy missing prompt metadata is explicitly flagged. Mock/live results are not mixed into one quality claim.

## 11. Prompt Versioning

Immutable ID/version/body/digest, purpose, created timestamp, change description and draft/active/archived lifecycle. Secret-like assignments are rejected. System safety templates prefix existing task-specific instructions. Agent-specific instructions and legacy RAG/workflow templates remain separate, visible provenance limitations. Evaluation freezes concrete prompt version at launch; changing active version does not mutate an existing benchmark. No Gold references are added to generator input.

## 12. Dashboard

New LLM Observability navigation: metrics, status/provider/model/operation/error/date filters, request detail, persisted comparisons, prompt versions, model/budget JSON editor and execution policy form. Backend validates all writes. RU/EN, dark/light, mobile width 390 px and history after reload verified. Unknown cost/usage and offline status are explicit. Technical JSON remains diagnostic metadata; editors are minimal administrative forms, not a full provider onboarding wizard.

## 13. Security

Legacy workspace stays owner-only. New /api/llm namespace derives tenant/user/role from authenticated server principals, never headers/body. Admin required for model/policy/budget/prompt/comparison changes; viewer/operator are read-only for these controls. Other principals cannot enter legacy workspace routes. Queries/detail/stats/config/prompts/comparisons scope tenant. Browser proxy preserves host/origin checks and server-side credential handling. No keys in UI/localStorage or diagnostic metadata. Secret bundle check and scoped API tests included. This is not enterprise identity/SSO or full multi-tenant RAG.

## 14. Database Migrations

Additive Alembic 007 after 006: llm_configurations, prompt_versions, llm_executions, budget_reservations, evaluation_comparisons; tenant/request/filter indexes and foreign keys. Existing tables unchanged. Pre-upgrade SQLite backup resides under excluded backend/data/backups. All prior row hashes remain present; .env hash unchanged. Alembic test upgrades an old schema and preserves rows; production database is head 007. Recovery marks interrupted traces failed and retains uncertain reserves. Downgrade not executed.

## 15. Test Results

Final backend count is recorded in docs/v08-test-results.json after completion. Frontend: 10 passed; Playwright: 10 passed; TypeScript PASS; production build PASS. New tests cover metadata privacy, offline gate, selection, errors, bounded retry, auth no-retry, cancellation, timeout, breaker/probe, concurrent budget, usage/unknown pricing, reconciliation/overrun, RBAC/tenant, prompt immutability/activation, pricing immutability, regression detection. Existing SDK function calling, tools/MCP/approvals, Single/Multi, RAG/source permission and migration tests retained. All API billing tests use local stubs.

Initial browser run lacked downloaded Chromium; installed Edge was used without downloading another browser. New observability tests found and fixed summary-object rendering and mobile min-content overflow. Durable tracing increased evaluation latency; E2E benchmark completion wait changed from 30 to 90 seconds within the existing 120-second backend cap. No quality assertions or Gold fixtures were removed/changed.

## 16. Benchmark Comparison v0.7/v0.8

Original 40, expanded 64 and holdout partitions remain separate; no claim of statistical significance or live LLM quality follows from these small deterministic fixtures.

| Dataset | Correct | CAR | FAR | Unsupported | Citation validity | Hit@1 / Hit@5 |
|---|---:|---:|---:|---:|---:|---:|
'''+ '\n'.join(lines)+'\n'+'\n'.join(notes)+'''

All comparable quality deltas are zero. Resource latency increased with durable observability; see persisted resource_delta rather than hiding this cost. Expanded v2 retains independent development/calibration/holdout grouped_metrics. Holdout hybrid remains 12/12 with CAR 4/4 and FAR 0/8. The original RTO reference-string mismatch remains documented; Gold was not altered. Mock tokens are estimates; offline external billed cost is zero.

## 17. Known Limitations

- Real Gemini availability, Free Tier pricing, live retries/fallback and real usage billing: **NOT VERIFIED**.
- Live security review, penetration tests and realistic load: **NOT VERIFIED**; not production-ready.
- Local SQLite / single-process concurrency and per-minute admission; distributed limit coordination and provider-specific request-weight limits require further work. Budget/circuit transitions are SQLite-atomic; this does not make the rest of the platform multi-worker safe.
- Summary currently scans tenant history; large-scale rollups, bounded retention and paginated comparison details are future work.
- Pricing requires administrator verification; no automatic current-price discovery or invoice reconciliation. Provider may overrun its declared limit; local detection cannot undo billing.
- Streaming not implemented. Other providers not integrated. Full provider-specific parameter matrices and live capability probes require separate authorization.
- Prompt registry versions safety prefix; moving every legacy domain template into it and sophisticated variable/compatibility linting remain future improvements.
- No configurable storage of diagnostic raw content; default always no content. Enterprise classifications, audit export, managed secrets/SSO and full tenant-aware legacy RAG remain future work.
- Mock benchmark verifies retrieval/grounding and plumbing, not native Gemini answer quality. Resource thresholds are informational, not performance acceptance claims.

## 18. Production Readiness Checklist

- [x] Offline defaults and server gate; key alone insufficient.
- [x] Additive schema, backup, pre-existing data and .env preservation.
- [x] Atomic local budgets, conservative uncertain billing, no unlimited retries.
- [x] Real provider/model provenance, metadata-only traces, protected dashboard.
- [x] Existing functionality and offline RAG quality regression checks.
- [x] RU/EN, theme, mobile and persisted history verification.
- [ ] Authorized live provider capability/pricing/billing verification.
- [ ] Real-provider retry/fallback and uncertain billing incident rehearsal.
- [ ] External security review, enterprise identity and full tenant migration.
- [ ] Representative load, distributed coordination and retention/rollups.

## 19. Recommendations for v0.9

Authorized bounded live verification first; then provider-side billing ceilings and permission lifecycle, operational alerts/exports, shared limiter/worker coordination, complete domain prompt migration and typed administrative forms. Add streaming only after cancellation/usage semantics are verified. Benchmark real providers separately with locked prompt/dataset/retrieval versions and explicit approval. No commit, push or deployment performed.

Artifacts: v08-gap-analysis.md, v08-evaluation-results.json, v08-preservation.json, v08-ui-verification.json and RU/EN/mobile screenshots. Modified code groups: backend config/providers/db + migration007; llm_reliability.py/llm_api.py; main/execution/workflow/evaluation integrations; backend reliability and migration tests; frontend navigation/types/i18n/proxy/styles/observability component; observability E2E and benchmark wait; local verification scripts.
'''
(root/'docs/v0.8.md').write_text(text,encoding='utf8')
assert ui['history_after_reload'] and not ui['mobile_overflow'] and preserve['all_preexisting_rows_preserved'] and preserve['env_unchanged']
print('v0.8 documentation generated from persisted local results.')
