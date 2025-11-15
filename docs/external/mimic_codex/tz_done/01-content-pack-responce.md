1) Область работ и ожидания (с фиксацией)

Что делаем:

Готовый закреплённый контент-пак (YAML для Memory37) с разделами scenes, npcs, art, lore и правилами id/prefix.

Поддержка нового домена lore в ingest + юнит-тесты.

Стандартизация путей/артефактов, DoD и быстрая проверка через /v1/knowledge/search.

Что сдаём:

Код (ingest.py + тесты), данные (<campaign_id>.yaml), документация (README + «источник истины» в PR).

Приёмка: тесты зелёные, YAML валиден и индексируется, поиск отдаёт все домены.

2) Финальные константы (зафиксировано)

Нарратив: Hub-and-Spoke; тон — Dark Fantasy 16+; мини-кампания 3–5 сессий.

Модель данных: YAML + JSON Schema в CI; префиксные id (scn_, npc_, art_, lore_).

Таксономия: контролируемый словарь тегов (темы/локации/тон).

L10n: ru + en; вынос строк в ресурсы + глоссарий.

Совместимость: SRD 5.1/5.2 CC-BY-4.0 (атрибуция обязательна).

Диалоги: шаблоны hub-and-spoke.

TTS/SSML: 2–4 голоса по архетипам + базовый набор SSML.

Визуал: единый стиль-гайд (палитра/теги/ракурсы).

Награды: смешанные (предметы + лор-анлоки/баджи).

Аналитика: Object-Action события: Scene_Entered, Choice_Made, NPC_Interacted, Reward_Granted, Lore_Unlocked.

Telegram: очередь/троттлинг; Mini App expand() на ключевых экранах.

A11y: WCAG 2.1 AA ориентиры (минимум).

Процесс: SemVer; Docs-as-Code; CI линт/валидации.

Медиа-бюджеты: ≤1–2 МБ на сцену; lazy-load.

DoD: схемы/линт зелёные, поиск работает, L10n/A11y чек-листы пройдены.

(Все пункты согласованы ранее; специфика интеграции и Memory37 — в главах 4–8 ТЗ, см. ссылки ниже.)
— Контракты и версии API/Event: OAS 3.1/CloudEvents, версии в /v1.
— Домены знаний и индексы Memory37: SRD/Lore/Episode/NPC/ArtCards; гибридный ретрив.

3) Изменения в коде (готовая спецификация)

Файл: packages/memory37/src/memory37/ingest.py

Добавить разбор lore и функцию _lore_to_knowledge(data: dict) -> KnowledgeItem.

Правило контента: content = f"{title}: {body}"; metadata={"tags":",".join(tags),"related":"scene:<id>,npc:<id>"} (только существующие связи).

Тесты:

Новый packages/memory37/tests/test_ingest_lore.py (домен, item_id, metadata), плюс возможная правка общего test_ingest.py.

Интеграция:

Gateway API использует HybridRetriever — без изменений; новые элементы индексируются автоматически.

Для локального демо: KNOWLEDGE_SOURCE_PATH=data/knowledge/campaigns/<campaign_id>.yaml (docker-compose подхватывает).

4) Данные: структура YAML (утверждённая) + пример вертикали

Путь: data/knowledge/campaigns/<campaign_id>.yaml (минимум: ≥5 сцен, ≥3 NPC, ≥3 art, ≥5 lore).

4.1 Контролируемый словарь тегов (v1)

themes: heist, intrigue, ritual, combat, exploration
locations: moon_bridge, forest, marsh, ruins, village
tone: dark_fantasy, grim, hopeful
entities: ronin, witch, smuggler, gatekeeper
misc: token, veil, oath, mist, moon

