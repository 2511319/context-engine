# SPI: точки расширения и интерфейсы

Документ фиксирует сервисные точки расширения (Service Provider Interfaces) и правила подключения плагинов.

## Провайдеры LLM/Embeddings

- Контракт (Python, Pydantic):
  - интерфейсы ввода/вывода (prompt, params, structured schema),
  - методы: `generate(request) -> StructuredResponse`, `embed(texts) -> list[Vector]`.
- Регистрация: entry points (`pyproject.toml` → `rpgbot.providers`), загрузка через importlib.metadata.

## Провайдеры TTS/IMG/Avatar

- Контракт: запрос/ответ, SLA (таймауты), коды ошибок, идемпотентность по `clientToken`.
- Регистрация: аналогично, в пространстве имён `rpgbot.media.providers`.

## Хранилища памяти

- Контракт: `upsert(chunks)`, `query(query, k, mode)`, `delete(filter)`; типы — домены, метаданные, policy.
- Адаптер PostgreSQL + pgvector — референс‑реализация.

## Фронтенд‑фичи

- Контракт манифеста: см. docs/architecture/frontend-modularity.md.
- Поставка: локальные модули (старт), опционально remote (Module Federation) с семантическими версиями.

