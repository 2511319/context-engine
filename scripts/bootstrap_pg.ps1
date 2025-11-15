$ErrorActionPreference = "Stop"
$env:PGPASSWORD = "codex"

# Create role and database if missing; ignore errors if they already exist
psql -h 127.0.0.1 -p 5432 -U postgres -d postgres -v ON_ERROR_STOP=0 -c "CREATE ROLE codex LOGIN PASSWORD 'codex'" | Out-Null
psql -h 127.0.0.1 -p 5432 -U postgres -d postgres -v ON_ERROR_STOP=0 -c "CREATE DATABASE codex OWNER codex" | Out-Null
psql -h 127.0.0.1 -p 5432 -U postgres -d codex    -v ON_ERROR_STOP=1 -c "CREATE EXTENSION IF NOT EXISTS vector" | Out-Null

Write-Host "PostgreSQL bootstrap completed (db=codex, user=codex)."