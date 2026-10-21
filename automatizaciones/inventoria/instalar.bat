@echo off
cd /d "%~dp0"
powershell -ExecutionPolicy Bypass -File ".\instalar.ps1"
pause
