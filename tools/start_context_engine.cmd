@echo off
setlocal

REM Proxy launcher to start Context Engine stack (Postgres 5433, Neo4j service, MCP server)
call "%~dp0..\..\context_engine\scripts\start_mcp.cmd"

endlocal
