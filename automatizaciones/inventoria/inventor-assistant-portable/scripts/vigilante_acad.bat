@echo off
title Vigilante InventorIA AutoCAD (sin Inventor) - no cerrar
cd /d "%~dp0.."
".venv\Scripts\python.exe" "scripts\vigilante.py" --sin-inventor --carpeta _pedidos_acad
pause
