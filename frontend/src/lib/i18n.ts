import {authEn,authRu} from './auth-i18n';
import {smokeEnKeys,smokeRuKeys} from './live-smoke-i18n';
import {validationEn,validationRu} from './validation-i18n';
import {evidenceEn,evidenceRu,evidenceReasonEn,evidenceReasonRu} from './evidence-i18n';
import {ragEn,ragRu} from './rag-i18n';
import {evaluationEn,evaluationRu} from './evaluation-i18n';
import {embeddingEn,embeddingRu} from './embedding-i18n';
import {toolEn,toolRu} from './tool-i18n';
import {workflowEn,workflowRu} from './workflow-i18n';
export const en = {
  ...validationEn,
  ...authEn,
  ...smokeEnKeys,
  observability:'LLM Observability',observabilityDescription:'Offline request traces, usage and execution policy.',
  ...workflowEn,
  ...toolEn,
  ...ragEn,
  ...evaluationEn,
  ...evidenceEn,
  ...evidenceReasonEn,
  ...embeddingEn,
  dashboard:'Overview',agents:'Agents',tasks:'Tasks',executions:'Executions',workflows:'Workflows',tools:'Tools',settings:'Settings',
  workspace:'LOCAL WORKSPACE',platform:'Agent orchestration',tagline:'Your operations, orchestrated.',dashboardDescription:'A live view of your agents, tasks, and execution activity.',
  agentsDescription:'Configure purpose, instructions, and boundaries for every agent.',tasksDescription:'Turn a business objective into an accountable execution.',executionsDescription:'Every run, every step, every result. Persisted locally.',
  workflowsDescription:'Create agent workflows and inspect every execution stage.',toolsDescription:'Explicit permissions. Bounded actions. No arbitrary code.',settingsDescription:'Provider configuration and local platform boundaries.',
  newAgent:'Create agent',newTask:'Create task',save:'Save changes',cancel:'Cancel',edit:'Edit',delete:'Delete',run:'Run task',confirmRun:'This sends your task to Gemini and may use paid quota. Continue?',confirmDelete:'Delete this item?',
  name:'Name',role:'Role',instructions:'System instructions',model:'Model',maxSteps:'Maximum model calls',maxTokens:'Total output token budget',permissions:'Allowed tools',title:'Title',prompt:'Task instructions',agent:'Agent',status:'Status',
  planner:'Planner',researcher:'Researcher',executor:'Executor',reviewer:'Reviewer',active:'Active',disabled:'Disabled',draft:'Draft',queued:'Queued',running:'Running',completed:'Completed',failed:'Failed',cancelled:'Cancelled',
  empty:'Nothing here yet',emptyAgents:'Create your first agent to define how work gets done.',emptyTasks:'Create a task and assign it to an agent.',emptyExecutions:'Run a task to start building your execution history.',
  loading:'Loading workspace…',retry:'Try again',recent:'Recent executions',all:'View all',activity:'Execution activity',totalAgents:'Configured agents',totalTasks:'Total tasks',totalExecutions:'Total executions',tokens:'Tokens consumed',success:'Completed',inFlight:'In progress',
  noActivity:'Your first execution will appear here.',result:'Result',trace:'Execution trace',duration:'Duration',inputTokens:'Input tokens',outputTokens:'Output tokens',cost:'Estimated cost',unknown:'Unavailable',details:'Open details',close:'Close',
  provider:'LLM provider',configured:'API key configured',notConfigured:'API key missing',defaultModel:'Default model',timeout:'Execution timeout',seconds:'seconds',discover:'Discover available models',unverified:'Availability is verified only by model discovery or a real request.',
  localAccess:'Local access',localAccessDescription:'Local servers use loopback. Browser sessions and role checks protect the application; API credentials are separate. Public deployment requires a security review.',mockNotice:'OFFLINE MOCK MODE — responses are test data.',
  readOnly:'Read only',calculator:'Calculator',calculatorDescription:'Arithmetic with bounded expressions. No code execution.',utc_time:'UTC clock',utc_timeDescription:'Read the current UTC date and time.',
  graphStart:'Task input',graphModel:'Selected agent · Gemini',graphTools:'Permitted tools',graphEnd:'Persist result',graphDescription:'The model can call permitted tools and return to the model within the step and token limits. Each transition is checkpointed in SQLite.',
  roadmap:'Next: parallel branches, approvals for side effects, RAG, queues, RBAC, and a visual workflow editor.',researcherNote:'Researcher works with supplied context only. Web retrieval is not enabled in this version.',
  started:'Execution started',model_requested:'Model request',model_completed:'Model response',tool_completed:'Tool completed',previous:'Previous',next:'Next',page:'Page',theme:'Switch theme',language:'Switch language',menu:'Open navigation',skip:'Skip to content',
  error:'An error occurred',backend_unavailable:'Backend is unavailable. Start the backend and retry.',missing_api_key:'GEMINI_API_KEY is missing in backend/.env.',unauthorized:'Backend access token is invalid.',not_found:'Item not found.',validation_error:'Check the input values and limits.',agent_in_use:'This agent is assigned to tasks. Remove those tasks first.',task_has_history:'This task has saved execution history and cannot be deleted.',task_running:'The task is already running.',agent_disabled:'Enable this agent before running a task.',queue_full:'The local queue is full. Wait for a run to finish.',
  rate_limit:'Gemini quota or rate limit reached. Check your provider account.',provider_auth:'Gemini rejected the API credentials.',model_unavailable:'The selected model is unavailable.',provider_error:'Gemini request failed.',provider_timeout:'Gemini request timed out.',execution_timeout:'Execution time limit reached.',step_limit:'Maximum number of model calls reached.',token_limit:'Output token budget reached.',tool_limit:'Too many tool calls requested.',tool_denied_or_invalid:'Tool call denied or arguments invalid.',empty_response:'The model returned no usable content.',internal_execution_error:'Execution failed unexpectedly.',server_restarted:'The server restarted during execution. Run the task again.',model_discovery_failed:'Could not discover models. Check the API key and network.',internal_error:'Unexpected server error.',forbidden_origin:'Request origin is not allowed.',forbidden_host:'Host is not allowed.',payload_too_large:'Request is too large.',
  createFirst:'Create your first agent',ready:'Ready to orchestrate',readyDescription:'Start with an agent, give it a task, and follow the execution from request to result.',total:'Total',step:'Step',saved:'Saved',history:'Agent history',viewHistory:'View runs',security:'SECURE LOCAL MODE',brand:'AgentOps',brandAi:'AI',copyright:'AgentOps AI · Local MVP',priceNote:'Cost is unknown until per-million-token prices are configured. Prices vary by model; no free-tier assumption is made.'
} as const;
export type Key = keyof typeof en;
export const ru: Record<Key,string> = {
  ...validationRu,
  ...authRu,
  ...smokeRuKeys,
  observability:'Наблюдаемость LLM',observabilityDescription:'История запросов, расход и политика выполнения.',
  ...workflowRu,
  ...toolRu,
  ...ragRu,
  ...evaluationRu,
  ...evidenceRu,
  ...evidenceReasonRu,
  ...embeddingRu,
  dashboard:'Обзор',agents:'Агенты',tasks:'Задачи',executions:'Запуски',workflows:'Процессы',tools:'Инструменты',settings:'Настройки',
  workspace:'ЛОКАЛЬНОЕ ПРОСТРАНСТВО',platform:'Оркестрация агентов',tagline:'Ваши процессы под контролем.',dashboardDescription:'Агенты, задачи и активность запусков в реальном времени.',
  agentsDescription:'Задайте цель, инструкции и границы работы каждого агента.',tasksDescription:'Превратите бизнес-цель в задачу с отслеживаемым результатом.',executionsDescription:'Каждый запуск, этап и результат сохраняются локально.',
  workflowsDescription:'Создавайте процессы из нескольких агентов и следите за каждым этапом.',toolsDescription:'Явные разрешения и ограниченные действия без произвольного кода.',settingsDescription:'Конфигурация провайдера и границы локальной платформы.',
  newAgent:'Создать агента',newTask:'Создать задачу',save:'Сохранить',cancel:'Отмена',edit:'Изменить',delete:'Удалить',run:'Запустить',confirmRun:'Задача будет отправлена в Gemini и может расходовать платную квоту. Продолжить?',confirmDelete:'Удалить этот объект?',
  name:'Название',role:'Роль',instructions:'Системные инструкции',model:'Модель',maxSteps:'Максимум вызовов модели',maxTokens:'Общий лимит выходных токенов',permissions:'Разрешённые инструменты',title:'Заголовок',prompt:'Инструкции задачи',agent:'Агент',status:'Статус',
  planner:'Планировщик',researcher:'Исследователь',executor:'Исполнитель',reviewer:'Рецензент',active:'Активен',disabled:'Отключён',draft:'Черновик',queued:'В очереди',running:'Выполняется',completed:'Завершён',failed:'Ошибка',cancelled:'Отменён',
  empty:'Пока здесь пусто',emptyAgents:'Создайте первого агента и определите его работу.',emptyTasks:'Создайте задачу и назначьте агента.',emptyExecutions:'Запустите задачу, чтобы начать историю выполнения.',
  loading:'Загрузка пространства…',retry:'Повторить',recent:'Последние запуски',all:'Все запуски',activity:'Активность выполнения',totalAgents:'Настроенные агенты',totalTasks:'Всего задач',totalExecutions:'Всего запусков',tokens:'Использовано токенов',success:'Завершено',inFlight:'В работе',
  noActivity:'Здесь появится первый запуск.',result:'Результат',trace:'Этапы выполнения',duration:'Длительность',inputTokens:'Входные токены',outputTokens:'Выходные токены',cost:'Оценка стоимости',unknown:'Нет данных',details:'Подробнее',close:'Закрыть',
  provider:'LLM-провайдер',configured:'API-ключ настроен',notConfigured:'API-ключ отсутствует',defaultModel:'Модель по умолчанию',timeout:'Таймаут выполнения',seconds:'секунд',discover:'Получить доступные модели',unverified:'Доступность проверяется запросом списка моделей или реальным запуском.',
  localAccess:'Локальный доступ',localAccessDescription:'Локальные серверы используют loopback. Приложение защищено пользовательскими сессиями и проверкой ролей; API credentials отделены. Для публикации необходим security review.',mockNotice:'ТЕСТОВЫЙ РЕЖИМ MOCK — ответы являются тестовыми данными.',
  readOnly:'Без побочных эффектов',calculator:'Калькулятор',calculatorDescription:'Арифметика с ограничением выражений. Без выполнения кода.',utc_time:'Часы UTC',utc_timeDescription:'Получение текущей даты и времени UTC.',
  graphStart:'Входная задача',graphModel:'Выбранный агент · Gemini',graphTools:'Разрешённые инструменты',graphEnd:'Сохранение результата',graphDescription:'Модель вызывает разрешённые инструменты и возвращается к обработке в пределах лимитов шагов и токенов. Переходы сохраняются в SQLite.',
  roadmap:'Далее: параллельные ветви, подтверждение действий, RAG, очереди, RBAC и визуальный редактор процессов.',researcherNote:'Исследователь работает только с переданным контекстом. Поиск в интернете пока не подключён.',
  started:'Запуск начат',model_requested:'Запрос модели',model_completed:'Ответ модели',tool_completed:'Инструмент выполнен',previous:'Назад',next:'Далее',page:'Страница',theme:'Переключить тему',language:'Переключить язык',menu:'Открыть навигацию',skip:'Перейти к содержимому',
  error:'Произошла ошибка',backend_unavailable:'Backend недоступен. Запустите сервер и повторите.',missing_api_key:'GEMINI_API_KEY отсутствует в backend/.env.',unauthorized:'Неверный токен доступа к backend.',not_found:'Объект не найден.',validation_error:'Проверьте введённые значения и лимиты.',agent_in_use:'Агент назначен задачам. Сначала удалите эти задачи.',task_has_history:'Задача содержит историю запусков и не может быть удалена.',task_running:'Задача уже выполняется.',agent_disabled:'Включите агента перед запуском.',queue_full:'Локальная очередь заполнена. Дождитесь завершения запуска.',
  rate_limit:'Исчерпана квота Gemini или достигнут лимит запросов.',provider_auth:'Gemini отклонил учётные данные.',model_unavailable:'Выбранная модель недоступна.',provider_error:'Ошибка запроса к Gemini.',provider_timeout:'Превышено время ожидания Gemini.',execution_timeout:'Превышен лимит времени выполнения.',step_limit:'Достигнут лимит вызовов модели.',token_limit:'Достигнут лимит выходных токенов.',tool_limit:'Запрошено слишком много вызовов инструментов.',tool_denied_or_invalid:'Инструмент запрещён или аргументы некорректны.',empty_response:'Модель не вернула доступный результат.',internal_execution_error:'Непредвиденная ошибка выполнения.',server_restarted:'Сервер перезапущен во время выполнения. Повторите запуск.',model_discovery_failed:'Не удалось получить модели. Проверьте ключ и сеть.',internal_error:'Непредвиденная ошибка сервера.',forbidden_origin:'Источник запроса запрещён.',forbidden_host:'Адрес сервера запрещён.',payload_too_large:'Запрос слишком большой.',
  createFirst:'Создать первого агента',ready:'Готовы к работе',readyDescription:'Создайте агента, назначьте ему задачу и проследите путь от запроса до результата.',total:'Всего',step:'Шаг',saved:'Сохранено',history:'История агента',viewHistory:'Посмотреть запуски',security:'ЗАЩИЩЁННЫЙ ЛОКАЛЬНЫЙ РЕЖИМ',brand:'AgentOps',brandAi:'AI',copyright:'AgentOps AI · Локальный MVP',priceNote:'Стоимость неизвестна, пока не заданы цены за миллион токенов. Цены зависят от модели; бесплатность не предполагается.'
};
export function translate(locale:'ru'|'en', key:string):string {const dict:Record<string,string>=locale==='ru'?ru:en;return dict[key] || dict.error;}