4.2 Вертикаль кампании ashen_moon_arc.yaml (готовый драфт)
# data/knowledge/campaigns/ashen_moon_arc.yaml
scenes:
  - id: scn_001
    title: Mist at the Moon Bridge
    summary: Party reaches a fog-draped bridge where tolls are paid in vows. A ronin bars the way, testing intent and truth.
    tags: [moon_bridge, encounter, dark_fantasy, intrigue]
    timeline:
      - Arrival at the bridge under a broken moon
      - Ronin challenges the party’s purpose
      - Hidden sigil glows on the arch

  - id: scn_002
    title: Smuggler’s Codes
    summary: In a wayside hut, a smuggler trades routes and rumors for favors; choices open or close future shortcuts.
    tags: [village, intrigue, heist, exploration]
    timeline:
      - Coded knock at the shutter
      - Map with redacted paths
      - Offer: carry a secret or pay in coin

  - id: scn_003
    title: Witch of the Veilwood
    summary: A witch bargains for moonlight in a vial; the trade reshapes how wards react to the party later.
    tags: [forest, ritual, dark_fantasy]
    timeline:
      - Circles of salt and moths
      - Vial catches pale moonlight
      - Price named: a remembered name

  - id: scn_004
    title: Under-Bridge Vault
    summary: Beneath the bridge lies a counterweight vault; a quiet heist with living mechanisms and whispering chains.
    tags: [moon_bridge, heist, puzzle, exploration]
    timeline:
      - Descent along chain ladders
      - Clockwork listening for lies
      - Counterweight release sequence

  - id: scn_005
    title: The Gatekeeper’s Oath
    summary: Final parley with the true gatekeeper spirit; oaths decide safe passage and who bears the moon token.
    tags: [moon_bridge, encounter, resolution]
    timeline:
      - Veil lifts; spirit manifests
      - Oaths weighed against intent
      - Passage granted—or the bridge refuses

npcs:
  - id: npc_ronin
    name: Li Shen
    archetype: ronin
    summary: Wandering swordsman bound to test resolve; respects clean choices over clever tricks.
    voice_tts: male_smoke_light

  - id: npc_smuggler
    name: Rada “Seven Knocks”
    archetype: smuggler
    summary: Deals in routes and hush; values reciprocity and plausible deniability.
    voice_tts: female_quick_bright

  - id: npc_witch
    name: Mara of the Veilwood
    archetype: witch
    summary: Trades memories and moonlight; detests careless promises.
    voice_tts: female_low_gravel

  - id: npc_gatekeeper
    name: The Gatekeeper
    archetype: spirit
    summary: Custodian of passage; hears the weight of vows.

art:
  - id: art_bridge_mist
    prompt: moonlit ancient stone bridge over chasm, heavy mist, lone ronin silhouette, fractured moon above
    tags: [moon, mist, ronin, moon_bridge]
    entities:
      npc: [npc_ronin]
      location: [loc_moon_bridge]

  - id: art_witch_circle
    prompt: forest witch circle with salt and moths, small vial glowing with pale moonlight, tense barter
    tags: [forest, ritual, witch]
    entities:
      npc: [npc_witch]
      location: [loc_forest_clearing]

  - id: art_underbridge_vault
    prompt: under-bridge vault of chains and counterweights, dim lanterns, mechanical whispers, stealthy figures
    tags: [heist, puzzle, moon_bridge]
    entities:
      location: [loc_under_bridge]

lore:
  - id: lore_reward_moon_token
    title: reward:moon_token
    body: A token carried by the worthy; bridges sworn to the moon yield safe passage to its bearer.
    tags: [reward, token, moon]
    related: { scene: scn_005, npc: npc_gatekeeper }

  - id: lore_moon_bridge_legend
    title: Legend of the Moon Bridge
    body: The bridge hears intent. Vows toll truer than coins; liars find the steps lengthen.
    tags: [lore, moon_bridge, veil]

  - id: lore_smuggler_codes
    title: Seven Knocks
    body: A sequence used by smugglers to signal safe parley; mismatched rhythm marks a trap.
    tags: [lore, smuggler, intrigue]
    related: { scene: scn_002, npc: npc_smuggler }

  - id: lore_witch_bargain
    title: Price of a Name
    body: A name given in moonlight binds; the witch returns what was lost—changed.
    tags: [lore, witch, ritual]
    related: { scene: scn_003, npc: npc_witch }

  - id: lore_gatekeeper_sigil
    title: Gatekeeper’s Sigil
    body: A luminescent brand beneath the arch responds to oaths; steady light marks truth.
    tags: [lore, moon_bridge, oath]
    related: { scene: scn_001, npc: npc_ronin }

5) JSON Schema для валидации YAML (под CI)

Файл: schemas/campaign_content.schema.json (JSON Schema 2020-12). Подключается к YAML через $schema в PR-линтере.

