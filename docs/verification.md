# Verification — 11 October 2026

**v0.3 verification:** Backend suite: 93 tests; frontend: 4 unit tests, TypeScript and production build; Playwright: 5 tests including real Calculator through Mock, local MCP, Approve/Reject and reload. An isolated local HTTP Fetch returned 200 / 577 bytes. Zero real Gemini calls. See [v0.3](v0.3.md).

**v0.2 verification:** 47 backend tests pass (10.48 s), including migration 001 → 002, structured handoffs, reviewer revisions, shared queue, every-stage cancellation/failure, budgets and restart recovery. Four frontend unit tests, TypeScript checks and production build pass. Four Playwright tests pass (21.7 s), including multi-agent RU/EN graph/results/history after reload and Single-Agent regression. Dialog placement was visually inspected and corrected. Real Gemini calls in v0.2: zero. Migration 002 was applied to local SQLite after online backup, preserving all previous rows and the successful v0.1 Gemini result. [Implementation and limitations](v0.2.md), [Mock run artifacts](workflow-mock-example.json).

The following sections describe the earlier v0.1 verification.
**Update:** The user subsequently confirmed the project's Free Tier and authorized one real generation. The live check succeeded with `gemini-3.5-flash-lite`: 67 input + 6 output tokens, 1521 ms, persisted SQLite result/events and UI verification after reload. See [gemini-live-verification.md](gemini-live-verification.md). The initial skipped-generation note below describes the earlier v0.1 verification, before this authorization.

## Passed

- Backend: **22 Pytest cases**, final run 3.91 seconds. CRUD, input validation, allowlist, arithmetic bounds, authentication, OpenAPI security contract, pagination, execution history, dashboard totals, persistent reopen, LangGraph tool loop, step/output limits, cancellation, duplicate prevention, timeout, rate-limit handling, restart recovery, immutable snapshots and configured cost calculation.
- Gemini SDK contract: async mock validates official google-genai configuration, native Content serialization, tool schemas, disabled automatic execution, token/think usage and sanitized 429 error. **No Google network request** in these tests.
- Frontend: **4 Vitest cases** covering RU/EN key parity, safe error fallback, API error propagation and no-content deletion.
- TypeScript: `tsc --noEmit` and Next.js build type validation pass.
- Frontend production build: passes with Next.js 16.4.0, one build worker.
- Playwright / installed Microsoft Edge: **3 E2E cases pass** (45.7 seconds including server startup). Real browser → Next.js proxy → real FastAPI → real LangGraph → SQLite, with an explicitly labeled offline LLM mock. Agent creation/edit, task creation/run, events and tokens, result after reload, RU/EN, theme switch, mobile navigation, no horizontal overflow, cross-origin mutation rejection, no token in provider output.
- Desktop dark/light and mobile screenshots inspected. Screenshots are generated under `frontend/test-results` (ignored by Git).
- `npm audit`: **0 known vulnerabilities** after upgrading Vitest to 5.0.3. This does not constitute a full security audit.
- Compiled browser bundle does not contain the existing Gemini key; comparison prints only PASS/FAILED.
- Git ignore patterns verified using an isolated temporary repository: `backend/.env`, `frontend/.env.local`, `backend/.local-token` are excluded. Project root was not initialized as a Git repository; no commit, push or merge performed.
- Existing `backend/.env` was not written; size remains 68 bytes and modification time remains 11 October 2026, 14:16:51 client local time.
- Application launched locally on 8000/3000. Health is healthy, provider is Gemini, key is configured, default model is `gemini-3.5-flash-lite`; application database has no test seed rows.

## Not verified / limitations

- Real Gemini generation intentionally skipped. User authorized one request **only if the model is confirmed available on the project's Free Tier**. Public model/pricing documentation and model discovery cannot establish the project's billing status or remaining free quota. No billing was enabled, paid model request made, or cloud resource created. Consequently an actual Gemini response from this user's key is **not yet demonstrated**.
- Official model catalog checked on 11 October 2026. Older Gemini 2.5 availability is restricted for new users, so the configurable default uses stable `gemini-3.5-flash-lite`. Free pricing at model level is not a claim about this project.
- Docker Compose, Docker images, PostgreSQL, CI runner and distributed deployment were not executed in this environment. Their configuration is supplied; they require validation before use.
- Tests/build under the Windows sandbox encountered filesystem canonicalization and temporary-folder permission errors. The same tests and build succeeded outside that sandbox. This is an execution-environment restriction, not evidence that a sandboxed launch works.
- The Python installation reports a path-location warning in the sandbox and initially failed ensurepip. The venv was populated locally using the existing main Python pip's `--python` option. Setup follows this working method, with `venv --without-pip`.
- Each execution runs one agent. Multi-agent workflows, internet research, side-effect approvals, MCP transport, RAG, Redis, pgvector and RBAC remain roadmap work.
- Durable checkpoints exist but automatic restart resume is not provided. Restart marks outstanding runs failed. Local cancel stops future calls; an in-flight transmitted request may still consume quota.
- Task assignment dropdown presently loads the first 50 agents; paginated agent management is available. Expand selection/search before large inventories.
- Logs omit prompts and secrets, but application DB and checkpoints store prompts/results without encryption. One-process local use only.
