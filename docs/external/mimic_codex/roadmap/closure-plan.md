# План закрытия до 100%

Этот документ фиксирует стратегию доведения модулей, эпох и глав до полного (100%) состояния. Используйте чекбоксы для отслеживания прогресса. Lean‑подход к тестам сохраняется: обязательны контракты/golden/smoke, а глубокие unit‑тесты добавляются только для стабилизированных интерфейсов.

---

## Срез состояния (на 2025‑10‑31)

- Готово в коде:
  - Контракты JSON Schema и golden‑проверки: `contracts/jsonschema/*`, `qa/tests/test_goldens.py` (покрывает Scene/Media schemas).
  - Spectral‑линт OpenAPI: шаг в CI (WebApp job) и правила `.spectral.yaml`.
  - Базовый CI: `pytest + ruff + mypy` для Python, `eslint + e2e (Playwright)` для WebApp.
  - Gateway API: `/config`, `/health`, `/v1/generation/*`, `/v1/knowledge/search` реализованы; единый формат ошибок; in‑app rate‑limit доступен (по умолчанию выключен).
  - Genlayers: JSON Schema‑валидация и ретраи; OpenAI Responses провайдер поддерживает structured outputs.
  - Memory37: ingest YAML (scenes/npcs/art), HybridRetriever, CLI `ingest-file/search` (dry‑run).
  - Party Sync: WebSocket + REST broadcast; история/лимиты подключений.
  - Media Broker: очередь image‑job → `succeeded`; smoke‑скрипт закрывает happy‑path.
  - Observability: включаемые через ENV OpenTelemetry и Prometheus `/metrics`; traceId в `/config` и логах.
- Осталось довести для вертикального среза:
  - Ingest домена `lore` в Memory37 + тест.
  - Закреплённый контент‑пак кампании `ashen_moon_arc.yaml` и README по формату.
  - CI‑валидация контента (ingest dry‑run + YAML lint) отдельным job.
  - UX строки/состояния в файлы `docs/ux/strings.*` и `docs/ux/states.md`.
  - Пример правил Prometheus и runbook поставки контента; базовые SLO/дашборды с последующей калибровкой.

## Приоритет модулей (сверху вниз)

1. Контракты/Схемы (источник истины)
2. Gateway API (краевая грань)
3. WebApp (UX)
4. Genlayers + Memory37
5. Party Sync (WS)
6. Media Broker
7. Наблюдаемость/Безопасность/Процессы (CI/CD, SLO)

---

## Эпохи → Deliverables + DoD

