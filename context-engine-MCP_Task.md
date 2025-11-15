
# Техническое задание 

**Система:** `context-engine-MCP`
**Назначение:** MCP-сервер, который по тексту задачи выдаёт нормализованный «контекст разработки» (фрагменты кода, фрагменты документации, подграф связей). Действует детерминированно: **только два состояния ответа — `ok` или `down`**.

---

## 0. Резюме и цели

* Предоставить IDE-ассистенту единый инструмент `get_context`, возвращающий **минимально достаточный** и **структурно корректный** контекст.
* Обеспечить **надёжность и воспроизводимость**: строгие схемы БД, фиксированные правила ретрива, explain-план.
* Обеспечить **универсальность**: конфигурируемость под разные проекты без переписывания кода.

---

## 1. Термины

* **Контекст** — набор артефактов (код/доки/подграф + explain), возвращаемый инструментом.
* **Модуль** — логическая область кода (папка/сервис/пакет), фигурирует в маршрутизации.
* **Чанк** — атомарный фрагмент кода/документа для индексации/поиска.
* **Подграф** — фрагмент графа знаний вокруг узла `Module` с заданной глубиной.

---

## 2. Область применения и ограничения

**Применение:** локальная/контейнерная разработка, интеграция с IDE-ассистентом через MCP.
**Не цели:** полнотекстовый поиск «для людей», автогенерация кода вместо IDE, частичные ответы при сбоях.

---

## 3. Функциональные требования

1. **Транспорт:** только **MCP-wire** (stdio/WebSocket) по спецификации MCP.
2. **Инструменты MCP:**

   * `get_context` — основной.
   * Административные: `ingest`, `search_raw`, `pin`, `forget`, `explain_plan`.
3. **Источники данных:**

   * Код (векторный+лексический индексы в Postgres).
   * Документация (векторный+лексический индексы в Postgres).
   * Граф устойчивых сущностей (Neo4j).
4. **Детерминизм:** при недоступности любого обязательного источника — `status:"down"` с указанием `component`. Частичных ответов нет.
5. **Конфигурируемость:** правила маршрутизации, параметры ретривера, эмбеддингов, глубины графа — в `config/engine.yml`, горячая перезагрузка с TTL.

---

## 4. Нефункциональные требования

* **Производительность:** средняя латентность `get_context` ≤ 500 мс при прогретых кэшах; пиковая ≤ 1500 мс.
* **Надёжность:** чёткая сигнализация `down`, логирование всех этапов с `plan_id`.
* **Воспроизводимость:** ответ всегда содержит версию/чексумму конфига, `commit_sha`/`chunk_id` артефактов.
* **Безопасность:** санитизация секретов на этапе индексации; allowlist расширений; denylist путей.

---

## 5. Архитектура (высокоуровнево)

* **MCP-сервер** (Python 3.11+): принимает вызовы инструментов, валидирует вход, оркестрирует ретрив.
* **Core-слои:**

  * **Resolver** (маршрутизация по `engine.yml` + эвристики).
  * **Retriever** (vector + lexical + hybrid, опциональный rerank).
  * **GraphContext** (подграф из Neo4j, глубина по умолчанию 3).
  * **Merger** (слияние результатов, отсечка по бюджету токенов, dedup).
* **Хранилища:** `PgVectorStore`, `PgLexStore`, `Neo4jGraphStore` — через стабильные интерфейсы (возможность заменить backend без изменения API MCP).

---

## 6. Схемы данных (Postgres)

### 6.1 Расширение

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

### 6.2 Индексы кода/доков

```sql
-- CODE
CREATE TABLE code_chunks (
  id          bigserial PRIMARY KEY,
  project     text NOT NULL,
  workspace   text,
  user_id     text,
  path        text NOT NULL,
  module      text,
  content     text NOT NULL,
  embedding   vector(1024),
  lex         tsvector,
  commit_sha  text,
  chunk_id    text,          -- canonical: project:path:range:fp
  fp_sha256   text NOT NULL,
  updated_at  timestamptz DEFAULT now()
);
CREATE INDEX code_chunks_proj_path_idx ON code_chunks (project, path);
CREATE INDEX code_chunks_proj_mod_idx  ON code_chunks (project, module);
CREATE INDEX code_chunks_lex_idx       ON code_chunks USING GIN(lex);

-- DOCS
CREATE TABLE doc_chunks (
  id          bigserial PRIMARY KEY,
  project     text NOT NULL,
  workspace   text,
  user_id     text,
  doc_name    text NOT NULL,
  section     text,
  content     text NOT NULL,
  embedding   vector(1024),
  lex         tsvector,
  commit_sha  text,
  chunk_id    text,          -- canonical: project:doc:section:fp
  fp_sha256   text NOT NULL,
  updated_at  timestamptz DEFAULT now()
);
CREATE INDEX doc_chunks_proj_doc_idx ON doc_chunks (project, doc_name);
CREATE INDEX doc_chunks_lex_idx      ON doc_chunks USING GIN(lex);
```

