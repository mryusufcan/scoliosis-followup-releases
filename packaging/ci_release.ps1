param(
    [switch]$SkipTests,
    [switch]$SkipInstaller,
    [switch]$Clean,
    [switch]$RunBenchmarks,
    [switch]$PublishGitHubRelease,
    [string]$Tag = "",
    [string]$FeedUrl = "",
    [string]$CertificateThumbprint = "",
    [string]$IntegrityPrivateKey = ""
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$version = (Get-Content -LiteralPath (Join-Path $root 'VERSION') -Raw).Trim()
if ($version -notmatch '^\d+\.\d+\.\d+$') {
    throw "VERSION dosyasında geçerli bir sürüm bulunamadı: $version"
}

$tagName = if ($Tag.Trim()) { $Tag.Trim() } else { "v$version" }
if ($tagName -notmatch '^v\d+\.\d+\.\d+$') {
    throw "Tag vX.Y.Z biçiminde olmalıdır: $tagName"
}

$logDir = Join-Path $root 'build\ci-release'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

function Invoke-ExternalStep([string]$Name, [string]$FilePath, [string[]]$Arguments) {
    $started = Get-Date
    $stdout = Join-Path $logDir "$Name.stdout.txt"
    $stderr = Join-Path $logDir "$Name.stderr.txt"
    Remove-Item -LiteralPath $stdout, $stderr -Force -ErrorAction SilentlyContinue
    Write-Host "[CI] $Name başlıyor..."
    $argumentString = ($Arguments | ForEach-Object {
        $argument = [string]$_
        if ($argument -match '[\s"]') {
            '"' + $argument.Replace('"', '\"') + '"'
        } else {
            $argument
        }
    }) -join ' '
    $process = Start-Process -FilePath $FilePath -ArgumentList $argumentString -WorkingDirectory $root `
        -NoNewWindow -Wait -PassThru -RedirectStandardOutput $stdout -RedirectStandardError $stderr
    foreach ($stream in @($stdout, $stderr)) {
        if (Test-Path -LiteralPath $stream) {
            Get-Content -LiteralPath $stream | Out-Host
        }
    }
    if ($process.ExitCode -ne 0) {
        throw "[CI] $Name başarısız oldu (exit=$($process.ExitCode)). Günlükler: $logDir\$Name.stdout.txt ve $logDir\$Name.stderr.txt"
    }
    $elapsed = ((Get-Date) - $started).TotalSeconds
    Write-Host ("[CI] {0} tamamlandı ({1:N1} s)" -f $Name, $elapsed)
}

$powershell = (Get-Command powershell.exe -ErrorAction Stop).Source
$buildScript = Join-Path $root 'packaging\build_windows.ps1'
$buildArgs = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $buildScript)
if ($Clean) { $buildArgs += '-Clean' }
if ($SkipTests) { $buildArgs += '-SkipTests' }
if ($CertificateThumbprint.Trim()) { $buildArgs += @('-CertificateThumbprint', $CertificateThumbprint.Trim()) }
if ($IntegrityPrivateKey.Trim()) { $buildArgs += @('-IntegrityPrivateKey', $IntegrityPrivateKey.Trim()) }
Invoke-ExternalStep 'build' $powershell $buildArgs

if (-not $SkipInstaller) {
    $installerScript = Join-Path $root 'packaging\build_installer.ps1'
    $installerArgs = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $installerScript)
    if ($CertificateThumbprint.Trim()) { $installerArgs += @('-CertificateThumbprint', $CertificateThumbprint.Trim()) }
    Invoke-ExternalStep 'installer' $powershell $installerArgs
}

$python = Join-Path $root '.venv-build\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) {
    throw "Build Python ortamı bulunamadı: $python"
}

$verifyScript = Join-Path $root 'packaging\verify_release.py'
$verifyArgs = @($verifyScript, '--root', $root)
if ($FeedUrl.Trim()) { $verifyArgs += @('--feed-url', $FeedUrl.Trim()) }
Invoke-ExternalStep 'verify-release' $python $verifyArgs

if ($RunBenchmarks) {
    $benchmarkScript = Join-Path $root 'tools\benchmark_worker_concurrency.py'
    $benchmarkArgs = @($benchmarkScript, '--limit', '8', '--repeats', '2', '--workers', '1,2,4')
    Invoke-ExternalStep 'worker-concurrency-benchmark' $python $benchmarkArgs
}

$exe = Join-Path $root 'dist\ScoliosisFollowUp\ScoliosisFollowUp.exe'
$installer = Join-Path $root 'installer\ScoliosisFollowUp_Setup.exe'
$manifest = Join-Path $root 'dist\ScoliosisFollowUp\runtime_integrity.json'
$artifacts = @($exe, $manifest)
if (Test-Path -LiteralPath $installer) { $artifacts += $installer }

$artifactManifest = [ordered]@{
    version = $version
    tag = $tagName
    generated_at_utc = (Get-Date).ToUniversalTime().ToString('o')
    artifacts = @(
        foreach ($path in $artifacts) {
            if (Test-Path -LiteralPath $path) {
                $item = Get-Item -LiteralPath $path
                [ordered]@{
                    path = $item.FullName.Substring($root.Length).TrimStart('\')
                    bytes = [int64]$item.Length
                    sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $path).Hash.ToLowerInvariant()
                }
            }
        }
    )
}
$artifactManifest | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $logDir 'artifacts.json') -Encoding UTF8

if ($PublishGitHubRelease) {
    $gh = (Get-Command gh.exe -ErrorAction SilentlyContinue)
    if (-not $gh) { throw 'GitHub yayınlama istendi ancak gh CLI bulunamadı.' }
    if (-not $env:GITHUB_TOKEN -and -not $env:GH_TOKEN) {
        throw 'GitHub yayınlama istendi ancak GITHUB_TOKEN veya GH_TOKEN tanımlı değil.'
    }
    $releaseFiles = @($exe)
    if (Test-Path -LiteralPath $installer) { $releaseFiles += $installer }
    $releaseFiles += (Join-Path $logDir 'artifacts.json')
    $releaseArgs = @('release', 'create', $tagName) + $releaseFiles + @('--title', "Scoliosis-Follow-Up $version", '--generate-notes', '--verify-tag')
    Invoke-ExternalStep 'github-release' $gh.Source $releaseArgs
}

Write-Host "[CI] Release hazır: $version / $tagName"
Write-Host "[CI] Artifact manifest: $logDir\artifacts.json"
Write-Host "[CI] Kullanıcı verileri: %LOCALAPPDATA%\ScoliosisFollowUp"
