# UI Smoke: Generation, Media, Party

## Предусловия

- Запущены сервисы:
  - Gateway API: `http://localhost:8000`
  - Party Sync: `http://localhost:8001`
  - Media Broker: `http://localhost:8002`
- В `.env` WebApp прописаны:
  - `VITE_API_BASE_URL=http://localhost:8000`
  - `VITE_PARTY_WS_URL=ws://localhost:8001`
  - `VITE_MEDIA_BASE_URL=http://localhost:8002`
- Включите `KNOWLEDGE_SOURCE_PATH=data/knowledge/sample.yaml` для проверки поиска (по желанию).

## Шаги

- Запуск WebApp: `npm run dev --prefix apps/webapp`
- Статус в шапке:
  - Отображается `API <версия>`; при доступности `/config` — суффикс `trace <id>`
- Generation:
  - Откройте вкладку Generation → загрузится список профилей
  - Выберите `scene.v1` → нажмите «Сгенерировать» → отобразится валидный JSON
- Media:
  - Откройте вкладку Media → `type=image` → «Заполнить пример» → «Отправить»
  - Статус перейдёт в `succeeded`, payload содержит `cdnUrl`
- Party:
  - Откройте вкладку Party → укажите `campaignId` (например, `cmp1`)
  - Нажмите «Подключиться» в двух вкладках/окнах, укажите одно и то же `campaignId`
  - Отправьте событие `{ "hello": "world" }` — второе окно получит сообщение; поздний подписчик получает реплей

