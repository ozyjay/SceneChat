$ErrorActionPreference = 'Stop'
Set-Location (Join-Path $PSScriptRoot '..')
if (-not (Test-Path .venv/bin/python)) { throw 'Run scripts/setup.ps1 first.' }
$Env:SCENECHAT_MODE = 'live'
& .venv/bin/python -m scenechat
if ($LASTEXITCODE -ne 0) { throw 'SceneChat live mode stopped with an error.' }
