# Scoliosis Follow-Up - Aşama 2 DEVAM / DÜZELTME
# Önceki script yarıda kaldıysa kaldığı yerden güvenli biçimde devam eder.

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

Write-Host ""
Write-Host "=== Aşama 2 | Devam ve Düzeltme ===" -ForegroundColor Cyan
Write-Host "Proje: $root"
Write-Host ""

# Gerekli klasörleri garanti et
@(
    "scripts\build",
    "scripts\dev",
    "scripts\maintenance",
    "scripts\release"
) | ForEach-Object {
    New-Item -ItemType Directory -Path (Join-Path $root $_) -Force | Out-Null
}

# -------------------------------------------------
# 1) 01_Risksiz_Proje_Temizligi.ps1 dosyasını düzelt ve taşı
# -------------------------------------------------
$cleanupSource = Join-Path $root "01_Risksiz_Proje_Temizligi.ps1"
$cleanupTarget = Join-Path $root "scripts\maintenance\01_Risksiz_Proje_Temizligi.ps1"

if (Test-Path $cleanupSource) {
    $cleanupText = Get-Content $cleanupSource -Raw -Encoding UTF8

    $oldLine = '$root = Split-Path -Parent $MyInvocation.MyCommand.Path'
    $newLines = @'
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$root = (Resolve-Path (Join-Path $scriptDir "..\..")).Path
'@

    if ($cleanupText.Contains($oldLine)) {
        $cleanupText = $cleanupText.Replace($oldLine, $newLines.Trim())
    }

    Set-Content -Path $cleanupTarget -Value $cleanupText -Encoding UTF8
    Remove-Item $cleanupSource -Force
    Write-Host "[TASINDI] 01_Risksiz_Proje_Temizligi.ps1 -> scripts\maintenance" -ForegroundColor Yellow
}
elseif (Test-Path $cleanupTarget) {
    Write-Host "[OK] 01_Risksiz_Proje_Temizligi.ps1 zaten taşınmış." -ForegroundColor Green
}
else {
    Write-Host "[UYARI] 01_Risksiz_Proje_Temizligi.ps1 bulunamadı." -ForegroundColor DarkYellow
}

# -------------------------------------------------
# 2) Taşınmış BAT dosyalarının proje kökünü kullandığını kontrol et
# -------------------------------------------------
$batFiles = Get-ChildItem (Join-Path $root "scripts") -Recurse -File -Filter "*.bat"

foreach ($bat in $batFiles) {
    $text = Get-Content $bat.FullName -Raw -Encoding UTF8

    if ($text -match 'set "ROOT=%~dp0\.\.\\\.\."') {
        Write-Host "[OK] $($bat.FullName.Replace($root + '\',''))" -ForegroundColor DarkGreen
        continue
    }

    # Önceki script taşımış ama ROOT satırı eklememişse düzelt.
    if ($text -match 'cd /d "%~dp0"') {
        $rootBlock = 'set "ROOT=%~dp0..\.."' + "`r`n" + 'cd /d "%ROOT%"'
        $text = $text.Replace('cd /d "%~dp0"', $rootBlock)
        Set-Content -Path $bat.FullName -Value $text -Encoding UTF8
        Write-Host "[DUZELTILDI] $($bat.Name)" -ForegroundColor Yellow
    }
}

# -------------------------------------------------
# 3) Proje araçları ana menüsü
# -------------------------------------------------
$menu = @'
@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
title Scoliosis Follow-Up - Proje Araclari

:menu
cls
echo ==========================================
echo        SCOLIOSIS FOLLOW-UP PROJE ARACLARI
echo ==========================================
echo.
echo  [1] Uygulamayi hata gostererek baslat
echo  [2] Otomatik testleri calistir
echo.
echo  [3] Hizli deneme EXE olustur
echo  [4] Tam surum + installer olustur
echo.
echo  [5] Guvenli temizlik
echo  [6] Kullanici verileri ve loglari ac
echo.
echo  [7] Guncelleme JSON olustur
echo  [8] Yayin paketini dogrula
echo.
echo  [0] Cikis
echo.
set /p "SECIM=Seciminiz: "

if "%SECIM%"=="1" call ".\scripts\dev\Uygulamayi_Hata_Gostererek_Baslat.bat"
if "%SECIM%"=="2" call ".\scripts\dev\Otomatik_Testleri_Calistir.bat"
if "%SECIM%"=="3" call ".\scripts\build\Hizli_Deneme_EXE_Olustur.bat"
if "%SECIM%"=="4" call ".\scripts\build\Tam_Surum_Olustur.bat"
if "%SECIM%"=="5" call ".\scripts\maintenance\Guvenli_Temizlik_Yap.bat"
if "%SECIM%"=="6" call ".\scripts\maintenance\Kullanici_Verilerini_ve_Loglari_Ac.bat"
if "%SECIM%"=="7" call ".\scripts\release\Guncelleme_JSON_Olustur.bat"
if "%SECIM%"=="8" call ".\scripts\release\Yayin_Paketini_Dogrula.bat"
if "%SECIM%"=="0" exit /b 0

goto menu
'@

Set-Content -Path (Join-Path $root "Proje_Araclari.bat") -Value $menu -Encoding UTF8
Write-Host "[OLUSTURULDU/GUNCELLENDI] Proje_Araclari.bat" -ForegroundColor Green

# -------------------------------------------------
# 4) Kök cache temizliği
# -------------------------------------------------
$rootCache = Join-Path $root "__pycache__"
if (Test-Path $rootCache) {
    Remove-Item $rootCache -Recurse -Force
    Write-Host "[TEMIZLENDI] kök __pycache__" -ForegroundColor DarkGray
}

Write-Host ""
Write-Host "Aşama 2 tamamlandı." -ForegroundColor Green
Write-Host ""
Write-Host "Kontrol:"
Write-Host "  scripts\build"
Write-Host "  scripts\dev"
Write-Host "  scripts\maintenance"
Write-Host "  scripts\release"
Write-Host "  Proje_Araclari.bat"
Write-Host ""
Write-Host "Devam etmek icin bir tusa basin..."
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
