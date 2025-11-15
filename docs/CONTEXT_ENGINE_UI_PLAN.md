# Context Engine UI — План реализации

## Структура проекта

```
context_engine/
├── api/                      # backend (FastAPI)
│   ├── main.py               # точка входа FastAPI + uvicorn
│   ├── deps.py               # настройки (DSN, пути, MCP адаптер)
│   ├── adapters/
│   │   ├── mcp.py            # клиент к context-engine MCP (subprocess/stdio)
│   │   ├── postgres.py       # read-only PG клиент
│   │   └── neo4j.py          # read-only Neo4j клиент
│   ├── services/
│   │   ├── plans.py          # чтение plan_log, explain, SSE поток
│   │   ├── health.py         # метрики code/docs/symbols/feedback
│   │   ├── graph.py          # подграфы и статистика Neo4j
│   │   ├── schema.py         # список таблиц/индексов
│   │   └── config.py         # чтение engine.yml + diff
│   ├── routers/
│   │   ├── plans.py          # /plans, /plan/{id}, /plans/stream
│   │   ├── graph.py          # /graph, /graph/stats
│   │   ├── health.py         # /health/indexes, /health/feedback
│   │   ├── schema.py         # /db/schema, /db/table/{name}
│   │   ├── config.py         # /config
│   │   └── tools.py          # /tools/{ingest|search_raw|pin|forget|explain_plan}
│   ├── models/               # Pydantic DTO (Plan, Artifact, GraphNode, ...)
│   └── static/               # билд фронтенда (React) после `npm run build`
│
└── ui/                       # фронтенд (React + Vite + TypeScript)
    ├── src/
    │   ├── api/              # hooks (React Query) для REST/SSE
    │   ├── components/       # таблицы, граф, charts, diff
    │   ├── pages/
    │   │   ├── LivePlans.tsx
    │   │   ├── Explain.tsx
    │   │   ├── GraphPreview.tsx
    │   │   ├── IndexHealth.tsx
    │   │   ├── QuickTools.tsx
    │   │   └── Config.tsx
    │   ├── router.tsx        # React Router
    │   └── main.tsx          # точка входа
    ├── package.json, vite.config.ts, tsconfig.json
    └── public/
```

## Список задач

- [x] **Инфраструктура проекта**
  - Создана директория `api/`, добавлены зависимости (`FastAPI`, `uvicorn`, `psycopg[binary]`, `neo4j-driver`, `pydantic-settings` и т. д.).
  - Инициализирован `ui/` (React + Vite + TypeScript + React Query + MUI/Recharts + react-force-graph).

- [x] **MCP адаптер**
  - `api/adapters/mcp.py` реализует persistent subprocess `python mcp/server.py` и последовательные JSON RPC вызовы.

- [x] **Read-only клиенты БД**
  - Построены вспомогательные адаптеры Postgres/Neo4j (read-only DSN/credentials).

- [x] **Сервис и роуты Live Plans**
  - `PlanService` читает `plan_log`, REST `/plans`, `/plans/stream` (SSE).

- [x] **Explain Viewer API**
  - Используем MCP `explain_plan` (через `/tools/explain_plan`), отдаём payload.

- [x] **Graph Preview API**
  - `/graph` и `/graph/stats` возвращают nodes/edges и агрегаты.

- [x] **Index Health + Schema Browser**
  - `/health/index`, `/db/schema`, `/db/table/{name}` реализованы.

- [x] **Quick Tools**
  - REST обёртки `/tools/ingest`, `/tools/search_raw`, `/tools/pin`, `/tools/forget`, `/tools/explain_plan`.

- [x] **Config viewer**
  - Endpoint `/config` отдаёт активный `engine.yml`, checksum и TTL.

- [x] **Frontend реализация**
  - Базовая навигация + страницы Live Plans, Explain, Graph, Health, Quick Tools, Config (React Query + MUI).

- [x] **Автозапуск MCP**
  - Скрипт `scripts/start_context_engine_mcp.ps1` для старта MCP при логине.

- [x] **Документация**
  - README/ONBOARDING2 обновлены (UI, автозапуск).

- [x] **Тесты**
  - Добавлены базовые pytest-тесты для API-роутов (`tests/api/*`) и vitest/RTL- smoke тест для LivePlans. При дальнейшем развитии покрытие можно расширять.

Документ обновляется по мере выполнения задач.
