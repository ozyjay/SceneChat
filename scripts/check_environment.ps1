$ErrorActionPreference = 'Continue'
Write-Host 'SceneChat environment check'
Get-Content /etc/os-release | Select-String '^PRETTY_NAME='
python3 --version
docker --version
podman --version
lspci | Select-String -Pattern 'VGA|3D|Display'
Get-ChildItem /dev/video* -ErrorAction SilentlyContinue
rocminfo | Select-Object -First 20
Write-Host 'Relevant listening ports:'
$RelevantPorts = 3900, 8900, 8000
$Listeners = @('/proc/net/tcp', '/proc/net/tcp6') |
    Where-Object { Test-Path $_ } |
    ForEach-Object { Get-Content $_ } |
    ForEach-Object {
        $Fields = $_.Trim() -split '\s+'
        if ($Fields.Count -gt 3 -and $Fields[3] -eq '0A') {
            $HexPort = ($Fields[1] -split ':')[-1]
            [Convert]::ToInt32($HexPort, 16)
        }
    } |
    Where-Object { $_ -in $RelevantPorts } |
    Sort-Object -Unique
if ($Listeners) { $Listeners | ForEach-Object { Write-Host "Port $_ is listening." } }
else { Write-Host 'None.' }
