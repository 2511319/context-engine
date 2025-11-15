# 02-profiles-quality-metrics-ab.md

## 0. Назначение и область

Документ задаёт:

* состав профильных **Structured Outputs** (scene / social / combat / epilogue) и их JSON-схемы (Draft 2020-12, строгие);
* инварианты полей для всех ответов;
* критерии качества (SLO/приёмка) и методику A/B;
* DX/CI, хранение, версионирование, логи/приватность;
* политику кэширования (с приоритетом уникального опыта).

**Нормативные источники (2024–2025):**

* OpenAI **Structured Outputs** / Responses API (строгая проверка по JSON Schema, `response_format:{type:'json_schema', strict:true}`). ([Платформа OpenAI][1])
* Azure OpenAI: поддержка того же подмножества JSON Schema, нюансы ограничений. ([Microsoft Learn][2])
* Anthropic Claude 3.7: «жёсткой» нативной JSON-схемы нет; добиваемся структуры через JSON-инструкции/шаблоны или «инструменты»/адаптеры. ([Claude Docs][3])
* Метрики RAG/LLM (faithfulness, answer relevancy, context precision/recall). ([Ragas][4])
* A/B и bandit-подходы: безопасный rollout 10/90; MAB — продвинутая опция. ([ACL Anthology][5])

---

## 1. Инварианты (обязательны для всех профилей)

* `lang`: `"ru" | "en"` — локаль вывода.
* `version`: строка SemVer профиля (напр. `"scene.v1"`).
* `trace_id`: строка (до 64 симв.) — корреляция запрос/ответ.
* `safety_notes`: краткий комментарий безопасных/чувствительных аспектов (≤200).
* Схемы — **строгие**: `additionalProperties:false`, заданы `min/maxLength`, `enum`, `min/maxItems`.
* По умолчанию — **Structured Outputs** (OpenAI/Azure). Для провайдеров без first-class JSON-схемы применяем адаптер/валидацию на клиенте. ([Платформа OpenAI][1])

---

## 2. Профили и поля

### 2.1 `scene.v1` — Сцена/нарратив

Краткая сцена с последовательностью «битов».
**Поля:** `title`, `summary`, `beats[]`, `tags[]`, инварианты.

**JSON Schema (`contracts/jsonschema/SceneResponse.schema.json`):**

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://rpg.bot/schemas/scene_response.schema.json",
  "type": "object",
  "required": ["title", "summary", "beats", "tags", "lang", "version", "trace_id", "safety_notes"],
  "properties": {
    "title": { "type": "string", "minLength": 1, "maxLength": 80 },
    "summary": { "type": "string", "minLength": 1, "maxLength": 300 },
    "beats": {
      "type": "array",
      "minItems": 3, "maxItems": 12,
      "items": { "type": "string", "minLength": 1, "maxLength": 260 }
    },
    "tags": {
      "type": "array", "minItems": 0, "maxItems": 8,
      "items": { "type": "string", "minLength": 1, "maxLength": 24 }
    },
    "lang": { "type": "string", "enum": ["ru", "en"] },
    "version": { "type": "string", "minLength": 1, "maxLength": 32 },
    "trace_id": { "type": "string", "minLength": 1, "maxLength": 64 },
    "safety_notes": { "type": "string", "maxLength": 200 }
  },
  "additionalProperties": false
}
```

**Пример payload:**

```json
{
  "title": "Туман над пристанью",
  "summary": "Группа встречает контрабандиста у причала.",
  "beats": ["Холодный туман стелется по воде", "Фонарик мигает трижды", "Из тени выходит шрамированный мужчина"],
  "tags": ["harbor","noir"],
  "lang": "ru",
  "version": "scene.v1",
  "trace_id": "abc123",
  "safety_notes": ""
}
```

---

### 2.2 `social.v1` — Диалог (с эмоциями)

Разговор нескольких участников; **каждый бит — объект `{speaker, emotion, text}`** (твоя правка — зафиксировано).
**Поля:** `topic`, `participants[]`, `beats[]: {speaker, emotion, text}`, `outcome`, инварианты.

**JSON Schema (`contracts/jsonschema/SocialResponse.schema.json`):**

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://rpg.bot/schemas/social_response.schema.json",
  "type": "object",
  "required": ["topic", "participants", "beats", "outcome", "lang", "version", "trace_id", "safety_notes"],
  "properties": {
    "topic": { "type": "string", "minLength": 1, "maxLength": 120 },
    "participants": {
      "type": "array", "minItems": 1, "maxItems": 6,
      "items": { "type": "string", "minLength": 1, "maxLength": 40 }
    },
    "beats": {
      "type": "array", "minItems": 3, "maxItems": 24,
      "items": {
        "type": "object",
        "required": ["speaker", "emotion", "text"],
        "properties": {
          "speaker": { "type": "string", "minLength": 1, "maxLength": 40 },
          "emotion": { "type": "string", "minLength": 1, "maxLength": 24 },
          "text": { "type": "string", "minLength": 1, "maxLength": 240 }
        },
        "additionalProperties": false
      }
    },
    "outcome": { "type": "string", "minLength": 1, "maxLength": 200 },
    "lang": { "type": "string", "enum": ["ru", "en"] },
    "version": { "type": "string", "minLength": 1, "maxLength": 32 },
    "trace_id": { "type": "string", "minLength": 1, "maxLength": 64 },
    "safety_notes": { "type": "string", "maxLength": 200 }
  },
  "additionalProperties": false
}
```

