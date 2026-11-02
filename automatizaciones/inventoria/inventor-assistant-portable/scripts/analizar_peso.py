"""Sólo lectura, SIN Inventor (Apprentice Server, no carga geometría): qué pesa en un ensamble.
Para cada ocurrencia de primer nivel: piezas (instancias), archivos únicos, MB de archivos únicos, extensiones raras
(dwg, jt, stp...), visibles/ocultas/suprimidas; y el ranking de archivos más pesados de todo el árbol.
Uso: python analizar_peso.py <iam> <salida.json> [--niveles N]
"""
import json
import os
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

import win32com.client

sys.stdout.reconfigure(encoding="utf-8")
ruta, salida = sys.argv[1], Path(sys.argv[2])
T0 = time.time()
ap = None
for prog in ("Inventor.ApprenticeServer", "Inventor.ApprenticeServerComponent.1", "{C343ED84-A129-11D3-B799-0060B0F159EF}"):
    try:
        ap = win32com.client.Dispatch(prog)
        break
    except Exception as ex:  # noqa: BLE001
        print("no", prog, repr(ex)[:80], flush=True)
if ap is None:
    sys.exit("no pude crear el Apprentice Server")
doc = ap.Open(ruta)


def tam(f):
    try:
        return os.path.getsize(f)
    except OSError:
        return 0


def archivos(fobj, vistos):
    """Archivos referenciados (recursivo) a partir de un File de Apprentice."""
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
            archivos(d.ReferencedFile, vistos)
        except Exception:  # noqa: BLE001
            pass


def instancias(occs, cont):
    for i in range(1, occs.Count + 1):
        o = occs.Item(i)
        try:
            sub = o.SubOccurrences
            n = sub.Count
        except Exception:  # noqa: BLE001
            n = 0
        if n:
            instancias(sub, cont)
        else:
            cont["piezas"] += 1


res = {"ensamble": ruta, "mb_iam": round(tam(ruta) / 2**20, 1), "occ": []}
todos = {}
archivos(doc.File, todos)
res["archivos_unicos_total"] = len(todos)
res["mb_total"] = round(sum(tam(f) for f in todos.values()) / 2**20, 1)
res["extensiones"] = Counter(Path(f).suffix.lower() for f in todos.values())
occs = doc.ComponentDefinition.Occurrences
for i in range(1, occs.Count + 1):
    o = occs.Item(i)
    e = {"n": o.Name}
    for k in ("Visible", "Suppressed"):
        try:
            e[k] = bool(getattr(o, k))
        except Exception:  # noqa: BLE001
            pass
    try:
        fn = o.ReferencedDocumentDescriptor.FullDocumentName
    except Exception:  # noqa: BLE001
        fn = ""
    e["archivo"] = fn
    e["mb_archivo"] = round(tam(fn) / 2**20, 1)
    v = {fn.lower(): fn} if fn else {}
    try:
        archivos(o.ReferencedDocumentDescriptor.ReferencedDocument.File, v)
    except Exception as ex:  # noqa: BLE001
        e["error_refs"] = repr(ex)[:120]
    e["archivos_unicos"] = len(v)
    e["mb_unicos"] = round(sum(tam(f) for f in v.values()) / 2**20, 1)
    e["ext"] = Counter(Path(f).suffix.lower() for f in v.values())
    c = Counter()
    try:
        instancias(o.SubOccurrences, c)
    except Exception:  # noqa: BLE001
        pass
    e["piezas"] = c["piezas"]
    e["top_archivos"] = sorted(((round(tam(f) / 2**20, 1), Path(f).name) for f in v.values()), reverse=True)[:8]
    res["occ"].append(e)
    print(f"[{time.time() - T0:5.0f} s] {o.Name}: {e['piezas']} piezas, {e['archivos_unicos']} archivos, {e['mb_unicos']} MB", flush=True)
res["top_archivos"] = sorted(((round(tam(f) / 2**20, 1), f) for f in todos.values()), reverse=True)[:40]
carpetas = defaultdict(float)
for f in todos.values():
    carpetas[str(Path(f).parent)] += tam(f) / 2**20
res["top_carpetas"] = sorted(((round(v, 1), k) for k, v in carpetas.items()), reverse=True)[:20]
res["s"] = round(time.time() - T0, 1)
doc.Close()
salida.parent.mkdir(parents=True, exist_ok=True)
salida.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps({k: v for k, v in res.items() if k != "occ"}, ensure_ascii=False, indent=1)[:12000])
