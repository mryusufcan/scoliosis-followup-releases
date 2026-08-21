# Scoliosis Follow-Up - Aşama 4
# Logo ve PyInstaller spec dosyasını profesyonel klasörlere taşır.
# license_app.py aktif importlar nedeniyle kökte bırakılır.

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

Write-Host ""
Write-Host "=== Aşama 4 | Branding ve Packaging Düzenleme ===" -ForegroundColor Cyan
Write-Host "Proje: $root"
Write-Host ""

# -------------------------------------------------
# 1) Yedek
# -------------------------------------------------
$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$backupDir = Join-Path $root ".restore_points\stage4_$stamp"
New-Item -ItemType Directory -Path $backupDir -Force | Out-Null

$backupItems = @(
    "logo.png",
    "ScoliosisFollowUp.spec",
    "modular_app\run_modular.py",
    "packaging\build_windows.ps1",
    "tools\safe_cleanup.ps1"
)

foreach ($item in $backupItems) {
    $src = Join-Path $root $item
    if (Test-Path $src) {
        $dst = Join-Path $backupDir $item
        New-Item -ItemType Directory -Path (Split-Path -Parent $dst) -Force | Out-Null
        Copy-Item $src $dst -Force
    }
}

Write-Host "[YEDEK] $backupDir" -ForegroundColor Green

# -------------------------------------------------
# 2) Logo -> resources\branding
# -------------------------------------------------
$brandingDir = Join-Path $root "resources\branding"
New-Item -ItemType Directory -Path $brandingDir -Force | Out-Null

$oldLogo = Join-Path $root "logo.png"
$newLogo = Join-Path $brandingDir "logo.png"

if (Test-Path $oldLogo) {
    if (Test-Path $newLogo) {
        Copy-Item $oldLogo $newLogo -Force
        Remove-Item $oldLogo -Force
    }
    else {
        Move-Item $oldLogo $newLogo
    }
    Write-Host "[TASINDI] logo.png -> resources\branding\logo.png" -ForegroundColor Yellow
}
elseif (Test-Path $newLogo) {
    Write-Host "[OK] Logo zaten doğru konumda." -ForegroundColor Green
}

# -------------------------------------------------
# 3) run_modular.py logo yolunu güncelle
# -------------------------------------------------
$runModular = Join-Path $root "modular_app\run_modular.py"
if (Test-Path $runModular) {
    $text = Get-Content $runModular -Raw -Encoding UTF8
    $original = $text

    # PROJECT_ROOT / "logo.png"
    $text = $text.Replace('PROJECT_ROOT / "logo.png"', 'PROJECT_ROOT / "resources" / "branding" / "logo.png"')
    $text = $text.Replace("PROJECT_ROOT / 'logo.png'", "PROJECT_ROOT / 'resources' / 'branding' / 'logo.png'")

    if ($text -ne $original) {
        Set-Content $runModular $text -Encoding UTF8
        Write-Host "[DUZELTILDI] modular_app\run_modular.py logo yolu" -ForegroundColor Green
    }
    else {
        Write-Host "[BILGI] run_modular.py içinde eski logo yolu bulunamadı veya zaten güncel." -ForegroundColor DarkGray
    }
}

# -------------------------------------------------
# 4) build_windows.ps1 logo yolunu güncelle
# -------------------------------------------------
$buildWindows = Join-Path $root "packaging\build_windows.ps1"
if (Test-Path $buildWindows) {
    $text = Get-Content $buildWindows -Raw -Encoding UTF8
    $original = $text

    $text = $text.Replace('$root\logo.png', '$root\resources\branding\logo.png')
    $text = $text.Replace('"$root\logo.png;."', '"$root\resources\branding\logo.png;resources\branding"')

    if ($text -ne $original) {
        Set-Content $buildWindows $text -Encoding UTF8
        Write-Host "[DUZELTILDI] packaging\build_windows.ps1 logo yolu" -ForegroundColor Green
    }
    else {
        Write-Host "[BILGI] build_windows.ps1 içinde eski logo yolu bulunamadı veya zaten güncel." -ForegroundColor DarkGray
    }
}

# -------------------------------------------------
# 5) Spec dosyasını packaging altına taşı
# -------------------------------------------------
$oldSpec = Join-Path $root "ScoliosisFollowUp.spec"
$newSpec = Join-Path $root "packaging\ScoliosisFollowUp.spec"

if (Test-Path $oldSpec) {
    Move-Item $oldSpec $newSpec -Force
    Write-Host "[TASINDI] ScoliosisFollowUp.spec -> packaging" -ForegroundColor Yellow
}
elseif (Test-Path $newSpec) {
    Write-Host "[OK] Spec zaten packaging altında." -ForegroundColor Green
}

# -------------------------------------------------
# 6) Spec içindeki mutlak logo/main yollarını mümkünse temizle
# -------------------------------------------------
if (Test-Path $newSpec) {
    $spec = Get-Content $newSpec -Raw -Encoding UTF8
    $originalSpec = $spec

    # Kullanıcının eski mutlak yollarını proje-relative yap.
    $spec = [regex]::Replace(
        $spec,
        "['""][A-Za-z]:[/\\][^'""]*[/\\]logo\.png['""]",
        "'resources/branding/logo.png'"
    )

    $spec = [regex]::Replace(
        $spec,
        "['""][A-Za-z]:[/\\][^'""]*[/\\]main\.py['""]",
        "'main.py'"
    )

    if ($spec -ne $originalSpec) {
        Set-Content $newSpec $spec -Encoding UTF8
        Write-Host "[DUZELTILDI] packaging\ScoliosisFollowUp.spec mutlak yollar temizlendi" -ForegroundColor Green
    }
}

# -------------------------------------------------
# 7) safe_cleanup.ps1 spec yolunu güncelle
# -------------------------------------------------
$safeCleanup = Join-Path $root "tools\safe_cleanup.ps1"
if (Test-Path $safeCleanup) {
    $text = Get-Content $safeCleanup -Raw -Encoding UTF8
    $original = $text

    $text = $text.Replace("'ScoliosisFollowUp.spec'", "'packaging\ScoliosisFollowUp.spec'")
    $text = $text.Replace('"ScoliosisFollowUp.spec"', '"packaging\ScoliosisFollowUp.spec"')

    if ($text -ne $original) {
        Set-Content $safeCleanup $text -Encoding UTF8
        Write-Host "[DUZELTILDI] tools\safe_cleanup.ps1 spec yolu" -ForegroundColor Green
    }
}

# -------------------------------------------------
# 8) Bu Aşama 4 scriptini maintenance altına taşı
# -------------------------------------------------
$selfPath = Join-Path $root "04_Branding_Packaging_Duzenle.ps1"
if (Test-Path $selfPath) {
    $target = Join-Path $root "scripts\maintenance\04_Branding_Packaging_Duzenle.ps1"
    Copy-Item $selfPath $target -Force
    Write-Host "[KOPYALANDI] Aşama 4 scripti -> scripts\maintenance" -ForegroundColor DarkGray
}

Write-Host ""
Write-Host "Aşama 4 tamamlandı." -ForegroundColor Green
Write-Host ""
Write-Host "Yeni konumlar:"
Write-Host "  resources\branding\logo.png"
Write-Host "  packaging\ScoliosisFollowUp.spec"
Write-Host ""
Write-Host "Kökte bırakılan:"
Write-Host "  license_app.py  (aktif Python importu)"
Write-Host "  VERSION         (uygulama + build metadata)"
Write-Host "  update.json     (güncelleme feed çıktısı)"
Write-Host ""
Write-Host "Devam etmek icin bir tusa basin..."
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
