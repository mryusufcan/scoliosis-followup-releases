@echo off
setlocal
cd /d "%~dp0"
echo Proje ZIP araci artik Proje Kontrol Merkezi icindedir.
call "%~dp0Proje_Araclari.bat" --page files
exit /b %ERRORLEVEL%
