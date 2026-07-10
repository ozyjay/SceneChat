$Busy = $false
foreach ($Port in 3900, 8900) {
    $Match = ss -ltn | Select-String -Pattern ":$Port\s"
    if ($Match) { Write-Error "Port $Port is already in use."; $Busy = $true }
    else { Write-Host "Port $Port is available." }
}
if ($Busy) { exit 1 }