{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://rpg.bot/schemas/campaign_content.schema.json",
  "type": "object",
  "required": ["scenes", "npcs", "art", "lore"],
  "properties": {
    "scenes": {
      "type": "array",
      "minItems": 5,
      "items": {
        "type": "object",
        "required": ["id", "title", "summary", "tags", "timeline"],
        "properties": {
          "id": { "type": "string", "pattern": "^scn_[a-z0-9_\\-]+$" },
          "title": { "type": "string", "minLength": 3 },
          "summary": { "type": "string", "minLength": 20 },
          "tags": { "$ref": "#/$defs/tags" },
          "timeline": {
            "type": "array",
            "minItems": 2,
            "items": { "type": "string", "minLength": 3 }
          }
        },
        "additionalProperties": false
      }
    },
    "npcs": {
      "type": "array",
      "minItems": 3,
      "items": {
        "type": "object",
        "required": ["id", "name", "archetype", "summary"],
        "properties": {
          "id": { "type": "string", "pattern": "^npc_[a-z0-9_\\-]+$" },
          "name": { "type": "string", "minLength": 2 },
          "archetype": { "type": "string", "minLength": 2 },
          "summary": { "type": "string", "minLength": 20 },
          "voice_tts": { "type": "string" }
        },
        "additionalProperties": false
      }
    },
    "art": {
      "type": "array",
      "minItems": 3,
      "items": {
        "type": "object",
        "required": ["id", "prompt", "tags"],
        "properties": {
          "id": { "type": "string", "pattern": "^art_[a-z0-9_\\-]+$" },
          "prompt": { "type": "string", "minLength": 10 },
          "tags": { "$ref": "#/$defs/tags" },
          "entities": {
            "type": "object",
            "properties": {
              "npc": { "type": "array", "items": { "type": "string", "pattern": "^npc_[a-z0-9_\\-]+$" }, "uniqueItems": true },
              "location": { "type": "array", "items": { "type": "string", "pattern": "^loc_[a-z0-9_\\-]+$" }, "uniqueItems": true }
            },
            "additionalProperties": false
          }
        },
        "additionalProperties": false
      }
    },
    "lore": {
      "type": "array",
      "minItems": 5,
      "items": {
        "type": "object",
        "required": ["id", "title", "body", "tags"],
        "properties": {
          "id": { "type": "string", "pattern": "^lore_[a-z0-9_\\-]+$" },
          "title": { "type": "string", "minLength": 3 },
          "body": { "type": "string", "minLength": 20 },
          "tags": { "$ref": "#/$defs/tags" },
          "related": {
            "type": "object",
            "properties": {
              "scene": { "type": "string", "pattern": "^scn_[a-z0-9_\\-]+$" },
              "npc": { "type": "string", "pattern": "^npc_[a-z0-9_\\-]+$" }
            },
            "additionalProperties": false
          }
        },
        "additionalProperties": false
      }
    }
  },
  "$defs": {
    "tags": {
      "type": "array",
      "items": { "type": "string", "pattern": "^[a-z0-9_\\-]+$" },
      "uniqueItems": true,
      "minItems": 1
    }
  },
  "additionalProperties": false
}

6) Spectral-линтер для YAML (минимум)

Файл: .spectral.yaml — проверка структуры и ряда инвариантов на уровне PR.

extends: "spectral:recommended"

rules:
  has-scenes:
    description: "Root must contain scenes[]"
    given: "$"
    then: { field: "scenes", function: truthy }
    severity: error

  has-npcs:
    description: "Root must contain npcs[]"
    given: "$"
    then: { field: "npcs", function: truthy }
    severity: error

  has-art:
    description: "Root must contain art[]"
    given: "$"
    then: { field: "art", function: truthy }
    severity: error

  has-lore:
    description: "Root must contain lore[]"
    given: "$"
    then: { field: "lore", function: truthy }
    severity: error

  id-pattern-scene:
    description: "Scene id must start with scn_"
    given: "$.scenes[*].id"
    then:
      function: pattern
      functionOptions: { match: "^scn_[a-z0-9_\\-]+$" }

  id-pattern-npc:
    description: "NPC id must start with npc_"
    given: "$.npcs[*].id"
    then:
      function: pattern
      functionOptions: { match: "^npc_[a-z0-9_\\-]+$" }

  id-pattern-art:
    description: "Art id must start with art_"
    given: "$.art[*].id"
    then:
      function: pattern
      functionOptions: { match: "^art_[a-z0-9_\\-]+$" }

  id-pattern-lore:
    description: "Lore id must start with lore_"
    given: "$.lore[*].id"
    then:
      function: pattern
      functionOptions: { match: "^lore_[a-z0-9_\\-]+$" }

  lore-title-reward-prefix:
    description: "Lore items tagged reward should have title starting with reward:"
    given: "$.lore[?(@.tags && @.tags.indexOf('reward')>=0)].title"
    then:
      function: pattern
      functionOptions: { match: "^reward:" }
    severity: warn


