# ТЗ (Creative) — Контент‑пак: вертикаль одной кампании

Цель: подготовить согласованный контент‑пак (вертикаль) кампании, соответствующий форматам приложения и пригодный для индексирования Memory37 и генерации сцен/медиа.

## Объём поставки
- YAML файл кампании: `data/knowledge/campaigns/<campaign_id>.yaml`.
- Минимальный состав:
  - Сцены (`scenes[]`) — ≥ 5: `{ id, title, summary (2–3 предложения), tags[], timeline[микро‑события] }`.
  - NPC (`npcs[]`) — ≥ 3: `{ id, name, archetype, summary (характер/мотивация), voice_tts? }`.
  - Артефакты (`art[]`) — ≥ 3: `{ id, prompt (краткий промпт для изображения), tags[], entities{ npc[], location[] } }`.
  - Лор/награды (`lore[]`) — ≥ 5: `{ id, title, body (короткая статья/описание награды), tags[], related{ scene?, npc? } }`.

## Качество и стиль
- Core‑fantasy: поддерживать тон и сеттинг кампании; язык — лаконичный, с гейм‑сигналами (теги/сущности).
- Безопасность/этика: следовать Lines & Veils; избегать запрещённого контента.
- Связность: сцены и NPC должны ссылаться на общий конфликт/цель; `tags` используются для поиска.

## Примеры
```
scenes:
  - id: scn_001
    title: Moon Bridge
    summary: Ancient bridge in mist; the party meets a ronin.
    tags: [moon, encounter]
    timeline:
      - Party arrives at the foggy bridge
      - A ronin blocks the way, demanding a toll
npcs:
  - id: npc_ronin
    name: Li Shen
    archetype: ronin
    summary: Wandering swordsman with a strict personal code.
    voice_tts: asian_male_light_smoke
art:
  - id: art_bridge
    prompt: moonlit misty bridge, solitary ronin with katana
    tags: [moon, mist, ronin]
    entities:
      npc: [npc_ronin]
      location: [loc_moon_bridge]
lore:
  - id: lore_reward_moon_token
    title: reward:moon_token
    body: A token that grants safe passage at moon bridges.
    tags: [reward, token]
    related:
      scene: scn_001
      npc: npc_ronin
```

## Критерии приёмки
- YAML валиден и соответствует структурам выше.
- Все `id` уникальны в пределах кампании; ссылки в `related` корректны.
- Быстрая проверка: `/v1/knowledge/search?q=<term>` на dev/staging возвращает элементы из всех доменов.

## Что должна вернуть команда
- `data/knowledge/campaigns/<campaign_id>.yaml` — основной файл кампании.
- (Опционально) ассеты для демо: `assets/<campaign_id>/...` с заглушками изображений/аудио (в прод ‑ URL в CDN указываются в ArtCard).
- `docs/creative/<campaign_id>-notes.md` — 1 страница с сеттингом/тоном и словарём тегов.
