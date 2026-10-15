from pathlib import Path
import json
root=Path(__file__).resolve().parents[1];data=json.loads((root/'docs/v05-comparison.json').read_text(encoding='utf8'))
lines=['# AgentOps AI v0.5 — Semantic RAG + Hybrid Search','', 'Проверка: 11 октября 2026. Реальных generation-запросов: **0**, embedding-запросов: **0**. Все новые ответы — **Mock**, не Live Gemini. `backend/.env` и существующий ключ не изменялись. Commit/push/deployment не выполнялись.','',
'## Реализовано','',
'- Отдельный EmbeddingProvider: официальный google-genai adapter для `gemini-embedding-2` и детерминированный Mock. Mock хеширует общие префиксы слов и символьные триграммы; не содержит ожидаемых ответов, синонимов корпоративного PDF или генеративной имитации embeddings.',
'- SQLite float32 L2 vectors, кеш SHA256 по очищенному содержимому, provider/model/dimension/parameters/sanitizer. Batching до 32 inputs, лимит 32 запросов на документ, таймаут, проверка размерности/NaN/Inf/нулевых векторов/размера batch. Автоматических повторов нет. Неизменённый готовый индекс пропускается; повторная загрузка того же SHA возвращает существующий документ.',
'- Lexical: два потоковых прохода, ограниченный TF-IDF, усиление точной фразы, понижение контрольного списка вопросов. Semantic: потоковый cosine по разрешённым векторам. Hybrid: RRF `sum(1/(60+rank))`, по 30 кандидатов каждой ветки.',
'- Воспроизводимый reranker: 0.85 нормализованного score + 0.10 покрытия терминов + 0.05 точной фразы; контрольные вопросы понижаются, явное отсутствие информации остаётся допустимым источником. Это текстовые признаки, не обученный cross-encoder.',
'- SQL фильтр документов и signature применяется **до чтения векторов**. Чтение порциями 128; материализация только до 60 финальных кандидатов. Возвращаются rank, причины, lexical/semantic/fusion/rerank scores, документ, страница и оригинальный фрагмент.',
'- Knowledge Search по умолчанию Hybrid в Single/Multi/RAG. MCP использует тот же backend поиск с разрешениями; собственный закреплённый stdio server получает проверенные данные отдельным RPC полем, недоступным через аргументы модели. Fixtures остаются локальными read-only.',
'- UI: статус embeddings, число векторов/фрагментов, reindex, выбор режима, rerank, retrieval preview, оценки, причины и источники; RU/EN, текущие темы, сохранение режима после reload. Mock-векторы явно помечены.',
'- История tool calls хранит реальные найденные фрагменты, режим и оценки. RAG сохраняет запрос, результат, проверенные цитаты, события, токены и длительность. Старые истории сохраняются.',
'', '## Модели и внешние запросы','',
'В рабочей конфигурации embeddings **Mock**, внешние запросы отключены. Google adapter создан и проверен offline через подменённый SDK-клиент; его реальные ответы/доступность в проекте пользователя не проверялись.',
'Официальные источники: [Embeddings](https://ai.google.dev/gemini-api/docs/embeddings), [Pricing](https://ai.google.dev/gemini-api/docs/pricing). Для стандартного текстового `gemini-embedding-2` опубликован Free Tier; платный асинхронный Batch API не используется. Для Embedding 2 task_type не передаётся: используются общие document/query prefixes. Каждый input завернут в отдельный Content, количество полученных векторов строго проверяется.',
'Перед будущим внешним запуском: 6 фрагментов этого PDF, размерность 768, до 1 стандартного batched embedding запроса при пустом кеше; затем до 1 query embedding запроса на каждый semantic/hybrid поиск. Передаются очищенные текстовые фрагменты/вопрос, не PDF-файл, пути или ключ. Нужны отдельное разрешение пользователя, проверка модели/квоты текущего Free Tier и включение embedding_external_enabled. Это **не** разрешение запускать сейчас.',
'', '## Сравнение одинаковых пяти перефразированных вопросов','',
'Корпус: существующий `AgentOps_RAG_Test_Corporate_Policy.pdf`, 3 страницы, 6 фрагментов. Везде limit=5, rerank=true. Правильный фрагмент определяется ожидаемым фактом **только в оценочном скрипте**, не в алгоритмах поиска или Mock. Для E релевантен фрагмент с явным отсутствием цены.','',
'| Режим | Hit@1 | Hit@5 |','|---|---:|---:|']
for mode,m in data['metrics'].items():lines.append(f"| {mode} | {m['hit_at_1']}/5 | {m['hit_at_5']}/5 |")
lines+=['','**Преимущество Hybrid не показано.** Semantic здесь — cosine над Mock hash-векторами, не настоящая semantic модель. Корпус из 6 фрагментов делает Hit@5 слабой метрикой. Не следует переносить эти числа на Google embeddings или большой корпус.','',
'| Вопрос | Lexical rank | Mock semantic rank | Hybrid rank | Цитата Mock отвечает на вопрос |','|---|---:|---:|---:|---|']
correct=0
for q in data['questions']:
    expected=q['expected_evaluation_only'];ok=(expected in q['answer']['answer']) if q['label']!='E' else not q['answer']['found'];correct+=ok
    ranks=[str(q['comparisons'][m]['first_relevant_rank'] or 'нет') for m in ('lexical','semantic','hybrid')]
    lines.append('| '+q['label']+' | '+' | '.join(ranks)+' | '+('Да' if ok else '**Нет**')+' |')
