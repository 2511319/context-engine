# Чанкинг и символ-индексация

Цели: устойчивые чанки кода/доков и маркировка символов для улучшения ретрива.

Код (.py/.ts/.tsx)
- Python AST: классы/функции/верхнеуровневые константы.
- TypeScript AST: классы/функции/enum/экспортируемые константы.
- Fallback при недоступности AST: блоки по ~120 строк.

Классификация `router | const`
- Python router:
  - Функции/методы с декораторами `@app.(get|post|put|delete|patch)`;
  - APIRouter().(get|post|...) и файлы `routers/*.py`.
- Python const:
  - Верхнеуровневые константы `^[A-Z0-9_]+\s*=`; Enum; конфигурационные объекты.
- TypeScript router:
  - `express.Router().(get|post|...)`; NestJS `@Controller()` + `@Get/@Post/...`.
- TypeScript const:
  - `export const NAME = ...`; `enum`; конфиг-объекты.

Документация/контракты/конфиги
- `.md`, `.yaml/.yml`, `.json`, `.toml`, `.ini` — секции по заголовкам `#`/`##`/`###`.
- `.proto`, `.graphql` — индексируются в `doc_chunks` с `kind=contract`.

Санитизация
- Не индексировать: `.env`, `*.pem`, `*.key`, `id_rsa*`, `id_ed25519*`, `secrets/*`.
- Маскировать ключи/токены с плейсхолдерами `[REDACTED:...]`.

