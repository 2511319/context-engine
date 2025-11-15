# Дорожная карта по эпохам и модульная архитектура

Документ описывает целевые «эпохи» развития RPG‑Bot и перечень артефактов, выходящих по каждой эпохе. Отдельный раздел формализует принципы модульной архитектуры для простого подключения новых фич и технологий без перехода к монолиту.

## Принципы модульной архитектуры

- Многомодульный монорепозиторий.
  - services/*: независимые сервисы (HTTP, WS, фоновые), каждый — отдельный контейнер/скейл‑юнит.
  - packages/*: общие SDK/библиотеки с жёсткой политикой зависимостей (контракты → SDK → сервисы, но не наоборот).
  - contracts/*: источник истины (OpenAPI 3.1, JSON Schema, CloudEvents) для генерации и валидации.
- Contracts‑first и обратная совместимость.
  - Версионирование API по пути: /v1, /v2; SemVer для packages/*.
  - Consumer‑driven contract tests и golden‑тесты в qa/.
- Порты и адаптеры.
  - Чёткие интерфейсы (SPI) для провайдеров TTS/IMG/LLM/Embeddings/Storage.
  - Реализации подключаются как плагины (Python entry points/pluggy) и выбираются конфигурацией.
- Слабая связность сервисов.
  - Коммуникации: REST (Gateway), WebSocket (Party Sync), асинхронные события (опционально Pub/Sub) для кросс‑доменных фич.
  - Никаких прямых импортов кода между сервисами; только через packages/* и контракты.
- Расширяемый фронтенд.
  - App‑shell + feature‑модули. Роут‑регистрация и lazy‑import фич по манифесту; фича — NPM‑пакет или локальный модуль.
  - Единые соглашения: фабрика маршрутов, точка инициализации, доступ к API‑клиенту и телеметрии через DI/контекст.
  - Рекомендации и альтернативы: см. docs/architecture/frontend-modularity.md.
- Наблюдаемость и безопасность по умолчанию.
  - Структурированный лог, трассировки с traceId, метрики. OWASP API Top‑10 чек‑лист в security/.
- Независимый жизненный цикл.
  - Каждый сервис имеет свой Dockerfile, Helm/Cloud Run манифест и политику релизов; Blue/Green/Canary на уровне сервиса.

## Эпоха A — UX/Auth Mini App

- Цель: безопасный вход через Telegram initData и базовый UX‑фрейм для модулей.
- Ключевые работы:
  - Обмен initData → JWT (gateway_api) и интеграция в WebApp (apps/webapp).
  - Хранилище токена (TTL), скрытие initData из URL, централизованный axios‑интерсептор.
  - App‑shell, AuthGate и контракт расширения для feature‑модулей.
- Артефакты:
  - contracts/openapi/rpg-bot.yaml (эндпоинт /v1/auth/telegram).
  - services/gateway_api/* (endpoint, валидация initData, JWT).
  - apps/webapp/src/api/client.ts (обмен, хранение токена, интерсепторы).
  - apps/webapp/src/App.tsx (AuthGate, базовая навигация).
  - qa/tests/* (тесты API обмена и webapp e2e‑спеки — при подключении Playwright).
  - docs/product/VISION.md (видение и целевые сценарии).
- Критерии готовности:
  - Авто‑вход в Mini App из Telegram; ошибки UX локализованы; pytest — зелёный.

### Прогресс (чек-лист)

- [x] Endpoint обмена initData → JWT в gateway_api.
- [x] Интеграция обмена и хранение токена с TTL в WebApp.
- [x] Axios‑интерсептор Authorization: Bearer и скрытие initData из URL.
- [x] AuthGate/PersistGate в app‑shell (AuthProvider + AuthGate).
- [x] Базовая навигация (таб‑бар) и локализация ключевых строк.
- [x] E2E‑спеки (Playwright) для авторизации и health‑флоу.

## Эпоха B — Party Sync UX

- Цель: живые обновления состояния кампаний в реальном времени.
- Ключевые работы:
  - WS‑клиент в webapp, визуализация событий, реплей истории для поздних подписчиков.
  - Схемы CloudEvents (contracts/events) и валидация на клиенте.
- Артефакты:
  - services/party_sync/* (hub, маршруты, политика ретеншна и реплея).
  - contracts/events/* (JSON Schema для канонических событий).
  - apps/webapp/src/features/party/* (UI, состояние, подписки, тесты на схему).
  - observability/dashboards (панели по WS соединениям и задержкам).
- Критерии готовности:
  - Два клиента получают одно событие, поздний подписчик — корректный реплей; метрики покрывают коннекты и лаг.

### Прогресс (чек-лист)

- [x] Базовый WS‑клиент в webapp (createPartyWs) и конфигурация URL.
- [x] UI потока событий: подключение/отключение, отображение входящих сообщений.
- [x] Отправка пользовательского события (eventType + payload JSON).
- [ ] Валидация по JSON Schema (envelope) на клиенте.
- [x] Добавлен каркас схемы событий: contracts/events/event_envelope.schema.json.
 - [x] Валидация конверта событий Ajv в webapp (отправка/приём).

## Эпоха C — Media Jobs UX

- Цель: пользовательский флоу задач TTS/IMG/Avatar с отслеживанием статуса.
- Ключевые работы:
  - Формы постановки задач, polling/subscribe статусов, идемпотентность на клиенте.
  - Абстракции провайдеров с конфигурируемыми реализациями (локально/облако).
- Артефакты:
  - services/media_broker/* (очередь, менеджер, эндпоинты, idempotency).
  - apps/webapp/src/features/media/* (UI, кэш результатов, ретраи).
  - contracts/jsonschema/* (схемы результатов, golden‑данные в qa/golden/*).
- Критерии готовности:
  - Пользователь получает артефакт (tts wav/img webp) и может переиспользовать по clientToken.

### Прогресс (чек-лист)

- [x] Форма постановки TTS/IMG задач (init → jobId).
- [x] Polling статусов c backoff, завершение/ошибки.
- [x] Идемпотентность на клиенте (clientToken) и повторное получение результата.
- [x] Кэш результатов (session/local) и UX прогресса.
- [x] Проверка контрактов (JSON Schema) на клиенте и golden‑тесты.
- [x] Каркас UI: выбор типа, payload JSON, clientToken, отправка и базовый polling.

## Эпоха C — Media Jobs UX

- Цель: пользовательский флоу задач TTS/IMG/Avatar с отслеживанием статуса.
- Ключевые работы:
  - Формы постановки задач, polling/subscribe статусов, идемпотентность на клиенте.
  - Абстракции провайдеров с конфигурируемыми реализациями (локально/облако).
- Артефакты:
  - services/media_broker/* (очередь, менеджер, эндпоинты, idempotency).
  - apps/webapp/src/features/media/* (UI, кэш результатов, ретраи).
  - contracts/jsonschema/* (схемы результатов, golden‑данные в qa/golden/*).
- Критерии готовности:
  - Пользователь получает артефакт (tts wav/img webp) и может переиспользовать по clientToken.

## Эпоха D — Генерация и Память

- Цель: управляемая генерация с проверяемой структурой и поиск по доменам знаний.
- Ключевые работы:
  - genlayers: конфигурации профилей, драйверы LLM провайдеров, structured outputs с JSON Schema.
  - memory37: адаптеры хранилищ (pgvector), пайплайн индексации SRD/лора.
- Артефакты:
  - packages/genlayers/* (драйверы, профили, тесты на схемы; примеры profiles/*).
  - packages/memory37/* (адаптеры store, ETL‑скрипты, конфиги knowledge.yaml).
  - services/* интеграции (при необходимости endpoint’ы для генерации/поиска).
  - docs/architecture/ai-stack.md (потоки данных, практики OpenAI и pgvector).
- Критерии готовности:
  - Тестовые профили генерируют валидный по схеме ответ; поиск по домену «srd» возвращает релевантные документы.

### Прогресс (чек-лист)

- [x] Драйвер OpenAI в genlayers (chat/responses) + structured outputs.
- [x] JSON Schema‑валидация ответов и ретраи с уточняющими подсказками.
- [x] Gateway endpoint `/v1/generation/{profile}` использует genlayers + OpenAI.
- [x] Минимальный UI-вызов генерации в Mini App (feature Generation).
- [ ] ETL индексатор в memory37: загрузка лора/SRD → embeddings (OpenAI) → pgvector.
- [ ] API/CLI для поиска (vector/hybrid) и интеграция в UI.
- [ ] Набор тестов профилей и интеграционных тестов поиска.

## Эпоха E — Наблюдаемость и Безопасность

- Цель: эксплуатационная готовность с видимостью и защитой.
- Ключевые работы:
  - Структурированные логи, трассировки (traceId), метрики RPS/latency/error rate.
  - Политика JWT (aud/iss/exp/nbf/clock skew), rate‑limits, hardening заголовков.
- Артефакты:
  - observability/dashboards/* (логинг, latency, ws, очереди).
  - security/owasp-api-top10-checklist.md (актуализация, threat‑model.md).
  - services/*: middleware/интерсепторы телеметрии и безопасности.
- Критерии готовности:
  - Дашборды отражают ключевые SLI; чек‑лист OWASP закрыт для целевой поверхности.

### Прогресс (чек-лист)

- [ ] Структурированные логи + traceId корелляция (HTTP/WS/Jobs).
- [ ] Метрики latency/RPS/error rate, панели в observability/dashboards/*.
- [ ] Rate‑limits, security headers, безопасные CORS.
- [ ] Политика JWT (aud/iss/exp/nbf/clock skew), тесты.
- [ ] Threat‑model.md и аудит по OWASP API Top‑10.

## Эпоха F — CI/CD и Облако

- Цель: надёжные сборки, проверки и выкладки по сервисам.
- Ключевые работы:
  - Docker, тегирование, сканирование; Cloud Run/Helm‑манифесты, секреты, переменные окружения.
  - Blue/Green/Canary и миграции (при появлении БД).
- Артефакты:
  - deploy/pipelines/* (pipeline, инструкции, секреты через Secret Manager).
  - .github/workflows/* (Poetry/pytest, npm lint, Spectral, образы).
  - docs/runbooks/* (процедуры релизов и откатов).
- Критерии готовности:
  - Релиз отдельного сервиса без простоя, с прогоном тестов и проверок на ветке main.

### Прогресс (чек-лист)

- [ ] Dockerfile для каждого сервиса (multi‑stage) и локальный запуск.
- [ ] CI: Poetry/pytest, npm lint, Spectral, сборка образов, базовое сканирование.
- [ ] Манифесты Cloud Run/Helm (cloud‑neutral), параметры и секреты.
- [ ] Blue/Green/Canary стратегия и хелсчек‑пробы.
- [ ] Документация по релизам/откатам (runbooks).

## Эпоха G — Расширяемость и Плагины

- Цель: стабильные точки расширения и модель поставки плагинов.
- Ключевые работы:
  - Описание и реализация SPI для: LLM/TTS/IMG/Embeddings/Storage (Python entry points/pluggy).
  - Фронтенд‑манифесты фич: контракт регистрации, тесты совместимости, сборка как пакет.
- Артефакты:
  - docs/architecture/spi.md (описание интерфейсов и lifecycle хуков).
  - packages/*/providers/* (референс‑реализации и шаблоны для сторонних интеграций).
  - apps/webapp/src/features/* (пример внешнего feature‑пакета с манифестом).
  - docs/architecture/frontend-modularity.md (варианты модульности FE и путь к Federation).
- Критерии готовности:
  - Подключение нового провайдера/фичи без изменений в ядре; только конфигурация и установка пакета.

### Прогресс (чек-лист)

- [ ] SPI для LLM/Embeddings/TTS/IMG/Storage (entry points/pluggy).
- [ ] Референс‑реализация OpenAI провайдеров на SPI.
- [ ] FE‑манифесты фич и пример внешнего пакета.
- [ ] PoC Module Federation (опционально) с fallback на локальные модули.
- [ ] Тесты совместимости (consumer‑driven contract tests).

## Эпоха H — Производительность и Стоимость

- Цель: устойчивость под нагрузкой и прозрачная стоимость.
- Ключевые работы:
  - Профилирование горячих путей, кэширование, back‑pressure для очередей, timeouts/retries/circuit‑breaker.
  - Снижение частоты вызовов провайдеров, кэш CDN для медиа.
- Артефакты:
  - observability/dashboards/* (latency budget, p95/p99), отчёты профилирования.
  - config/* (таймауты/ретраи/квоты), документация SLA/SLO/SLA.
- Критерии готовности:
  - На целевой нагрузке выдерживаются SLO, деградации управляемы.

### Прогресс (чек-лист)

- [ ] Профилирование серверов и фронтенда; отчёты и фиксация bottlenecks.
- [ ] Кэширование и back‑pressure в media_broker; таймауты/ретраи/circuit‑breaker.
- [ ] CDN для медиа (img/tts) и стратегия кэширования.
- [ ] Отчёт по стоимости OpenAI/запрос и бюджетирование.
- [ ] Нагрузочные прогоны и метрики p95/p99.

---

## Требования к качеству и проверкам

- Тесты: unit/contract/golden, e2e (Playwright) для критичных пользовательских флоу.
- Линт/типизация: ruff, mypy (строгий режим) — зелёные в CI.
- Документация: ADR на ключевые решения, схемы архитектуры в docs/.

## Переиспользуемые шаблоны

- Сервис: FastAPI app factory, health, конфиг через pydantic‑settings, структурированный логгер, middleware телеметрии.
- Пакет: Pydantic модели, лоадеры YAML/JSON, валидация, явный public API.
- Фича фронтенда: манифест регистрации, lazy‑маршрут, доступ к API/логгеру через контекст, локализация.

## Стратегические решения (уточнено)

- Провайдер ИИ: OpenAI (основной), абстракции сохраняются для альтернатив.
- Память: PostgreSQL + pgvector.
- Облако/хостинг: не зафиксировано, архитектура cloud‑neutral (контейнеры, 12‑factor).
- Фронтенд‑модули: app‑shell + feature registry (старт), дальнейший апгрейд к Module Federation при необходимости.

## Карта артефактов (резюме)

- Контракты: contracts/openapi/*, contracts/jsonschema/*, contracts/events/*.
- Сервисы: services/gateway_api/*, services/party_sync/*, services/media_broker/*.
- Пакеты: packages/rpg_contracts/*, packages/genlayers/*, packages/memory37/*.
- Приложение: apps/webapp/src/app‑shell и features/*.
- Наблюдаемость/Безопасность/Деплой: observability/*, security/*, deploy/*.
- Тесты/QA: services/*/tests/*, packages/*/tests/*, qa/tests/*, qa/golden/*.
