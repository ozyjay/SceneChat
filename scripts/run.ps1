$ErrorActionPreference = 'Stop'
Set-Location (Join-Path $PSScriptRoot '..')

if (-not (Test-Path -PathType Leaf .venv/bin/python)) {
    throw 'Run scripts/setup.ps1 first.'
}
if (-not (Test-Path -PathType Leaf .env)) {
    throw 'Missing .env. Run scripts/setup.ps1 first.'
}

$EnvironmentLines = Get-Content .env
$ModelDeckSelected = [bool]($EnvironmentLines | Where-Object { $_ -eq 'MODEL_PROVIDER=modeldeck' })
if ($ModelDeckSelected) {
    $ModelDeckUrl = 'http://127.0.0.1:8600'
    $ModelDeckModel = 'scenechat-vision'
    $ModelDeckUrlLine = $EnvironmentLines | Where-Object { $_ -like 'MODELDECK_URL=*' } | Select-Object -First 1
    $ModelDeckModelLine = $EnvironmentLines | Where-Object { $_ -like 'MODELDECK_MODEL=*' } | Select-Object -First 1
    if ($ModelDeckUrlLine) { $ModelDeckUrl = ($ModelDeckUrlLine -split '=', 2)[1] }
    if ($ModelDeckModelLine) { $ModelDeckModel = ($ModelDeckModelLine -split '=', 2)[1] }
    try {
        & (Join-Path $PSScriptRoot 'check_modeldeck.ps1') -GatewayUrl $ModelDeckUrl -ModelAlias $ModelDeckModel
    } catch {
        Write-Warning "$($_.Exception.Message) SceneChat will still start for camera-only, replay or mock operation."
    }
}

# The project .env is authoritative. Clear inherited values for its keys so a
# previous launcher or shell session cannot silently override the configuration.
$EnvironmentLines | ForEach-Object {
    if ($_ -match '^([A-Z][A-Z0-9_]*)=') {
        Remove-Item "Env:$($Matches[1])" -ErrorAction SilentlyContinue
    }
}

$PidFile = Join-Path (Get-Location) '.scenechat.pid'
if (Test-Path -PathType Leaf $PidFile) {
    $ExistingPid = Get-Content -Raw $PidFile
    $ExistingProcess = Get-Process -Id $ExistingPid -ErrorAction SilentlyContinue
    if ($ExistingProcess) {
        Write-Host "SceneChat is already running with PID $ExistingPid."
        exit 0
    }
    Remove-Item -Force $PidFile
}

$LogDirectory = Join-Path (Get-Location) 'logs'
[void](New-Item -ItemType Directory -Force -Path $LogDirectory)
$StandardOutput = Join-Path $LogDirectory 'scenechat.log'
$StandardError = Join-Path $LogDirectory 'scenechat-error.log'
$Process = Start-Process `
    -FilePath (Resolve-Path .venv/bin/python) `
    -ArgumentList @('-m', 'scenechat') `
    -WorkingDirectory (Get-Location) `
    -RedirectStandardOutput $StandardOutput `
    -RedirectStandardError $StandardError `
    -PassThru

Start-Sleep -Seconds 2
if ($Process.HasExited) {
    throw "SceneChat failed to start. See $StandardError"
}

Set-Content -Path $PidFile -Value $Process.Id
Write-Host "SceneChat started with PID $($Process.Id)."
Write-Host 'Open http://127.0.0.1:3700/'
Write-Host "Logs: $StandardOutput and $StandardError"