### 6.3 Происхождение/связи/фидбек

```sql
CREATE TABLE dp_datapoint (
  id          bigserial PRIMARY KEY,
  project     text NOT NULL,
  kind        text NOT NULL,   -- code | doc
  uri         text NOT NULL,   -- file://... | doc://...
  module      text,
  commit_sha  text,
  fp_sha256   text NOT NULL,
  created_at  timestamptz DEFAULT now()
);
CREATE UNIQUE INDEX dp_unique ON dp_datapoint(project, uri, fp_sha256);

CREATE TABLE dp_edge (
  id          bigserial PRIMARY KEY,
  project     text NOT NULL,
  src_uri     text NOT NULL,
  rel         text NOT NULL,   -- IMPORTS | REFERENCES | DESCRIBED_IN | IMPLEMENTS
  dst_uri     text NOT NULL
);
CREATE INDEX dp_edge_proj_src_idx ON dp_edge (project, src_uri);

CREATE TABLE dp_feedback (
  id          bigserial PRIMARY KEY,
  project     text NOT NULL,
  task_fp     text NOT NULL,
  uri         text NOT NULL,
  label       smallint NOT NULL,  -- -1 | 0 | +1
  created_at  timestamptz DEFAULT now()
);
CREATE INDEX dp_feedback_proj_task_idx ON dp_feedback (project, task_fp);
```

### 6.4 Символьный индекс кода

```sql
CREATE TABLE symbols (
  id          bigserial PRIMARY KEY,
  project     text NOT NULL,
  module      text,
  path        text NOT NULL,
  kind        text NOT NULL,   -- class | func | router | const
  name        text NOT NULL,
  range       int4range,
  sig         text,
  commit_sha  text
);
CREATE INDEX symbols_proj_name_idx ON symbols (project, name);

CREATE TABLE symbol_refs (
  id          bigserial PRIMARY KEY,
  project     text NOT NULL,
  from_path   text NOT NULL,
  to_symbol   text NOT NULL,
  rel         text NOT NULL    -- DECLARES | REFERENCES
);
CREATE INDEX symbol_refs_proj_to_idx ON symbol_refs (project, to_symbol);
```

---

## 7. Схема графа (Neo4j)

**Узлы:**
`:Module{project,name,path}`, `:Contract{project,name,file}`, `:DocSection{project,doc_name,name}`, `:Tool{name,kind}`.
**Рёбра:**
`(:Module)-[:IMPLEMENTS]->(:Contract)`
`(:Module)-[:DESCRIBED_IN]->(:DocSection)`
`(:DocSection)-[:APPLIES_TO]->(:Module)`
`(:Module)-[:BEST_ACCESSED_VIA]->(:Tool)`

**Ограничения:**

```cypher
CREATE CONSTRAINT module_unique IF NOT EXISTS
FOR (m:Module) REQUIRE (m.project, m.name) IS UNIQUE;

CREATE CONSTRAINT contract_unique IF NOT EXISTS
FOR (c:Contract) REQUIRE (c.project, c.name) IS UNIQUE;

CREATE CONSTRAINT docsection_unique IF NOT EXISTS
FOR (d:DocSection) REQUIRE (d.project, d.doc_name, d.name) IS UNIQUE;
```

---

## 8. Конфигурация `config/engine.yml`

