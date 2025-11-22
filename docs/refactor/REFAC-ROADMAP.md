# REFAC-ROADMAP: План рефакторинга `context_engine`

Версия: v1  
Статус: draft  
Владелец архитектуры: Dushilov  

Этот документ описывает **пошаговый план рефакторинга** `context_engine` на основе четырёх архитектурных ТЗ:

- `docs/refactor/TZ-1-foundation.md` — фундамент: `project`-модель, DAL, статусы MCP  
- `docs/refactor/TZ-2-datagraph.md` — ingest & data-graph: `dp_edge`, `symbols`, новый `graphify`  
- `docs/refactor/TZ-3-policy-retrieval.md` — data-first `get_context`, policy-routing, feedback, Explain  
- `docs/refactor/TZ-4-admin-devex.md` — Admin UI и DevEx  

Роадмап разбит на **“волны” (Wave 0–5)**.  
Каждая волна опирается на соответствующее ТЗ и **не должна перескакивать вперёд**.

---

## Wave 0 — Подготовка

**Цель:**  
Подготовить репозиторий и окружение к рефакторингу, чтобы LLM/разработчик могли работать по ТЗ.

**Задачи:**

1. Разместить ТЗ в репозитории:
   - `docs/refactor/TZ-1-foundation.md`
   - `docs/refactor/TZ-2-datagraph.md`
   - `docs/refactor/TZ-3-policy-retrieval.md`
   - `docs/refactor/TZ-4-admin-devex.md`
   - `docs/refactor/REFAC-ROADMAP.md` (текущий документ)

2. Минимальный sanity-check:
   - Проект собирается.
   - Базовые команды/скрипты (в текущем виде) умеют запускаться без фатальных ошибок.

**Критерии завершения:**

- Все ТЗ лежат в `docs/refactor` и доступны редактору/LLM.
- Репозиторий “живой”: запуск в текущем виде не разваливается на старте.

---

## Wave 1 — Фундамент (ТЗ-1 Foundation)

**Связанное ТЗ:** `TZ-1-foundation.md`  

**Цель:**  
Укрепить “скелет” приложения: единая модель `project`, единый DAL для Postgres/Neo4j, честные статусы MCP, минимальный CLI.  
Поведение бизнес-логики **по возможности не менять**, только перенести её на здоровый фундамент.

### Основные задачи

1. **Project-модель**

- Проаудировать все места, где используется `project`, `workspace`, `user_id`.
- Убедиться, что все ключевые таблицы (`code_chunks`, `doc_chunks`, `dp_*`, `symbols`, `symbol_refs`, `jobs`, `plans` и т.д.):
  - содержат поле `project`,
  - обращаются через запросы с фильтром по `project`.
- Очистить бизнес-логику от использования `workspace` / `user_id`:
  - оставить только `project` как рабочий контекст.

2. **Единый DAL (Postgres + Neo4j)**

- В `core/` реализовать или доработать:
  - `PgClient`, `GraphClient`,
  - репозитории: `CodeRepo`, `DocRepo`, `GraphRepo`, `FeedbackRepo` и др. по необходимости.
- Переподключить на DAL:
  - MCP-сервер (`mcp/server.py`),
  - backend API (FastAPI-сервис),
  - tools (`index_repo`, `memify`, `graphify`).
- Удалить прямые `psycopg.connect` / `GraphDatabase.driver` вне DAL.

3. **Честные статусы MCP**

- В начале обработки `get_context`:
  - выполнять health-check Postgres и Neo4j.
  - если что-то критично недоступно → вернуть `status="down"` и осмысленный `error_code`.
- Удалить “тихие фолбеки” (варианты “работаем без графа” и т.п.).

4. **Минимальный DevEx (начало)**

- Ввести начальный Python CLI (`manage.py` или аналог):
  - команда `health-check` через core/DAL.
- Избавиться от жёсткого хардкода путей в PowerShell-скриптах там, где это блокирует тестовый запуск.

### Критерии завершения Wave 1

- MCP `get_context`:
  - честно возвращает `status="down"` при недоступности критичных компонентов,
  - не маскирует деградации.
- Все основные пути доступа к БД идут через DAL.
- Любые операции с данными учитывают `project`.
- Есть работающая CLI-команда `health-check` без завязки на PowerShell.

---

## Wave 2 — Data-Graph (ТЗ-2 Ingest & Data-Graph)

**Связанное ТЗ:** `TZ-2-datagraph.md`  

**Цель:**  
Построить **data-driven граф**: Neo4j полностью синхронизирован с данными в PG (`dp_*`, `symbols`, `symbol_refs`, `code_chunks`, `doc_chunks`), **без** зависимости от YAML-routing.  

**Замечание по реализации (выполнено):**
- Канонические URI добавлены (chunks/symbols/dp_edge), graphify переписан на PG-данные, PowerShell-скрипты удалены. Оставшиеся ограничения: резолв импортов/USES и doc-link детекция пока эвристические (можно доработать позже, но data-driven граф уже строится из PG).

