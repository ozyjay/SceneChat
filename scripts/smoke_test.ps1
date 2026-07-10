$ErrorActionPreference = 'Stop'

$BaseUrl = if ($Env:SCENECHAT_URL) { $Env:SCENECHAT_URL.TrimEnd('/') } else { 'http://127.0.0.1:8900' }

$Health = Invoke-RestMethod -Uri "$BaseUrl/api/health"
$Health | ConvertTo-Json -Depth 5
[void](Invoke-RestMethod -Uri "$BaseUrl/api/config")
[void](Invoke-WebRequest -Uri "$BaseUrl/")

Write-Host 'SceneChat smoke test passed.'
