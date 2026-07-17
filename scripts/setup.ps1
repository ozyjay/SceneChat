$ErrorActionPreference = 'Stop'
Set-Location (Join-Path $PSScriptRoot '..')
if (-not (Test-Path -PathType Leaf .env)) {
    Copy-Item .env.example .env
    Write-Host 'Created .env from .env.example.'
}
python3 -m venv .venv
if ($LASTEXITCODE -ne 0) { throw 'Failed to create the SceneChat virtual environment.' }
$Prefix = & .venv/bin/python -c 'import sys; print(sys.prefix)'
if ($LASTEXITCODE -ne 0) { throw 'Failed to inspect the SceneChat virtual environment.' }
if ($Prefix -ne (Join-Path (Get-Location) '.venv')) {
    throw 'Refusing to install outside the project .venv'
}
& .venv/bin/python -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw 'Failed to upgrade pip in the SceneChat virtual environment.' }
& .venv/bin/python -m pip install -e '.[test,camera,yoloe,yoloworld]'
if ($LASTEXITCODE -ne 0) { throw 'Failed to install SceneChat dependencies.' }
Write-Host 'SceneChat is set up. Run scripts/download.ps1 next.'
