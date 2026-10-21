"""Reinicia el vigilante (para que tome una versión nueva de vigilante.py) sin intervención del usuario.
Lo lanza el propio vigilante como pedido: deja el resultado, marca el pedido como hecho, abre un vigilante nuevo
en otra ventana y cierra el viejo (su proceso padre).
Uso (pedido): {"script": "reiniciar_vigilante.py", "args": ["pNNN"]}
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

rid = sys.argv[1]
ROOT = Path(__file__).resolve().parents[1]
JOBS = Path.home() / "Documents" / "InventorIA" / "_pedidos"
padre = os.getppid()
(JOBS / f"{rid}.resultado.json").write_text(json.dumps(
    {"id": rid, "script": "reiniciar_vigilante.py", "codigo_salida": 0,
     "salida": f"Vigilante viejo (pid {padre}) cerrado; vigilante nuevo lanzado en otra ventana."},
    ensure_ascii=False, indent=1), encoding="utf-8")
job = JOBS / f"{rid}.json"
if job.exists():
    job.rename(job.with_suffix(".hecho"))
bat = ROOT / "scripts" / "vigilante.bat"
subprocess.Popen(["cmd", "/c", "start", "Vigilante InventorIA", str(bat)], cwd=str(ROOT),
                 creationflags=0x00000008 | 0x00000200)      # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
time.sleep(1)
try:
    import win32api
    import win32con
    h = win32api.OpenProcess(win32con.PROCESS_TERMINATE, False, padre)
    win32api.TerminateProcess(h, 0)
except Exception as exc:  # noqa: BLE001
    print("No pude cerrar el vigilante viejo:", exc)
