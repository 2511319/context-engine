# 02-generation-profiles-retcon-responce.md

> Финальный пакет для разработки и приёмки: профили генерации (Scene/Social/Combat/Epilogue) с **жёсткими JSON-контрактами**, политиками инструментария/ретраев/фолбэков и формализованным **ретконом** (governance, события, аудит, трассировка). Документ согласован по лучшим практикам на октябрь 2025.

---

## 0. Результат этого файла 

* **Артефакты, которые надо внести в репозиторий:**

  * `/profiles.yaml` — единый источник правды для профилей генерации.
  * `/contracts/jsonschema/*.schema.json` — строгие схемы JSON (Draft 2020-12) для каждого профиля.
  * `/docs/ab/retcon-notes.md` — краткая справка по реткону (флоу, запреты, аудит).
* **Рантайм-политики (обязательно реализовать):**

  * Structured Outputs через **Responses API** с `text.format: { type: "json_schema", … }`. Это текущая рекомендованная форма строгого вывода вместо «вольного JSON-mode». ([platform.openai.com][1])
  * **tool_choice: "auto"** (модель может вернуть сообщение или вызвать 0/1/N инструментов; цифры/правила всегда подтверждаются движком). ([platform.openai.com][2])
  * Валидация по **JSON Schema Draft 2020-12**, `additionalProperties: false`, явные `required`. ([json-schema.org][3])
  * Наблюдаемость: OpenTelemetry spans с консистентным неймингом; события в формате **CloudEvents**, привязка к трассам через **W3C Trace Context** (`traceparent`). ([opentelemetry.io][4])
  * Качество: контракт-тесты (ajv/spectral), интеграционные сценарии, лёгкий eval-набор. ([platform.openai.com][5])
  * Политика данных: отключить обучение на наших данных/логирование провайдером, минимизировать PII (см. **Data controls**). ([platform.openai.com][6])

---

## 1. Профили генерации (`/profiles.yaml`)

> Все профили используют Responses API c **Structured Outputs** (см. ниже) и общую политику инструментов/ретраев/фолбэков. ([platform.openai.com][1])

```yaml
# /profiles.yaml
version: 1
meta:
  owner: "rpg-bot"
  updated_at: "2025-10-30"
  notes: "Profiles for Scene/Social/Combat/Epilogue with strict JSON outputs"

defaults:
  provider: "openai"
  tool_choice: "auto"            # модель сама решает, вызывать ли инструменты
  safety: "standard"
  tracing: "otel_default"
  retries:
    invalid_json:
      attempts: 1                # 1 авто-ретрай
      repair_prompt: true        # мини-ремонт (см. §3.2)
  fallback:
    minimal_valid_json: true     # минимально валидный ответ, помеченный degraded:true
  timeouts:
    tool_call_ms: 1800           # SLA инструментов
    overall_ms: 12000

profiles:
  scene.v1:
    model: "gpt-5-mini"
    text:
      format:
        type: json_schema
        json_schema:
          name: "SceneResponse"
          # Схему загружаем из репозитория:
          schema_ref: "contracts/jsonschema/SceneResponse.schema.json"
    max_output_tokens: 800

  social.v1:
    model: "gpt-5-mini"
    text:
      format:
        type: json_schema
        json_schema:
          name: "SocialResponse"
          schema_ref: "contracts/jsonschema/SocialResponse.schema.json"
    max_output_tokens: 600

  combat.v1:
    model: "gpt-5-mini"
    text:
      format:
        type: json_schema
        json_schema:
          name: "CombatResponse"
          schema_ref: "contracts/jsonschema/CombatResponse.schema.json"
    max_output_tokens: 720

  epilogue.v1:
    model: "gpt-5-mini"
    text:
      format:
        type: json_schema
        json_schema:
          name: "EpilogueResponse"
          schema_ref: "contracts/jsonschema/EpilogueResponse.schema.json"
    max_output_tokens: 450
```

---

## 2. Контракты ответов (JSON Schema, Draft 2020-12)

> Все схемы имеют `$schema`, `$id`, `required`, `maxLength`, `minItems/maxItems`, `additionalProperties:false`. Используем текущую стабильную версию спецификации — **2020-12**. ([json-schema.org][3])

