"""Busca archivos CAD por patrón (sólo lectura) en Documentos y Escritorio/Descargas.
Uso: python buscar_archivos.py "ADN-32" ["HNA-32" ...]
"""
import json
import os
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
pats = [p.lower() for p in sys.argv[1:]]
roots = [Path.home() / d for d in ("Documents", "Desktop", "Downloads", "OneDrive")]
roots.append(Path("C:/Users/Public/Documents/Autodesk"))
EXT = {".ipt", ".iam", ".stp", ".step", ".igs", ".iges", ".sat", ".x_t"}
hits = {p: [] for p in pats}
for root in roots:
    if not root.exists():
        continue
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d.lower() not in ("oldversions", "$recycle.bin", "appdata")]
        for f in filenames:
            fl = f.lower()
            if Path(fl).suffix in EXT:
                for p in pats:
                    if p in fl and len(hits[p]) < 40:
                        hits[p].append(str(Path(dirpath) / f))
print(json.dumps(hits, ensure_ascii=False, indent=1))
