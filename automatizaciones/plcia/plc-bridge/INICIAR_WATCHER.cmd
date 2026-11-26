@echo off
title PLC_Bridge - watcher (no cerrar)
cd /d "%~dp0"
rem Openness necesita Windows PowerShell 5.1 (.NET Framework), no pwsh 7.
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -NoExit -File "%~dp0watcher.ps1"
