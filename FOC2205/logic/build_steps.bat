@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0build_steps.ps1"
exit /b %ERRORLEVEL%
