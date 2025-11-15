param(
  [string]$ProjectRoot = "D:\project\context_engine",
  [switch]$StartMcp = $true,
  [switch]$StartBackend = $true,
  [switch]$StartFrontendDev = $false
)

$ErrorActionPreference = "Stop"

function Import-DotEnv {
  param([string]$EnvFile)
  if (-not (Test-Path $EnvFile)) { return }
  Get-Content $EnvFile | ForEach-Object {
    if ([string]::IsNullOrWhiteSpace($_)) { return }
    if ($_ -match '^\s*#') { return }
    if ($_ -match '^\s*([^=]+)=(.*)$') {
      $key = $matches[1].Trim()
      $value = $matches[2]
      Set-Item -Path ("Env:{0}" -f $key) -Value $value
    }
  }
}

function Start-ManagedProcess {
  param(
    [string]$Executable,
    [string]$Arguments,
    [string]$WorkingDirectory,
    [string]$MatchToken,
    [System.Diagnostics.ProcessWindowStyle]$WindowStyle = [System.Diagnostics.ProcessWindowStyle]::Hidden
  )

  $running = Get-Process -ErrorAction SilentlyContinue | Where-Object {
    $_.Path -and ($_.Path -eq $Executable) -and $_.CommandLine -match [Regex]::Escape($MatchToken)
  }
  if ($running) {
    Write-Host "Process already running for $MatchToken (PID(s): $($running.Id -join ', '))."
    return
  }
  Start-Process -FilePath $Executable -ArgumentList $Arguments -WorkingDirectory $WorkingDirectory -WindowStyle $WindowStyle
  Write-Host "Started process: $Executable $Arguments"
}

if (-not (Test-Path $ProjectRoot)) {
  throw "Project root '$ProjectRoot' not found."
}

$python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
  throw "Python virtual environment not found at $python. Run install.ps1 first."
}

Import-DotEnv (Join-Path $ProjectRoot ".env")

if ($StartMcp) {
  $server = Join-Path $ProjectRoot "mcp\server.py"
  if (-not (Test-Path $server)) { throw "MCP server script not found at $server" }
  Start-ManagedProcess -Executable $python -Arguments "`"$server`"" -WorkingDirectory $ProjectRoot -MatchToken "mcp\server.py"
}

if ($StartBackend) {
  $uvicornArgs = "-m uvicorn api.main:app --host 127.0.0.1 --port 8900 --reload"
  Start-ManagedProcess -Executable $python -Arguments $uvicornArgs -WorkingDirectory $ProjectRoot -MatchToken "uvicorn api.main:app" -WindowStyle Minimized
}

if ($StartFrontendDev) {
  $npm = "npm"
  $frontendDir = Join-Path $ProjectRoot "ui"
  if (-not (Test-Path (Join-Path $frontendDir "package.json"))) {
    throw "ui/package.json not found; cannot start frontend dev server."
  }
  $running = Get-Process -Name node -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -match "context-engine-ui" }
  if ($running) {
    Write-Host "Frontend dev server already running (PID(s): $($running.Id -join ', '))."
  }
  else {
    Start-Process -FilePath $npm -ArgumentList "run dev -- --host 127.0.0.1 --port 5173" -WorkingDirectory $frontendDir -WindowStyle Minimized
    Write-Host "Started Vite dev server."
  }
}
