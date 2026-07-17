$ErrorActionPreference = 'Stop'
Set-Location (Join-Path $PSScriptRoot '..')

$Python = Join-Path (Get-Location) '.venv/bin/python'
if (-not (Test-Path -PathType Leaf $Python)) {
    throw 'Run scripts/setup.ps1 first.'
}

try {
    Invoke-RestMethod `
        -Uri 'http://127.0.0.1:3700/api/state' `
        -Method Get `
        -TimeoutSec 3 | Out-Null
} catch {
    throw 'SceneChat is not running on http://127.0.0.1:3700/. Run scripts/run.ps1 first.'
}

$VariableName = 'SCENECHAT_MODELDECK_ACCEPTANCE'
$PreviousValue = [Environment]::GetEnvironmentVariable($VariableName, 'Process')
$ExitCode = 1

try {
    [Environment]::SetEnvironmentVariable($VariableName, '1', 'Process')
    & $Python -m pytest tests/hardware/test_modeldeck_acceptance.py -v -s
    $ExitCode = $LASTEXITCODE
} finally {
    [Environment]::SetEnvironmentVariable($VariableName, $PreviousValue, 'Process')
}

exit $ExitCode
