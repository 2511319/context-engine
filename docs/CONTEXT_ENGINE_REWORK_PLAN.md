# Context Engine — План доведения до «продготовности»

## 1. Текущее состояние

- **MCP‑слой** — реализован полный MCP-wire (initialize/tools/call) и обновлён `get_context`: поддерживаются переопределения retrieval mode/weights/candidates и token budget, а все фоновые операции (`ingest`, `graphify`, `index_repo`) запускаются как jobs с логированием в `plan_log` и файловый сторедж (`mcp/server.py`, `jobs/run_*.py`).
- **Наблюдаемость плана** — `plan_log` расширен, backend `/plans`/`/plan/{id}`/`/plans/export`/`/plans/stream` возвращают полный payload, а UI (Live Plans + Explain) визуализируют latency, token budget, источники и артефакты.
- **Мультипроектность** — MCP, backend и UI работают с параметром `project`: в шапке приложения есть селектор, все страницы и SSE/REST‑вызовы фильтруют данные по проекту, а `/jobs` и `/plans` принимают соответствующий query‑параметр.
- **UI‑функциональность** — реализованы страницы Live Plans, Explain (с диаграммами, экспортом JSON/CSV и панелью rerun get_context), Graph Preview (экспорт PNG/SVG, подсказки), Index Health (метрики по индексам), Quick Tools (вызовы MCP‑тулов + ссылки на jobs), Jobs (просмотр фоновых задач и логов).
- **Тесты** — существуют базовые pytest‑тесты для REST‑эндпоинтов (`tests/api/*`) и vitest smoke‑тест для Live Plans.
- **Документация/онбординг** — исходные ONBOARDING/README покрывают установку, но ещё не отражают последние изменения (live‑панель Explain, мультипроектность, экспорт графов и т. д.).

## 2. Основные пробелы (обновлено)

1. **Health/Backend производительность**  
   - Кэш health‑метрик внедрён (TTL 30с). Read‑only роли/health‑checks в проде — в работе по инфраструктуре.  
   - В `/health/index` добавлена статистика по background‑jobs.

2. **Index Health и аналитика**  
   - Базовые визуализации добавлены (Doc kinds / Symbol kinds). Near‑dup и CTR‑графики — в следующую очередь.

3. **Тестовое покрытие**  
   - Pytest покрывает API/health; для UI добавлен smoke и стабилизация окружения (happy‑dom, forks). Интеграции MCP и дополнительные RTL‑тесты — в очереди.

4. **Документация/репорты**  
   - README/ONBOARDING частично обновлены (Node 20, test:ci, Jobs). Требуется синхронизация текущего документа с чек‑листом.

5. **Мониторинг и CI**  
   - CI добавлен (pytest + vitest, Node 20, Ubuntu). Мониторинг `/metrics` — опциональная задача.

6. **Стабильность UI при переключении проекта**  
   - Explain очищает состояние и поддерживает предвыбор плана через `?plan=...`.

7. **Гигиена логов/UX**  
   - Quick Tools отображает `plan_id` для `get_context` и даёт переход в Explain. В Explain добавлены быстрые действия (Copy plan_id / Open Live Plans).

## 3. План завершения (по приоритетам)

### 3.1. Наблюдаемость и производительность
1. [done] Ввести кэш health‑метрик (TTL 30–60 с) и параметры конфигурации read-only DSN/health‑checks.  
2. [done] Добавить background‑job статистику в `/health` (количество jobs, последние ошибки).  
3. [done] Обновить ONBOARDING3 описанием health‑контуров и Jobs.

### 3.2. UI‑аналитика и Explain
1. [partial] Расширить Index Health: добавлены диаграммы doc kind/symbol kind. Near‑dup/CTR остаются.  
2. [partial] В Explain Viewer:
   - [done] Быстрые действия (Copy plan_id, Open Live Plans).  
   - [done] Переход из Quick Tools в Explain с `?plan=`.  
   - [done] Переключение retrieval mode с подсказками влияния.  
3. [done] Документировать live‑панель и Jobs в README/ONBOARDING3.

### 3.3. Тесты и документация
1. [todo] Pytest интеграции MCP (ok/down, feedback, jobs).  
2. [partial] RTL тесты: smoke есть; для Explain/Graph/Quick Tools/Jobs — добавить после стабилизации окружения, CI уже готов.  
3. [done] README/ONBOARDING обновлены (Node20/test:ci/Jobs). Этот документ синхронизирован частично — см. отметки выше.

### 3.4. Мониторинг и CI
1. [done] CI добавлен (pytest + vitest `test:ci`).  
2. [opt] Подготовить plan log/job метрики для Prometheus (или pseudo‑эндпоинт `/metrics`).  
3. [done] Чек‑лист пост‑деплоя (health, jobs, SSE) — добавлен в README.

### 3.5. UX‑полировка
1. Сбрасывать выбранный план в Explain при смене проекта/ошибке 404.  
2. В истории rerun хранить не только summary, но и ссылку на сохранённые параметры (например, `payloadId` или экспорты JSON).  
3. На Quick Tools отображать результат rerun (plan/job id) и давать кнопки перехода.

## 4. Ожидаемый результат

После выполнения шагов из раздела 3:
- Context Engine предоставляет детерминированный `get_context` с live‑настройками из UI, а Explain Viewer становится главным центром диагностики (графики, история rerun, экспорт).
- Health/Graph/Jobs страницы отражают мультипроектное состояние без просадок производительности.
- Тесты покрывают ключевые сценарии (REST + MCP + UI), документация описывает все новые возможности, а CI/мониторинг гарантируют повторяемость.

Этот документ обновляет исходный rework‑план и служит чек‑листом для финализации проекта. После завершения пунктов 3.1–3.5 система может считаться «продготовной».
