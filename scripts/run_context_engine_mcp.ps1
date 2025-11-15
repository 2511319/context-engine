param(
  [string]$ProjectRoot = "D:\project\context_engine"
)

$ErrorActionPreference = "Stop"

Set-Location -Path $ProjectRoot

$python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$server = Join-Path $ProjectRoot "mcp\server.py"
if (-not (Test-Path $python)) { throw "Python venv not found at $python" }
if (-not (Test-Path $server)) { throw "MCP server script not found at $server" }

$envFile = Join-Path $ProjectRoot ".env"
if (Test-Path $envFile) {
  Get-Content $envFile | ForEach-Object {
    if ([string]::IsNullOrWhiteSpace($_)) { return }
    if ($_ -match '^\s*#') { return }
    if ($_ -match '^\s*([^=]+)=(.*)$') {
      $key = $matches[1].Trim()
      $value = $matches[2]
      Set-Item -Path ("Env:{0}" -f $key) -Value $value
    }
  }
}

& $python $server
