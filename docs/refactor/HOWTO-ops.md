# HOWTO: эксплуатация и проверки (Wave 5)

Быстрая шпаргалка по работе с пайплайнами и проверками после рефакторинга.

## CLI (manage.py)
- Индексировать репозиторий: `python manage.py ingest --project <project>`
- Построить граф: `python manage.py build-graph --project <project> [--dry-run]`
- Health-check (PG/Neo4j/Backend без MCP): `python manage.py health-check --project <project>`

## MCP инструменты (mcp/server.py)
- Контекст: `get_context` (обязателен `task`, опционально `project`, `token_budget`, `max_*`).
- Сырый поиск: `search_raw` (code/doc/both).
- Джобы: `ingest`, `graphify`, `index_repo` — запускают фоновые процессы, см. `logs/jobs/*.log`.
- Feedback: `pin` / `forget` (`project`, `uri`, `task`).
- Explain: `explain_plan` (последний или по `plan_id`).
- Инвариант: данные остаются доступными, политика только смещает приоритеты; скрытие возможно только через `sensitive`.

### get_context / Explain
- Пример вызова (stdio JSON-RPC): `{"method":"tools/call","params":{"name":"get_context","arguments":{"task":"add auth","project":"context_engine","token_budget":8000}}}`.
- `explain.data_route` — что нашёл data-layer (candidates, modules_base, graph_stats).
- `explain.policy_route` — какие routing-правила сработали, какие feedback-эффекты учтены, какие URI/модули отфильтрованы как sensitive.
- `explain.selection` — финальные модули/чанки после policy и budget.
- Инварианты: при пустой policy/feedback результат детерминирован; policy не создаёт/не скрывает данные без явных sensitive; `max_tokens_share` ограничивает долю бюджета на модуль.

## Admin UI (ui/)
- Установка зависимостей один раз: `npm install`.
- Dev-режим: `npm run dev -- --host` (порт по умолчанию 5173).
- В UI есть selector `project`; страницы: Health, Jobs, Plans/Explain, Config/Policy.
- Backend API, которое дергает UI: `/api/admin/health`, `/api/admin/jobs`, `/api/admin/plans`, `/api/admin/plans/{id}`, `/api/admin/config`.

## Что проверять после изменений
- Пустая policy/feedback => детерминированное поведение `get_context` (score сортировка, нет скрытых данных).
- Sensitive-правила — единственный способ убрать артефакт при наличии данных.
- routing/feedback-config валидируется через `PolicyLoader` (TTL, checksum), правила с ошибками не ломают обработку.
