$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $root
$stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$restore = Join-Path $root (Join-Path '.restore_points' ("pre_security_hardening_1.7.7_" + $stamp))
New-Item -ItemType Directory -Force -Path $restore | Out-Null

$relativeSources = @(
    'main.py', 'VERSION', 'README.md', 'requirements.txt', 'requirements-dev.txt',
    'modular_app', 'pacs', 'dicom', 'anonymization', 'ai', 'tests', 'tools',
    'docs', 'packaging', 'resources', 'scripts', 'license_app.py', '.github'
)
$sourceItems = @($relativeSources | ForEach-Object {
    $path = Join-Path $root $_
    if (Test-Path -LiteralPath $path) { $path }
})
$archive = Join-Path $restore 'source_state_1.7.7.zip'
Compress-Archive -Path $sourceItems -DestinationPath $archive -CompressionLevel Optimal -Force

$artifactEntries = @()
$artifactPaths = @(
    @{ label = 'installer'; path = (Join-Path $root 'build\release_1.7.7\ScoliosisFollowUp_Setup_1.7.7.exe') },
    @{ label = 'signed_update_feed'; path = (Join-Path $root 'build\release_1.7.7\update.json') },
    @{ label = 'runtime_integrity'; path = (Join-Path $root 'dist\ScoliosisFollowUp\runtime_integrity.json') }
)
foreach ($item in $artifactPaths) {
    if (Test-Path -LiteralPath $item.path) {
        $file = Get-Item -LiteralPath $item.path
        $artifactEntries += [ordered]@{
            label = $item.label
            path = $file.FullName.Substring($root.Length).TrimStart('\')
            bytes = [int64]$file.Length
            sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $file.FullName).Hash.ToLowerInvariant()
        }
    }
}

$gitHead = (& git rev-parse HEAD 2>$null | Out-String).Trim()
$gitBranch = (& git branch --show-current 2>$null | Out-String).Trim()
$metadata = [ordered]@{
    created_at_utc = (Get-Date).ToUniversalTime().ToString('o')
    release_baseline = '1.7.7'
    restore_directory = $restore
    source_archive = $archive
    git_head = $gitHead
    git_branch = $gitBranch
    excluded_from_archive = @('.git', '.venv-build', 'build', 'dist', 'installer', 'dev_data', '.restore_points', 'security_keys', 'project_archives')
    private_key_note = 'security_keys is intentionally excluded; private signing keys are not duplicated into restore points.'
    published_artifacts = $artifactEntries
    release_url = 'https://github.com/mryusufcan/scoliosis-followup-releases/releases/tag/1.7.7'
    pages_url = 'https://mryusufcan.github.io/scoliosis-followup-releases/'
}
$metadata | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $restore 'restore_metadata.json') -Encoding UTF8
Write-Output $restore
Write-Output ("archive_bytes=" + (Get-Item -LiteralPath $archive).Length)
$artifactEntries | ConvertTo-Json -Depth 5
