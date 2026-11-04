"""Lanza en otra ventana el vigilante sin Inventor (scripts\\vigilante_acad.bat, carpeta _pedidos_acad), si no está ya
corriendo. Uso: python lanzar_vigilante_acad.py"""
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
BAT = Path(__file__).resolve().parent / "vigilante_acad.bat"
ACT = Path.home() / "Documents" / "InventorIA" / "_pedidos_acad" / "vigilante.activo"
if ACT.exists() and time.time() - ACT.stat().st_mtime < 30:
    print("ya está corriendo (vigilante.activo reciente)")
    sys.exit(0)
subprocess.Popen(["cmd.exe", "/c", "start", "Vigilante AutoCAD", str(BAT)], cwd=str(BAT.parent),
                 creationflags=0x00000008 | 0x00000200)      # DETACHED_PROCESS | NEW_PROCESS_GROUP
for _ in range(30):
    time.sleep(1)
    if ACT.exists() and time.time() - ACT.stat().st_mtime < 10:
        print(f"vigilante AutoCAD activo {datetime.now():%H:%M:%S}")
        break
else:
    print("lanzado, pero todavía no late vigilante.activo")
