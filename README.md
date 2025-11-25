Context Engine MCP
==================

MCP‑совместимый сервер, который по тексту задачи возвращает минимально достаточный контекст разработки (код, документация, подграф). Ответ детерминированный: `status` строго `ok` или `down` с указанием проблемного компонента.

## Структура репозитория

| Путь | Назначение |
| ---- | ---------- |
| `config/engine.yml` | правила маршрутизации, параметры ретривера, дефолты инструментов |
| `core/` | конфиг‑лоадер, план‑лог, pg клиент, hybrid retrieval, merger, graph |
| `mcp/server.py` | MCP сервер (stdio), инструменты `get_context`, `search_raw`, `ingest`, `pin`, `forget`, `explain_plan` |
| `schemas/sql/*.sql` | миграции PostgreSQL (pgvector, GIN) |
| `schemas/cypher/*.cql` | ограничения и индексы Neo4j |
| `tools/*.py` | индексатор репозитория, memify, graphify, task fingerprint |
| `scripts/*.ps1` | (удалены, заменены CLI) |
| `manage.py` | Python CLI для ingest/graph/health |
| `tests/` | pytest‑покрытие (`test_task_fp.py`) |

## Размещение инфраструктуры (диск D:)

| Компонент | Директория |
| --------- | ---------- |
| Репозиторий | `D:\project\context_engine` |
| PostgreSQL cluster | `D:\infra\postgresql\cluster` (внутри `data/`, `postgres.log`, `pw.txt`) |
| Neo4j | `D:\infra\neo4j\server` |

### PostgreSQL 16 + pgvector 0.8.1
- Бинарники установлены через Scoop (`postgresql16`), всё состояние живёт в `D:\infra\postgresql\cluster`.
- Запуск / остановка:
  ```powershell
  $pg = (scoop prefix postgresql16)
  & "$pg\bin\pg_ctl.exe" -D "D:\infra\postgresql\cluster\data" -l "D:\infra\postgresql\cluster\postgres.log" -o "-p 5432" start
  & "$pg\bin\pg_ctl.exe" -D "D:\infra\postgresql\cluster\data" stop -m fast
  ```
- Роль/БД: `codex/codex`, `PG_DSN=postgres://codex:codex@127.0.0.1:5432/codex`.
- Миграции: применяйте `schemas/sql/*.sql` вручную через psql (`psql -f schemas/sql/000_init.sql`, затем `psql -f schemas/sql/010_pgvector_hnsw.sql`, `psql -f schemas/sql/020_chunk_uri.sql`, `psql -f schemas/sql/021_uri_symbols_edges.sql`).

### Neo4j Community 5.22
- Корень: `D:\infra\neo4j\server`.
- Сервис Windows установлен командой `neo4j.bat windows-service install`, старт/стоп: `neo4j.bat start|stop`.
- Пользователь `neo4j`, пароль `codex1234`.
- Примените `schemas/cypher/*.cql` вручную через `cypher-shell` (ps1-скрипты удалены).

## Подготовка окружения разработчика
1. Python 3.12+ 64‑bit. Установка зависимостей: `python -m venv .venv && .\.venv\Scripts\activate && pip install -r requirements.txt`. (install.ps1 удалён.)
2. Настройте `.env` (см. `.env.example`): `OPENAI_API_KEY`, `PG_DSN`, `NEO4J_*`.
3. Убедитесь, что Postgres и Neo4j подняты (см. команды выше). MCP сервер умеет проверять их доступность.
4. Индексация репозитория (повторять при изменении кода/доков) — через CLI:
   ```powershell
   python manage.py ingest --project context_engine
   # отдельно graphify при необходимости
   python manage.py build-graph --project context_engine --dry-run
   python manage.py build-graph --project context_engine
   ```
   Оригинальные скрипты `tools/index_repo.py`/`memify.py`/`graphify.py` остаются, но рекомендуется использовать CLI.
