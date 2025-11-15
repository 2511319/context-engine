# 6\. Операции: безопасность, наблюдаемость, QA и деплой — финальная редакция v1

Эта глава отвечает за то, **как игра остаётся безопасной, наблюдаемой и стабильно деплоится**. Ниже — полный практический стандарт: что делаем, зачем, где это живёт в репозитории и как проверяем. Выверено на индустриальных рекомендациях: валидация Telegram **initData**, **OWASP API Security Top-10 (2023)**, **W3C Trace Context**, **OpenTelemetry**, **SRE SLO/error-budget**, **blue-green/canary**. Ключевые решения снабжены источниками. (Ссылки отмечены в тексте.)

## 6.0 Принципы

- **Secure by default:** минимальные привилегии, короткоживущие токены, строгая валидация входа. Telegram требует использовать **только** провалидированные на сервере данные initData, не доверяя initDataUnsafe. Это наш канон аутентификации Mini App.
- **Observe everything:** единый контекст трассировки (**W3C Trace Context**) и «триединая» телеметрия (**OpenTelemetry**: трейсы+метрики+логи).
- **SLO→error-budget:** приоритизация стабильности исходя из бюджета ошибок (не «CPU>80%», а «горит бюджет»).
- **Zero-downtime deploy:** базово **blue-green**, для рискованных изменений — **canary**.

## 6.1 Безопасность

### 6.1.1 Аутентификация (Telegram Mini App)

**Что и зачем.** Мини-приложение передаёт tgWebAppData (**initData**) — строку с параметрами запуска. На бэке мы **подписанно** валидируем её и только после этого выдаём короткоживущий **JWT** (Bearer), который используем в API. Это защищает от подмен и соответствует требованиям Telegram.

**Как:**

