# Knowledge Ingest Runbook

Этот документ описывает, как подготовить и загрузить знания в хранилище Memory37 и как проверить результат.

## Предварительные условия

- Подготовлен YAML-файл с данными (см. пример `data/knowledge/sample.yaml`).
- Указаны переменные окружения:
  - `MEMORY37_DATABASE_URL` — строка подключения к PostgreSQL с расширением pgvector.
  - `OPENAI_API_KEY` — ключ OpenAI (не обязателен для локального режима).
  - `OPENAI_MODEL` и/или `OPENAI_EMBEDDING_MODEL` — при использовании OpenAI.

## Загрузка знаний

```bash
python -m memory37.cli ingest-file data/knowledge/sample.yaml --dsn %MEMORY37_DATABASE_URL%
```

Для локальной проверки без базы данных добавьте `--dry-run`, чтобы использовать in-memory store.

## Загрузка runtime snapshot

```bash
python -m memory37.cli ingest-runtime-snapshot --scenes-file scenes.yaml --npcs-file npcs.yaml --art-file art.yaml --dsn %MEMORY37_DATABASE_URL%
```

## Поиск и проверка

```bash
python -m memory37.cli search "moon ruins" --knowledge-file data/knowledge/sample.yaml --dry-run
```

При наличии подключения к базе можно выполнять поиск напрямую в pgvector:

```bash
python -m memory37.cli search "moon ruins" --dsn %MEMORY37_DATABASE_URL% --use-openai --use-openai-rerank
```

## Интеграция с Gateway API

После загрузки знаний установите переменную `KNOWLEDGE_SOURCE_PATH` и перезапустите `gateway_api`. Endpoint `/v1/knowledge/search?q=moon` вернёт список найденных элементов с оценками и метаданными.
