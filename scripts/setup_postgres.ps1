param(
  [string]$Host = "127.0.0.1",
  [int]$Port = 5432,
  [string]$SuperUser = "postgres"
)

$ErrorActionPreference = "Stop"

# Prompt for superuser password securely
$sec = Read-Host "Enter PostgreSQL superuser password for user '$SuperUser'" -AsSecureString
$BSTR = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($sec)
$SUPER_PASS = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto($BSTR)

# Create database/user and apply migrations
$env:PGPASSWORD = $SUPER_PASS

$psql = (Get-Command psql -ErrorAction SilentlyContinue)
if (-not $psql) { throw "psql is not found. Install PostgreSQL and ensure psql is on PATH." }

# Create user/db if not exists
$createSql = @"
DO $$
BEGIN
   IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'codex') THEN
      CREATE ROLE codex LOGIN PASSWORD 'codex';
   END IF;
   IF NOT EXISTS (SELECT FROM pg_database WHERE datname = 'codex') THEN
      CREATE DATABASE codex OWNER codex;
   END IF;
END$$;
"@

& psql -h $Host -p $Port -U $SuperUser -d postgres -v ON_ERROR_STOP=1 -c $createSql

# Ensure vector extension in target DB
& psql -h $Host -p $Port -U $SuperUser -d codex -v ON_ERROR_STOP=1 -c "CREATE EXTENSION IF NOT EXISTS vector;"

# Apply migrations using DSN from .env if present, else build DSN
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$dsn = if ($env:PG_DSN) { $env:PG_DSN } else { "postgres://codex:codex@$Host:$Port/codex" }

& (Join-Path $root "scripts/apply_migrations.ps1") -PgDsn $dsn

# Cleanup
Remove-Item Env:\PGPASSWORD

Write-Host "PostgreSQL is ready (db=codex, user=codex)." -ForegroundColor Green
