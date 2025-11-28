Context Engine MCP
==================

Что это
- MCP‑совместимый сервер, возвращающий минимально достаточный контекст (кодовые чанки, доковые чанки, подграф) по тексту задачи.
- Детерминированный ответ: `status` всегда `ok` или `down` с указанием компонента и плана.
- Используется гибридный ретривер (вектор + BM25), граф в Neo4j и хранилище чанков/фидбека в Postgres.

Структура репозитория (кратко)
- `config/engine.yml` — дефолты ретривера/маршрутизации; `config/policy.yml` — правила policy.
- `core/` — конфиг‑лоадер, retrieval/merger/graph, подсчёт токенов, политика.
- `mcp/server.py` — MCP сервер (stdio) с инструментами `get_context`, `search_raw`, `ingest`, `graphify`, `index_repo`, `pin`, `forget`, `explain_plan`.
- `jobs/` — cli-обёртки для ingest/graphify/index_repo.
- `api/` — FastAPI backend для UI (health/plans/graph/tools/jobs/config/schema/root) и отдача статики `api/static`.
- `ui/` — React/Vite фронтенд (Node 20 LTS).
- `schemas/sql` / `schemas/cypher` — миграции Postgres/Neo4j.

Текущее окружение (факты)
- Python 3.12+; виртуальное окружение в `.venv` (не коммитить).
- Postgres: локальный кластер в `./.pgdata`, порт `5433`, DSN `postgres://codex:codex@127.0.0.1:5433/codex`. Бинарь из Scoop `postgresql16`.
  - Старт: `set "pg=%USERPROFILE%\\scoop\\apps\\postgresql16\\current"` затем `%pg%\\bin\\pg_ctl.exe -D ".\\.pgdata" -l ".\\.pgdata\\postgres.log" -o "-p 5433" start`
  - Стоп: `%pg%\\bin\\pg_ctl.exe -D ".\\.pgdata" stop -m fast`
- Neo4j: доступен на `bolt://127.0.0.1:7687`, учетные данные `neo4j/codex1234` (убедитесь, что служба запущена).
- Переменные окружения: см. `.env` (не коммитить). Минимум `OPENAI_API_KEY`, `PG_DSN`/`PG_DSN_RO`, `NEO4J_URI`/`NEO4J_USER`/`NEO4J_PASS`.
- Docker Compose сейчас не используется (`docker-compose.yml` оставлен только как пример; каталоги `_data/*` отсутствуют).

Запуск и проверки
- MCP сервер (stdio): `python mcp/server.py`.
- Ингест/граф: `python manage.py ingest --project context_engine`, `python manage.py build-graph --project context_engine --dry-run` / без `--dry-run` для записи.
- Health CLI: `python manage.py health-check --project context_engine` (проверяет Postgres/Neo4j/backend_api).
- Тесты backend: `python -m pytest`.
- Backend UI: `uvicorn api.main:app --reload --port 8900`.
- Frontend UI: `cd ui && nvm use 20.17.0 && npm install && npm run dev` (по умолчанию API `http://127.0.0.1:8900`).

Работа с MCP инструментами
- Основные: `get_context` (контекст задачи), `search_raw` (гибридный поиск), `ingest`/`graphify`/`index_repo` (фоновые джобы), `pin`/`forget` (фидбек), `explain_plan` (последний план).
- Если Postgres/Neo4j недоступны, инструменты вернут `status="down"` с деталями.

Обслуживание и чистка
- Рабочие артефакты: `.pgdata/`, `.venv/`, `logs/` (оставлять каталог), `.env`.
- Мусор, удалённый из репозитория: `_build/pgvector/`, временные `tmp_*`/`_check_yaml.py`/`_import_server.py`, кеши `.pytest_cache/`, `__pycache__/`.
- Для чистки кешей: удалить `__pycache__/`, `.pytest_cache/`, содержимое `logs/`; не трогать `.pgdata/`, если используется текущий кластер на 5433.

Полезное
- `docs/PROJECT_BRIEF.md` — краткий бриф о цели системы.
- `config/engine.yml` — дефолты ретривера; при изменениях прогоняйте ingest/graph.
- Логи MCP/джобов: `logs/` и `logs/jobs/` (создаются автоматически). При росте размера — очищайте содержимое, каталоги оставляйте.