```yaml
project: <string>
namespaces:
  enabled: true

routing:
  rules:
    - match: ["gateway","auth","jwt","initdata","mini app"]
      module: "services/gateway_api"
      docs: ["Глава 4 Контракты API"]
      contracts: ["InitDataAuth"]
    - match: ["party","sync","ws","realtime"]
      module: "services/party_sync"
      docs: ["Глава 3 Сетевая логика"]
    - match: ["media","tts","image","avatar"]
      module: "services/media_broker"
      docs: ["Глава 5 Генеративные слои"]
    - match: ["ui","react","vite","webapp","miniapp"]
      module: "apps/webapp"
      docs: ["Глава 2 UX-флоу"]

defaults:
  graph_depth: 3
  max_code_chunks: 8
  max_doc_chunks: 5

retrieval:
  mode: hybrid          # vector | lexical | hybrid
  weights:
    vector: 0.7
    bm25: 0.3
  rerank:
    enabled: false

embed:
  code:
    model: text-embedding-3-large
    dimensions: 1024
  docs:
    model: text-embedding-3-small
    dimensions: 1024

provenance:
  include_commit_sha: true
  include_fp_sha256: true

observability:
  config_ttl_seconds: 30
  plan_id: true
```

---

## 9. Индексация (E→C→L)

**Запуск:** `python tools/index_repo.py --project <name>`

**Extract:**

* Источник файлов: `git ls-files`.
* Denylist путей: `deploy/**`, `observability/**`, `qa/**`, `**/__pycache__/**`, `**/node_modules/**`, сборочные артефакты.
* Allowlist расширений: `.py,.ts,.tsx,.md,.yaml,.yml`.

**Sanitize:** удаление секретов и чувствительных токенов по шаблонам.

**Cognify:**

* Чанкинг кода: AST для `.py/.ts/.tsx`; fallback — блок **120** строк.
* Чанкинг доков: деление по заголовкам `#`/`##`/`###`.
* Извлечение импортов/ссылок → `dp_edge`.
* Лексика: `lex = to_tsvector('simple', content)`.

**Embed:**

* code → `text-embedding-3-large (dims=1024)`; docs → `text-embedding-3-small (dims=1024)`.
* Заполнять `embedding`, `commit_sha`, `fp_sha256`, `chunk_id`.

**Load:**

* upsert в `code_chunks`/`doc_chunks`;
* запись в `dp_datapoint`, `dp_edge`, `symbols`, `symbol_refs`.

**Файловые артефакты:**
`.mimic_index/code_index.json`, `.mimic_index/docs_index.json` (path/module/doc/hash/size/commit_sha/chunk_id).

**Служебные CLI:**

* `tools/memify.py` — пересчёт `lex`, чистка дублей (fp/near-dup).
* `tools/graphify.py` — проекция устойчивых рёбер Neo4j (`DESCRIBED_IN`, `IMPLEMENTS`, `REFERENCES`), поддержка `--dry-run`.

---

## 10. Ретрив и слияние

### 10.1 Выбор модуля

* Шаг 1: лексический матч по `routing.rules.match`.
* Шаг 2 (если Шаг 1 не дал результата): эвристика по Neo4j (по именам узлов/синонимам).

### 10.2 Поиск

* **Vector:** pgvector, оператор **`<=>`** (косинусная дистанция), сортировка `ASC`.
  Преобразование в схожесть: `sim_vec = 1 - dist_cos`.
* **Lexical:** `ts_rank_cd(lex, plainto_tsquery(...))` → нормализация в `[0,1]`.
* **Hybrid:** объединение top-K списков с весами:
  `score = w_vec * sim_vec + w_bm25 * sim_bm25 + bias_pin - penalty_neg`,
  где `bias_pin`/`penalty_neg` — поправки из `dp_feedback`.
* **Rerank:** по умолчанию `disabled`; при включении — лёгкий cross-encoder на top-N (параметризуемо).

### 10.3 Бюджет токенов и dedup

* Удалять перекрывающиеся чанки одного файла.
* Контролировать суммарный размер контекста; при нехватке — уменьшать K у менее значимого источника (сначала доки).

---

## 11. MCP API

### 11.1 `get_context`

**params:**

```json
{
  "task": "string",
  "project": "string",
  "workspace": "string(optional)",
  "user_id": "string(optional)",
  "max_code_chunks": 8,
  "max_doc_chunks": 5,
  "graph_depth": 3
}
```

**result (status="ok"):**

