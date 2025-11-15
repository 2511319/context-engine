param(
  [string]$PgRoot,
  [string]$VsPath = "D:\\VS\\BuildTools",
  [string]$Version = "v0.8.1"
)

$ErrorActionPreference = "Stop"

if (-not $PgRoot) {
  # Try to resolve from psql
  $psql = (Get-Command psql -ErrorAction SilentlyContinue).Path
  if (-not $psql) { throw "psql not found. Ensure postgresql16 is installed and on PATH." }
  $bin = Split-Path -Parent $psql
  $PgRoot = Split-Path -Parent $bin
}

if (-not (Test-Path (Join-Path $PgRoot 'include'))) { throw "Invalid PGROOT: $PgRoot" }

# Ensure git
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
  scoop install git | Out-Null
}

$work = "D:\\project\\context_engine\\_build"
New-Item -ItemType Directory -Force -Path $work | Out-Null
Set-Location $work

if (Test-Path "$work\\pgvector") { Remove-Item -Recurse -Force "$work\\pgvector" }

# Clone
git clone --branch $Version https://github.com/pgvector/pgvector.git | Out-Null
Set-Location "$work\\pgvector"

# Build using nmake with VS environment
$vcvars = Join-Path $VsPath "VC\Auxiliary\Build\vcvars64.bat"
if (-not (Test-Path $vcvars)) { throw "vcvars64.bat not found at $vcvars" }

$env:PGROOT = $PgRoot

cmd /c "call `"$vcvars`" && nmake /F Makefile.win" | Write-Output
cmd /c "call `"$vcvars`" && nmake /F Makefile.win install" | Write-Output

# Verify installation
$lib = Join-Path $PgRoot "lib"
$ext = Join-Path $PgRoot "share\extension"
if (-not (Test-Path (Join-Path $lib 'vector.dll'))) { throw "vector.dll not installed to $lib" }
if (-not (Get-ChildItem $ext | Where-Object { $_.Name -like 'vector*' })) { throw "vector extension files missing in $ext" }

Write-Host "pgvector installed for PGROOT=$PgRoot" -ForegroundColor Green
