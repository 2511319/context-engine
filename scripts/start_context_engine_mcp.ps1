param(
  [string]$ProjectRoot = "D:\project\context_engine"
)

$ErrorActionPreference = "Stop"

$python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$server = Join-Path $ProjectRoot "mcp\server.py"
if (-not (Test-Path $python)) { throw "Python venv not found at $python" }
if (-not (Test-Path $server)) { throw "MCP server script not found at $server" }

$running = Get-Process -Name python -ErrorAction SilentlyContinue | Where-Object {
  $_.Path -eq $python -and $_.CommandLine -match [Regex]::Escape($server)
}

if ($running) {
  Write-Host "context-engine MCP already running (PID(s): $($running.Id -join ', '))."
  return
}

Start-Process -FilePath $python -ArgumentList "`"$server`"" -WorkingDirectory $ProjectRoot -WindowStyle Hidden
Write-Host "context-engine MCP started in background."
