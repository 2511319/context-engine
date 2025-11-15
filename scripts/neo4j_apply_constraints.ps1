param(
  [string]$User = "neo4j"
)

$ErrorActionPreference = "Stop"

$sec = Read-Host "Enter Neo4j password for user '$User'" -AsSecureString
$BSTR = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($sec)
$PASS = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto($BSTR)

$cypher = (Get-Command cypher-shell -ErrorAction SilentlyContinue)
if (-not $cypher) { throw "cypher-shell is not found. Install Neo4j and ensure cypher-shell is on PATH." }

$repo = Split-Path -Parent $MyInvocation.MyCommand.Path
$root = Split-Path -Parent $repo

& cypher-shell -u $User -p $PASS -f (Join-Path $root "schemas/cypher/000_constraints.cql")
& cypher-shell -u $User -p $PASS -f (Join-Path $root "schemas/cypher/001_schema.cql")

Write-Host "Neo4j constraints applied." -ForegroundColor Green
