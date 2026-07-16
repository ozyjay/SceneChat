param(
    [ValidateSet('s', 'm', 'l', 'all')]
    [string]$Variant = 's',
    [string]$Destination = (Join-Path $PSScriptRoot '../models')
)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$ReleaseBase = 'https://github.com/ultralytics/assets/releases/download/v8.4.0'
$Artifacts = @{
    'yoloe-26s-seg.pt' = '48f24206bc8680d60cbbfa296b0140da849669b9515058b72f5a945142df0654'
    'yoloe-26m-seg.pt' = '585f5ec9028fd358035da8d860c27c56be285a795cba2076fba536a4391c2c83'
    'yoloe-26l-seg.pt' = 'a612d2d505f24e14d87ec82d688b823b6cb600646664f16125ce6c84ce360da9'
    'mobileclip2_b.ts' = '35d7f213e4d75f38514e4656ad3cb91158bd33e3805d8ac349f23b186f66982f'
}

$SelectedModels = if ($Variant -eq 'all') {
    @('yoloe-26s-seg.pt', 'yoloe-26m-seg.pt', 'yoloe-26l-seg.pt')
} else {
    ,"yoloe-26$Variant-seg.pt"
}
$Names = @($SelectedModels) + @('mobileclip2_b.ts')
[void](New-Item -ItemType Directory -Force -Path $Destination)
$Destination = (Resolve-Path $Destination).Path

foreach ($Name in $Names) {
    $Target = Join-Path $Destination $Name
    $ExpectedHash = $Artifacts[$Name]
    if (Test-Path $Target) {
        $ExistingHash = (Get-FileHash -Algorithm SHA256 $Target).Hash.ToLowerInvariant()
        if ($ExistingHash -eq $ExpectedHash) {
            Write-Host "$Name is already downloaded and verified."
            continue
        }
        throw "$Target exists but its SHA-256 checksum is not recognised. Remove it manually before retrying."
    }

    $Temporary = "$Target.part"
    try {
        Write-Host "Downloading $Name..."
        Invoke-WebRequest -Uri "$ReleaseBase/$Name" -OutFile $Temporary
        $ActualHash = (Get-FileHash -Algorithm SHA256 $Temporary).Hash.ToLowerInvariant()
        if ($ActualHash -ne $ExpectedHash) {
            throw "Checksum verification failed for $Name."
        }
        Move-Item $Temporary $Target
        Write-Host "Verified $Target"
    } finally {
        if (Test-Path $Temporary) { Remove-Item $Temporary }
    }
}

Write-Host 'YOLOE artefacts are ready. SceneChat will not download weights at start-up.'
