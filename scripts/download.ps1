$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
Set-Location (Join-Path $PSScriptRoot '..')

$Destination = Join-Path (Get-Location) 'models'
$Artifacts = @{
    'yoloe-26s-seg.pt' = @{
        Uri = 'https://github.com/ultralytics/assets/releases/download/v8.4.0/yoloe-26s-seg.pt'
        Sha256 = '48f24206bc8680d60cbbfa296b0140da849669b9515058b72f5a945142df0654'
    }
    'mobileclip2_b.ts' = @{
        Uri = 'https://github.com/ultralytics/assets/releases/download/v8.4.0/mobileclip2_b.ts'
        Sha256 = '35d7f213e4d75f38514e4656ad3cb91158bd33e3805d8ac349f23b186f66982f'
    }
    'yolov8s-worldv2.pt' = @{
        Uri = 'https://github.com/ultralytics/assets/releases/download/v8.2.0/yolov8s-worldv2.pt'
        Sha256 = '9b2c17ab6124a913e9b3a5c170617920d91b0f01111a8479da69f00e2cf27792'
    }
    'ViT-B-32.pt' = @{
        Uri = 'https://openaipublic.azureedge.net/clip/models/40d365715913c9da98579312b702a82c18be219cc2a73407c4526f58eba950af/ViT-B-32.pt'
        Sha256 = '40d365715913c9da98579312b702a82c18be219cc2a73407c4526f58eba950af'
    }
}

[void](New-Item -ItemType Directory -Force -Path $Destination)
foreach ($Name in $Artifacts.Keys | Sort-Object) {
    $Artifact = $Artifacts[$Name]
    $Target = Join-Path $Destination $Name
    if (Test-Path -PathType Leaf $Target) {
        $ExistingHash = (Get-FileHash -Algorithm SHA256 $Target).Hash.ToLowerInvariant()
        if ($ExistingHash -eq $Artifact.Sha256) {
            Write-Host "$Name is already downloaded and verified."
            continue
        }
        throw "$Target exists but its SHA-256 checksum is not recognised. Remove it manually before retrying."
    }

    $Temporary = "$Target.part"
    try {
        Write-Host "Downloading $Name..."
        Invoke-WebRequest -Uri $Artifact.Uri -OutFile $Temporary
        $ActualHash = (Get-FileHash -Algorithm SHA256 $Temporary).Hash.ToLowerInvariant()
        if ($ActualHash -ne $Artifact.Sha256) {
            throw "Checksum verification failed for $Name."
        }
        Move-Item $Temporary $Target
        Write-Host "Verified $Target"
    } finally {
        if (Test-Path -PathType Leaf $Temporary) {
            Remove-Item $Temporary
        }
    }
}

Write-Host 'Detector artefacts are ready. Run scripts/run.ps1 to start SceneChat.'