### 2.1 SceneResponse

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://example.com/schemas/SceneResponse.schema.json",
  "title": "SceneResponse",
  "type": "object",
  "required": ["narration", "choices", "lang", "safety_notes"],
  "properties": {
    "narration": { "type": "string", "maxLength": 1800 },
    "choices": {
      "type": "array",
      "minItems": 1,
      "maxItems": 3,
      "items": { "type": "string", "maxLength": 140 }
    },
    "tags": {
      "type": "array",
      "maxItems": 8,
      "items": { "type": "string", "maxLength": 32 }
    },
    "art_prompt": { "type": "string", "maxLength": 300 },
    "safety_notes": { "type": "string", "maxLength": 200 },
    "lang": { "type": "string", "enum": ["ru", "en"] },
    "degraded": { "type": "boolean", "default": false }
  },
  "additionalProperties": false
}
```

### 2.2 SocialResponse

(учтена структура «битов»: `{speaker, emotion, text}`)

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://example.com/schemas/SocialResponse.schema.json",
  "title": "SocialResponse",
  "type": "object",
  "required": ["turns", "lang"],
  "properties": {
    "turns": {
      "type": "array",
      "minItems": 1,
      "maxItems": 6,
      "items": {
        "type": "object",
        "required": ["speaker", "text"],
        "properties": {
          "speaker": { "type": "string", "maxLength": 32 },
          "emotion": { "type": "string", "maxLength": 24 },
          "text": { "type": "string", "maxLength": 300 }
        },
        "additionalProperties": false
      }
    },
    "npc_intent": { "type": "string", "maxLength": 120 },
    "safety_notes": { "type": "string", "maxLength": 200 },
    "lang": { "type": "string", "enum": ["ru", "en"] },
    "degraded": { "type": "boolean", "default": false }
  },
  "additionalProperties": false
}
```

### 2.3 CombatResponse

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://example.com/schemas/CombatResponse.schema.json",
  "title": "CombatResponse",
  "type": "object",
  "required": ["narration", "effect_hints", "lang"],
  "properties": {
    "narration": { "type": "string", "maxLength": 1000 },
    "effect_hints": {
      "type": "array",
      "maxItems": 6,
      "items": { "type": "string", "maxLength": 80 }
    },
    "lang": { "type": "string", "enum": ["ru", "en"] },
    "degraded": { "type": "boolean", "default": false }
  },
  "additionalProperties": false
}
```

### 2.4 EpilogueResponse

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://example.com/schemas/EpilogueResponse.schema.json",
  "title": "EpilogueResponse",
  "type": "object",
  "required": ["narration", "closure_tags", "lang"],
  "properties": {
    "narration": { "type": "string", "maxLength": 1200 },
    "closure_tags": {
      "type": "array",
      "maxItems": 8,
      "items": { "type": "string", "maxLength": 32 }
    },
    "lang": { "type": "string", "enum": ["ru", "en"] },
    "degraded": { "type": "boolean", "default": false }
  },
  "additionalProperties": false
}
```

---

## 3. Политики рантайма (инструменты, ретраи, ремонт, фолбэк)

### 3.1 Tool-calling

* **tool_choice: "auto"** в профилях. Модель может:

  1. отдать сразу текстовый контейнер (валидный по схеме),
  2. вызвать один или несколько инструментов (например, для правил/бросков/канона).
     Расчёт правил и чисел всегда делает движок/инструменты; **модель не «придумывает» цифры**. ([platform.openai.com][2])

### 3.2 Ретраи и «ремонт»

* **Авто-ретрай**: 1 повтор при невалидном JSON (по схеме).
* **Ремонт**: короткий системный хинт:

  > «Верни **строго** по схеме `<Name>`; лишние поля отбрось; недостающие не выдумывай».
  > Это соответствует рекомендованной практике для Structured Outputs — модель формирует JSON строго под схему. ([platform.openai.com][1])

### 3.3 Фолбэк

* Если после ретрая и ремонта ответ невалиден — формируем **минимально валидный JSON** (пустые массивы/строки в рамках схемных допусков) с флагом `"degraded": true`, отдаём в UI и логируем инцидент.

---

## 4. Интеграция с Responses API (скелеты запросов)

