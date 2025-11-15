# ТЗ (Dev) — Закреплённый контент‑пак: кампания/сцены/NPC/награды

Цель: подготовить и встроить в приложение согласованный контент‑пак одной кампании, совместимый с Memory37 (retrieval) и контрактами приложения. Результат — воспроизводимый YAML‑пак и поддержка нового домена `lore` в ingest.

## Область работ
- Формат знаний для Memory37 (YAML): `scenes`, `npcs`, `art`, `lore`.
- Расширение ingest для поддержки `lore` (включая награды) как `KnowledgeItem(domain="lore")`.
- Стандартизация путей, id‑паттернов и артефактов кампании.

## Требования к данным и структурам
- Путь к основному файлу кампании: `data/knowledge/campaigns/<campaign_id>.yaml`.
- Допустимые домены `KnowledgeItem`: `scene | npc | art | lore` (см. `packages/memory37/src/memory37/domain.py`).
- Формат YAML (минимум):
  - `scenes[]`: `{ id: string, title: string, summary: string, tags: string[], timeline: string[] }`
  - `npcs[]`: `{ id: string, name: string, archetype: string, summary: string, voice_tts?: string }`
  - `art[]`: `{ id: string, prompt: string, tags: string[], entities?: { npc?: string[], location?: string[] } }`
  - `lore[]`: `{ id: string, title: string, body: string, tags: string[], related?: { scene?: string, npc?: string } }`
- Правила идентификаторов и item_id:
  - Scene: `item_id = "scene::<scene_id>"` (уникально в кампании)
  - NPC: `item_id = "npc::<npc_id>"`
  - Art: `item_id = "art::<image_id>"`
  - Lore/награды: `item_id = "lore::<lore_id>"` (`title` допускает префиксы вида `reward:<code>`)

## Изменения в коде (обязательно)
- `packages/memory37/src/memory37/ingest.py`:
  - Добавить разбор секции `lore` и функцию `_lore_to_knowledge(data: dict) -> KnowledgeItem`.
  - `content = f"{title}: {body}"`; `metadata`: `{"tags": ",".join(tags), "related": "scene:<id>,npc:<id>"}` (только существующие связи).
- Тесты:
  - `packages/memory37/tests/test_ingest_lore.py` — новый: проверка загрузки `lore`, домена, item_id, полей `metadata`.
  - Актуализировать `packages/memory37/tests/test_ingest.py` при необходимости (регрессия).

## Интеграция в приложение
- Gateway API (`services/gateway_api/.../knowledge.py`) использует `HybridRetriever` и не требует изменений — новые элементы индексируются автоматически.
- Для локального запуска/демо: `KNOWLEDGE_SOURCE_PATH=data/knowledge/campaigns/<campaign_id>.yaml`.
- Dev‑ланчер/docker‑compose уже подхватывают `KNOWLEDGE_SOURCE_PATH`.

## Качество и валидации
- Валидация YAML: уникальные `id` в пределах раздела; непустые `summary/body`.
- Unit‑тесты ingest: ≥ 1 новый тест на `lore`, вся тестовая матрица зелёная (`pytest -q`).

## Что должен вернуть разработчик
- Код:
  - `packages/memory37/src/memory37/ingest.py` (новая `_lore_to_knowledge`).
  - Тесты: `packages/memory37/tests/test_ingest_lore.py` (+ правки существующих при необходимости).
- Данные:
  - `data/knowledge/campaigns/<campaign_id>.yaml` (пример кампании: ≥ 5 сцен, ≥ 3 NPC, ≥ 3 art, ≥ 5 lore/награды).
- Документация:
  - Короткий README `data/knowledge/README.md` с описанием полей YAML.
  - Блок «Источник истины» в PR: ссылка(и) на официальные документы/гайдлайны формата (если применимо) и дата/время просмотра.

## Приёмка (DoD)
- Тесты зелёные; `/v1/knowledge/search?q=<term>` возвращает элементы всех доменов.
- YAML кампании валиден и индексируется ingest без ошибок.
