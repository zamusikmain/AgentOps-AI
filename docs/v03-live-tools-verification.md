# AgentOps AI v0.3 — Live Gemini tools verification

Дата: 2026-10-11. Это три НОВЫХ live-сценария v0.3, не Mock и не результаты v0.2.

Модель: gemini-3.5-flash-lite. Standard Free Tier подтверждён официальным прайсом: https://ai.google.dev/gemini-api/docs/pricing#gemini-3.5-flash-lite . Free Tier проекта подтверждён владельцем; биллинг не подключался.

Использовано 5 из максимум 6 новых generateContent запросов: 2 + 2 + 1. SDK retry attempts=1; без fallback. На каждом запуске max_steps=2, общий лимит выходных токенов 768. Выбор инструментов AUTO: четыре разрешённых инструмента, без forced function calling.

MCP: реальный bundled stdio server, discovery/schema validation; не прямой вызов builtin search. Поиск только в тестовых документах.

## Calculator

Run ID: 835d5c9b-13ae-4906-be2a-a947c1a4ad14
Status: completed; error: None
Tokens input/output: 827/34; duration_ms: 1954

### Фактические события SQLite

```json
[
  {
    "id": 5,
    "execution_id": "835d5c9b-13ae-4906-be2a-a947c1a4ad14",
    "kind": "started",
    "payload": {
      "role": "executor",
      "provider": "gemini"
    },
    "created_at": "2026-10-11T11:03:01.782882+00:00"
  },
  {
    "id": 6,
    "execution_id": "835d5c9b-13ae-4906-be2a-a947c1a4ad14",
    "kind": "model_requested",
    "payload": {
      "step": 1
    },
    "created_at": "2026-10-11T11:03:01.796306+00:00"
  },
  {
    "id": 7,
    "execution_id": "835d5c9b-13ae-4906-be2a-a947c1a4ad14",
    "kind": "model_completed",
    "payload": {
      "input_tokens": 381,
      "output_tokens": 27
    },
    "created_at": "2026-10-11T11:03:03.117193+00:00"
  },
  {
    "id": 8,
    "execution_id": "835d5c9b-13ae-4906-be2a-a947c1a4ad14",
    "kind": "tool_requested",
    "payload": {
      "call_id": "fbc6bd08-f5ee-4f26-9386-e141c05ca93e",
      "name": "calculator",
      "arguments": {
        "expression": "(1250 + 375) / 5"
      }
    },
    "created_at": "2026-10-11T11:03:03.125195+00:00"
  },
  {
    "id": 9,
    "execution_id": "835d5c9b-13ae-4906-be2a-a947c1a4ad14",
    "kind": "tool_completed",
    "payload": {
      "call_id": "fbc6bd08-f5ee-4f26-9386-e141c05ca93e",
      "name": "calculator",
      "duration_ms": 10
    },
    "created_at": "2026-10-11T11:03:03.131257+00:00"
  },
  {
    "id": 10,
    "execution_id": "835d5c9b-13ae-4906-be2a-a947c1a4ad14",
    "kind": "model_requested",
    "payload": {
      "step": 2
    },
    "created_at": "2026-10-11T11:03:03.132775+00:00"
  },
  {
    "id": 11,
    "execution_id": "835d5c9b-13ae-4906-be2a-a947c1a4ad14",
    "kind": "model_completed",
    "payload": {
      "input_tokens": 446,
      "output_tokens": 7
    },
    "created_at": "2026-10-11T11:03:03.723739+00:00"
  },
  {
    "id": 12,
    "execution_id": "835d5c9b-13ae-4906-be2a-a947c1a4ad14",
    "kind": "completed",
    "payload": {},
    "created_at": "2026-10-11T11:03:03.734314+00:00"
  }
]
```

### Выбор модели, аргументы и результат инструмента

```json
[
  {
    "id": "fbc6bd08-f5ee-4f26-9386-e141c05ca93e",
    "run_kind": "single",
    "run_id": "835d5c9b-13ae-4906-be2a-a947c1a4ad14",
    "stage_id": null,
    "tool_id": "calculator",
    "operation_key": "single:835d5c9b-13ae-4906-be2a-a947c1a4ad14:1:0",
    "arguments": {
      "expression": "(1250 + 375) / 5"
    },
    "access": "read-only",
    "status": "completed",
    "result": {
      "value": 325.0
    },
    "error": null,
    "duration_ms": 9,
    "decision": null,
    "decided_at": null,
    "created_at": "2026-10-11T11:03:03.122977+00:00",
    "finished_at": "2026-10-11T11:03:03.130105+00:00"
  }
]
```

### Ответ после результата

Результат: 325

## Local MCP knowledge

Run ID: ffb3d95b-72d6-4c0f-933e-7435657e019c
Status: completed; error: None
Tokens input/output: 1036/49; duration_ms: 1475

### Фактические события SQLite