- [x] Эпоха 0: Фундамент
  - [x] Включить Spectral в CI (OpenAPI/JSON Schema линт)
  - [ ] Golden/contract‑тесты зелёные (qa/tests, packages/*/tests) — тесты есть, подтвердить прохождение в CI
  - [x] CI базовый: pytest + ruff + mypy + npm lint
  - DoD: PR‑проверки зелёные, документация запуска актуальна

- [ ] Эпоха 1: Вертикальный срез
  - [x] Gateway: `/v1/auth/telegram`, `/v1/generation/*`, `/v1/knowledge/search`, `/config` стабилизированы; единый формат ошибок
  - [ ] WebApp: статус через `/config`, фичи Generation/Media/Party отполированы (loading/error/empty) — строки вынести в `docs/ux/strings.*`
  - [x] Genlayers/Memory37: профили/схемы закреплены; dev‑ingest YAML по умолчанию; ДОБАВЛЕН ingest `lore` + тест
  - [x] Party Sync: WS + REST broadcast; история/лимиты
  - [x] Media Broker: enqueue→succeeded (`image`), идемпотентность (минимум)
  - [x] CI: контент‑валидация (`ingest-file --dry-run`) для кампании
  - DoD: `tools/smoke.py` и UI‑runbook проходят целиком; `/v1/knowledge/search` возвращает элементы доменов `scene|npc|art|lore`

- [ ] Эпоха 2: Операции/Масштаб/Стоимость
  - [x] Метрики/трейсинг (включаемые через ENV); ДОБАВЛЕНЫ правила Prometheus `observability/prometheus/rules/*.yaml`
  - [ ] Дашборды p95/p99, error‑rate; SLO/алерты (мягкие пороги → калибровка по метрикам 1–2 недели)
  - [ ] Включить rate‑limit для тяжёлых маршрутов (`generation`, `knowledge`) в dev/staging; опционально circuit‑breaker
  - [ ] Media: back‑pressure, кэш, прототип CDN
  - [ ] Стоимость OpenAI: отчёт/квоты/лимиты
  - DoD: дашборды активны, правила алертов задеплоены, деградация управляемая

- [ ] Эпоха 3: Продуктизация/Доставка
  - [ ] Semantic release + CHANGELOG
  - [ ] Docker build/push; auto‑deploy staging (Blue‑Green)
  - [ ] Базовые операторские действия (health‑дашборд/перезапуск воркеров/очереди)
  - DoD: релизная цепочка от PR до staging полностью автоматизирована

---

## Главы 1–10 → Закрытие

- [ ] Гл.1 Геймдизайн & Концепт: тон‑гайд, безопасные темы в UI
- [ ] Гл.2 UX‑флоу & Навигация: единые состояния и навигация; ВЫНЕСТИ строки/состояния в `docs/ux/*`
- [ ] Гл.3 Системный дизайн: SPI/плагины документированы, альт‑провайдер подключаем конфигом
- [x] Гл.4 Контракты: Spectral в CI; backward‑compat policy (минимум) — правила применяются в WebApp job
- [ ] Гл.5 Данные/Медиа: миграции pgvector; CDN прототип; ETL/ingest путь; ДОБАВИТЬ ingest `lore`
- [ ] Гл.6 Операции/Безопасность/Деплой: метрики/трейсинг/дашборды; CI/CD workflows; секреты; ДОБАВИТЬ правила алертов и runbook
- [x] Гл.7 Методология: trunk‑based, pre‑commit, PR‑чек‑лист (каркас соблюдён)
- [ ] Гл.8 Память37: домены/фильтры/индексы; производительность поиска — расширить под `lore`
- [x] Гл.9 Генеративные слои: валидация/ретраи реализованы в genlayers; финализация профилей и политик — на базе текущего формата `profiles.yaml`
- [ ] Гл.10 Рекомендации: semantic‑release, CHANGELOG, ADR

---

## Инкрементальный чеклист задач (выполняем по порядку)

- [ ] Memory37: добавить домен `lore` в ingest (`packages/memory37/src/memory37/ingest.py`) + тест `packages/memory37/tests/test_ingest_lore.py`
- [ ] Контент: `data/knowledge/campaigns/ashen_moon_arc.yaml` (≥5 сцен, ≥3 NPC, ≥3 art, ≥5 lore) + `data/knowledge/README.md`
- [ ] CI: job `content-validate` — ingest dry‑run (`python -m memory37.cli ingest-file ... --dry-run`) + YAML lint
- [ ] WebApp: UX‑состояния и строки в `docs/ux/strings.*`, `docs/ux/states.md`; e2e smoke Generation/Media/Party
- [ ] Observability: добавить `observability/prometheus/rules/app-rules.yaml`; включить `/metrics` через ENV; базовые дашборды p95/p99, error‑rate
- [ ] Rate‑limit/Circuit‑breaker: включить для `generation` и `knowledge` в dev/staging
- [ ] Media Broker: back‑pressure, кэш/стратегии, CDN прототип
- [ ] Semantic‑release + CHANGELOG; релизные роли
- [ ] Auto‑deploy staging (Blue‑Green) в CI

---

## Политика тестирования (Lean)

- Обязательные гейты: контракты+golden, smoke (CLI+UI)
- Unit‑тесты добавляются для стабилизированных публичных интерфейсов

## Примечания

- TraceId и `/config` реализованы во всех сервисах
- In‑app rate‑limit доступен и выключен по умолчанию (dev/staging)
- Smoke‑наборы: `tools/smoke.py`, `docs/runbooks/ui-smoke.md`, `docs/runbooks/smoke-tests.md`

---

## Источники истины (для PR/ревью)

- JSON Schema Draft 2020‑12 — json‑schema.org (просмотрено 2025‑10‑31 18:36 UTC)
- Prometheus Alerting Rules — prometheus.io (просмотрено 2025‑10‑31 18:36 UTC)
- OpenTelemetry документация — opentelemetry.io (просмотрено 2025‑10‑31 18:36 UTC)
- Telegram Mini Apps (Web Apps) — core.telegram.org (просмотрено 2025‑10‑31 18:36 UTC)
- C2PA / Content Credentials — c2pa.org (просмотрено 2025‑10‑31 18:36 UTC)
- OpenAI Responses API Structured Outputs — platform.openai.com (источник ограничен/403; требуется разрешённый доступ)
