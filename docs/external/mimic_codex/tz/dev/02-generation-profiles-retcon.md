# ТЗ (Dev) — Финализация профилей генерации и правил реткона

Цель: закрепить набор профилей генерации и довести ретраи/реткон до прод‑уровня с прозрачными схемами и ошибками, строго по актуальной официальной документации OpenAI Responses API (5‑я серия) на дату выполнения работ.

Требование «Источник истины»: в PR обязательно приложить ссылки на раздел(ы) официальной документации и дату/время просмотра, на базе которых приняты решения по параметрам/формам запросов.

## Область работ
- Профили в `profiles.yaml` (root): `scene.v1`, `social.v1`, `combat.v1`, `epilogue.v1`.
- Схемы ответов в `contracts/jsonschema/*.schema.json` — актуализировать поля/ограничения.
- Ретрай/реткон в `genlayers` (без не‑подтверждённых деградаций).
- Рефакторинг провайдера OpenAI на корректную форму Structured Outputs (Responses API).

## Требования к профилям (`profiles.yaml`)
- Для `gpt‑5‑nano` не указывать модель‑специфичные параметры без явного подтверждения в доке (например, `temperature`, `top_p`).
- Фиксировать проверенные параметры:
  - `max_output_tokens`: сцена ≤ 800; соц ≤ 600; бой ≤ 720; эпилог ≤ 450 (уточнить по доке; URL/дата в PR).
  - `response_schema`: имя файла схемы (из `contracts/jsonschema`).
- Имена профилей стабильные (SemVer в имени, напр. `scene.v1`).

## Требования к схемам (`contracts/jsonschema`)
- Минимальные поля и ограничения:
  - Scene: `title: string(minLength=1)`, `summary: string(minLength=1)`, `beats: array(minItems=3, items: string)`, `tags: array(string)`.
  - Social: `topic: string`, `participants: array(string, minItems=2)`, `beats: array(minItems=3)`, `outcome: string`.
  - Combat: `situation: string`, `rounds: array(minItems=2)`, `outcome: string`, `tags: array(string)`.
  - Epilogue: `tone: string`, `summary: string`, `aftermath: array(string)`.
- `additionalProperties: false`; черновик JSON Schema 2020‑12.

## Ретрай/реткон
- Ретрай: `StructuredGenerationEngine` повторяет попытку при невалидном JSON/схеме до `max_retries`.
- Реткон (augment prompt):
  - Дополнять подсказку причиной (`Invalid JSON`/`Schema error`) и именем схемы `schema_name`.
  - При валидационной ошибке — указывать путь поля (`/beats/0` и т.п.).
- Деградации параметров (temperature/top_p/длина) по умолчанию НЕ применять для `gpt‑5‑nano`. Разрешены только при явном подтверждении в доке (URL/дата в PR).
- При провайдерской ошибке — логировать, возвращать 502 с `traceId` (без «догадочных» фолбэков).

## Изменения в коде
- `packages/genlayers/src/genlayers/generator.py`: доработать `_augment_prompt()` (включить имя схемы и путь поля при `jsonschema.ValidationError`).
- `packages/genlayers/src/genlayers/providers.py`:
  - Перевести на Structured Outputs через `text.format`: `client.responses.create(..., text={"format": {"type": "json_schema", "name": schema_name, "schema": schema}}, max_output_tokens=...)`.
  - Не использовать устаревший верхнеуровневый `response_format`.
  - Любые модель‑специфичные параметры указывать только при наличии подтверждения в доке (URL+дата в PR).
- `profiles.yaml`: привести к требованиям выше.

## Тестирование
- `packages/genlayers/tests/test_generator.py`: проверка, что последний prompt содержит подсказку с именем схемы и (при валидации) путь поля.
- (Опционально) модульный тест провайдера: проверка, что при генерации передаётся `text.format` JSON Schema и `max_output_tokens` (без `response_format`).
- `services/gateway_api/tests/test_generation.py` — без изменений.

## Что должен вернуть разработчик
- Код: правки `generator.py`, `providers.py`, тесты.
- Данные: обновлённый `profiles.yaml`, при необходимости — правки `contracts/jsonschema/*.schema.json`.
- Документация: заметки по реткону в `docs/ab/retcon-notes.md` и блок «Источник истины» (URL официальной документации + дата/время просмотра).
