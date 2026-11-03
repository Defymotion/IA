@echo off
title Vigilante InventorIA 2 (paralelo) - no cerrar
cd /d "%~dp0.."
".venv\Scripts\python.exe" "scripts\vigilante.py" --privado --carpeta _pedidos_2 --nombre InventorIA.Paralelo2 --visible
pause