5. Тесты: `python -m pytest`.
6. MCP сервер (stdio): `python mcp/server.py`. Инструменты: `get_context`, `search_raw`, `ingest`, `pin`, `forget`, `explain_plan`. Для фоновых задач/ингеста используйте `python manage.py …`.
7. Автостарт ps1-скриптов убран; для автозапуска создавайте ярлыки/службы, вызывающие `python manage.py …` и `uvicorn api.main:app`.

## Переменные окружения (`.env.example`)
- `OPENAI_API_KEY`
- `PG_DSN=postgres://codex:codex@127.0.0.1:5432/codex`
- `NEO4J_URI=bolt://127.0.0.1:7687`
- `NEO4J_USER=neo4j`
- `NEO4J_PASS=codex1234`

## URI и dp_edge (ТЗ-2 базовые форматы)
- URI:
  - code file: `file://{project}/{relative_path}` (от корня репо)
  - module: `module://{project}/{module_name}`
  - symbol: `symbol://{project}/{module_name}#{symbol_name}`
  - doc: `doc://{project}/{doc_name}`
  - doc section: `docsection://{project}/{doc_name}#{section_id}`
- `dp_edge` (канонические поля `edge_kind`, `from_uri`, `to_uri`), допустимые `edge_kind` на этапе ТЗ-2:
  - `DEFINED_IN`: symbol -> file|module
  - `USES`: symbol -> symbol
  - `DESCRIBED_IN`: module|symbol -> docsection
  - `REFERENCES`: docsection -> symbol|module|docsection
Все сущности и рёбра должны иметь валидные URI и project.

## Примечания
- Размерность эмбеддингов — 1024 для кода и документов (`text-embedding-3-large/small`).
- Векторный поиск использует HNSW (`SET hnsw.ef_search=40` задаётся в `PgClient`).
- `graph.subgraph` возвращает компактный набор `{type,target,source}`; при сбое Neo4j возвращается пустой подграф и `status="down"`.
- Логи планов пишутся в `logs/context-engine.log` (JSONL).
- План по разработке локального UI и backend FastAPI лежит в `docs/CONTEXT_ENGINE_UI_PLAN.md`.
- Если Postgres/Neo4j недоступны, `get_context` возвращает `status="down"` с деталями компонента (тихие фолбеки отключены).
- Health‑эндпоинты кешируют метрики на 30 секунд и дополнительно резюмируют последние фоновые задачи (статусы/последний job).
- `max_tokens_share` в policy сейчас задаёт долю токен‑бюджета на модуль. Для более тонкого распределения по тегам/скоупам потребуется расширить модель policy и учёт тегов при отборе чанков.

## UI/Backend (FastAPI + React)
1. JS-зависимости: `cd ui && npm install`.
   - Требуется Node.js LTS 20.x (см. `.nvmrc`). Рекомендуется `nvm use 20.17.0` перед установкой и тестами, иначе Vitest зависает на Node 22.
