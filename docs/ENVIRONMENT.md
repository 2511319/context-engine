# Актуальное окружение

## База данных
- Локальный кластер Postgres в `./.pgdata`, порт `5433`, DSN `postgres://codex:codex@127.0.0.1:5433/codex`.
- Бинарь: `postgresql16` (Scoop). Старт: `set "pg=%USERPROFILE%\\scoop\\apps\\postgresql16\\current"` затем `%pg%\\bin\\pg_ctl.exe -D ".\\.pgdata" -l ".\\.pgdata\\postgres.log" -o "-p 5433" start`. Стоп: `%pg%\\bin\\pg_ctl.exe -D ".\\.pgdata" stop -m fast`.
- При смене порта/кластера — обновить `.env` и прогнать `manage.py health-check --project context_engine`.

## Neo4j
- Доступен на `bolt://127.0.0.1:7687`, пользователь `neo4j`, пароль `codex1234`.
- Убедитесь, что служба запущена перед `ingest/build-graph/get_context`.

## Переменные окружения
- Использовать `.env` (не коммитить). Минимум: `OPENAI_API_KEY`, `PG_DSN`, `PG_DSN_RO`, `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASS`.
- Пример — `.env.example` (отличие от боевого: порт 5433 и учётки ro при необходимости).

## Запуск и проверки
- MCP сервер (stdio): `python mcp/server.py`.
- Ингест/граф: `python manage.py ingest --project context_engine`; `python manage.py build-graph --project context_engine --dry-run` / без `--dry-run`.
- Health: `python manage.py health-check --project context_engine`.
- Тесты backend: `python -m pytest`.
- Backend UI: `uvicorn api.main:app --reload --port 8900`.
- Frontend UI: `cd ui && nvm use 20.17.0 && npm install && npm run dev`.

## Обслуживание
- Рабочие каталоги: `.pgdata/`, `.venv/`, `logs/`, `.env`.
- Мусор, удалённый из репозитория: `_build/pgvector/`, временные `tmp_*`, `_check_yaml.py`, `_import_server.py`, кеши `.pytest_cache/`, `__pycache__/`.
- Для очистки логов: удалить содержимое `logs/`, оставить каталог.
