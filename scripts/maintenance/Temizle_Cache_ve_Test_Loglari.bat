@echo off
setlocal
cd /d "%~dp0\..\.."

if exist .venv\Scripts\python.exe (
    set "PYTHON=.venv\Scripts\python.exe"
) else (
    set "PYTHON=python"
)

%PYTHON% scripts\maintenance\safe_cache_log_cleanup.py %*
if errorlevel 1 (
    echo Cache/log bakimi basarisiz oldu.
    exit /b 1
)

echo.
echo Varsayilan mod dry-run'dir. Gercek silme icin --apply ve CLEAN_GENERATED_OUTPUTS onayi gerekir.
pause
endlocal
