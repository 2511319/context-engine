$ErrorActionPreference = "Stop"
$pg = (scoop prefix postgresql16) 2>$null
$psql = Join-Path $pg 'bin\psql.exe'
$env:PGPASSWORD = 'codex'
& $psql -h 127.0.0.1 -p 5432 -U postgres -d postgres -v ON_ERROR_STOP=0 -c "CREATE ROLE codex LOGIN PASSWORD 'codex'" | Out-Null
& $psql -h 127.0.0.1 -p 5432 -U postgres -d postgres -v ON_ERROR_STOP=0 -c "CREATE DATABASE codex OWNER codex" | Out-Null
Write-Host "Role/DB ensured"