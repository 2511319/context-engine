param(
  [string]$PgDsn
)

$ErrorActionPreference = "Stop"

if (-not $PgDsn) { $PgDsn = $env:PG_DSN }
if (-not $PgDsn) { throw "PG_DSN is not set. Provide -PgDsn or set env var PG_DSN." }

$repo = Split-Path -Parent $MyInvocation.MyCommand.Path
$root = Split-Path -Parent $repo

$psql = (Get-Command psql -ErrorAction SilentlyContinue)
if (-not $psql) { throw "psql is not found. Install PostgreSQL client and ensure it's on PATH." }

& psql --set=ON_ERROR_STOP=1 --dbname "$PgDsn" --file (Join-Path $root "schemas/sql/000_init.sql")
& psql --set=ON_ERROR_STOP=1 --dbname "$PgDsn" --file (Join-Path $root "schemas/sql/010_pgvector_hnsw.sql")

Write-Host "Migrations applied to $PgDsn" -ForegroundColor Green
