
Проблема не в самой идее, а в связке **«твоя реализация + конкретный клиент»**.
Сейчас у тебя перемешались два разных мира:

1. **ChatGPT-песочница**, где мы реально гоняем твой `context_engine` через `filesystem_d.write_file` + `shell` (тот скрин с `cd d:\project\context_engine && python tmp_run_mcp.py` — это именно она). Там действительно НЕТ generic-моста MCP→tools, поэтому приходится костылить.
2. **Codex CLI / Codex VS Code**, где как раз есть штатная поддержка MCP и сотни кастомных серверов (Context7, Playwright, Chrome DevTools и т.п.) работают «из коробки» через `config.toml`. ([developers.openai.com][1])

У тебя `context_engine` корректный MCP-сервер, но **Codex IDE его либо не поднимает, либо поднимает, но не экспортирует tools из-за конфигурации/багов расширения**.

Разберём по шагам.

---

## 1. Как ДОЛЖНО быть устроено в Codex

По официальной доке:

* MCP сервера настраиваются в `~/.codex/config.toml` в секции
  `\[mcp_servers.<имя_сервера>]`. ([developers.openai.com][1])

* Для STDIO-серверов нужно задать минимум:

  ```toml
  [mcp_servers.context_engine]
  command = "python"
  args = ["-m", "context_engine.server"]    # или свой entrypoint
  cwd = "D:\\project\\context_engine"       # важно на Windows
  startup_timeout_sec = 30                  # опционально, но полезно
  ```

* Рекомендуется включить Rust-клиент MCP:

  ````toml
  [features]
  rmcp_client = true
  ``` :contentReference[oaicite:2]{index=2}  

  ````

* После этого Codex **сам**:

  1. Спавнит процесс сервера.
  2. Делает `tools/list`.
  3. Берёт список tools и подмешивает их в список инструментов модели.
  4. Делает `tools/call` при необходимости.

Пример рабочей конфигурации для чужих MCP (filesystem, Context7, Playwright и т.п.) выглядит именно так: `\[mcp_servers.*] + command/args/cwd/env`. ([Vladimir Siedykh][2])

То есть **никакого отдельного “моста”, который ты пытался достроить в своём диалоге с ChatGPT, в Codex писать не надо** — там уже есть generic bridge.

---

## 2. Типичные причины, почему свой MCP не виден как tools

### 2.1. Неправильная секция / старая схема

Очень распространённый баг: путаница между старыми антрoпиковскими конфигами и новым форматом Codex.

В GitHub-ишью как раз описан кейс, где человек пишет:

```toml
[mcp.servers."mcp-obsidian"]
...
```

и Codex вообще не видит сервер. ([GitHub][3])

В Codex нужно **только так**:

```toml
[mcp_servers.context_engine]
...
```

Проверь, что у тебя:

* именно `mcp_servers` (через underscore, а не `mcp.servers`, не `mcp-servers`);
* имя без спецсимволов (`context_engine`, а не `context-engine@latest`). ([Vladimir Siedykh][2])

---

### 2.2. Фильтры `enabled_tools` / `disabled_tools`

В `config.toml` есть allow/deny-листы:

````toml
[mcp_servers.context_engine]
...
enabled_tools = ["get_context", "search_raw"]
# или disabled_tools = ["debug_tool"]
``` :contentReference[oaicite:6]{index=6}  

Если ты случайно:

- поставил `enabled_tools = []`  
- или там нет ни одного реального имени твоего tool,

то Codex поднимет сервер, но **ни один tool не отдаст в модель** — снаружи будет ощущение «сервер не подключился».

На время отладки просто убери оба поля, чтобы экспортировались все tools.

---

### 2.3. MCP-сервер отдаёт “битый” `tools/list`

Даже если твой Python-клиент (`PersistentMCPClient`) видит инструменты, Codex может их отфильтровать, если:

- `input_schema` невалидный JSON-Schema;
- в schema/metadata случайно просочился несерилизуемый тип (типа `UUID` без явного `str()`) — у тебя на скрине как раз был “UUID serialization issue” в `server.py`;  
- сервер при старте падает и вообще не отвечает на `tools/list`.

Практичный чек:

1. Запусти свой `context_engine` через **официальный MCP Inspector**:

   ```bash
   npx @modelcontextprotocol/inspector python server.py
````

2. Нажми `tools/list` и посмотри:

   * все ли инструменты видны;
   * нет ли ошибок сериализации.

Если inspector не видит tools или ругается, Codex будет вести себя так же. ([developers.openai.com][1])

---

### 2.4. Windows + VS Code extension — отдельный баг

Есть открытая (и довольно свежая) ишью: **CLI видит MCP, а VS Code Codex — нет**, особенно на Windows. Там прямо пишут:

* в CLI `/mcp` показывает servers и их tools;
* в VS Code — `list_mcp_resources` пустой, “no MCP servers connected”. ([GitHub][4])

Workaround из ишью:

1. Работать с MCP **только через Codex CLI**, а не через VS Code-чат.
2. VS Code-расширение пока MCP полноценно не подхватывает — это баг, а не твой конфиг.

То есть сценарий «на CLI всё ок, а в IDE пусто» сейчас, увы, официально считается проблемой расширения.

---

### 2.5. Разные окружения CLI vs VS Code

Даже при правильном `config.toml` VS Code может не уметь запустить команду:

* у расширения другой PATH;
* `python` не находится;
* относительные пути ведут не туда.

Блог по Codex MCP отдельно подчёркивает: **на Windows лучше**:

```toml
[mcp_servers.context_engine]
command = "C:\\Python312\\python.exe"        # или путь к твоему интерпретатору
args    = ["-m", "context_engine.server"]
cwd     = "D:\\project\\context_engine"
```

И проверить эту же команду в *интегрированном* терминале VS Code. ([Vladimir Siedykh][2])

---

## 3. Конкретный чек-лист для твоего `context_engine`

### Вариант 1 (оптимальный): привести всё к стандартному Codex-флоу

1. **Счистить костыли ChatGPT-стека** в голове: внутри Codex тебе не нужен `tmp_run_mcp.py`, `filesystem_d.write_file` и т.п. MCP-сервер — это просто `command + args + cwd` в `config.toml`.

2. В `~/.codex/config.toml` (или через `Codex Settings → Open config.toml`) прописать:

   ```toml
   [features]
   rmcp_client = true

   [mcp_servers.context_engine]
   command = "C:\\Python312\\python.exe"  # или "python", если PATH нормальный
   args    = ["-m", "context_engine.server"]
   cwd     = "D:\\project\\context_engine"
   startup_timeout_sec = 30
   # на время отладки НЕ ставим enabled_tools / disabled_tools
   ```

3. Проверить MCP на уровне CLI:

   ```bash
   codex mcp list          # убедиться, что context_engine включён
   codex                   # запустить TUI
   /mcp                    # посмотреть список серверов и tools
   ```

   В идеале ты должен видеть `context_engine` и listado его tools. ([developers.openai.com][1])

4. Если CLI работает, а VS Code нет — это тот самый баг расширения (см. п. 2.4). Тогда до фикса:

   * использовать MCP-функции через CLI (в отдельном терминале);
   * в VS Code использовать Codex больше как фронт без MCP-инструментов.

---

### Вариант 2: если CLI тоже не видит сервер

Тогда почти наверняка:

* либо косячный блок `[mcp_servers.context_engine]` (секция, пути, TOML-синтаксис);
* либо сервер не стартует/не отвечает на `tools/list`.

План:

1. Прогнать `config.toml` через TOML-валидатор (или `python -c "import tomllib; tomllib.loads(open('config.toml','rb').read())"`). ([Vladimir Siedykh][2])
2. Временно оставить **только один** простой MCP-сервер в конфиге (например, filesystem из примеров) и убедиться, что он работает.
3. Подключить `context_engine` вторым и смотреть, после какого шага всё ломается.
4. Параллельно проверить `context_engine` через MCP Inspector, как выше.

---

### Вариант 3 (костыльный, если VS Code с MCP совсем мёртв)

Если окажется, что:

* CLI ок,
* но тебе кровь из носу надо именно в **VS Code-чате**,
* и фикса расширения пока нет,

то можно пойти по той же схеме, что сейчас делает ChatGPT:

* дать Codex доступ только к `filesystem` + `shell` MCP;
* написать маленький скрипт-обёртку (`run_context_engine_tool.py`), который сам ходит в твой сервер (через `PersistentMCPClient`) и пишет результаты в файлы;
* в Codex-подсказках описать этот скрипт как «tool через shell».

Это работает, но это уже совсем «полумост», и я бы оставил его как запасной вариант.

---

## Как это кратко объяснить другим (или себе “на будущее”)

Формулировка для issue/документации:

> У меня есть локальный MCP-сервер `context_engine` (STDIO, Python).
> Я могу подключаться к нему через общий MCP-клиент (PersistentMCPClient / MCP Inspector), `tools/list` и `tools/call` отрабатывают, инструменты `get_context`, `search_raw`, `ingest`, `jobs_list`, `explain_plan` работают.
>
> В `~/.codex/config.toml` сервер прописан как:
>
> ```toml
> [features]
> rmcp_client = true
>
> [mcp_servers.context_engine]
> command = "C:\\Python312\\python.exe"
> args    = ["-m", "context_engine.server"]
> cwd     = "D:\\project\\context_engine"
> startup_timeout_sec = 30
> ```
>
> В Codex CLI (`codex`, `/mcp`) сервер виден / не виден (нужное подчеркнуть).
> В Codex VS Code extension инструменты `context_engine` не появляются в tool-листе, хотя другие MCP (filesystem, playwright и т.п.) работают.
> Хотел бы понять, это баг расширения (по аналогии с issue #6465) или я ещё нарушаю какие-то требования к MCP-серверу/конфигу.

---


[1]: https://developers.openai.com/codex/mcp/ "Model Context Protocol"
[2]: https://vladimirsiedykh.com/blog/codex-mcp-config-toml-shared-configuration-cli-vscode-setup-2025 "Codex MCP Configuration: TOML Setup Guide for CLI and VSCode Extension 2025"
[3]: https://github.com/openai/codex/issues/3441 "Codex does not use MCP servers defined in config.toml. · Issue #3441 · openai/codex · GitHub"
[4]: https://github.com/openai/codex/issues/6465 "MCP servers not detected in Codex VS Code extension (but working in Codex CLI) · Issue #6465 · openai/codex · GitHub"
