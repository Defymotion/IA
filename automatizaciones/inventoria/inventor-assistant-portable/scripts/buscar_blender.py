"""Busca blender.exe en las ubicaciones habituales y muestra su versión (sólo lectura). Uso: python buscar_blender.py"""
import json
import os
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
raices = [Path(os.environ.get("ProgramFiles", r"C:\Program Files")), Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")),
          Path(os.environ.get("LOCALAPPDATA", "")) / "Programs", Path.home() / "AppData" / "Roaming" / "Blender Foundation",
          Path(r"C:\Program Files\WindowsApps"), Path(r"C:\Program Files (x86)\Steam\steamapps\common")]
res = {"encontrados": [], "avisos": []}
for r in raices:
    if not r.exists():
        continue
    try:
        for p in r.glob("**/blender.exe") if "Blender" in str(r) else list(r.glob("Blender*/blender.exe")) + list(r.glob("Blender*/*/blender.exe")):
            res["encontrados"].append(str(p))
    except Exception as e:  # noqa: BLE001
        res["avisos"].append(f"{r}: {e!r}"[:200])
try:
    w = subprocess.run(["where", "blender"], capture_output=True, text=True, timeout=20)
    res["where"] = w.stdout.strip().splitlines()
except Exception as e:  # noqa: BLE001
    res["where_error"] = repr(e)
for exe in dict.fromkeys(res["encontrados"] + res.get("where", [])):
    try:
        v = subprocess.run([exe, "--version"], capture_output=True, text=True, timeout=120)
        res.setdefault("versiones", {})[exe] = v.stdout.strip().splitlines()[:3]
    except Exception as e:  # noqa: BLE001
        res.setdefault("versiones", {})[exe] = repr(e)[:200]
print(json.dumps(res, ensure_ascii=False, indent=1))