Примечание: уникальность id и кросс-ссылки related валидируются в юнит-тестах ingest (см. ниже). В самом ТЗ требование есть.

7) README для data/knowledge/README.md (добавить в репозиторий)

Файл кампании: data/knowledge/campaigns/<campaign_id>.yaml (ru/en поддерживаются через выбор языка партии).

Домены: scene|npc|art|lore; правила id: scn_..., npc_..., art_..., lore_....

Минимальные количества: Scenes ≥5; NPC ≥3; Art ≥3; Lore ≥5.

Ingest: домен lore маппится в KnowledgeItem(domain="lore"); item_id="lore::<lore_id>".

Быстрый тест: GET /v1/knowledge/search?q=<term> на dev/stage.

Источник истины: ссылка на JSON Schema + дата проверки (см. PR чек-лист).

8) Юнит-тесты (схема, уникальность id, ingest lore)

packages/memory37/tests/test_ingest_lore.py (пример ядра):

import json, yaml, pathlib
from jsonschema import validate, Draft202012Validator
from memory37.ingest import ingest_yaml

SCHEMA = json.load(open("schemas/campaign_content.schema.json","r",encoding="utf-8"))
DATA = yaml.safe_load(open("data/knowledge/campaigns/ashen_moon_arc.yaml","r",encoding="utf-8"))

def test_yaml_schema_valid():
    Draft202012Validator(SCHEMA).validate(DATA)

def test_ids_unique_within_sections():
    for sec in ("scenes","npcs","art","lore"):
        ids = [x["id"] for x in DATA[sec]]
        assert len(ids) == len(set(ids)), f"duplicate id in {sec}"

def test_ingest_lore_domain_and_metadata():
    items = ingest_yaml("data/knowledge/campaigns/ashen_moon_arc.yaml")
    lore = [i for i in items if i.domain=="lore"]
    assert len(lore) >= 5
    for it in lore:
        assert it.item_id.startswith("lore::")
        assert "tags" in it.metadata


Общий регресс ingest: обновить test_ingest.py при необходимости (структура без изменений).

9) Операционные моменты и наблюдаемость (выжимка)

Запуск медиа-джобов/ошибки/429: соответствуем протоколам ответов, CloudEvents, retry/backoff.

SLO/OTel и дашборды (Run/Turns, Media, Billing): метрики/трейсы/логи по шаблону.

Инциденты/DR/Feature-flags: готовность к откатам/канареечным свитчам.

10) Память37: ретрив/качество/стоимость (коротко)

Индексы и параметры: hybrid (BM25 + vector) с RRF; размеры embedding по доменам.

Бюджет контекста: ~1.2–1.8k токенов на сцену — комфортно.

Шлюзы качества: degenerate-path, lore_assert, запрет внезапных смен отношений NPC.

11) Атрибуция SRD (если применимо)

Добавьте к заметкам кампании (и/или в раздел «лицензии» в приложении) строку атрибуции CC-BY-4.0 для SRD 5.1/5.2 (формулировка по гайду SRD; без использования защищённых IP вроде Beholder/Illithid). (Источники SRD/лицензии в репозитории знаний; не включаем защищённые сущности.)

12) Как проверить (локально/CI)

Валидация схемы:

yq -oj data/knowledge/campaigns/ashen_moon_arc.yaml | \
  ajv validate -s schemas/campaign_content.schema.json -d -


Линт YAML:

spectral lint data/knowledge/campaigns/ashen_moon_arc.yaml


Тесты ingest:

export KNOWLEDGE_SOURCE_PATH=data/knowledge/campaigns/ashen_moon_arc.yaml
pytest -q packages/memory37/tests/test_ingest_lore.py


Sanity-поиск:
GET /v1/knowledge/search?q=moon → получить элементы scene|npc|art|lore.

13) Что попадёт в PR (структура)
data/knowledge/campaigns/ashen_moon_arc.yaml
schemas/campaign_content.schema.json
.spectral.yaml
data/knowledge/README.md
packages/memory37/src/memory37/ingest.py        # _lore_to_knowledge(...)
packages/memory37/tests/test_ingest_lore.py


PR-чек-лист:

 Схема валидирует YAML; Spectral без ошибок.

 Тесты ingest зелёные (pytest -q).

 /v1/knowledge/search возвращает все домены.

 «Источник истины»: ссылка на Schema/гайды + дата просмотра.