> Ниже — форма для профиля `scene.v1`. Обратите внимание: строгий вывод задаётся внутри **text-контейнера** через `format: { type:"json_schema", json_schema:{…} }`. ([platform.openai.com][1])

```json
POST /v1/responses
{
  "model": "gpt-5-mini",
  "input": [
    { "role": "system", "content": "Политики безопасности/тона/..."},
    { "role": "user", "content": "Контекст сцены + состояние..." }
  ],
  "tool_choice": "auto",
  "text": {
    "format": {
      "type": "json_schema",
      "json_schema": {
        "name": "SceneResponse",
        "schema": { "$ref": "contracts/jsonschema/SceneResponse.schema.json" }
      }
    }
  }
}
```

---

## 5. Реткон (governance, данные, события)

### 5.1 Политика

* **Глубина**: **только последний применённый шаг** (≤ 1).
* **Запрет реткона**, если шаг содержал: платеж/Stars, он-чейн/минт/NFT, внешние необратимые вебхуки, либо уже помечен `finalized:true`.
* **Права**: только `GM/Co-DM`, обязательна **причина** (≤ 140 симв.).
* **SLO/Анти-абьюз**: лимит, напр., **≤ 3 реткона/сутки/кампания**, фича-флаг с поэтапным rollout.

### 5.2 Откатываемые сущности

* **Состояние партии**: транзакционный откат к `prevStep` (optimistic-lock по версии).
* **Episodic Summary**: пометка `superseded_by`, запись новой сводки, пересчёт дельт (NPC/флаги/ресурсы).
* **Ассеты**: артовые карточки шага архивируем, клиент получает актуальные.

### 5.3 Доменные события (CloudEvents)

> Формат события реткона. Используем **CloudEvents** (v1.0.x). Для сквозной диагностики вклеиваем заголовок **W3C Trace Context** (`traceparent`) и/или переносим `trace_id` в расширения события. ([cloudevents.io][7])

```json
{
  "specversion": "1.0",
  "type": "rpg.run.retcon.applied.v1",
  "source": "urn:rpg:campaign/<campaign_id>",
  "id": "c2f37e1e-6c9a-4c7b-9f65-2ed6f7bfe1f4",
  "time": "2025-10-30T18:20:00Z",
  "datacontenttype": "application/json",
  "traceparent": "00-<trace-id>-<span-id>-01",
  "data": {
    "user": { "id": "<gm_id>", "role": "GM" },
    "reason": "Откат из-за конфликтного лора",
    "prev_step_id": "step_0412",
    "new_step_id": "step_0412r1",
    "limits": { "daily_remaining": 2 },
    "forbidden": false
  }
}
```

---

## 6. Наблюдаемость (OpenTelemetry)

* **Именование спанов**: `gen.scene.response`, `gen.social.response`, `gen.combat.response`, `gen.epilogue.response`, `tools.lookup.rules`, `tools.roll.dice`, `retcon.apply`. Придерживаемся OTel-семантики: **dot-namespacing**, нижнее_подчёркивание в компонентах, латиница. ([opentelemetry.io][4])
* **Связность**: все tool-вызовы — как дочерние спаны генерации; CloudEvents несут `traceparent` для кликабельной связки «запрос → генерация → инструменты → событие». ([w3.org][8])
* **Атрибуты** (минимум):

  * `rpg.profile`, `rpg.campaign_id`, `rpg.run_id`, `rpg.step_id`
  * `gen.degraded` (bool), `gen.retry_count` (int)
  * `tool.name`, `tool.duration_ms`, `tool.timeout_hit` (bool)

---

## 7. Тестирование и приёмка

### 7.1 Контракт-тесты (CI)

* Ветка PR не мержится без зелёных:

  * `ajv` валидация всех `*.schema.json` (Draft 2020-12).
  * `spectral` (lint на схемы/конвенции).
  * golden-фикстуры для каждого профиля: стабильные пример-ответы **строго валидны**. ([json-schema.org][3])

### 7.2 Интеграционные тесты

* Сценарии:

  1. Валидный ответ без инструментов.
  2. Ответ с 1-N tool-вызовами (тайм-лимиты соблюдены).
  3. Невалидный JSON → 1 ретрай → ремонт → валидно.
  4. Полный провал → минимальный валидный фолбэк (`degraded:true`).
  5. Реткон успешный (≤ 1 шаг), событие и аудит записи.
  6. Реткон запрещён (платёж/он-чейн/финализированный шаг).

