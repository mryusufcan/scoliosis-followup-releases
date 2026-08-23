@echo off
setlocal
chcp 65001 >nul
set "ROOT=%~dp0..\.."
cd /d "%ROOT%"
title Scoliosis Follow-Up - Imzali Guncelleme Dosyasi

set "PYTHON_EXE="
if exist ".venv-build\Scripts\python.exe" set "PYTHON_EXE=.venv-build\Scripts\python.exe"
if not defined PYTHON_EXE if exist ".venv\Scripts\python.exe" set "PYTHON_EXE=.venv\Scripts\python.exe"
if not defined PYTHON_EXE goto missing_environment
if not exist ".\VERSION" goto missing_version
if not exist ".\installer\ScoliosisFollowUp_Setup.exe" goto missing_installer
if "%SCOLIOSIS_FOLLOWUP_SECURITY_DIR%"=="" set "SCOLIOSIS_FOLLOWUP_SECURITY_DIR=%LOCALAPPDATA%\ScoliosisFollowUp\security_keys"
set "INTEGRITY_PRIVATE_KEY=%SCOLIOSIS_FOLLOWUP_SECURITY_DIR%\integrity_private.pem"
if not exist "%INTEGRITY_PRIVATE_KEY%" goto missing_key

set /p "APP_VERSION=" < ".\VERSION"
set "DEFAULT_URL=https://github.com/mryusufcan/scoliosis-followup-releases/releases/download/%APP_VERSION%/ScoliosisFollowUp_Setup_%APP_VERSION%.exe"

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
"%PYTHON_EXE%" ".\packaging\generate_update_feed.py" --version "%APP_VERSION%" --url "%DOWNLOAD_URL%" --installer ".\installer\ScoliosisFollowUp_Setup.exe" --private-key "%INTEGRITY_PRIVATE_KEY%" --output ".\update.json"
if errorlevel 1 goto failed

echo.
echo HAZIR: %ROOT%\update.json
echo Bu dosyayi ve installer\ScoliosisFollowUp_Setup.exe dosyasini ayni GitHub surumune yukleyin.
echo Gizli anahtar dosyasini GitHub'a yuklemeyin.
echo.
pause
exit /b 0

:missing_environment
echo Python ortami bulunamadi. .venv veya .venv-build ortamlarindan biri gerekli.
goto failed

:missing_version
echo VERSION dosyasi bulunamadi.
goto failed

:missing_installer
echo Kurulum dosyasi bulunamadi. Once Tam_Surum_Olustur.bat dosyasini calistirin.
goto failed

:missing_key
echo Gizli butunluk anahtari bulunamadi: %INTEGRITY_PRIVATE_KEY%
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

