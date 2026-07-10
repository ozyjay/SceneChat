$ErrorActionPreference = 'Stop'
Set-Location (Join-Path $PSScriptRoot '..')
if (-not (Test-Path .venv/bin/python)) { throw 'Run scripts/setup.ps1 first.' }
$Env:SCENECHAT_MODE = 'live'
if (-not $Env:DETECTOR_BACKEND) { $Env:DETECTOR_BACKEND = 'yolo' }
if (-not $Env:VISION_PROVIDER) { $Env:VISION_PROVIDER = 'vllm' }
& .venv/bin/python -m scenechat

