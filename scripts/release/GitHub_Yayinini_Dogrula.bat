@echo off
setlocal EnableExtensions
set "ROOT=%~dp0..\.."
cd /d "%ROOT%"
title Scoliosis Follow-Up - GitHub Yayin Dogrulama

echo.
echo ============================================================
echo             GITHUB YAYINI SON KONTROL
echo ============================================================
echo.

set "DEFAULT_FEED=https://github.com/mryusufcan/scoliosis-followup-releases/releases/latest/download/update.json"
echo Bu kontrol YALNIZCA yeni surumu GitHub'a yukledikten sonra kullanilir.
echo.
echo Varsayilan:
echo %DEFAULT_FEED%
echo.

set "FEED_URL="
set /p "FEED_URL=Update JSON adresi [Enter=varsayilan]: "
if not defined FEED_URL set "FEED_URL=%DEFAULT_FEED%"

powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\tools\release_acceptance.ps1" -FeedUrl "%FEED_URL%"
set "CHECK_RESULT=%ERRORLEVEL%"

echo.
if not "%CHECK_RESULT%"=="0" (
    echo GITHUB YAYIN DENETIMI BASARISIZ.
    pause
    exit /b %CHECK_RESULT%
)

echo GITHUB YAYIN DENETIMI BASARILI.
echo Yayinlanan surum yerel paketle eslesiyor.
pause
exit /b 0
