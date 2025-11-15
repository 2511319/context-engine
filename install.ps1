# Requires: PowerShell 5+, Python 3.12 64-bit installed and on PATH
$ErrorActionPreference = "Stop"

$venv = Join-Path $PSScriptRoot ".venv"
if (-Not (Test-Path $venv)) {
  python -m venv $venv
}

$pip = Join-Path $venv "Scripts/pip.exe"
& $pip install --upgrade pip
& $pip install -r (Join-Path $PSScriptRoot "requirements.txt")

Write-Host "Environment ready. Activate: `"$venv\Scripts\Activate.ps1`""
