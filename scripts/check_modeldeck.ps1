[CmdletBinding()]
param(
    [string]$GatewayUrl = 'http://127.0.0.1:8600',
    [string]$ModelAlias = 'scenechat-vision'
)

$ErrorActionPreference = 'Stop'

$Uri = [Uri]$GatewayUrl
$LoopbackHosts = @('127.0.0.1', 'localhost', '::1')
if (
    $Uri.Scheme -notin @('http', 'https') -or
    $Uri.Host -notin $LoopbackHosts -or
    $Uri.Port -ne 8600 -or
    $Uri.AbsolutePath -ne '/' -or
    $Uri.UserInfo -or
    $Uri.Query -or
    $Uri.Fragment
) {
    throw 'ModelDeck preflight accepts only a loopback gateway URL on port 8600.'
}
if ($ModelAlias -ne 'scenechat-vision') {
    throw 'ModelDeck preflight requires the scenechat-vision public route.'
}

$BaseUrl = $GatewayUrl.TrimEnd('/')
$Models = Invoke-RestMethod -Uri "$BaseUrl/v1/models" -Method Get -TimeoutSec 3
$Route = @($Models.data) | Where-Object { $_.id -eq $ModelAlias } | Select-Object -First 1
if (-not $Route) {
    throw 'ModelDeck has not published the scenechat-vision route.'
}

$Capabilities = Invoke-RestMethod -Uri "$BaseUrl/v1/capabilities" -Method Get -TimeoutSec 3
$RouteCapabilities = $Capabilities.PSObject.Properties[$ModelAlias].Value
if (-not $RouteCapabilities.image_input -or -not $RouteCapabilities.structured_output) {
    throw 'The scenechat-vision route lacks image_input or structured_output.'
}

$Routes = Invoke-RestMethod -Uri "$BaseUrl/v1/routes" -Method Get -TimeoutSec 3
if ($Routes.cloud_fallback -ne $false) {
    throw 'ModelDeck did not confirm that cloud fallback is disabled.'
}
if (-not $Route.ready) {
    throw 'Start the SceneChat Worker in ModelDeck and wait for ready.'
}

Write-Host 'ModelDeck scenechat-vision is ready with image_input and structured_output.'
