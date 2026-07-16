$ErrorActionPreference = 'Stop'
$Busy = $false
$SocketTables = @('/proc/net/tcp', '/proc/net/tcp6') |
    Where-Object { Test-Path $_ } |
    ForEach-Object { Get-Content $_ }

$Port = 3700
$HexPort = '{0:X4}' -f $Port
$Listening = $SocketTables | Where-Object {
    $Fields = $_.Trim() -split '\s+'
    $Fields.Count -gt 3 -and $Fields[1] -match ":$HexPort$" -and $Fields[3] -eq '0A'
}
if ($Listening) {
    Write-Error "Port $Port is already in use."
    $Busy = $true
} else {
    Write-Host "Port $Port is available."
}

if ($Busy) { exit 1 }
Write-Host 'ModelDeck owns management port 3600, gateway port 8600, and worker ports 8610-8699.'
