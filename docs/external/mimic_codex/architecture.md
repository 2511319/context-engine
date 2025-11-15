# Архитектура RPG-Bot Monorepo

- **Mini App** (`apps/webapp`) — Vite + React, обращается к Gateway API.
- **Gateway API** (`services/gateway_api`) — FastAPI, валидация Telegram initData, выпуск JWT, health.
- **Память37** (`packages/memory37`) — загрузка YAML-конфигураций knowledge-индексов.
- **Генеративные слои** (`packages/genlayers`) — описания профилей генерации и связанных JSON-схем.
- **Контракты** (`contracts/`) — OpenAPI/JSON Schema/примеры, lint Spectral.
- **CI/CD** — GitHub Actions (`.github/workflows/ci.yml`), Cloud Run пайплайн (`deploy/pipelines/cloud-run.yaml`).

Детали взаимодействия и API соответствуют глазам 3–10.