- Библиотека: @telegram-apps/init-data-node (серверные утилиты валидации). ([Telegram Mini Apps Docs](https://docs.telegram-mini-apps.com/packages/telegram-apps-init-data-node?utm_source=chatgpt.com"%20\o%20"telegram-apps/init-data-node))
- Поток: initData→проверка подписи/свежести→выдаём access_token (JWT, короткоживущий); по истечении снова подтверждаем initData (или короткий refresh-cookie).

**Где живёт:** security/auth/telegram-initdata.md, services/auth/\*.

### 6.1.2 JWT и авторизация

**Что и зачем.** JWT трудно отзывать, поэтому он **короткоживущий**; подпись с ротацией ключей, проверка aud/iss/exp/nbf/sub, уникальный jti. Роли — **RBAC**: player, gm, author, admin, с ресурсной проверкой по campaign_id/party_id. Практики согласованы с OWASP (JWT cheatsheet & WSTG).

**Инварианты:**

- TTL access-JWT — **минуты/часы**, не дни.
- kid в заголовке JWT; ключи подписи — в Secret Manager (ротация).
- В payload — минимум данных (без PII).

**Где:** security/jwt-policy.md, security/rbac.yaml.

### 6.1.3 OWASP API Security Top-10 (чек-лист ревью)

**Что и зачем.** Для каждого эндпойнта в PR заполняется короткий чек-лист рисков Top-10 (BOLA/Broken Auth/Excessive Data Exposure/Mass Assignment/Resource Consumption/…); особенно важны **ограничения потребления ресурсов** (API4:2023), так как у нас медиа-пайплайны и внешние AI-провайдеры.

**Где:** security/owasp-api-top10-checklist.md.

### 6.1.4 Лимиты, анти-абьюз, модерация

- **Rate-limits** на API-шлюзе: per-user / per-campaign / per-endpoint; при превышении — 429 + Retry-After (клиент обязан делать backoff).
- **Контент SAFE + Lines&Veils** (из Глав 1–3) — обязательны; для изображений — авто-классификаторы + перцептуальные хэши и ручная модерация краёв (см. Главу 5).
- **Webhooks** — подписаны HMAC; окно допусков по времени.

**Где:** security/rate-limits.md, security/webhooks-signing.md.

### 6.1.5 Секреты, ключи, доступ

- Secret Manager / KMS; .env — только шаблон.
- Подписи CDN/Webhook — **ротация**, держим 2–3 активных ключа.
- Доступ в прод — по SSO + MFA; все админ-действия в **аудит-лог**.

**Где:** security/secrets.md, logs/audit_gm.md.

## 6.2 Наблюдаемость (Observability)

### 6.2.1 Трассировка и корреляция

**Что и зачем.** Сквозной контекст — **W3C Trace Context**: принимаем/прокидываем traceparent/tracestate во всех REST-вызовах, а trace_id вкладываем в ошибки API и как расширение в CloudEvents. Это позволяет связать «нажатую кнопку» с событием в очереди/медиа-воркере и вебхуком.

**Где:** observability/trace-context.md.

### 6.2.2 OpenTelemetry (трейсы/метрики/логи)

**Что и зачем.** **OpenTelemetry (OTel)** — единая модель телеметрии (трейсы, метрики, логи) + экспортеры к любому вендору. Мы аннотируем:

- трейсы: http.\*, db.\*, queue.\*, llm.\*, media.\*;
- метрики: latency p50/p95, error-rate, queue depth, cache-hit, DLQ-rate;
- логи: структурированные, с trace_id.

**Где:** observability/opentelemetry.md, infra/otel-collector.yaml.

### 6.2.3 SLO/алёрты/дашборды

**Что и зачем.** **SLO→error-budget**: алёрим не на «CPU 80%», а на выгорание бюджета SLO (доля ошибок/латентность). Для медиапайплайнов — отдельные SLO: p95 TTS/ASR/IMG, DLQ-rate, время в очереди.

**Базовые дашборды:**

- **Run/Turns**: средняя длина сцены, время на ход, доля частичных/провалов.
- **Party-sync**: WebSocket connect/error/reconnect, таймер.
- **Media**: queue depth, p95 latency, success-rate, DLQ-rate, cache-hit.
- **Billing**: 429-rate, списания, refunds.

**Где:** observability/dashboards/\*.json, ops/slo.md, ops/alerts.md.

## 6.3 QA: тест-пирамида, фикстуры, нагрузка

### 6.3.1 Пирамида тестов

**Что и зачем.** Принимаем **Test Pyramid**: много unit-тестов, умеренно integration/contract, минимум е2е. Это даёт быстрые обратные связи и меньше хрупкости. ([Octopus Deploy](https://octopus.com/devops/software-deployments/canary-deployment/?utm_source=chatgpt.com"%20\o%20"Canary%20Deployments:%20Pros,%20Cons,%20And%205%20Critical%20Best%20...))

**Слои и смысл:**

- **Unit** (детерминированные): эффекты предметов, расчёт DC/Director, парсинг initData.
- **Integration/Contract**: валидации **OpenAPI/JSON Schema** и CloudEvents с «золотыми файлами» из Глав 4.
- **E2E (Vertical Slice):** Мини-App → Сцена → Голосование → Бой → Лут → Журналы.

### 6.3.2 Нагрузка и деградации

- **Медиа-очереди:** профили «burst» и «sustained», ретраи/backoff, **circuit-breaker** на провайдера, DLQ.
- **Сеть:** WebSocket под сменой сети, jitter, реконнекты.
- **Долгие операции:** 202→события media.job.\*; UX фолбэки.

**Где:** qa/load/media-scenarios.md, qa/e2e/vertical-slice.md.

### 6.3.3 Критерии приёмки (MVP/Vertical Slice)

- **Темп Core-loop:** средняя длина сцены, время на ход, % частичных успехов, % боёв, AFK-rate (из Глав 1–2 — теперь как измеримые KPI в QA).
- **Надёжность:** нет тупиков в графе; Retcon≤1 шаг; Failsafe в Story-тональности срабатывает ≤1/2 раза согласно длине модуля.
- **Наблюдаемость:** все ключевые действия порождают трейсы/события.

**Где:** qa/acceptance-checklist.md.

## 6.4 Деплой: окружения, CI/CD, миграции, флаги

### 6.4.1 Контуры и конфигурации

- **Envs:** dev / stage / prod.
- Шаблон .env.example; реальные секреты — только через Secret Manager.
- Инфраструктура — IaC (манифесты в deploy/).

### 6.4.2 Стратегии релизов

- **Blue-Green** — основная: готовим «green», прогоняем smoke/e2e, переключаем трафик; легко откатываемся на «blue». Практики: green держим read-only, миграции — репликационно-совместимые.
- **Canary** — для рискованных изменений/моделей LLM: выкатываем 5%→25%→50%→100%, метрики/алёрты на каждом шаге; автоматическая остановка, если SLO проседает.

**Где:** deploy/strategy.md, deploy/pipelines/\*.yml.

### 6.4.3 Миграции БД

- Процесс **expand/contract**: сначала добавление совместимых изменений, потом — переключение кода, затем контрактная чистка; индексы **CONCURRENTLY**. Zero-downtime. (См. Главу 5.)
- Авто-прогон Alembic в CI; кнопка **Rollback**.

**Где:** deploy/migrations.md, ci/migrations.yml.

### 6.4.4 Feature-flags

- Серверные фичефлаги по user/campaign, без влияния на шансы/баланс (принцип Глав 3).
- Флаги версионируются; аудит «кто/когда включил».

**Где:** config/feature-flags.yaml, logs/audit_system.md.

## 6.5 Инциденты, DR, доступ

### 6.5.1 Инцидент-менеджмент

- **Серьёзность:** Sev-0/1/2; RACI, дежурный SRE.
- **Шаблон пост-мортема:** факты→timeline→корневые причины→мероприятия→SLO/бюджет.
- **MTTA/MTTR** — в SLO-дашбордах.

**Где:** ops/incident-playbook.md, ops/postmortem-template.md.

### 6.5.2 Резерв и восстановление (DR)

- Бэкапы БД: горячие снапшоты + PITR; проверка восстановления еженедельно.
- Объекты медиа — версионирование, lifecycle-политики.

**Где:** ops/dr-plan.md.

## 6.6 Чек-листы (для ежедневной работы)

### 6.6.1 Security & SLO Checklist (выжимка)

- initData валидируется сервером; initDataUnsafe не используется.
- JWT: короткие TTL, kid/ротация, jti, минимум PII.
- OWASP API Top-10: BOLA/Excessive Exposure/Mass Assignment/Resource Consumption — отмечены в PR.
- W3C Trace Context в каждом запросе/событии; trace_id в ошибках.
- SLO/бюджет, алёрты «по бюджету», не по суррогатам.
- Blue-Green/Canary — playbook готов, smoke/e2e до переключения

### 6.6.2 Test Plan (выжимка)

- Unit: эффекты, DC/Director, валидации initData/JWT.
- Contract: схемы OpenAPI/JSON Schema + «золотые» примеры CloudEvents.
- Load/Fault: очереди, DLQ, circuit-breaker, reconnection.
- E2E: vertical slice, Retcon/Override/Failsafe, SAFE/Lines&Veils.

## 6.7 Артефакты главы (DoR/DoD)

**DoR (готовность):** приняты и зафиксированы:

- Telegram initData → JWT, недоверие initDataUnsafe; RBAC; rate-limits/HMAC-webhooks.
- OWASP API Top-10 чек-лист в PR.
- W3C Trace Context + OpenTelemetry; SLO/error-budget.
- Стратегии деплоя: blue-green/canary + миграции expand/contract.

**DoD (в репозитории):**

- security/auth/telegram-initdata.md, security/jwt-policy.md, security/rbac.yaml, security/owasp-api-top10-checklist.md, security/rate-limits.md, security/webhooks-signing.md.
- observability/trace-context.md, observability/opentelemetry.md, observability/dashboards/\*.json, ops/slo.md, ops/alerts.md.
- qa/test-pyramid.md, qa/acceptance-checklist.md, qa/e2e/vertical-slice.md, qa/load/media-scenarios.md.
- deploy/strategy.md, deploy/pipelines/\*.yml, deploy/migrations.md, ci/migrations.yml, config/feature-flags.yaml.
- ops/incident-playbook.md, ops/postmortem-template.md, ops/dr-plan.md.

### Зачем это всё (кратко)

- **Верифицированный вход** через initData → неуязвимость к самоподписанным данным Mini App.
- **OWASP Top-10** → системное покрытие типовых уязвимостей API.
- **Trace Context + OTel** → конец «тёмным зонам»: от клика в сцене до медиа-воркера и вебхука видна одна цепочка.
- **SLO/error-budget** → релизы и приоритизация фич на основе реальной надёжности.
- **Blue-Green/Canary** → безопасные выкладки и быстрые откаты.

Если хочешь, сразу сгенерирую **шаблон пайплайна CI/CD** (линт схем → тест-пирамида → миграции expand → blue-green rollout → smoke/e2e → переключение трафика → post-deploy алёрты) и положу «болванки» всех перечисленных документов в структуру репозитория.