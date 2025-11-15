# ТЗ (Dev) — Операционные метрики (SLO/алерты) и процесс поставки контента

Цель: определить и внедрить наблюдаемость (метрики/трейсинг) с целевыми SLO и алертингом, а также формализовать процесс поставки контента.

## Метрики и эндпоинты
- Экспорт Prometheus по всем сервисам: `/metrics` (включается через `ENABLE_METRICS=true`).
- Ключевые метрики (минимальный набор):
  - Gateway: `http_requests_total{method,path,status}`, `http_request_duration_seconds_bucket`, `generation_failures_total`.
  - Party Sync: `ws_connections_gauge`, `broadcast_events_total`, `broadcast_failures_total`.
  - Media Broker: `media_jobs_total{type,status}`, `media_queue_depth`, `media_processing_duration_seconds_bucket`.
  - Memory37 (на уровне приложения): `retrieval_queries_total`, `retrieval_latency_seconds_bucket`, `rerank_used_total`.
- Трейсинг OTEL (включение `ENABLE_OTEL=true`, `OTEL_EXPORTER_OTLP_ENDPOINT=http://<collector>:4318`).

## Целевые SLO (стартовые)
- Gateway `/v1/generation/*`: p95_latency ≤ 2.5s, error_rate ≤ 2% (5‑минутное окно).
- Party Sync broadcast: p95_end_to_end ≤ 250ms, delivery_success ≥ 99.5%.
- Media job end‑to‑end: p95_time_to_succeeded ≤ 5s (dev), ≤ 8s (staging), success_rate ≥ 98%.
- Knowledge search: p95_latency ≤ 120ms (in‑memory), ≤ 300ms (pgvector).

## Алертинг (правила)
- `HighErrorRate` Gateway: error_rate > 5% за 10 минут — page.
- `SlowGeneration` Gateway: p95_latency > 4s за 10 минут — warn.
- `WSDisconnected` Party: резкое падение `ws_connections_gauge` > 30% — warn.
- `MediaBacklog` Media: `media_queue_depth` > 50 за 5 минут — warn.

## Процесс поставки контента
- Формат кампании: `data/knowledge/campaigns/<campaign_id>.yaml` (см. ТЗ Dev 01) + артефакты (изображения/аудио) в `assets/<campaign_id>/...` (опционально для демо; для прод — через CDN, URL в ArtCard).
- Ветки и проверки:
  - PR с контентом запускает проверки: линт YAML (валидность), ingest dry‑run `python -m memory37.cli ingest-file data/knowledge/campaigns/<campaign_id>.yaml --dry-run`.
  - Автосборка docker‑образов с тегом `<campaign_id>-<short_sha>` при мерже в `main`.
- Деплой (staging):
  - Обновление переменной `KNOWLEDGE_SOURCE_PATH` на путь к новой YAML; smoke‑проверка `tools/smoke.py`.
- Документация: `docs/runbooks/content-delivery.md` — добавить пошаговое руководство (создать файл).

## Изменения в коде/инфраструктуре
- `/metrics` доступен во всех сервисах (Observability уже добавлен; включать через ENV).
- Добавить Prometheus rules/alerts примером в `observability/prometheus/rules/*.yaml` (см. ниже).
- В CI (GitHub Actions) для контента: job с `python -m memory37.cli ingest-file ... --dry-run`.

### Пример правил (`observability/prometheus/rules/app-rules.yaml`)
```yaml
groups:
  - name: rpg-app
    rules:
      - alert: HighErrorRateGateway
        expr: sum(rate(http_requests_total{status=~"5.."}[5m])) / sum(rate(http_requests_total[5m])) > 0.05
        for: 10m
        labels: { severity: page }
        annotations: { summary: "Gateway 5xx error_rate > 5% (10m)" }
      - alert: SlowGeneration
        expr: histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket{path=~"/v1/generation/.*"}[5m])) by (le)) > 4
        for: 10m
        labels: { severity: warn }
        annotations: { summary: "Generation p95 > 4s (10m)" }
      - alert: MediaBacklog
        expr: avg_over_time(media_queue_depth[5m]) > 50
        for: 5m
        labels: { severity: warn }
        annotations: { summary: "Media queue depth > 50 (5m)" }
```

## Что должен вернуть разработчик
- Файлы правил: `observability/prometheus/rules/app-rules.yaml` (как минимум — алерты из примера).
- CI‑job: правка `.github/workflows/ci.yml` (job `content-validate` с ingest dry‑run).
- Документация: `docs/runbooks/content-delivery.md` — как создавать/проверять/выкатывать контент.
 - «Источник истины»: в PR приложить ссылки на официальные разделы документации по Prometheus/OTel/Alerting (URL/дата просмотра), подтверждающие выбранные метрики и SLO.

## Приёмка (DoD)
- `/metrics` доступен на всех сервисах; правила алертов лежат в `observability/prometheus/rules/`.
- SLO зафиксированы в `docs/ops/slo.md` и отражены в правилах Prometheus.
- Контент‑пайплайн в CI валидирует YAML ingest; staging видит новый контент через `KNOWLEDGE_SOURCE_PATH`.
