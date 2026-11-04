"""Sólo lectura: estudio de una mesa giratoria en el ingreso de la celda A (layout liviano v7).
Releva (mm, coordenadas del layout):
- la giratoria de las celdas B y C (ocurrencia, archivo, matriz, caja; hijos con caja y caja local de su definición);
- todo lo de la celda A (hasta 4 niveles) cuya caja toque la zona de la giratoria (por defecto X -12400..-8800,
  Z -37400..-34200): mesas de rolos, cinta interna, rejas, barrera, pallet, robot;
- lo de primer nivel del layout que toque esa zona (robot aéreo, línea, buffers).
Uso: python l3n_giratoria_A_relevar.py <salida.json> [--zona x0,z0,x1,z1]
"""
import json
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
import inventor_mcp as inv  # noqa: E402

S = inv._safe
T0 = time.time()
LAY = Path(r"C:\DEFYMOTION\L3N\Celdas_IA\LayoutL3N_liviano_v7.iam")
OUT = Path(sys.argv[1])
ZONA = [float(v) for v in sys.argv[sys.argv.index("--zona") + 1].split(",")] if "--zona" in sys.argv else [-12400, -37400, -8800, -34200]
app = inv._inventor(start_if_needed=False)
res = {"avisos": [], "zona": ZONA}


def mread(m):
    return [[round(m.Cell(r, c) * (10 if c == 4 else 1), 4) for c in range(1, 5)] for r in range(1, 4)]


def caja_b(b):
    return [round(v * 10, 1) for v in (b.MinPoint.X, b.MinPoint.Y, b.MinPoint.Z, b.MaxPoint.X, b.MaxPoint.Y, b.MaxPoint.Z)]


def caja(o):
    return S(lambda: caja_b(o.RangeBox), None)


def arch(o):
    return S(lambda: o.ReferencedDocumentDescriptor.FullDocumentName, None)


def en_zona(c):
    return c and not (c[3] < ZONA[0] or c[0] > ZONA[2] or c[5] < ZONA[1] or c[2] > ZONA[3])


def recorrer(occs, ruta, prof, maxprof, filtro=True):
    out = []
    for o in inv._items(occs):
        c = caja(o)
        if filtro and not en_zona(c):
            continue
        nh = S(lambda: o.SubOccurrences.Count, 0)
        out.append({"n": ruta + o.Name, "f": arch(o), "c": c, "vis": S(lambda: bool(o.Visible)), "nh": nh,
                    "M": S(lambda: mread(o.Transformation))})
        if prof < maxprof and nh:
            out += recorrer(o.SubOccurrences, ruta + o.Name + "/", prof + 1, maxprof, filtro)
    return out


def buscar_giratorias(occs, ruta, prof):
    out = []
    for o in inv._items(occs):
        f = arch(o) or ""
        if "rotating" in o.Name.lower() or "rotating" in f.lower():
            e = {"n": ruta + o.Name, "f": f, "c": caja(o), "M": S(lambda: mread(o.Transformation)), "hijos": []}
            for h in inv._items(o.SubOccurrences):
                d = S(lambda: h.Definition, None)
                e["hijos"].append({"n": h.Name, "f": arch(h), "c": caja(h), "M": S(lambda: mread(h.Transformation)),
                                   "c_def": S(lambda: caja_b(d.RangeBox), None) if d is not None else None,
                                   "nh": S(lambda: h.SubOccurrences.Count, 0)})
            out.append(e)
            continue
        if prof < 4 and S(lambda: o.SubOccurrences.Count, 0):
            out += buscar_giratorias(o.SubOccurrences, ruta + o.Name + "/", prof + 1)
    return out


app.SilentOperation = True
try:
    lay = next((d for d in inv._items(app.Documents) if S(lambda d=d: Path(d.FullFileName).resolve() == LAY.resolve(), False)), None)
    lay = lay or app.Documents.Open(str(LAY), False)
    cd = lay.ComponentDefinition
    tops = list(inv._items(cd.Occurrences))
    res["tops_zona"] = [{"n": o.Name, "f": arch(o), "c": caja(o)} for o in tops if en_zona(caja(o))]
    res["giratorias"] = []
    for o in tops:
        if o.Name.startswith(("Celda_B", "Celda_C")):
            res["giratorias"] += buscar_giratorias(o.SubOccurrences, o.Name + "/", 1)
    ca = next((o for o in tops if o.Name.startswith("Celda_A")), None)
    if ca is None:
        res["avisos"].append("no encontré la celda A")
    else:
        res["celda_A"] = {"n": ca.Name, "f": arch(ca), "M": mread(ca.Transformation),
                          "zona": recorrer(ca.SubOccurrences, ca.Name + "/", 1, 4)}
    for o in tops:
        if o.Name.startswith(("Robot_Aereo", "Linea_Pallets", "Extension_")):
            res.setdefault("otros_zona", []).extend(recorrer(o.SubOccurrences, o.Name + "/", 1, 2))
except Exception as exc:  # noqa: BLE001
    import traceback
    res["error"] = repr(exc)
    res["traza"] = traceback.format_exc()[-2000:]
finally:
    S(lambda: setattr(app, "SilentOperation", False))
res["s"] = round(time.time() - T0, 1)
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps({k: (len(v) if isinstance(v, list) else v) for k, v in res.items() if k != "celda_A"}, ensure_ascii=False))
print("celda_A zona:", len(res.get("celda_A", {}).get("zona", [])))
