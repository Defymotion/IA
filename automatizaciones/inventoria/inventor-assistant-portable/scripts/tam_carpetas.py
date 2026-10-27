"""Tamaño y contenido de primer nivel de una o más carpetas (sólo lectura).
Uso: python tam_carpetas.py <ruta> [<ruta> ...]
"""
import json
import os
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")


def tam(p, limite_s=120.0):
    t, n, b = time.time(), 0, 0
    for r, ds, fs in os.walk(p):
        for f in fs:
            try:
                b += os.stat(os.path.join(r, f)).st_size
                n += 1
            except OSError:
                pass
        if time.time() - t > limite_s:
            return {"gb": round(b / 1e9, 3), "archivos": n, "parcial": True}
    return {"gb": round(b / 1e9, 3), "archivos": n}


out = []
for a in sys.argv[1:]:
    p = Path(a)
    d = {"ruta": str(p), "existe": p.exists()}
    if p.is_dir():
        d.update(tam(p))
        h = []
        for c in sorted(p.iterdir(), key=lambda x: x.name.lower()):
            e = {"nombre": c.name + ("\\" if c.is_dir() else ""),
                 "modif": time.strftime("%Y-%m-%d %H:%M", time.localtime(c.stat().st_mtime))}
            if c.is_dir():
                e.update(tam(c, 60))
            else:
                e["mb"] = round(c.stat().st_size / 1e6, 2)
            h.append(e)
        d["contenido"] = h
    elif p.is_file():
        d["mb"] = round(p.stat().st_size / 1e6, 2)
    out.append(d)
print(json.dumps(out, ensure_ascii=False, indent=1))