**Пример payload:**

```json
{
  "topic": "Торг о цене информации",
  "participants": ["Контрабандист","Рейнджер"],
  "beats": [
    {"speaker":"Контрабандист","emotion":"настороженность","text":"Цена выросла."},
    {"speaker":"Рейнджер","emotion":"спокойствие","text":"И всё же у вас нет времени торговаться."},
    {"speaker":"Контрабандист","emotion":"уступка","text":"Ладно, половину сейчас, остальное после."}
  ],
  "outcome": "Сделка на жестких условиях.",
  "lang": "ru",
  "version": "social.v1",
  "trace_id": "abc123",
  "safety_notes": ""
}
```

---

### 2.3 `combat.v1` — Стычка/бой

Ситуация, раунды, исход.
**Поля:** `situation`, `rounds[]`, `outcome`, `tags[]`, инварианты.

**JSON Schema (`contracts/jsonschema/CombatResponse.schema.json`):**

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://rpg.bot/schemas/combat_response.schema.json",
  "type": "object",
  "required": ["situation", "rounds", "outcome", "tags", "lang", "version", "trace_id", "safety_notes"],
  "properties": {
    "situation": { "type": "string", "minLength": 1, "maxLength": 220 },
    "rounds": {
      "type": "array", "minItems": 3, "maxItems": 12,
      "items": { "type": "string", "minLength": 1, "maxLength": 220 }
    },
    "outcome": { "type": "string", "minLength": 1, "maxLength": 220 },
    "tags": {
      "type": "array", "minItems": 0, "maxItems": 8,
      "items": { "type": "string", "minLength": 1, "maxLength": 24 }
    },
    "lang": { "type": "string", "enum": ["ru", "en"] },
    "version": { "type": "string", "minLength": 1, "maxLength": 32 },
    "trace_id": { "type": "string", "minLength": 1, "maxLength": 64 },
    "safety_notes": { "type": "string", "maxLength": 200 }
  },
  "additionalProperties": false
}
```

---

### 2.4 `epilogue.v1` — Эпилог/последствия

**Поля:** `tone`, `summary`, `aftermath[]`, инварианты.

**JSON Schema (`contracts/jsonschema/EpilogueResponse.schema.json`):**

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://rpg.bot/schemas/epilogue_response.schema.json",
  "type": "object",
  "required": ["tone", "summary", "aftermath", "lang", "version", "trace_id", "safety_notes"],
  "properties": {
    "tone": { "type": "string", "minLength": 1, "maxLength": 40 },
    "summary": { "type": "string", "minLength": 1, "maxLength": 320 },
    "aftermath": {
      "type": "array", "minItems": 3, "maxItems": 12,
      "items": { "type": "string", "minLength": 1, "maxLength": 200 }
    },
    "lang": { "type": "string", "enum": ["ru", "en"] },
    "version": { "type": "string", "minLength": 1, "maxLength": 32 },
    "trace_id": { "type": "string", "minLength": 1, "maxLength": 64 },
    "safety_notes": { "type": "string", "maxLength": 200 }
  },
  "additionalProperties": false
}
```

---

## 3. Промпт-пакеты (минимум)

Файлы: `docs/prompts/<profile>.md`
Формат: **system-преамбула** (краткие правила), **assistant-role** (стиль/тон), **user-frames** (2–3 примера).

**Пример (`social.v1`):**

```md
# system
Ты — мастер диалогов. Строго следуй схеме JSON (social.v1). Не выходи за лимиты длин.
# assistant
Тон: лаконичный, кинематографичный. Эмоции — одним словом.
# user-frame
Тема: торг у причала. Участники: Контрабандист, Рейнджер. Итог: сделка на жёстких условиях.
```

---

## 4. Политика валидации и совместимости

1. **Primary**: Responses API с `response_format:{type:"json_schema",strict:true}` (OpenAI/Azure). ([Платформа OpenAI][1])
2. **Fallback**: для провайдеров без строгой схемы — принуждение JSON-макета в промпте + **клиентская валидация** и малый auto-repair (правка запятых/кавычек) → 1 быстрый **retry**. ([Claude Docs][3])
3. **CI-линт**: в каждом PR — проверка схем и пример-payload.

---

## 5. Критерии качества / SLO

**Технические SLO (v1):**

* Валидность JSON по схеме ≥ **99%**;
* Ошибки парсинга ≤ **1%** запросов;
* Средняя задержка в профиле ≤ **3.5s** (целевой бенч);
* Стоимость/запрос — фиксируется и контролируется (дельта ≤ +10% к базовой).

**Содержательные SLO (v1):**

