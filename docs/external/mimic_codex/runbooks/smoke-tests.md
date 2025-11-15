# Smoke-тесты сервисов (локально)

Короткий чек-лист для ручной верификации ключевых интерфейсов без углублённых тестов.

## Предусловия

- Python 3.12+, Poetry 1.8+
- `.env` создан из `.env.example` и заполнен (минимум: `BOT_TOKEN`, `JWT_SECRET`, `API_VERSION`).
- Для генерации: `OPENAI_API_KEY` (или оставьте пустым — сервис будет disabled).

## Gateway API

- Запуск: `poetry run uvicorn rpg_gateway_api.app:create_app --factory --reload`
- Проверки:
  - `GET /config` — `{ apiVersion, knowledge, generation, traceId }` (traceId меняется по запросам)
  - `GET /health` — `{ status: "ok", api_version: "..." }`
  - `GET /v1/generation/profiles` — список профилей
  - `POST /v1/generation/scene.v1` с `{ "prompt": "..." }` — валидный JSON по схеме
  - `GET /v1/knowledge/search?q=moon` — список items (если есть `KNOWLEDGE_SOURCE_PATH` или БД)

## Party Sync

- Запуск: `poetry run uvicorn rpg_party_sync.app:create_app --factory --reload`
- Проверки:
  - `GET /config` — `{ apiVersion, traceId }`
  - `GET /health` — `{ status: "ok", api_version }`
  - WS: подключиться к `/ws/campaign/{id}` двумя клиентами; отправить JSON `{ eventType, payload }` — второй клиент получает то же сообщение; поздний подписчик получает историю.

## Media Broker

- Запуск: `poetry run uvicorn rpg_media_broker.app:create_app --factory --reload`
- Проверки:
  - `GET /config` — `{ apiVersion, traceId }`
  - `POST /v1/media/jobs` с `{ jobType: "image", payload: { prompt: "..." } }` — 202 и `jobId`
  - `GET /v1/media/jobs/{jobId}` — статус переходит в `succeeded`, payload содержит `cdnUrl`

## WebApp

- Запуск: `npm run dev --prefix apps/webapp`
- Проверки:
  - Шапка отображает `API <версия>`; если Gateway отдаёт `/config`, отображается короткий суффикс `trace <id>`.
  - Фича Generation: список профилей загружается; выполнение промпта возвращает JSON и показывается на экране.

