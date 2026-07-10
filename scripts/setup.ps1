$ErrorActionPreference = 'Stop'
Set-Location (Join-Path $PSScriptRoot '..')
python3 -m venv .venv
$Prefix = & .venv/bin/python -c 'import sys; print(sys.prefix)'
if ($Prefix -ne (Join-Path (Get-Location) '.venv')) {
    throw 'Refusing to install outside the project .venv'
}
& .venv/bin/python -m pip install --upgrade pip
& .venv/bin/python -m pip install -e '.[test]'
Write-Host 'SceneChat development environment is ready.'
