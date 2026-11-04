"""Sólo lectura, SIN Inventor (Apprentice): todos los archivos que referencian (recursivo) los ensambles raíz que se
conservan. Sirve para apartar lo que no se usa sin romper referencias.
Uso: python referencias_a_conservar.py <salida.json> <raiz1.iam> [<raiz2.iam> ...]
"""
import json
import sys
import time
from pathlib import Path

import win32com.client

sys.stdout.reconfigure(encoding="utf-8")
OUT = Path(sys.argv[1])
ap = None
for prog in ("Inventor.ApprenticeServer", "Inventor.ApprenticeServerComponent.1"):
    try:
        ap = win32com.client.Dispatch(prog)
        break
    except Exception:  # noqa: BLE001
        pass
res = {"raices": {}, "todos": []}
vistos = {}


def archivos(fobj):
    try:
        refs = fobj.ReferencedFileDescriptors
    except Exception:  # noqa: BLE001
        return
    for i in range(1, refs.Count + 1):
        d = refs.Item(i)
        try:
            fn = d.FullFileName
        except Exception:  # noqa: BLE001
            continue
        if fn.lower() in vistos:
            continue
        vistos[fn.lower()] = fn
        try:
            archivos(d.ReferencedFile)
        except Exception:  # noqa: BLE001
            pass


for r in sys.argv[2:]:
    t0 = time.time()
    n0 = len(vistos)
    try:
        doc = ap.Open(r)
        vistos[r.lower()] = r
        archivos(doc.File)
        doc.Close()
        res["raices"][r] = {"nuevos": len(vistos) - n0, "s": round(time.time() - t0, 1)}
    except Exception as exc:  # noqa: BLE001
        res["raices"][r] = {"error": repr(exc)}
    print(r, res["raices"][r], flush=True)
res["todos"] = sorted(vistos.values())
OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
print(len(res["todos"]))
