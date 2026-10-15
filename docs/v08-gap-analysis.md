# v0.8 — анализ до реализации

Проверены README, отчёты v0.5–v0.7, providers.py, Single/Multi LangGraph runners, RAG/evaluation, SQLite модели и миграции, UI и тесты. Реальных API вызовов нет; .env не изменяется.

| Компонент | Текущее состояние | Изменение |
|---|---|---|
| Provider | Совместимый generate(snapshot, messages, remaining) у Gemini/Mock | Protocol, расширенный Reply и общий execution facade |
| Offline | Mock выбирается явно; Gemini default, ключ позволяет попытку | Mock default; backend environment gate + scoped operation/model grants |
| Модели | model ID агента, без registry | Версионируемая SQLite конфигурация; неизвестные лимиты/цены не выдумываются |
| Reliability | SDK attempts=1, timeout; общие ошибки | Классификация, bounded retries/jitter, persisted breaker, cancellation/concurrency |
| Cost | Необязательные env prices, без резервов | Separate versioned pricing, BEGIN IMMEDIATE reservations, conservative uncertain billing |
| Observability | Execution/Workflow события и evaluation JSON | Metadata-only request/trace/usage records, scoped aggregates and filters |
| Prompts | Строки в коде/agent instructions | Immutable versioned system templates; provenance in traces/benchmarks |
| Evaluation | Только fixed Mock corpus | Config/version metadata, compatible-run comparison, regression criteria; no live benchmark |
| Auth | Owner token, один workspace; agent document allowlist | Новый LLM namespace получает server-derived tenant/user/role scopes. Legacy workspace остаётся owner-only, не объявляется multi-tenant |
| UI | RAG evaluation | RU/EN observability, trace detail, provider settings, comparison |

Порядок: additive schema → registry/prompt/config → execution/budget/reliability → integrate existing call sites → scoped API/UI → tests/migration/offline comparison → docs/v0.8.md. Внешние подключения и платные операции не включаются. Подтверждённость Gemini specs/price/live остаётся unknown/unverified.
