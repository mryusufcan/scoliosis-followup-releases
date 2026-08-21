@echo off
setlocal
cd /d "%~dp0\..\.."
python scripts\maintenance\restore_point_retention.py --keep-days 7 --keep-last 10 --max-auto-delete-mib 500
if errorlevel 1 (
    echo Retention dry-run basarisiz oldu.
    exit /b 1
)
echo.
echo Rapor docs klasorune yazildi. Varsayilan mod dry-run'dir; dosya silinmedi.
pause
endlocal