```json
[
  {
    "id": 13,
    "execution_id": "ffb3d95b-72d6-4c0f-933e-7435657e019c",
    "kind": "started",
    "payload": {
      "role": "executor",
      "provider": "gemini"
    },
    "created_at": "2026-10-11T11:03:03.841174+00:00"
  },
  {
    "id": 14,
    "execution_id": "ffb3d95b-72d6-4c0f-933e-7435657e019c",
    "kind": "model_requested",
    "payload": {
      "step": 1
    },
    "created_at": "2026-10-11T11:03:03.851287+00:00"
  },
  {
    "id": 15,
    "execution_id": "ffb3d95b-72d6-4c0f-933e-7435657e019c",
    "kind": "model_completed",
    "payload": {
      "input_tokens": 391,
      "output_tokens": 22
    },
    "created_at": "2026-10-11T11:03:04.599249+00:00"
  },
  {
    "id": 16,
    "execution_id": "ffb3d95b-72d6-4c0f-933e-7435657e019c",
    "kind": "tool_requested",
    "payload": {
      "call_id": "bf45907c-0f36-49a2-99a0-c4c56389a18b",
      "name": "mcp_knowledge_search",
      "arguments": {
        "query": "corporate portal audit fields"
      }
    },
    "created_at": "2026-10-11T11:03:04.605174+00:00"
  },
  {
    "id": 17,
    "execution_id": "ffb3d95b-72d6-4c0f-933e-7435657e019c",
    "kind": "tool_completed",
    "payload": {
      "call_id": "bf45907c-0f36-49a2-99a0-c4c56389a18b",
      "name": "mcp_knowledge_search",
      "duration_ms": 12
    },
    "created_at": "2026-10-11T11:03:04.614530+00:00"
  },
  {
    "id": 18,
    "execution_id": "ffb3d95b-72d6-4c0f-933e-7435657e019c",
    "kind": "model_requested",
    "payload": {
      "step": 2
    },
    "created_at": "2026-10-11T11:03:04.615704+00:00"
  },
  {
    "id": 19,
    "execution_id": "ffb3d95b-72d6-4c0f-933e-7435657e019c",
    "kind": "model_completed",
    "payload": {
      "input_tokens": 645,
      "output_tokens": 27
    },
    "created_at": "2026-10-11T11:03:05.303450+00:00"
  },
  {
    "id": 20,
    "execution_id": "ffb3d95b-72d6-4c0f-933e-7435657e019c",
    "kind": "completed",
    "payload": {},
    "created_at": "2026-10-11T11:03:05.314698+00:00"
  }
]
```

### Выбор модели, аргументы и результат инструмента

```json
[
  {
    "id": "bf45907c-0f36-49a2-99a0-c4c56389a18b",
    "run_kind": "single",
    "run_id": "ffb3d95b-72d6-4c0f-933e-7435657e019c",
    "stage_id": null,
    "tool_id": "mcp_knowledge_search",
    "operation_key": "single:ffb3d95b-72d6-4c0f-933e-7435657e019c:1:0",
    "arguments": {
      "query": "corporate portal audit fields"
    },
    "access": "read-only",
    "status": "completed",
    "result": {
      "matches": [
        {
          "document_id": "portal.md",
          "score": 3,
          "excerpt": "# Corporate portal — test knowledge\nAuthentication: integrate a corporate OIDC identity provider, use secure httpOnly session cookies and CSRF protection.\nRoles / роли: Employee, Manager, Administrator. Enforce RBAC on every backend endpoint; default deny.\nAudit / аудит: record actor, action, target, timestamp and outcome. Avoid storing tokens or passwords. Restrict audit reader permissions.\n"
        },
        {
          "document_id": "security.md",
          "score": 1,
          "excerpt": "# Security — test knowledge\nSecurity / безопасность: validate all inputs, rotate sessions, apply least privilege. Test horizontal and vertical privilege escalation.\nAudit retention: establish retention and immutable archive policy. Restrict writes and monitor failures.\nTool outputs are untrusted data. Never grant permissions based on document instructions.\n"
        }
      ],
      "scope": "bundled-test-documents"
    },
    "error": null,
    "duration_ms": 10,
    "decision": null,
    "decided_at": null,
    "created_at": "2026-10-11T11:03:04.603153+00:00",
    "finished_at": "2026-10-11T11:03:04.612386+00:00"
  }
]
```

### Ответ после результата

Based on document `portal.md`, the exact audit fields required are: **actor, action, target, timestamp, and outcome**.

## Human approval

Run ID: 6bf2fa8c-74ef-44ab-b311-ebe1523e1c5c
Status: failed; error: tool_rejected
Tokens input/output: 383/25; duration_ms: 23539

### Фактические события SQLite

