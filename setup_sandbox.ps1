$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
python -m venv "$Root\sandbox\.venv"
& "$Root\sandbox\.venv\Scripts\python.exe" -m pip install --upgrade pip
& "$Root\sandbox\.venv\Scripts\python.exe" -m pip install -r "$Root\sandbox\requirements.txt"
Write-Host "Sandbox ready: $Root\sandbox\.venv\Scripts\python.exe"
