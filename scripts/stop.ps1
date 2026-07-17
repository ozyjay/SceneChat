$ErrorActionPreference = 'Stop'
Set-Location (Join-Path $PSScriptRoot '..')

$PidFile = Join-Path (Get-Location) '.scenechat.pid'
if (-not (Test-Path -PathType Leaf $PidFile)) {
    Write-Host 'SceneChat is not running.'
    exit 0
}

$SceneChatPid = (Get-Content -Raw $PidFile).Trim()
if ($SceneChatPid -notmatch '^\d+$') {
    Remove-Item -Force $PidFile
    throw 'Removed an invalid SceneChat PID file.'
}

$Process = Get-Process -Id $SceneChatPid -ErrorAction SilentlyContinue
if (-not $Process) {
    Remove-Item -Force $PidFile
    Write-Host 'Removed a stale SceneChat PID file.'
    exit 0
}

Stop-Process -Id $SceneChatPid
Wait-Process -Id $SceneChatPid -Timeout 5 -ErrorAction SilentlyContinue
Remove-Item -Force $PidFile
Write-Host "SceneChat stopped (PID $SceneChatPid)."