* **Accept-rate** (ручная/полуавто приёмка) ≥ **90%**;
* **Relevancy** к запросу/контексту ≥ **0.9** (LLM-судья по рубрике);
* (Если есть RAG) **Faithfulness ≥ 0.9**, **Context precision/recall ≥ 0.8**. ([Ragas][4])

**Приёмка (авто/полуручно):**

* Валидность по JSON-схеме (CI);
* Соответствие профилю и лору;
* Стиль: лаконичность, отсутствие мета-языка;
* Для `social.v1`: во всех `beats[]` заполнен `emotion`.

---

## 6. Метрики и оценка

* **Жёсткие:** валидность JSON, длины/лимиты, заполненность обязательных полей.
* **LLM-as-Judge:** читабельность/стилистическая целостность/релевантность (чёткая рубрика).
* **RAG:** faithfulness, answer relevancy, context precision/recall (RAGAS). ([Ragas][4])

**Рубрика (фрагмент, шкала 0–1):**

* Relevancy (запрос↔ответ); Consistency (без противоречий лору); Brevity (в лимитах); Tone match.

---

## 7. Методика A/B

**Ед. эксперимента:** профиль×тематика×локаль.
**Набор:** 20–30 промптов/профиль (golden-поднабор для регрессов).
**Распределение:** безопасный **10/90 ramp-up**; при стабильности → 50/50; **MAB** (многорукий бандит) — как продвинутая стадия, когда цель — единый near-term KPI и есть много «рук». ([Medium][6])
**Остановка:** по эффекту (минимальный размер эффекта + минимальная длительность).
**Отчётность:** CSV/Parquet с промптами, версиями профилей, метриками, выводами.

---

## 8. Политика кэширования (уникальный опыт > экономия)

**Принципы:**

* **Не кэшировать** генеративные ответы профилей по умолчанию (во имя уникальности).
* Разрешён **строго идемпотентный** кэш:

  * статические ассеты, схемы, справочные таблицы;
  * результаты детерминированных препроцессоров (например, нормализация входа);
  * *краткоживущий* (≤30s) dedupe-кэш на **идентичный** запрос (защита от дребезга UI), отключаем по флагу `no_dedupe`.
* **Запрещено** кэшировать ответы, зависящие от персонального состояния/seed/случайности.
* Опционально — **персонализированный seed** (входной хэш user×session×context) для стабильной вариативности **без хранения** самих ответов.
* Для RAG — кэш **ретривера** (индекс/эмбеддинги) разрешён; контент ответа — нет.

---

## 9. Версионирование, хранение, каталог

* Имена профилей — SemVer: `scene.v1`, `social.v1` …
* Схемы — в `contracts/jsonschema/*.schema.json`; промпт-пакеты — в `docs/prompts/`; A/B карточки — в `docs/ab/*.yaml`, результаты — в `docs/ab/results/*.csv`.
* Каталог профилей — автоген из схем/метаданных (скрипт генерации страницы каталога).

---

## 10. DX/CI

* Проверки в PR:

  1. валидность JSON-схем (`jsonschema`);
  2. «пример-payload ↔ схема»;
  3. линт лимитов длины;
  4. smoke-генерация 3–5 образцов/профиль через sandbox провайдера.
* Матрица CI: OpenAI (Responses API), Azure OpenAI; **Claude** — через адаптер (JSON-инструкции/инструмент). ([Платформа OpenAI][1])

---

## 11. Логи, приватность, аудит

* Логируем: `trace_id`, профиль/версия, метрики; **сэмплинг** payload с деперсонализацией; TTL для журналов модерации.
* Храним решения модерации вместе с `safety_notes` (TTL).

---

## 12. Rollout/rollback

* Мониторинг SLO: валидность, latency, accept-rate; алерты.
* При деградации — автоматический откат на пред-стабильную версию профиля (флаг в конфиге экспозиции).

---

## 13. Примеры вызова API

**OpenAI (Responses API, Structured Outputs):** ([Платформа OpenAI][1])

```ts
const response = await client.responses.create({
  model: "gpt-5",
  input: [{ role: "user", content: "Сцена: пристань в тумане..." }],
  response_format: {
    type: "json_schema",
    json_schema: { name: "SceneResponse", schema: /* содержимое SceneResponse.schema.json */, strict: true }
  }
});
```

**Azure OpenAI (тот же подход):** см. ограничения JSON Schema в их доке. ([Microsoft Learn][2])

**Anthropic (альтернатива):** задать JSON-макет в промпте/инструмент с соответствующей входной схемой; валидация — на клиенте. ([Claude Docs][3])

---

## 14. Чек-лист приёмки пакета

* [ ] 4 схемы в `contracts/jsonschema/` (строгие, с инвариантами)
* [ ] 4 промпт-пакета в `docs/prompts/` (system/assistant/user-frames)
* [ ] smoke-набор 20–30 промптов/профиль и golden-кейсы
* [ ] настроен A/B (10/90, карточка, метрики, критерий остановки)
* [ ] CI-валидации и отчёты
* [ ] «Источник истины» — список ссылок/дат просмотра (ниже)

---