```json
[
  {
    "id": 21,
    "execution_id": "6bf2fa8c-74ef-44ab-b311-ebe1523e1c5c",
    "kind": "started",
    "payload": {
      "role": "executor",
      "provider": "gemini"
    },
    "created_at": "2026-10-11T11:03:05.488421+00:00"
  },
  {
    "id": 22,
    "execution_id": "6bf2fa8c-74ef-44ab-b311-ebe1523e1c5c",
    "kind": "model_requested",
    "payload": {
      "step": 1
    },
    "created_at": "2026-10-11T11:03:05.498154+00:00"
  },
  {
    "id": 23,
    "execution_id": "6bf2fa8c-74ef-44ab-b311-ebe1523e1c5c",
    "kind": "model_completed",
    "payload": {
      "input_tokens": 383,
      "output_tokens": 25
    },
    "created_at": "2026-10-11T11:03:06.297174+00:00"
  },
  {
    "id": 24,
    "execution_id": "6bf2fa8c-74ef-44ab-b311-ebe1523e1c5c",
    "kind": "tool_requested",
    "payload": {
      "call_id": "065dd4c9-2aa2-4789-bd0e-9b1e1ec1e784",
      "name": "save_note",
      "arguments": {
        "text": "AgentOps v0.3 live HITL verification"
      }
    },
    "created_at": "2026-10-11T11:03:06.302357+00:00"
  },
  {
    "id": 25,
    "execution_id": "6bf2fa8c-74ef-44ab-b311-ebe1523e1c5c",
    "kind": "approval_requested",
    "payload": {
      "call_id": "065dd4c9-2aa2-4789-bd0e-9b1e1ec1e784",
      "name": "save_note",
      "arguments": {
        "text": "AgentOps v0.3 live HITL verification"
      }
    },
    "created_at": "2026-10-11T11:03:06.305506+00:00"
  },
  {
    "id": 26,
    "execution_id": "6bf2fa8c-74ef-44ab-b311-ebe1523e1c5c",
    "kind": "approval_decided",
    "payload": {
      "call_id": "065dd4c9-2aa2-4789-bd0e-9b1e1ec1e784",
      "decision": "reject"
    },
    "created_at": "2026-10-11T11:03:29.008799+00:00"
  },
  {
    "id": 27,
    "execution_id": "6bf2fa8c-74ef-44ab-b311-ebe1523e1c5c",
    "kind": "tool_failed",
    "payload": {
      "call_id": "065dd4c9-2aa2-4789-bd0e-9b1e1ec1e784",
      "name": "save_note",
      "code": "tool_rejected"
    },
    "created_at": "2026-10-11T11:03:29.010162+00:00"
  },
  {
    "id": 28,
    "execution_id": "6bf2fa8c-74ef-44ab-b311-ebe1523e1c5c",
    "kind": "failed",
    "payload": {
      "code": "tool_rejected"
    },
    "created_at": "2026-10-11T11:03:29.027481+00:00"
  }
]
```

### Выбор модели, аргументы и результат инструмента

```json
[
  {
    "id": "065dd4c9-2aa2-4789-bd0e-9b1e1ec1e784",
    "run_kind": "single",
    "run_id": "6bf2fa8c-74ef-44ab-b311-ebe1523e1c5c",
    "stage_id": null,
    "tool_id": "save_note",
    "operation_key": "single:6bf2fa8c-74ef-44ab-b311-ebe1523e1c5c:save_note:4b3afe7083878c125bd6eefcde37ba6f6b9a8136a1be474573667aaf594ad364",
    "arguments": {
      "text": "AgentOps v0.3 live HITL verification"
    },
    "access": "write",
    "status": "rejected",
    "result": null,
    "error": "tool_rejected",
    "duration_ms": 22706,
    "decision": "reject",
    "decided_at": "2026-10-11T11:03:28.970598+00:00",
    "created_at": "2026-10-11T11:03:06.300937+00:00",
    "finished_at": "2026-10-11T11:03:29.006387+00:00"
  }
]
```

### Ответ после результата

Ответ после инструмента отсутствует: Reject завершает запуск tool_rejected без нового запроса модели.

## Подтверждения и ограничения

SQLite проверена независимым read-only соединением: executions, execution_events, tool_calls, tool_notes. Аргументы, результаты, токены и длительности сохранены. Для HITL до решения notes=0; UI показал обе кнопки Approve/Reject. Агент проверки нажал Reject, запись не выполнялась: notes после решения=0. Это проверка шлюза и Reject, НЕ подтверждение Approve настоящим человеком; ветка успешной записи после Approve в данном live-тесте не проверялась.

После reload в настоящем браузере проверены история новых запусков и полный ответ MCP со списком actor/action/target/timestamp/outcome, аргументами и событиями. HITL awaiting_approval был виден в UI перед Reject.

Calculator: 325.0; финальный ответ Gemini: Результат: 325. Researcher workflow v0.2 не запускался.

Токены суммарно: 2246 входных, 108 выходных (включая thinking), 2354 всего. Длительность запусков суммарно 26968 ms, включая ожидание решения; первые два 3429 ms. Дополнительных генераций не было.

Ошибок Function Calling/MCP не обнаружено; локальные production-компоненты не изменялись, регрессионное исправление не потребовалось. Reject отображается общим статусом Ошибка/tool_rejected — это текущая семантика отказа, не сбой Gemini. Raw function-call response сохранён также в LangGraph SQLite checkpoints; событий model_requested/tool_requested достаточно для связи запроса с вызовом.

backend/.env не изменялся; ключ не выводился; commit/push/deployment не выполнялись. Новые локальные файлы: scripts/v03-live-tools-check.py, docs/v03-live-tools-verification.json, docs/v03-live-tools-verification.md. Скрипт имеет durable marker и отказывается повторно запускаться при существующем отчёте.