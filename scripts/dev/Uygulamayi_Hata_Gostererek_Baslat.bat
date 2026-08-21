@echo off
setlocal
chcp 65001 >nul
set "ROOT=%~dp0..\.."
cd /d "%ROOT%"
title Scoliosis Follow-Up - Gelistirme Baslaticisi

if exist ".venv-build\Scripts\python.exe" (
    ".venv-build\Scripts\python.exe" ".\main.py"
    set "APP_RESULT=%ERRORLEVEL%"
    goto finished
)

where python.exe >nul 2>nul
if not errorlevel 1 (
    python.exe ".\main.py"
    set "APP_RESULT=%ERRORLEVEL%"
    goto finished
)

where py.exe >nul 2>nul
if not errorlevel 1 (
    py.exe -3 ".\main.py"
    set "APP_RESULT=%ERRORLEVEL%"
    goto finished
)

echo Python bulunamadi. Once Python 3 kurun veya tam paketleme islemini calistirin.
pause
exit /b 1

:finished
echo.
if not "%APP_RESULT%"=="0" (
    echo Uygulama hata koduyla kapandi: %APP_RESULT%
    echo Hata ayrintisi yukarida gorunuyor.
) else (
    echo Uygulama normal olarak kapandi.
)
echo.
pause
exit /b %APP_RESULT%

