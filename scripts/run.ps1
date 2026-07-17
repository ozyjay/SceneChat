$ErrorActionPreference = 'Stop'
Set-Location (Join-Path $PSScriptRoot '..')

if (-not (Test-Path -PathType Leaf .venv/bin/python)) {
    throw 'Run scripts/setup.ps1 first.'
}
if (-not (Test-Path -PathType Leaf .env)) {
    throw 'Missing .env. Run scripts/setup.ps1 first.'
}

# The project .env is authoritative. Clear inherited values for its keys so a
# previous launcher or shell session cannot silently override the configuration.
Get-Content .env | ForEach-Object {
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

$StandardOutput = Join-Path (Get-Location) 'scenechat.log'
$StandardError = Join-Path (Get-Location) 'scenechat-error.log'
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
