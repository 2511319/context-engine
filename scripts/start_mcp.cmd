@echo off
setlocal

REM Root of the project
set "ROOT=%~dp0.."
cd /d "%ROOT%"
if not exist "%ROOT%\logs" mkdir "%ROOT%\logs"

REM Start local Postgres on port 5433 if not running
set "PG_BIN=%USERPROFILE%\scoop\apps\postgresql16\current\bin"
if exist "%PG_BIN%\pg_ctl.exe" (
  if not exist ".\.pgdata\postmaster.pid" (
    "%PG_BIN%\pg_ctl.exe" -D ".\.pgdata" -l ".\.pgdata\postgres.log" -o "-p 5433" start
  )
)

REM Start Neo4j Windows service (if installed and not running)
sc query "neo4j" >nul 2>&1
if %errorlevel%==0 (
  for /f "tokens=4" %%s in ('sc query "neo4j" ^| find "STATE"') do set "NEO4J_STATE=%%s"
  if /I not "%NEO4J_STATE%"=="RUNNING" (
    sc start "neo4j" >nul 2>&1
  )
)

REM Start MCP server in a minimized console, log to logs/mcp-autostart.log
if not exist "logs\mcp-autostart.log" type nul > "logs\mcp-autostart.log"
start "context-engine-mcp" /min cmd /d /c "cd /d \"%ROOT%\" && python mcp\server.py >> logs\mcp-autostart.log 2>&1"

endlocal
