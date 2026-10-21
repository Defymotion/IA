"""Copia piezas comerciales (sin modificarlas) a Documents\\InventorIA\\Comerciales\\<destino>.
Uso: python copiar_comerciales.py <carpeta_origen> <destino> <archivo1> [archivo2 ...]"""
import json
import shutil
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
src, dst = Path(sys.argv[1]), Path.home() / "Documents" / "InventorIA" / "Comerciales" / sys.argv[2]
dst.mkdir(parents=True, exist_ok=True)
res = {}
for f in sys.argv[3:]:
    a, b = src / f, dst / f
    if not a.exists():
        res[f] = "no existe en origen"
    elif b.exists():
        res[f] = "ya estaba"
    else:
        shutil.copy2(a, b)
        res[f] = "copiado"
print(json.dumps({"destino": str(dst), "archivos": res}, ensure_ascii=False, indent=1))
