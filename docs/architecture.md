# Architecture decisions

## Boundaries

Browser → same-origin Next.js proxy → bearer-protected FastAPI → application services and Runner → SQLAlchemy / Gemini / tool registry. Secret configuration lives only in backend settings or server environment. SQLAlchemy entities use portable SQL types; migrations establish schema explicitly before startup.

`backend/app/config.py`: environment configuration. `schemas.py`: input contracts. `db.py`: persistence models and serialization. `repository.py`: data access helpers. `services.py`: business invariants, CRUD and launch policies. `providers.py`: Gemini and explicit offline mock. `tools.py`: allowlist, schemas, policy enforcement, and extensible ToolAdapter protocol for future MCP. `execution.py`: lifecycle, graph transitions, event persistence, queue and cancellation. `main.py`: HTTP layer and local authorization.

Frontend uses central translations in `src/lib/i18n.ts`, strict typed API contracts in `src/lib/types.ts`, server-only proxy route, and client workspace. Polling is bounded to four seconds for lists and two seconds for an opened execution. No fake seed data is created. Dashboard aggregates actual stored rows. Agent/task lists and execution/event APIs provide offset/limit pagination.

## Execution model

The run endpoint captures immutable agent instructions, model, tool permissions, limits and task prompt. A local async worker serializes executions; at most ten jobs can be queued. A LangGraph StateGraph calls the model and routes either to allowed tools or END. Native SDK response content is retained, including function-call signatures, to preserve valid Gemini multi-turn tool calling. Automatic SDK tool execution and hidden retries are disabled.

Application history records statuses, events, token usage, result and safe error codes. AsyncSqliteSaver stores durable graph snapshots under execution ID in a separate DB with strict msgpack restrictions. Output tokens accumulate across requests, including thinking usage. Input usage also accumulates, so repeated context is accounted for. Checkpoint persistence supports inspection and future replay, but interrupted runs currently fail explicitly on process restart rather than resume automatically.

Cancellation prevents further graph transitions. An already transmitted provider request can still consume quota. API permission checks happen before invoking tools; model instructions cannot extend tool permissions. Calculator parses a small arithmetic AST and never evaluates arbitrary Python. v0.3 adds exact-allowlist public HTTPS Fetch, a trusted local stdio MCP client/server and transactional application notes requiring human approval. Shell tools and arbitrary URLs remain prohibited.

## Local deployment

SQLite WAL and one backend process suit a low-memory laptop. No Docker, Redis, or local LLM is required. PostgreSQL is supported for application tables via SQLAlchemy/psycopg configuration; migration portability should be verified before moving real data. The checkpoint DB remains SQLite. Horizontal scaling requires a shared checkpoint store, durable job queue and distributed task-launch locks; running multiple workers is currently unsupported.

## Security and limitations

Loopback binding, random server-side token, explicit Origin/Host checks, no secret exposure, no permissive CORS, bounded task inputs, no prompt/body/provider-exception logging, protected Swagger and strict tool allowlist. Browser renders model output as plain text, without HTML injection. Database/checkpoint contents are sensitive and unencrypted; local account permissions provide their present protection.

Full tenant isolation, identities, RBAC, CSRF tied to authenticated sessions, HTTPS, encrypted storage, audit retention, distributed workers and approvals for external side effects are required before public deployment. v0.3 implements a pinned stdio MCP tools transport for the bundled read-only server; remote transports and arbitrary server configuration remain unsupported. Multi-agent coordination is implemented in v0.2; arbitrary DAG editing and parallel branches remain roadmap features. See [v0.2](v0.2.md) for orchestration contracts, budgets, persistence and verified examples. Settings are read-only apart from explicit model discovery; environment files remain authoritative.


## v0.3 tools

See [v0.3 architecture, security boundaries and tests](v0.3.md). ToolExecutor is shared by both runners. ToolRegistry imports only pinned tools and verified MCP schemas. ToolCall stores masked parameters/results, decisions and elapsed time; ToolNote uses a unique call reference and transactional completion to prevent replay. Permissions and schema validation are enforced on every invocation, independently of model policy.
