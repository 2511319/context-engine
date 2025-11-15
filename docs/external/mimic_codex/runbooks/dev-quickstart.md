# Dev Quickstart

Запуск полного вертикального среза локально одной командой.

## Предусловия

- Python 3.12+
- Node.js 20+
- Зависимости Python установлены: `pip install -e . "psycopg[binary]"`
- Зависимости webapp установлены: `cd apps/webapp && npm ci`

## Запуск

```
python tools/dev_run.py --open
```

- Поднимутся сервисы: Gateway (8000), Party Sync (8001), Media Broker (8002)
- WebApp стартует на порту 4173 с переменными:
  - `VITE_API_BASE_URL=http://127.0.0.1:8000`
  - `VITE_MEDIA_BASE_URL=http://127.0.0.1:8002`
  - `VITE_PARTY_WS_URL=ws://127.0.0.1:8001`

Опционально: `--smoke` — выполнит `tools/smoke.py` для быстрой проверки.

## Остановка

Нажмите `Ctrl+C` в терминале — ланчер корректно остановит подпроцессы.

