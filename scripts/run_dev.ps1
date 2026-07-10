$ErrorActionPreference = 'Stop'
Set-Location (Join-Path $PSScriptRoot '..')
if (-not (Test-Path .venv/bin/python)) { throw 'Run scripts/setup.ps1 first.' }
$Env:SCENECHAT_MODE = 'development'; $Env:VISION_PROVIDER = 'mock'; $Env:DETECTOR_BACKEND = 'replay'
& .venv/bin/python -m scenechat

