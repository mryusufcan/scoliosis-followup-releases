@echo off
setlocal
chcp 65001 >nul
set "ROOT=%~dp0..\.."
cd /d "%ROOT%"
title Scoliosis Follow-Up - Kullanici Verileri

set "APP_DATA=%LOCALAPPDATA%\ScoliosisFollowUp"
if not exist "%APP_DATA%" (
    echo Kullanici verisi klasoru henuz olusmamis:
    echo %APP_DATA%
    echo.
    echo Uygulamayi en az bir kez calistirdiktan sonra yeniden deneyin.
    pause
    exit /b 1
)

start "" "%APP_DATA%"
exit /b 0

