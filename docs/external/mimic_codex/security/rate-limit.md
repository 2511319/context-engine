# Rate limiting и базовая защита API

## Варианты

- Reverse-proxy (Nginx/Envoy/Cloud Load Balancer)
  - Лимиты по IP/route, burst + nodelay, отдельные лимиты на heavy endpoints
- In-app для FastAPI
  - `slowapi` (limits per route), `starlette-limiter` (Redis), custom dependency
- Gateway quotas
  - JWT claims (tier, userId) → лимиты по пользователю/сеансу, защита от злоупотреблений

## Рекомендации (dev/staging)

- Внешний слой: 100 rps / IP на `/health|/config`, 10 rps / IP на `/v1/generation/*`, 20 rps / IP на `/v1/media/*`
- Внутренний слой (in-app):
  - `generation`: 1 rps / user (JWT `sub`), очередь и таймауты
  - `media`: 2 rps / user, идемпотентность по `clientToken` (уже реализовано)

## Таймауты/ретраи

- OpenAI Responses: `OPENAI_TIMEOUT_SECONDS=120`, `GENERATION_MAX_RETRIES=2`
- Media: ограничить `processing_delay_ms` в dev; в проде — circuit-breaker/таймауты на провайдеров

## Минимальная реализация (in-app)

- Добавить dependency, читающий JWT `sub` и ограничивающий rps (Redis‑бэкенд)
- Возвращать `429 Too Many Requests` для превышений