### Основные задачи

1. **Канонизация URI**

- В `index_repo` / `memify` обеспечить формирование URI в канонических форматах:
  - `file://{project}/{relative_path}`
  - `module://{project}/{module_name}`
  - `symbol://{project}/{module_name}#{symbol_name}`
  - `doc://{project}/{doc_name}`
  - `docsection://{project}/{doc_name}#{section_id}`
- Обеспечить связь `dp_datapoint` ↔ chunks через `uri`.

2. **Code-symbol analyser**

- Реализовать/доработать анализатор кода:
  - таблица `symbols` (определения),
  - таблица `symbol_refs` (использования).
- На основе этих таблиц формировать `dp_edge`:
  - `edge_kind="DEFINED_IN"` (символ → файл),
  - `edge_kind="USES"` (символ → символ).

3. **Doc-link analyser**

- Реализовать парсинг документации:
  - выделение документов и секций,
  - генерация `doc://` и `docsection://` URI.
- Извлекать ссылки из документации на код и другие доки:
  - формировать `dp_edge`:
    - `DESCRIBED_IN` (код/модуль → раздел документа),
    - `REFERENCES` (раздел документа → символ/модуль/секция).

4. **Унификация `dp_edge`**

- Привести таблицу `dp_edge` к единому контракту:
  - `project`, `from_uri`, `to_uri`, `edge_kind`, `source`, `confidence`.
- Зафиксировать набор используемых `edge_kind` на данном этапе:
  - `DEFINED_IN`, `USES`, `DESCRIBED_IN`, `REFERENCES` (минимальный набор).

5. **Новый `graphify`**

- Реализовать новый `graphify`, который:
  - читает данные только из PG через DAL (`code_chunks`, `doc_chunks`, `symbols`, `dp_edge`);
  - строит узлы:
    - `File`, `Module`, `Symbol`, `Doc`, `DocSection`,
    - с полем `uri` и базовыми атрибутами.
  - строит рёбра:
    - `DEFINED_IN`, `USES`, `DESCRIBED_IN`, `REFERENCES`, `PART_OF_MODULE`.
- Ввести режимы:
  - `dry_run` — только статистика (сколько нод/рёбер будет создано, какие проблемы у данных),
  - `apply` — фактическая запись в Neo4j.
- Полностью убрать из `graphify` зависимость от `engine.yml`/routing.

### Критерии завершения Wave 2

- Запуск `build-graph` строит граф **исключительно** по данным из PG.
- Каждый узел в Neo4j имеет `uri`, на который есть соответствующие записи в PG.
- Существование/отсутствие записей в `policy`/`routing` не влияет на наличие нод и рёбер в графе.

---

## Wave 3 — Retrieval & Policy-Layer (ТЗ-3 `get_context` + Policy)

**Связанное ТЗ:** `TZ-3-policy-retrieval.md`  

**Цель:**  
Переписать `get_context` так, чтобы:

- сначала работал **data-слой** (гибридный поиск + data-graph),
- затем подключался **policy-слой** (routing + feedback + sensitive),
- Explain честно показывал, где решение принял data-слой, а где — политика.

### Основные задачи

1. **Разделение конфигов**

- Явно развести:
  - инфраструктуру (`.env`, DSN, ключи),
  - параметры движка (`engine`),
  - **policy** (`policy.yml` или секция в `engine.yml`).
- Определить структуру:
  - `routing`-правила,
  - `sensitive`-зоны,
  - базовые параметры (boost/penalty, global weights).

2. **Routing engine**

- Реализовать модуль `core.policy.routing`:
  - загрузка и валидация `policy`-конфига;
  - match-режимы (keyword_any, keyword_all, regex);
  - генерация `RoutingEffects`:
    - boosts/penalties по модулям и тегам,
    - глобальные коэффициенты для code/docs и ограничений по токен-бюджету.

3. **Feedback engine**

- Реализовать модуль `core.policy.feedback`:
  - API `get_feedback_effects(project, uris)` для агрегирования pin/forget.
- Интегрировать существующую таблицу `dp_feedback`:
  - конвертировать данные в численные эффекты (bias/penalty) на уровне URI/модулей.

4. **Sensitive-зоны**

- Реализовать обработку `policy.sensitive`:
  - кандидаты (URI/модули), попадающие под `uri_pattern`, не должны попадать в финальный контекст.
- Добавить информацию об отфильтрованных URI в Explain.

5. **Рефакторинг `get_context`**

- Логически разделить `get_context` на две фазы:
  - **Data-слой:**
    - гибридный поиск по PG (code + docs),
    - агрегация по модулям,
    - выбор подграфа в Neo4j,
    - вычисление базовых score.
  - **Policy-слой:**
    - применение `RoutingEffects` и `FeedbackEffects`,
    - фильтрация sensitive-зон,
    - перерасчёт финальных score модулей/чанков,
    - выбор чанков под токен-бюджет.
