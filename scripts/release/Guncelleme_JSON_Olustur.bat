@echo off
setlocal
chcp 65001 >nul
set "ROOT=%~dp0..\.."
cd /d "%ROOT%"
title Scoliosis Follow-Up - Imzali Guncelleme Dosyasi

if not exist ".venv-build\Scripts\python.exe" goto missing_environment
if not exist ".\VERSION" goto missing_version
if not exist ".\installer\ScoliosisFollowUp_Setup.exe" goto missing_installer
if not exist ".\security_keys\integrity_private.pem" goto missing_key

set /p "APP_VERSION=" < ".\VERSION"
set "DEFAULT_URL=https://github.com/mryusufcan/scoliosis-followup-releases/releases/download/v%APP_VERSION%/ScoliosisFollowUp_Setup.exe"

echo Surum: %APP_VERSION%
echo Varsayilan kurulum adresi:
echo %DEFAULT_URL%
echo.
set /p "DOWNLOAD_URL=Kurulum EXE adresi (varsayilan icin bos birakin): "
if not defined DOWNLOAD_URL set "DOWNLOAD_URL=%DEFAULT_URL%"

if not exist ".\update.json" goto generate
echo.
echo Mevcut update.json dosyasi degistirilecek.
set /p "CONFIRM=Devam etmek icin EVET yazin: "
if /I not "%CONFIRM%"=="EVET" goto cancelled

:generate
echo.
".venv-build\Scripts\python.exe" ".\packaging\generate_update_feed.py" --version "%APP_VERSION%" --url "%DOWNLOAD_URL%" --installer ".\installer\ScoliosisFollowUp_Setup.exe" --private-key ".\security_keys\integrity_private.pem" --output ".\update.json"
if errorlevel 1 goto failed

echo.
echo HAZIR: %ROOT%\update.json
echo Bu dosyayi ve installer\ScoliosisFollowUp_Setup.exe dosyasini ayni GitHub surumune yukleyin.
echo Gizli anahtar dosyasini GitHub'a yuklemeyin.
echo.
pause
exit /b 0

:missing_environment
echo Paketleme ortami bulunamadi. Once Tam_Surum_Olustur.bat dosyasini calistirin.
goto failed

:missing_version
echo VERSION dosyasi bulunamadi.
goto failed

:missing_installer
echo Kurulum dosyasi bulunamadi. Once Tam_Surum_Olustur.bat dosyasini calistirin.
goto failed

:missing_key
echo Gizli butunluk anahtari bulunamadi: security_keys\integrity_private.pem
goto failed

:cancelled
echo.
echo Islem iptal edildi. Mevcut update.json degistirilmedi.
pause
exit /b 0

:failed
echo.
echo ISLEM BASARISIZ.
pause
exit /b 1

