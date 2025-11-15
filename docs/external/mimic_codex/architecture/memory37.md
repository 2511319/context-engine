# Memory37: архитектура подсистемы памяти

Документ фиксирует целевую структуру подсистемы памяти, описанной в главе 8, и определяет артефакты текущего этапа (Эпоха D).

## Цели

- Хранить долговременное состояние кампаний (сцены, NPC, артефакты) в PostgreSQL + pgvector.
- Поддерживать гибридный поиск (BM25 + dense, fusion RRF) с rerank LLM.
- Обеспечить идемпотентный ETL из статических источников (SRD/лора) и runtime-снимков кампаний.

## Слои

1. **Domain** — Pydantic-модели:
   - `SceneState`: состояние сцены (summary, chronology, relations delta).
   - `NpcProfile`: статическая + динамическая информация NPC.
   - `ArtCard`: карточка медиа-ресурса с метаданными.
   - `RelationDelta`: изменения отношений между сущностями.
2. **Providers** — интерфейсы для встраивания провайдеров embedding/LLM (OpenAI, локальные).
3. **Storage** — адаптеры:
   - `VectorStore` (базовый протокол) и реализация `PgVectorStore`.
   - Уровень репозитория с upsert/query и audit полями (created_at, source).
4. **ETL** — загрузка YAML/JSON в доменные модели (`ingest.load_knowledge_items_from_yaml`), конвертация runtime-состояний (`build_runtime_items`), батчевые embedding/запись (`ETLPipeline`).
5. **Retrieval** — гибридный поиск `HybridRetriever` (dense similarity + lexical счётчики + опциональный rerank провайдер, например LLM).

## Минимальный инкремент (Step 1)

- Доменные модели (`memory37/domain.py`).
- Интерфейсы `EmbeddingProvider`, `VectorStore`, in-memory store.
- ETL и ingestion helpers (файлы `ingest.py`, `etl.py`).
- `PgVectorStore` как база для подключения к PostgreSQL + pgvector.
- Гибридный ретривер с optional rerank.
- CLI (`memory37/cli.py`): команды `ingest-file` и `ingest-runtime-snapshot`, поддержка dry-run и подключения через `MEMORY37_DATABASE_URL`.
- CLI (`memory37/cli.py`): команды `ingest-file`, `ingest-runtime-snapshot`, `search` (с поддержкой OpenAI/pgvector), dry-run режим для локальной работы.

Дальнейшие шаги (Step 2/3) включат реализацию pgvector-адаптера, ETL и гибридного поиска.
