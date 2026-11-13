@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start-10um.ps1" -WorkDir "%CD%"
set "launcher_exit=%ERRORLEVEL%"
if not "%launcher_exit%"=="0" pause
exit /b %launcher_exit%
