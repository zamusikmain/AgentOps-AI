# v0.9 gap analysis

Inspected v0.7/v0.8 docs, current adapters, LLM layer, SQLite, evaluation, vector signatures, UI and tests. Existing Mock benchmark is real local execution; Gemini status remains UNVERIFIED. No live request is authorized.

Changes: add a validation orchestration record linked to existing evaluation rather than replacing it; immutable datasets in existing configuration storage; three modes with immutable plans and double permission/data scope; scoped readiness/export/dashboard; monotonic phase/SQLite instrumentation; controlled performance/failure fixtures; contract tests through local HTTP transport; compare quality against v0.7 and v0.8. Additive migration only if these records/indexes require it.

Performance optimization will follow measured baseline, keeping mandatory security/budget/audit durability. Existing vector signatures remain unchanged; compatibility exposes embedding/index/cache version and demands reindex instead of mixing vectors. REAL_EXECUTION stays disabled and is tested only with local injected transports/providers. No .env changes, external AI requests, commit/push/deployment, or user data deletion.
