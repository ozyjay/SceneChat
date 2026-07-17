param(
    [ValidateSet('s', 'm', 'l', 'all')]
    [string]$Variant = 's',
    [string]$Destination = (Join-Path $PSScriptRoot '../models')
)

$ErrorActionPreference = 'Stop'
Write-Warning 'download_yoloe.ps1 is retained for compatibility; use download_detectors.ps1 for new setup.'
& (Join-Path $PSScriptRoot 'download_detectors.ps1') `
    -Detector yoloe `
    -YoloEVariant $Variant `
    -Destination $Destination
