"""Lista archivos de una carpeta (sólo lectura). Uso: python listar.py <carpeta> [profundidad=3]"""
import json, os, sys
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
root = Path(sys.argv[1]); depth = int(sys.argv[2]) if len(sys.argv) > 2 else 3
out = []
for dp, dn, fn in os.walk(root):
    rel = Path(dp).relative_to(root)
    if len(rel.parts) >= depth:
        dn[:] = []
    dn[:] = [d for d in dn if d.lower() != "oldversions"]
    for f in fn:
        p = Path(dp) / f
        out.append(f"{str(p.relative_to(root))}  [{p.stat().st_size // 1024} KB]")
print("\n".join(out[:600]))
print("TOTAL", len(out))
