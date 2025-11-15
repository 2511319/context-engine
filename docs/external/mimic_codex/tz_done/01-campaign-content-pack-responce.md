1) Область работ и формат сдачи

Что сдаём (ровно то, что просит ТЗ):

Основной YAML-файл кампании: data/knowledge/campaigns/<campaign_id>.yaml.

Минимальный состав (готовность в этом ответе): ≥5 сцен, ≥3 NPC, ≥3 арта, ≥5 элементов лора/наград — со структурами полей как в ТЗ.

(Опционально) ассеты-заглушки под демо и короткие creative-ноты по сеттингу/тону/тегам.

Критерии приёмки (DoD):

YAML валиден, структуры соблюдены; ID уникальны, related указывают существующие связи.

Быстрый sanity-тест: /v1/knowledge/search?q=<term> на dev/stage возвращает элементы из всех доменов.

2) Принятые константы для этой вертикали (согласованные ранее)

Скелет повествования: hub-and-spoke (узлы-хабы с возвратами).

Тон: dark fantasy 16+, лаконичный язык с явными «гейм-сигналами» (теги/сущности).

L10n: авторский текст — нейтральный/англ. формулировки; вывод в клиенте следует языку партии.

TTS/SSML: 2–4 голоса под архетипы, умеренный SSML.

Ретривабилити/связность: сцены и NPC подчинены одному конфликту/цели, теги — управляемый словарь.

Под бюджет LLM-контекста: 1.2–1.8k токенов на сцену (итог), что комфортно для mini-модели.

3) Структура PR (что попадёт в репозиторий)
data/
  knowledge/
    campaigns/
      ashen_moon_arc.yaml          # основной YAML контент-пака (см. ниже)
assets/
  ashen_moon_arc/
    art_bridge_mist.jpg            # заглушки для демо (опционально)
    art_witch_circle.jpg
    art_underbridge_vault.jpg
docs/
  creative/
    ashen_moon_arc-notes.md        # 1 страница: сеттинг/тон/словарь тегов


(Файлы и пути соответствуют «Что должна вернуть команда» из ТЗ.)

4) Creative-ноты кампании (docs/creative/ashen_moon_arc-notes.md)

Campaign ID: ashen_moon_arc

Elevator-pitch: «Лунный мост судит по клятвам. Пройти можно, только если правда тяжелее монет.»

Тон: dark fantasy 16+; Lines & Veils соблюдены (никаких запрещённых тем; моральная серость допустима).

Скелет: hub-and-spoke: мост ⇄ хутор контрабандистов ⇄ ведьмин лес ⇄ подмостовой сейф ⇄ дух-привратник (финал).

Цель игрока: безопасный проход и добыча «лунного жетона» (reward:moon_token) как social-key для будущих локаций.

Контролируемый словарь тегов v1:

themes: heist, intrigue, ritual, combat, exploration

locations: moon_bridge, forest, marsh, ruins, village

tone: dark_fantasy, grim, hopeful

entities: ronin, witch, smuggler, gatekeeper

misc: token, veil, oath, mist, moon

Голоса TTS (пример):

Ronin — male_smoke_light; Smuggler — female_quick_bright; Witch — female_low_gravel; Gatekeeper — «нейтральный древний».

UX-ярлыки (в клиенте): 
𝐿
𝑂
𝑅
𝐸
LORE для фактов, 
𝐺
𝐸
𝑁
−
𝐼
GEN−I для арта, 
𝐺
𝐸
𝑁
−
𝑉
GEN−V для речи, 
𝐴
𝑆
𝐾
ASK для подсказок. (см. стандарт ярлыков)

5) Основной YAML контент-пака (data/knowledge/campaigns/ashen_moon_arc.yaml)

Соответствует полям и минимальным количествам из ТЗ: scenes≥5, npcs≥3, art≥3, lore≥5.

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


Примечание по стилю/объёму: текст сцен краткий, «сигнальный» (под ретрив и под бюджет токенов), единый тон, связность через теги/сущности. Это соответствует разделу «Качество и стиль» и целям индексации/генерации.

6) Приёмка и быстрые проверки

Критерии DoD (из ТЗ):

YAML валиден, структура соблюдена; ID уникальны; related — корректные ссылки.

GET /v1/knowledge/search?q=moon (или bridge) возвращает элементы из доменов scene|npc|art|lore.

Рекомендованный sanity-чек редактору/QA:

Пробежать глазами таймлайны сцен (нет ли логических разрывов).

Открыть артефакты art_* — промпты непротиворечивы сеттингу.

Лор с тегами reward корректно помечен; используется в финальной сцене (соц-ключ).

Локализация: строки лаконичны, без неустойчивых идиом (готовы к ru/en).

В «creative-нотах» словарь тегов исчерпывающий для этой вертикали.

7) Что именно попадёт в PR (формулировка для заказчика)

Контент: data/knowledge/campaigns/ashen_moon_arc.yaml — вертикаль кампании, готовая к индексации и генерации.

Документация: docs/creative/ashen_moon_arc-notes.md — 1-страничный гайд по тону/тегам/целям.

(Опционально) ассеты-заглушки под демо: assets/ashen_moon_arc/* (в проде — ссылки CDN на ArtCard).

Ожидаемый результат после мерджа: контент автоматически подхватывается ingest’ом/поиском (как часть общей системы знаний «Память37»), хранится и выдаётся в сценах через [LORE]/подсказки, а также используется генератором арта/голоса согласно правилам проекта (ретрив/экономика токенов — см. гайд в Главе 8).