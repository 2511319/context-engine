Назначение: локальный read-only веб-интерфейс для наблюдаемости и отладки работы context-engine-MCP. Панель не заменяет СУБД-UI: Neo4j Browser и pgAdmin используются как штатные интерфейсы для графа и Postgres.

1. Рамки и цели

Показ «как и почему» движок собрал контекст: планы ретрива, веса, источники, подграфы, объёмы.

Быстрый доступ к базовым операциям через обёртки MCP-тулов: ingest, search_raw, pin, forget, explain_plan.

Read-only к БД (Postgres/Neo4j). Любая модификация — только через MCP-тулы.

Локальный доступ (127.0.0.1). Без внешней аутентификации.

2. Архитектура

UI-backend: FastAPI (Python 3.11+). Порты: 127.0.0.1:8900.

UI-frontend: React + Vite (SPA). Статика раздаётся FastAPI.

Связи:

Чтение JSONL-логов context-engine из ./logs/context-engine.log.

Read-only подключения: Postgres (pgvector), Neo4j (Bolt).

Вызов MCP-тулов — через локальный адаптер (subprocess/stdio) к context-engine-MCP.

Контейнеры docker-compose (дополнение к существующим):
pgadmin (порт 5050), context-engine-ui (порт 8900). Neo4j Browser уже доступен на 7474.

3. Страницы UI
3.1. Live Plans

Цель: поток последних планов ретрива.

Таблица: time, plan_id, project, module, status(ok/down), latency_ms, code/docs count, source_latencies.{pg,neo4j}.

Автообновление (SSE/WebSocket) каждые 2 сек.

Клик по строке → переход в Explain Viewer.

3.2. Explain Viewer

Цель: детальный разбор одного плана.

Поля: plan_id, route, params (включая graph_depth, max_code_chunks, max_doc_chunks, retrieval.mode/weights/rerank), config_version, config_checksum.

Две вкладки:

Retrieval: top-K vector (dist/score), top-K BM25 (rank/score), объединение, dedup, итоговые веса, token-budget.

Artifacts: списки code[]/docs[] с path/doc, uri, commit_sha, chunk_id, fp_sha256 (контент скрыт по умолчанию, раскрывается по клику).

3.3. Graph Preview

Цель: визуализация подграфа, который был отдан в ответ.

Параметры: project, module, depth (по умолчанию 3).

Рёбра: IMPLEMENTS, DESCRIBED_IN, APPLIES_TO, BEST_ACCESSED_VIA.

Интерактив: наведение → метаданные узла; экспорт в PNG/SVG.

3.4. Index Health

Цель: состояние индексов и качество базы.

Метрики:

code_chunks: count, средний/медианный размер чанка, дубликаты по fp_sha256, near-dup %, доля без module.

doc_chunks: аналогично.

symbols/symbol_refs: count, распределение по видам (class/func/router/...).

dp_edge: распределение по типам IMPORTS/REFERENCES/DESCRIBED_IN/IMPLEMENTS.

feedback: количество pin/forget, CTR позитива.

Визуализации: мини-карточки + бары.

3.5. Quick Tools

Цель: запуск MCP-тулов из UI.

Формы:

ingest(project)

search_raw(project, query, scope, k) — вывод top-результатов с оценками.

pin(project, uri) / forget(project, uri)

explain_plan(plan_id | last=true)

Все вызовы проходят через UI-backend → MCP адаптер (stdio) → возвращают JSON.

3.6. Config

Цель: видимость используемого конфига.

Показ текущей версии/хэша engine.yml, активных параметров ретрива и TTL горячей перезагрузки.

Diff с файлом на диске (read-only).

4. API UI-backend (HTTP)

Базовый URL: http://127.0.0.1:8900

4.1. Живые планы

GET /plans?limit=50 → [{time, plan_id, project, module, status, latency_ms, counts, source_latencies}]

GET /plan/{plan_id} → полный explain JSON (как вернул движок)

GET /plans/stream → SSE поток последних записей (1–2 сек интервал)

4.2. Граф

GET /graph?project=...&module=...&depth=3
Возвращает список узлов/рёбер для визуализации:
{"nodes":[{id,label,props}], "edges":[{source,target,type}]}

4.3. Здоровье индексов

GET /index/health?project=... → агрегаты по SQL (см. §7)

4.4. MCP-обёртки

POST /mcp/ingest → {project}

POST /mcp/search_raw → {project, query, scope, k}

POST /mcp/pin → {project, uri}

POST /mcp/forget → {project, uri}

GET /mcp/explain_plan?plan_id=...&last=true

Ошибки: единый формат — {"error": {"code": "<string>", "message": "<string>"}}

5. Чтение логов и формат JSONL

Файл: ./logs/context-engine.log

Формат строки (JSONL):

{
  "ts":"2025-11-06T13:45:12.345Z",
  "plan_id":"uuid-...",
  "project":"string",
  "module":"string",
  "status":"ok|down",
  "latency_ms": 432,
  "source_latencies": {"pg": 120, "neo4j": 55},
  "result_sizes": {"code": 8, "docs": 5},
  "route":"engine.yml: rule(...)",
  "params":{
    "max_code_chunks":8,
    "max_doc_chunks":5,
    "graph_depth":3,
    "retrieval":{"mode":"hybrid","weights":{"vector":0.7,"bm25":0.3},"rerank":false},
    "config_version":"v1.3",
    "config_checksum":"sha256:..."
  }
}


context-engine-UI должен: tail-ить файл, защищаться от ротации (reopen на ENOENT), игнорировать битые строки.