```json
{
  "status": "ok",
  "project": "string",
  "module": "string",
  "code": [
    {
      "path": "string",
      "uri": "file://...",
      "commit_sha": "string",
      "chunk_id": "string",
      "fp_sha256": "string",
      "content": "string"
    }
  ],
  "docs": [
    {
      "doc": "string",
      "section": "string",
      "uri": "doc://...",
      "commit_sha": "string",
      "chunk_id": "string",
      "fp_sha256": "string",
      "content": "string"
    }
  ],
  "graph": {
    "node": "string",
    "depth": 3,
    "relations": [
      {"type":"IMPLEMENTS","target":"string","source":"rule:contracts"},
      {"type":"DESCRIBED_IN","target":"string","source":"rule:docs"}
    ]
  },
  "explain": {
    "plan_id": "uuid",
    "route": "engine.yml: rule(...)",
    "sources": {
      "code": "postgres: code_chunks",
      "docs": "postgres: doc_chunks",
      "graph": "neo4j"
    },
    "params": {
      "max_code_chunks": 8,
      "max_doc_chunks": 5,
      "graph_depth": 3,
      "retrieval": {"mode":"hybrid","weights":{"vector":0.7,"bm25":0.3},"rerank":false},
      "config_version": "v1.3",
      "config_checksum": "sha256:..."
    }
  }
}
```

**error (status="down"):**

```json
{"status":"down","component":"neo4j","message":"neo4j unavailable","plan_id":"uuid"}
```

### 11.2 `ingest`

```json
{"project":"string"}
```

**result:** `{ "status":"ok", "indexed": { "code":N, "docs":M } }`

### 11.3 `search_raw`

```json
{"project":"string","query":"string","scope":"code|doc|both","k":10}
```

**result:** список `{uri,path_or_doc,score,content?}`

### 11.4 `pin` / `forget`

```json
{"project":"string","uri":"string","label":1}   // pin(+1) / forget(-1)
```

**result:** `{ "status":"ok" }`

### 11.5 `explain_plan`

```json
{"plan_id":"uuid","last":true}
```

**result:** подробный план (vector/lex наборы, веса, отсечка).

---

## 12. Развёртывание

**docker-compose.yml**:

* `pg` — образ `ankane/pgvector`, порт `5432`, volume `./_data/pg`.
* `neo4j` — образ `neo4j:5`, `NEO4J_PLUGINS='["apoc","graph-data-science"]'`, порты `7474/7687`, volume `./_data/neo4j`.
* `context-engine` — MCP-сервер; ENV: `OPENAI_API_KEY`, `PG_DSN`, `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASS`; volume `./logs`.

**Шаги:**

1. `docker compose up -d`
2. `python tools/index_repo.py --project <name>`
3. запуск MCP-сервера `context-engine/mcp/server.py`.

---

## 13. Логирование и наблюдаемость

* Логи JSONL: `logs/context-engine.log` (`ts, plan_id, project, module, latency_ms, source_latencies, result_sizes`).
* `plan_id` — в каждом ответе/ошибке.
* Горячая перезагрузка `engine.yml` с `config_ttl_seconds`.

---

## 14. Безопасность

* Санитизация перед индексацией (регулярные выражения для ключей/токенов).
* Allowlist расширений, denylist путей.
* ENV-секреты вне репозитория, `.env.example` с шаблонами.

---

## 15. Тестирование и приёмка

* **Unit:** парсер `engine.yml`, AST-чанкинг, гибридный скоринг, `pin/forget`.
* **Интеграция:** поднять контур, выполнить индексацию, `get_context` → `ok` с кодом/доками/подграфом.
* **Негатив:** остановить Neo4j → `down` c `component:"neo4j"`.
* **Критерии готовности (DoD):**

  * Инструмент `get_context` полностью соответствует контракту.
  * Индексы заполнены, `.mimic_index/*` созданы.
  * Гибрид по умолчанию (`vector 0.7 / bm25 0.3`), `rerank=false`.
  * Подграф глубины 3 возвращается и настраивается.
  * Логи и `plan_id` присутствуют; версия/чексумма конфига в ответе.

---

## 16. Структура репозитория (минимум)

```
context_engine/
  core/ (resolve, retriever, graph, merger, stores/)
  mcp/  (server.py, tools.json)
config/
  engine.yml
schemas/
  sql/    (000_init.sql, ...)
  cypher/ (000_constraints.cql, 001_schema.cql)
tools/
  index_repo.py
  memify.py
  graphify.py
.mimic_index/
logs/
docker-compose.yml
.env.example
README.md
```

