@echo off
setlocal
cd /d "%~dp0\..\.."

if exist .venv\Scripts\python.exe (
    set "PYTHON=.venv\Scripts\python.exe"
) else (
    set "PYTHON=python"
)

%PYTHON% scripts\maintenance\safe_root_temp_cleanup.py %*
if errorlevel 1 (
    echo Kok gecici dosya bakimi basarisiz oldu.
    exit /b 1
)

echo.
echo Varsayilan mod dry-run'dir. Gercek silme icin --apply ve CLEAN_ROOT_TEMP onayi gerekir.
pause
endlocal
