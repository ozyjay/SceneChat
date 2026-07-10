$ErrorActionPreference = 'Stop'

$ProcessIds = Get-ChildItem /proc -Directory -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -match '^\d+$' } |
    ForEach-Object {
        $CommandLinePath = Join-Path $_.FullName 'cmdline'
        try {
            $CommandLine = (Get-Content -Raw -Path $CommandLinePath -ErrorAction Stop) -replace "`0", ' '
            if ($CommandLine -match 'python.*-m scenechat') { [int]$_.Name }
        } catch {
            # Processes can exit while /proc is being inspected.
        }
    }

if (-not $ProcessIds) {
    Write-Host 'SceneChat is not running.'
    exit 0
}

$ProcessIds | ForEach-Object { Stop-Process -Id $_ }
Write-Host "Requested graceful SceneChat shutdown for PID(s): $($ProcessIds -join ', ')"
