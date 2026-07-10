$ErrorActionPreference = 'Continue'
Write-Host 'SceneChat environment check'
Get-Content /etc/os-release | Select-String '^PRETTY_NAME='
python3 --version
docker --version
podman --version
lspci | Select-String -Pattern 'VGA|3D|Display'
Get-ChildItem /dev/video* -ErrorAction SilentlyContinue
rocminfo | Select-Object -First 20
ss -ltn | Select-String -Pattern ':3900|:8900|:8000'

