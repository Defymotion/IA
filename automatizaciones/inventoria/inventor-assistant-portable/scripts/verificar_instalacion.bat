@echo off
title Verificacion InventorIA
cd /d "%~dp0.."
".venv\Scripts\python.exe" "scripts\verificar_instalacion.py"
pause
