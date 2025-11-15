# UX States (Loading / Ready / Empty / Error / Unauthorized / Reconnect)

Principles
- Mobile-first lengths: titles ≤48, placeholders ≤40, CTA ≤24; snackbars 1–2 lines.
- Use native Telegram Mini Apps UI where applicable (MainButton, BackButton, Popup, HapticFeedback).
- Reconnect with exponential backoff + jitter.

Screens
- Auth / Init
  - Loading: «Проверяем данные запуска…»
  - Unauthorized: «Нет доступа. Открой Mini App из чата Telegram.» (CTA: «Открыть чат»)
  - Error: «Не удалось подтвердить запуск. Попробуй ещё раз.» (CTA: «Повторить»)
  - Ready: «Готово» (CTA: «Продолжить»)
- Campaigns
  - Empty: «У тебя ещё нет кампаний» (CTA: «Создать кампанию»)
  - Error: «Не вышло загрузить кампании. Попробуй снова.»
- Scene/Generation
  - Loading: «Готовим сцену…»
  - Empty: «Здесь пока пусто»
  - Error: «Не вышло сгенерировать сцену. Повторим?»
- Media
  - Loading: «Генерируем медиа…»
  - Done: toast «Медиа готово»
  - Error: «Не удалось получить медиа. Повторим?»
- WS/Party
  - Connected: «Онлайн»
  - Connecting: «Пытаемся подключиться…»
  - Disconnected: «Связь потеряна. Пытаемся подключиться…»

Notes
- Show correlation code (trace id short) on error details when available.
- Do not block primary action with snackbars.

Source of truth (reviewed 2025-10-31 18:36 UTC)
- Telegram Mini Apps — core.telegram.org
- WCAG 2.2 AA — w3.org
- Backoff with jitter — aws.amazon.com/architecture