6. Интеграции СУБД-UI

Neo4j Browser (порт 7474) — используется для ручной работы с графом (Cypher).

pgAdmin (порт 5050) — для ручного просмотра/SQL в Postgres.

docker-compose фрагмент:

pgadmin:
  image: dpage/pgadmin4:latest
  ports: ["5050:80"]
  environment:
    PGADMIN_DEFAULT_EMAIL: admin@example.com
    PGADMIN_DEFAULT_PASSWORD: adminpass
  depends_on: [pg]

7. SQL-агрегаты для Index Health (must-have)

Дубликаты:

SELECT COUNT(*) AS dup_cnt
FROM (
  SELECT fp_sha256, COUNT(*) c
  FROM code_chunks
  WHERE project = $1
  GROUP BY fp_sha256
  HAVING COUNT(*) > 1
) t;


Near-dup (эмуляция, если внедрён MinHash): таблица near_dup(code_fp, similar_fp, jacc), иначе — пропустить метрику.

Распределение размеров:

SELECT
  COUNT(*) AS n,
  AVG(length(content)) AS avg_sz,
  PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY length(content)) AS p50,
  PERCENTILE_CONT(0.9) WITHIN GROUP (ORDER BY length(content)) AS p90
FROM code_chunks
WHERE project = $1;


Доля без module:

SELECT COUNT(*) FILTER (WHERE module IS NULL OR module='')::float / COUNT(*) AS ratio
FROM code_chunks
WHERE project = $1;


dp_edge по типам:

SELECT rel, COUNT(*) FROM dp_edge WHERE project = $1 GROUP BY rel ORDER BY COUNT(*) DESC;


feedback:

SELECT
  SUM(CASE WHEN label = 1 THEN 1 ELSE 0 END) AS pinned,
  SUM(CASE WHEN label = -1 THEN 1 ELSE 0 END) AS forgotten
FROM dp_feedback
WHERE project = $1;

8. Безопасность

UI-backend слушает только 127.0.0.1:8900.

Read-only доступ к БД: отдельный пользователь Postgres/Neo4j с правами SELECT/MATCH.

Любые изменения — только через MCP-тулы (вызовы из UI).

CORS выключен.

Файлы логов подключаются как read-only volume.

9. Переменные окружения

.env.example:

UI_HOST=127.0.0.1
UI_PORT=8900

PG_DSN=postgresql://ui_readonly:ui_readonly_pass@pg:5432/postgres
NEO4J_URI=bolt://neo4j:7687
NEO4J_USER=ui_readonly
NEO4J_PASS=ui_readonly_pass

LOG_PATH=./logs/context-engine.log
MCP_SERVER_BIN=python mcp/server.py                  # путь к исполняемому MCP-серверу
MCP_START_MODE=attach|spawn                          # attach к живому процессу или spawn на запрос

10. Нефункциональные требования

Латентность UI-API: p95 ≤ 150 мс для чтения планов/агрегатов; p95 ≤ 800 мс для графа depth=3.

Надёжность: обработка отсутствия логов (показывать «источник недоступен»), таймауты к БД ≤ 2 с.

Ресурсы: UI-backend ≤ 200 МБ RAM, CPU ≤ 1 vCPU при нормальной нагрузке.

11. Тестирование

Unit (backend): парсер JSONL, пагинация, SSE-поток, SQL-агрегаторы.
Интеграция:

Поднять docker-контур (pg, neo4j, context-engine, pgadmin, context-engine-ui).

Сгенерировать ≥ 50 планов (через вызовы MCP).

Проверить:

GET /plans возвращает последние записи, сортировка правильная;

GET /plan/{plan_id} совпадает с оригинальным explain;

GET /graph возвращает подграф;

GET /index/health — корректные агрегаты;

POST /mcp/ingest/pin/forget — отрабатывают и логируются.
Негатив:

Отсутствует файл логов → /plans отвечает 200 с пустым массивом и source:"missing".

Отключён Neo4j → /graph возвращает 503 с component:"neo4j".

Недоступен MCP-сервер → MCP-обёртки возвращают 502.

12. Критерии готовности (DoD)

UI доступен по http://127.0.0.1:8900, все страницы работают.

Все заявленные API-эндпоинты выдают корректные ответы.

MCP-обёртки корректно вызывают ingest/search_raw/pin/forget/explain_plan.

Read-only политика к БД соблюдается (верифицировано ролями).

pgAdmin на :5050, Neo4j Browser на :7474 доступны.

Логи читаются устойчиво, ротация не ломает Live Plans.

README содержит инструкции развёртывания и раздел «Как читать Explain».

13. Структура проекта (минимум)
ui/
  backend/
    app.py                 # FastAPI
    deps.py                # подключения к PG/Neo4j, MCP-адаптер
    routes/
      plans.py
      graph.py
      health.py
      mcp.py
    services/
      logs_tail.py
      graph_service.py
      health_service.py
      mcp_client.py
    models/
      schemas.py
  frontend/
    index.html
    src/
      main.tsx
      pages/{LivePlans,Explain,Graph,Health,Tools,Config}.tsx
      components/{Table,GraphView,Cards}.tsx
    vite.config.ts
Dockerfile

14. README (обязательные разделы)

Развёртывание (docker-compose), переменные окружения.

Доступ к pgAdmin/Neo4j Browser.

Описание страниц UI.

Справочник API UI.

Шпаргалки Cypher/SQL.

Диагностика: типовые ошибки и их причины.
