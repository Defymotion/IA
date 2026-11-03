@echo off
title Vigilante InventorIA 3 (paralelo) - no cerrar
cd /d "%~dp0.."
".venv\Scripts\python.exe" "scripts\vigilante.py" --privado --carpeta _pedidos_3 --nombre InventorIA.Paralelo3 --visible
pause
