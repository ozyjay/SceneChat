$ErrorActionPreference = 'Stop'
Set-Location (Join-Path $PSScriptRoot '..')
python3 -m venv .venv
if ($LASTEXITCODE -ne 0) { throw 'Failed to create the SceneChat virtual environment.' }
$Prefix = & .venv/bin/python -c 'import sys; print(sys.prefix)'
if ($LASTEXITCODE -ne 0) { throw 'Failed to inspect the SceneChat virtual environment.' }
if ($Prefix -ne (Join-Path (Get-Location) '.venv')) {
    throw 'Refusing to install outside the project .venv'
}
& .venv/bin/python -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw 'Failed to upgrade pip in the SceneChat virtual environment.' }
& .venv/bin/python -m pip install -e '.[test]'
if ($LASTEXITCODE -ne 0) { throw 'Failed to install SceneChat development dependencies.' }
Write-Host 'SceneChat development environment is ready.'
