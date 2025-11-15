param(
  [string]$User = "neo4j",
  [string]$Password = "codex1234",
  [string]$InstallDir = "D:\\infra\\neo4j",
  [string]$Neo4jZipUrl = "https://dist.neo4j.org/neo4j-community-5.22.0-windows.zip",
  [int]$WaitSeconds = 120
)

$ErrorActionPreference = "Stop"

function Write-Step($Text) {
  Write-Host ("[neo4j-setup] {0}" -f $Text)
}

function Wait-Port($Port, $TimeoutSec) {
  $deadline = (Get-Date).AddSeconds($TimeoutSec)
  while ((Get-Date) -lt $deadline) {
    try {
      $res = Test-NetConnection -ComputerName 127.0.0.1 -Port $Port -WarningAction SilentlyContinue
      if ($res.TcpTestSucceeded) { return $true }
    } catch { }
    Start-Sleep -Seconds 2
  }
  return $false
}

function Get-Neo4jBin {
  $cmd = Get-Command neo4j -ErrorAction SilentlyContinue
  if ($cmd) {
    return Split-Path -Parent $cmd.Source
  }
  return $null
}

function Install-Neo4jManual {
  param(
    [string]$InstallDir,
    [string]$ZipUrl
  )

  New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
  $zipPath = Join-Path $InstallDir "neo4j.zip"
  Write-Step "Downloading Neo4j from $ZipUrl ..."
  Invoke-WebRequest -UseBasicParsing -Uri $ZipUrl -OutFile $zipPath
  Expand-Archive -Path $zipPath -DestinationPath $InstallDir -Force
  Remove-Item $zipPath -Force

  $folder = Get-ChildItem $InstallDir -Directory | Where-Object { $_.Name -like "neo4j*" } | Sort-Object LastWriteTime -Descending | Select-Object -First 1
  if (-not $folder) {
    throw "Neo4j archive extracted but installation directory not found under $InstallDir"
  }
  return Join-Path $folder.FullName "bin"
}

function Ensure-Neo4jBin {
  param(
    [string]$InstallDir,
    [string]$ZipUrl
  )

  $bin = Get-Neo4jBin
  if ($bin) { return $bin }

  if (Get-Command scoop -ErrorAction SilentlyContinue) {
    try {
      scoop bucket add extras | Out-Null
    } catch { }
    try {
      scoop install neo4j-lts | Out-Null
      $bin = Get-Neo4jBin
      if ($bin) { return $bin }
      Write-Warning "scoop neo4j-lts installation finished but binaries are still unavailable. Falling back to manual install."
    } catch {
      Write-Warning "scoop neo4j-lts install failed: $($_.Exception.Message). Falling back to manual install."
    }
  } else {
    Write-Warning "Scoop not found; proceeding with manual Neo4j install."
  }

  return Install-Neo4jManual -InstallDir $InstallDir -ZipUrl $ZipUrl
}

$neo4jBin = Ensure-Neo4jBin -InstallDir $InstallDir -ZipUrl $Neo4jZipUrl
$neo4jExe = Join-Path $neo4jBin "neo4j.bat"
$neo4jAdmin = Join-Path $neo4jBin "neo4j-admin.bat"
$cypherShell = Join-Path $neo4jBin "cypher-shell.bat"

Write-Step "Using Neo4j binaries from $neo4jBin"

try {
  & $neo4jAdmin dbms set-initial-password $Password | Out-Null
  Write-Step "Initial password set."
} catch {
  Write-Warning "set-initial-password: $($_.Exception.Message)"
}

if (-not (Get-Service -Name neo4j -ErrorAction SilentlyContinue)) {
  Write-Step "Installing Windows service..."
  & $neo4jExe windows-service install | Write-Output
}

Write-Step "Starting Neo4j service..."
& $neo4jExe start | Write-Output

if (-not (Wait-Port -Port 7687 -TimeoutSec $WaitSeconds)) {
  throw "Neo4j failed to open port 7687 within $WaitSeconds seconds. Check neo4j.log."
}

$root = Split-Path -Parent $PSScriptRoot
$constraints = Join-Path $root "schemas/cypher/000_constraints.cql"
$schema = Join-Path $root "schemas/cypher/001_schema.cql"

Write-Step "Applying constraints..."
& $cypherShell -u $User -p $Password -a bolt://127.0.0.1:7687 -f $constraints
& $cypherShell -u $User -p $Password -a bolt://127.0.0.1:7687 -f $schema

Write-Host "Neo4j is ready. User='$User'. Constraints and indexes applied." -ForegroundColor Green
