$ErrorActionPreference = "Stop"
$pg = (scoop prefix postgresql16) 2>$null
if (-not $pg) { throw "postgresql16 not found via scoop" }
$psql = Join-Path $pg 'bin\psql.exe'
$env:PGPASSWORD = 'postgres'

# Create role and database (idempotent)
& $psql -h 127.0.0.1 -p 5432 -U postgres -d postgres -v ON_ERROR_STOP=0 -c "CREATE ROLE codex LOGIN PASSWORD 'codex'" | Out-Null
& $psql -h 127.0.0.1 -p 5432 -U postgres -d postgres -v ON_ERROR_STOP=0 -c "CREATE DATABASE codex OWNER codex" | Out-Null

Write-Host "Bootstrap completed"