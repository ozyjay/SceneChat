$Processes = Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'python.*-m scenechat' }
if (-not $Processes) { Write-Host 'SceneChat is not running.'; exit 0 }
$Processes | ForEach-Object { Stop-Process -Id $_.ProcessId }
Write-Host 'Requested graceful SceneChat shutdown.'

