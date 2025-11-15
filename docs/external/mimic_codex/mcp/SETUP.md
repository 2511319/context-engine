# MCP FS + Git — Быстрый Старт

- Предпосылки:
  - Node.js/npm для `npx`
  - uv (или Python 3.11+ и pip) для `uvx mcp-server-git`

- Переменные окружения (пример):
  - `MCP_FS_ROOT` — корень доступа файловой системы (например, путь к репозиторию)
  - `MCP_GIT_ROOT` — рабочий каталог Git (обычно совпадает с корнем репозитория)

- Конфиг клиента (пример для Claude): `config/mcp/clients/claude.config.json`
  - Раздел `mcpServers.filesystem` — Filesystem сервер
  - Раздел `mcpServers.git` — Git сервер

- Запуск напрямую:
  - Filesystem: `npx -y @modelcontextprotocol/server-filesystem "$MCP_FS_ROOT"`
  - Git (через uv): `uvx mcp-server-git`

- Примечания:
  - Ограничивайте доступ через `MCP_FS_ROOT` (read-only по умолчанию рекомендован)
  - Для Git можно задать `GIT_WORKDIR` в окружении