### 7.3 Evals

* Набор eval-тасков для нарратива/соц-диалога/боя:

  * метрики: валидность по схеме, читабельность/лаконичность, отсутствие «самопридуманных» чисел.
  * инфраструктура: OpenAI Evals (или совместимый runner). ([platform.openai.com][5])

---

## 8. Секьюрити и данные

* Включить политику **Data Controls**: не использовать наши данные для обучения, минимизация PII, регламенты хранения. Для enterprise/edu/регионов учитывать резидентность, если применимо. ([platform.openai.com][6])

---

## 9. i18n

* Язык ответа фиксируем схемным полем `"lang": "ru|en"`.
* UI даёт явный переключатель; автодетект не используем (детерминизм для тестов).

---

## 10. Производительность/стоимость

* **Стриминг**: `scene/social` — допускается стриминг текстового контейнера (для UX скорости), `combat/epilogue` — целевой JSON без стрима (для простоты).
* **Параллелизм инструментов**: до 3 одновременных вызовов; суммарный SLA на tool-фазу ≤ 1.8 с.
* **Backoff**: экспоненциальный с джиттером для повторов запросов к провайдеру.

---

## 11. UI/UX реакции

* Если `choices` пуст (деградация) — показываем «Свой ход» и кнопку «Перегенерировать» (без реткона).
* В RUN для GM — «Retcon последнего шага», модалка с причиной; в журналах/истории шаг помечаем бейджем `superseded`.

---

## 12. Управление изменениями

* Feature-flags:

  * `ff_retcon` (вкл/выкл),
  * `ff_structured_outputs` (переключатель в случае провайдера-фолбэка),
  * `ff_streaming_scene`.
* Rollout: 1% → 25% → 100% с мониторингом ошибок/latency.

---

## 13. Приложение A — Мини-гайд рецензенту PR

1. **Профили**: проверить `profiles.yaml` — для всех профилей задан `text.format: json_schema` и `tool_choice:"auto"`. ([platform.openai.com][1])
2. **Схемы**: `additionalProperties:false`, `required`, лимиты полей, `$schema` = Draft 2020-12. ([json-schema.org][3])
3. **Ретраи/ремонт**: есть 1 авто-ретрай, текст репарации, фолбэк `degraded:true`.
4. **OTel/CloudEvents**: имена спанов соответствуют гайдлайнам; события несут `traceparent`. ([opentelemetry.io][4])
5. **Evals/CI**: есть ajv/spectral, golden-фикстуры, базовые eval-таски. ([platform.openai.com][5])
6. **Data controls**: включены политики, нет утечек PII. ([platform.openai.com][6])

---

## 14. Приложение B — Пример подсказки «ремонта» (system)

> «Если предыдущий ответ не проходит валидацию по `SceneResponse`, верни **строго** JSON, соответствующий `SceneResponse`. **Не добавляй** лишних полей, **не выдумывай** недостающие. Соблюдай `maxLength` и `maxItems`. Поле `lang` выставь в язык сессии.»

---

## 15. Приложение C — Мини-FAQ (для заказчика)

* **Зачем Structured Outputs?**
  Чтобы ответ **гарантированно** соответствовал контракту и не «ломал» UI/игровую логику. Это официально поддерживаемый способ строгих структур в Responses API. ([platform.openai.com][1])
* **Почему `tool_choice:"auto"`?**
  Это дефолт в Function Calling: модель может выбрать вернуть сообщение или вызвать инструмент(ы); мы всё равно валидируем правила через движок. ([platform.openai.com][2])
* **Почему именно Draft 2020-12?**
  Это актуальная стабильная редакция спецификации JSON Schema; поддерживается в основных валидаторах и платформах. ([json-schema.org][3])
* **Как мы проверяем качество?**
  Комбо из контракт-тестов/интеграции и лёгких eval-тасков под стиль/валидность/«без самопридуманных чисел». ([platform.openai.com][5])
* **Как отслеживаем реткон?**
  События CloudEvents с переносом `traceparent` для сквозного анализа в Observability. ([cloudevents.io][7])

---

