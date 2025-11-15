$ErrorActionPreference = "Stop"
$DataDir = "D:\\project\\context_engine\\_data\\pg\\data"
$PwFile = "D:\\project\\context_engine\\_data\\pg\\pw.txt"
$pg = (scoop prefix postgresql16) 2>$null
if (-not $pg) { throw "postgresql16 not found via scoop" }

if (Test-Path $DataDir) { Remove-Item -Recurse -Force $DataDir }
New-Item -ItemType Directory -Force -Path $DataDir | Out-Null

& (Join-Path $pg 'bin\initdb.exe') -D $DataDir -U postgres -A scram-sha-256 --pwfile $PwFile -E UTF8 --locale=C
Write-Host "initdb completed"