- Не ломать внешний контракт MCP: расширения только через metadata/plan.

6. **Explain/plan**

- Расширить структуру плана:
  - `data_route`: кандидаты, base-score, статистика по графу.
  - `policy_route`: сработавшие rules, feedback-эффекты, sensitive-filter.
  - `selection`: финальный выбор модулей и чанков.
  - `plan_schema_version`.

### Критерии завершения Wave 3

- `get_context` при **пустом** policy и отсутствии feedback:
  - ведёт себя детерминированно,
  - выдаёт контекст, основанный на data-слое (гибридный поиск + граф).
- При наличии policy/feedback:
  - данные не пропадают “просто потому, что их нет в YAML”;
  - влияние правил и feedback видно в Explain.
- Explain/plan имеет полную структуру: `data_route`, `policy_route`, `selection`.

---

## Wave 4 — Admin UI & DevEx (ТЗ-4)

**Связанное ТЗ:** `TZ-4-admin-devex.md`  

**Цель:**  
Сделать систему **наблюдаемой и удобной** в эксплуатации: Admin UI для диагностики + устойчивый CLI/DevEx без хардкода.

### Основные задачи

1. **Backend API для Admin UI**

Реализовать набор эндпоинтов `/api/admin/*` (через DAL):

- `GET /api/admin/health?project=...`
  - состояние: PG, Neo4j, MCP, backend.
- `GET /api/admin/jobs?project=...`
  - список ingest/graphify/прочих job’ов.
- `GET /api/admin/plans?project=...`
  - список сохранённых планов `get_context`.
- `GET /api/admin/plans/{id}`
  - детальный Explain.
- `GET /api/admin/config?project=...`
  - агрегированное представление `engine` и `policy`.

2. **Admin UI (Next.js / существующий фронт)**

Добавить разделы:

- Project selector:
  - глобальный выбор `project` для всех страниц.
- Health dashboard:
  - статусы компонентов, диагностика.
- Jobs dashboard:
  - таблица job’ов с фильтрами.
- Plans / Explain viewer:
  - список планов и подробная карточка каждого.
- Config / Policy viewer (read-only):
  - просмотр текущих настроек `engine` и `policy`.

3. **CLI и DevEx**

- Завершить реализацию `manage.py` / CLI:
  - `ingest --project ...`,
  - `build-graph --project ...`,
  - `health-check --project ...`.
- PowerShell/батники:
  - удалить либо превратить в тонкие обёртки над CLI **без логики и путей**.

### Критерии завершения Wave 4

- Через UI можно:
  - выбрать `project`,
  - посмотреть health, jobs, планы и конфиги.
- Все `/api/admin/*`-эндпоинты работают через DAL.
- Основные служебные операции запускаются через CLI, а не через хрупкие `.ps1`.

---

## Wave 5 — Hardening (опциональный хвост)

**Цель:**  
Закрепить новую архитектуру тестами и инвариантами, убрать мелкий техдолг.

**Состояние:** выполнено. Покрыты unit/integration (tests/policy/*, tests/test_policy_invariants.py, tests/test_budget_selection.py, tests/test_get_context_invariants.py), обновлён HOWTO (docs/refactor/HOWTO-ops.md) по get_context/explain/Admin UI.

### Основные задачи

- Интеграционные тесты для ключевых инвариантов:
  - data есть → policy не может “магически” спилить её из системы без явных правил.
  - при пустой policy и отсутствии feedback поведение `get_context` стабильно и воспроизводимо.
- Минимальные unit-тесты:
  - `core.policy.routing`,
  - `core.policy.feedback`,
  - парсинг `policy.yml`/конфигов.
- Мелкий рефакторинг и документация:
  - короткие HowTo для `ingest`, `build-graph`, `get_context`, работы с Admin UI.

### Критерии завершения Wave 5

- Набор тестов позволяет с уверенностью менять детали реализации, не ломая архитектурные инварианты.
- Документация для разработчика и оператора отражает новую архитектуру.

---

## Как использовать этот роадмап с LLM / Codex

1. **Все архитектурные детали** находятся в:
   - `TZ-1-foundation.md`,
   - `TZ-2-datagraph.md`,
   - `TZ-3-policy-retrieval.md`,
   - `TZ-4-admin-devex.md`.

2. **Работаем по Waves:**
   - Сначала полностью закрываем задачи Wave 1,
   - затем Wave 2,
   - затем Wave 3,
   - затем Wave 4,
   - Wave 5 — хвост/стабилизация.

3. **Для каждой задачи/тикета:**
   - явно указывать Wave и соответствующее ТЗ,
   - формулировать локальный промпт для LLM:
     - “Мы сейчас в Wave N, см. `TZ-N-*.md`, задача: …, не выходить за рамки этого ТЗ”.

Этот документ — **карта**, а не замена ТЗ.  
Детальные требования и ограничения всегда берём из соответствующих `TZ-*.md`.
