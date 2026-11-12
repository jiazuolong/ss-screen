@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start-10um.ps1"
exit /b %ERRORLEVEL%
