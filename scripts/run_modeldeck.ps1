$ErrorActionPreference = 'Stop'
Set-Location (Join-Path $PSScriptRoot '..')
if (-not (Test-Path .venv/bin/python)) { throw 'Run scripts/setup.ps1 first.' }
$Env:SCENECHAT_MODE = 'live'
$Env:DETECTOR_BACKEND = 'none'
$Env:MODEL_PROVIDER = 'modeldeck'
& .venv/bin/python -m scenechat