2. Локальный запуск:
   - Backend: `uvicorn api.main:app --reload --port 8900`
   - Frontend: `cd ui && npm run dev` (http://127.0.0.1:5173)
3. Билд: `npm run build` (статические файлы окажутся в `api/static` и будут раздаваться FastAPI).
4. При необходимости можно задать `VITE_API_BASE` (по умолчанию `http://127.0.0.1:8900`) для фронтенда.
5. Тесты фронтенда: `cd ui && npm run test:ci` (использует Vitest с `pool=forks` и отключённым параллелизмом, чтобы избежать утечек процессов на Windows). Для локальной отладки допустим `npm run test`, но в CI рекомендуется `test:ci`.
- Background Jobs: чтобы избежать «зombie»-процессов Vitest/uvicorn, задайте переменные окружения `MCP_BG_JOB_TIMEOUT=900` и `MCP_BG_MAX_JOBS=8`, либо вручную завершайте job’ы старше 15 минут через `/jobs`. Health страница отображает сводку по job’ам.

## Continuous Integration (CI)
- Workflow: `.github/workflows/ci.yml` запускается на `push`/`pull_request` в ветках `main`/`master`.
- Backend job:
  - Python 3.12, установка зависимостей из `requirements.txt`, запуск `python -m pytest`.
- Frontend job:
  - Node 20 (LTS), `npm ci`, запуск `npm run test:ci`.
  - Vitest настроен на `happy-dom`, `pool=forks`, без параллельного запуска файлов и с таймаутами, чтобы исключить залипания процессов.
- Локально можно эмулировать CI:
  - Backend: `python -m pytest`
  - Frontend: `cd ui && nvm use 20.17.0 && npm ci && npm run test:ci`

## Post‑Deploy Checklist
- API/Health:
  - `GET /healthz` → `{"status":"ok"}`
  - `GET /health/index?project=context_engine` → метрики + блок `jobs` (total, by_status, latest)
- Plans/Streaming:
  - `GET /plans?limit=5&project=context_engine` возвращает свежие планы
  - `GET /plans/stream` (SSE) обновляет ленту каждые 1–2 сек
- Jobs:
  - `GET /jobs` список фоновых задач; по клику в UI открывается лог последнего job’а
- UI:
  - Live Plans — отображает последние планы
  - Explain — принимает `?plan=<plan_id>`, кнопки Copy/Open Live Plans доступны
  - Index Health — карточки + бар‑диаграммы doc kinds/symbol kinds
  - Graph Preview — загрузка и экспорт PNG/SVG
  - Quick Tools — `get_context` показывает `plan_id` и ссылку «Открыть в Explain»
- Background Jobs параметры заданы (рекомендуется): `MCP_BG_JOB_TIMEOUT=900`, `MCP_BG_MAX_JOBS=8`
- Explain Viewer теперь поддерживает мгновенный `get_context` rerun с историей параметров, Live Plans стримит через SSE, Graph Preview умеет экспортировать PNG/SVG, Quick Tools отображают идентификаторы созданных планов/джобов, а страница Jobs показывает логи и статус фоновых процессов.

## Роли read-only для UI
```sql
-- Postgres
CREATE ROLE context_ui_ro LOGIN PASSWORD 'context_ui_ro';
GRANT CONNECT ON DATABASE codex TO context_ui_ro;
GRANT USAGE ON SCHEMA public TO context_ui_ro;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO context_ui_ro;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO context_ui_ro;

-- Neo4j (в cypher-shell)
CREATE USER context_ui_ro SET PASSWORD 'context_ui_ro' CHANGE NOT REQUIRED;
GRANT ROLE reader TO context_ui_ro;
```
Затем пропишите DSN/учётки в `.env` (переменные `PG_DSN_RO`, `NEO4J_USER_RO`, `NEO4J_PASS_RO`) и при необходимости обновите `api/deps.py`.

## Хаускипинг (что хранить в репозитории)
- Код, схемы, SQL/Cypher миграции, UI‑источники и документация (`docs/`, `schemas/`, `tools/`, `core/`, `api/`, `ui/`).
- Не коммитим окружения и артефакты: `node-v*-win-x64/`, `node_modules/`, `.venv/`, `.pgdata/`, `logs/`, кеши тестов/buildов, локальные данных Neo4j/Postgres.
- Для Node используйте `nvm use 20.17.0` (см. `.nvmrc`) вместо вложения бинарей в репо; при необходимости больших артефактов — только через Git LFS.
- Индексация: запускайте `python manage.py ingest --project <proj> --prune` (или `tools/index_repo.py --prune`) после изменений кода/доков, чтобы база очищалась от устаревших файлов.
- Перед пушем проверяйте `git status` и размер файлов (`git ls-tree -r HEAD --long | sort -k4 -n | tail`) — не должно быть бинарей >50 MB.
