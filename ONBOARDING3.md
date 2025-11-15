# Context Engine MCP — Onboarding (UI Snapshot)

## 1. Текущее состояние (07.11.2025)
- **Репозиторий:** `D:\project\context_engine`.
- **Инфраструктура:**
  - PostgreSQL 16 (pgvector 0.8.1) — кластер `D:\infra\postgresql\cluster`, роль/БД `codex/codex`.
  - Neo4j 5.22 — `D:\infra\neo4j\server`, пользователь `neo4j/codex1234`.
  - MCP сервер `python mcp/server.py` поддерживает инструменты `get_context/search_raw/ingest/pin/forget/explain_plan`.
  - Автозапуск MCP: `scripts/start_context_engine_mcp.ps1 -ProjectRoot "D:\project\context_engine"` (ярлык в Startup).
- **Background Jobs:** рекомендуется выставить `MCP_BG_JOB_TIMEOUT=900` и `MCP_BG_MAX_JOBS=8`, чтобы зависшие Vitest/uvicorn не забивали пул. Страница Index Health показывает текущее состояние job’ов.
- **UI/Backend:**
  - FastAPI (`uvicorn api.main:app --reload --port 8900`), выдаёт API + статическую сборку React на `/ui`.
  - React/Vite (`cd ui && npm install && npm run dev`), страницы: Live Plans (SSE), Explain Viewer (scoring, token budget), Graph Preview (force graph + фильтры), Index Health, Quick Tools, Config.
  - `scripts/start_context_engine_stack.ps1` можно добавить в Startup — он поднимает MCP, uvicorn backend и опционально Vite dev server.
  - `.env` используется для MCP и backend; фронтенд может читать `VITE_API_BASE`.
  - Explain Viewer поддерживает rerun `get_context` с сохранением истории параметров, Graph Preview экспортирует PNG/SVG, Quick Tools показывают созданные `plan_id`/`job_id`, Jobs страница раскрывает логи фоновых задач.
- **Node.js:** LTS 20.x (см. `.nvmrc`, рекомендуем `nvm use 20.17.0`). На Node 22 Vitest залипает и оставляет процессы, поэтому CI/локальные тесты гоняем только под 20.
- **Тесты:** `python -m pytest` (6 тестов) и `cd ui && npm run test:ci` (Vitest + RTL smoke, `pool=forks`, без параллельного запуска файлов; избегает висящих процессов на Windows).

## 2. Как запустить
1. **Postgres/Neo4j:** запустите службы (см. README/ONBOARDING2). Проверить: `psql %PG_DSN% -c "SELECT 1"`, `cypher-shell -u neo4j -p codex1234 "RETURN 1"`.
2. **MCP:** убедитесь, что `scripts/start_context_engine_mcp.ps1` поднял сервер, либо вручную `python mcp/server.py`.
3. **Backend:** `uvicorn api.main:app --reload --port 8900`.
4. **Frontend:** `cd ui && npm install && npm run dev` (http://127.0.0.1:5173). Для production — `npm run build`, статика будет отдаваться FastAPI.
5. **Node:** перед установкой фронтенд-зависимостей выполните `nvm use 20.17.0` (либо установите Node 20.x любым способом). Скрипт `npm run test:ci` предполагает именно эту версию.

## 3. Полезные команды
```powershell
# Индексация/граф
python tools/index_repo.py --project context_engine
python tools/memify.py
python tools/graphify.py --project context_engine --dry-run
python tools/graphify.py --project context_engine

# Тесты
python -m pytest
cd ui && npm run test:ci
```

## 4. Следующие шаги
1. **MCP совместимость (приоритет №1):** обернуть `mcp/server.py` в полноценный MCP-протокол (initialize/handshake, объявление инструментов, обработка `call_tool`). До тех пор сервер не может использоваться как MCP-клиентом Codex.
2. **Explain Viewer:** добавить графики вкладов, историю feedback, экспорт JSON/CSV.
3. **Graph Preview:** улучшить раскраску/кластеризацию, экспорт снимков, подсказки для метаданных.
4. **UI-переключатели параметров:** добавить на отдельную панель слайдеры/селекторы для:
   - `max_code_chunks` / `max_doc_chunks` (глубина выдачи);
   - `graph_depth` / фильтров по типам рёбер;
   - `retrieval.weights` (vector vs BM25) и `candidates.vector_k/bm25_k`;
   - token budget (для временного расширения/сжатия);
   - коэффициентов feedback (PIN/forget bias).
   Каждая настройка должна сопровождаться описанием влияния на качество/производительность, но изменение допускается “на лету”, т.к. доступ к UI уже подразумевает максимальные права.
5. **Оптимизация backend:** рассмотреть read-only роли в Prod, добавить кэш health-метрик при росте объёмов.
6. **Тесты:** расширить React/RTL и pytest покрытия (особенно Explain/Graph/метрики).
7. **Документация:** при изменении инфраструктуры обновлять README/ONBOARDING3.

Этот документ фиксирует состояние перед паузой; далее можно продолжать по списку выше.