lines+=['',f'Правильная селекция цитаты существующим Mock LLM: **{correct}/5**. A/B/D не прошли проверку ответа: точная цитата существует в документе, но выбранный Mock фрагмент не отвечает на перефразированный вопрос. Валидность источника не доказывает релевантность ответа. Эти результаты не были подменены правильными ответами.','', '## Пять вопросов: источник и фактический Mock результат','']
for q in data['questions']:
    expected=q['expected_evaluation_only'];matches=q['comparisons']['hybrid']['retrieval']['matches'];hit=next(m for m in matches if expected in m['excerpt'])
    rows=hit['excerpt'].splitlines();i=next(i for i,line in enumerate(rows) if expected in line);quote='\n'.join(rows[max(0,i-1):min(len(rows),i+2)])
    lines += [f"### {q['label']}. {q['question']}",'',f"Проверяемый факт: **{expected}**. Источник: `{hit['document']}`, страница {hit['page']}, chunk `{hit['chunk_id']}`.",'','Подтверждающий фрагмент PDF:','',*['> '+line for line in quote.splitlines()],'',f"Фактический Mock ответ (run `{q['run_id']}`):",'','```text',q['answer']['answer'],'```','',f"Статус found={q['answer']['found']}; input={q['input_tokens']}, output={q['output_tokens']} Mock-токенов, {q['duration_ms']} ms. Цитаты и события полностью: `docs/v05-comparison.json`.",'']
lines+=['## Проверки и данные','',
'- Backend: 142 теста (123 прежних + 19 новых). Проверены все три режима, batching/cache, смена signature/dimension, NaN/Inf/ошибка/таймаут, внешний запрет без сетевого вызова, SQL scope до provider, dedup/reindex/delete/restart, MCP uploaded PDF, прежний Single/Multi, HITL, SSRF, поддельные цитаты и известная PDF injection.',
'- Frontend unit: 6 тестов, включая совпадение RU/EN ключей и сохранение парсинга старых ответов. TypeScript и production build прошли.',
'- Playwright: 7 сценариев, включая новый v0.5 retrieval/reindex/reload/RU/EN и старые PDF/Single/Multi/MCP/HITL/security/mobile.',
'- Миграция 005 аддитивная. Перед ней online SQLite backup в исключённом `backend/data/backups`. Все старые строки каждого существовавшего столбца сравнивались по SHA256 и числу строк: сохранены, включая 15 executions и live v0.2 workflow. Детали `docs/v05-migration.json`.',
'- В текущей рабочей базе сохранены 5 новых Mock запусков и 6 векторов реального PDF. API повторное чтение истории подтверждено. Проверка UI после reload и screenshots: `docs/v05-ui-verification.json`, `docs/v05-ui-ru-dark.png`, `docs/v05-ui-en-light.png`, `docs/v05-ui-mobile.png`.',
'', '## Ограничения и production roadmap','',
'- **Реальное semantic качество не проверено**: требуется разрешённая индексация Google embeddings и независимый корпус/запросы без подгонки. Mock paraphrase A/B/D ошибочны; нужен LLM relevance check/abstention evaluation и, при необходимости, обученный reranker. Exact quote validator блокирует выдуманные цитаты, но не неверный выбор настоящей цитаты.',
'- Локальный cosine — O(число разрешённых векторов × размерность); ограниченное потребление памяти не устраняет линейную задержку. 60 000 cache entries, до 100 документов; PDF до 5 МиБ/100 страниц/лимит извлечённого текста. Для production нужен pgvector/ANN, transactional jobs и нагрузочные тесты. VectorIndex отделён от provider, search читает candidates через него; pgvector adapter не реализован.',
'- Индексация одного документа читает его фрагменты в память; streaming относится к retrieval по базе. Query embeddings не кешируются; при будущем Google поиске каждый запрос расходует отдельную embedding квоту. Автоматический Hybrid fallback на Lexical явно помечен warning, Semantic выдаёт ошибку.',
'- Приложение остаётся **однопользовательским локальным workspace** с owner token. Разрешения отдельных агентов проверяются; полноценные разные пользователи/tenants отсутствуют. Публичная многопользовательская эксплуатация требует authentication/tenant isolation/RBAC и независимого security review.',
'- Prompt injection фильтруется существующей эвристикой, контекст помечается untrusted, tool permissions фиксированы и citations проверяются по SQLite. Не заявляется универсальная защита от любой скрытой инструкции PDF. OCR, таблицы сложной структуры, DOCX и incremental text extraction не добавлены.',
'- Worker embedding вызов выполняется в thread; cancellation не убивает уже начатый HTTP request. HTTP timeout и attempts=1 ограничивают его. Нужен durable cancellation/job state для production.',
'- Исторические цитаты остаются в истории после удаления исходного документа, как в v0.4. Удаляются PDF, chunks, vectors и неиспользуемые кеши соответствующего содержимого; общей политике retention и удалению истории нужна отдельная продуктовая спецификация.',
'- Free Tier pricing опубликован, но индивидуальные project quotas и фактический SDK response реальной модели не проверены. Модель не переключается автоматически, биллинг не включается.','']
(root/'docs/v0.5.md').write_text('\n'.join(lines),encoding='utf8')
print('docs/v0.5.md generated; Mock answer correctness',correct,'/5.')
