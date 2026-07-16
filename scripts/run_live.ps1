$ErrorActionPreference = 'Stop'
Set-Location (Join-Path $PSScriptRoot '..')
if (-not (Test-Path .venv/bin/python)) { throw 'Run scripts/setup.ps1 first.' }
$Env:SCENECHAT_MODE = 'live'
if (-not $Env:DETECTOR_BACKEND) { $Env:DETECTOR_BACKEND = 'yolo' }
if (-not $Env:MODEL_PROVIDER) {
    throw 'Set MODEL_PROVIDER explicitly to modeldeck, replay, fallback, or mock.'
}
& .venv/bin/python -m scenechat
