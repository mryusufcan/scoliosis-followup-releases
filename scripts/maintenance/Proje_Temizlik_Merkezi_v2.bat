@echo off
setlocal
cd /d "%~dp0..\.."
echo Temizlik araci artik Proje Kontrol Merkezi icindedir.
call "%CD%\tools\Proje_Araclari.bat" --page files
exit /b %ERRORLEVEL%
