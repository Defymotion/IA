"""Sólo lectura: relevamiento de la celda B (Celda_B_existente) y de las rejas de A y B para la simulación v5.
Escribe Analisis\\L3N\\sim_relevamiento_B.json:
- celda_B: ocurrencias en 3 niveles (nombre, archivo, matriz y caja en coordenadas del layout, visibilidad);
- kuka_B: robot armado (matriz, eslabones con matriz relativa y archivo);
- grippers: todo ensamble cuyo nombre o archivo diga "gripper" (caja local, hijos con caja local, módulos de pala
  con su restricción de apertura);
- rejas: columnas y paneles de A y B (archivo, matriz, caja) y los parámetros del panel Fademaq;
- piezas: caja local (RangeBox de la definición) de cada archivo de pieza relevado, para pasar de matriz a volumen.
Uso: python l3n_sim_relevar_B.py
"""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
import inventor_mcp as inv  # noqa: E402

S = inv._safe
TOP = Path(r"C:\DEFYMOTION\L3N\Celdas_IA\LayoutL3N_Celdas.iam")
OUT = Path.home() / "Documents" / "InventorIA" / "Analisis" / "L3N" / "sim_relevamiento_B.json"
app = inv._inventor(start_if_needed=False)
res = {"avisos": []}


def its(x):
    """Ítems de una colección COM (o lista vacía si no hay colección)."""
    if x is None or isinstance(x, list):
        return x or []
    try:
        return inv._items(x)
    except Exception:  # noqa: BLE001
        return []


def mread(m):
    return [[round(m.Cell(r, c) * (10 if (c == 4 and r < 4) else 1), 4) for c in range(1, 5)] for r in range(1, 5)]


def bx(b):
    return [round(v * 10, 1) for v in (b.MinPoint.X, b.MinPoint.Y, b.MinPoint.Z, b.MaxPoint.X, b.MaxPoint.Y, b.MaxPoint.Z)]


def caja(o):
    b = S(lambda: o.RangeBox, None)
    return None if b is None else bx(b)


def arch(o):
    return S(lambda: o.Definition.Document.FullFileName, None)


def lista(occs, prof=1, maxprof=1, ruta=""):
    out = []
    for o in inv._items(occs):
        e = {"n": ruta + o.Name, "f": arch(o), "M": S(lambda: mread(o.Transformation)), "c": caja(o),
             "vis": S(lambda: o.Visible), "sup": S(lambda: o.Suppressed), "nh": S(lambda: o.SubOccurrences.Count, 0)}
        out.append(e)
        if prof < maxprof and e["nh"] and not e["sup"]:
            out += lista(o.SubOccurrences, prof + 1, maxprof, ruta + o.Name + "/")
    return out


def params(doc):
    out = []
    for p in its(S(lambda: doc.ComponentDefinition.Parameters.ModelParameters, None)):
        out.append({"n": S(lambda: p.Name), "expr": S(lambda: p.Expression), "v": S(lambda: round(p.Value, 5))})
    for p in its(S(lambda: doc.ComponentDefinition.Parameters.UserParameters, None)):
        out.append({"n": S(lambda: p.Name), "expr": S(lambda: p.Expression), "v": S(lambda: round(p.Value, 5)), "user": True})
    return out


def feats(doc):
    out = []
    for f in its(S(lambda: doc.ComponentDefinition.Features, None)):
        out.append({"n": S(lambda: f.Name), "tipo": S(lambda: f.Type), "sup": S(lambda: f.Suppressed)})
    return out


app.SilentOperation = True
try:
    top = next((d for d in inv._items(app.Documents) if S(lambda: Path(d.FullFileName).resolve() == TOP.resolve(), False)), None)
    top = top or app.Documents.Open(str(TOP), False)
    occ = {o.Name: o for o in inv._items(top.ComponentDefinition.Occurrences)}
    celB = occ["Celda_B_existente:1"]
    res["celda_B_M"] = mread(celB.Transformation)
    res["celda_B"] = lista(celB.SubOccurrences, 1, 3)
    sub = {o.Name: o for o in inv._items(celB.SubOccurrences)}

    # robot armado de B (puede estar dentro de un subensamble)
    def buscar(occs, pred, prof=0):
        for o in its(occs):
            if pred(o):
                return o
            if prof < 3 and not S(lambda: o.Suppressed, False):
                r = buscar(its(S(lambda: o.SubOccurrences, None)), pred, prof + 1)
                if r is not None:
                    return r
        return None

    kuka = buscar(celB.SubOccurrences, lambda o: Path(arch(o) or "").name.upper().startswith("KUKA") or o.Name.upper().startswith("KUKA"))
    if kuka is not None:
        res["kuka_B"] = {"n": kuka.Name, "f": arch(kuka), "M_layout": mread(kuka.Transformation), "vis": S(lambda: kuka.Visible),
                         "links": {o.Name: {"f": arch(o), "M_rel": mread(o.Transformation),
                                            "c_def": S(lambda: bx(o.Definition.RangeBox))} for o in inv._items(kuka.Definition.Occurrences)}}
    # grippers (A y B)
    gr = []
    for celda, oc in (("A", occ["Celda_A_L3N:1"]), ("B", celB)):
        def todos(occs, ruta, prof=0):
            for o in its(occs):
                if S(lambda: o.Suppressed, False):
                    continue
                f = Path(arch(o) or "").name
                if "gripper" in (o.Name + f).lower() and f.lower().endswith(".iam"):
                    yield ruta + o.Name, o
                elif prof < 3:
                    yield from todos(its(S(lambda: o.SubOccurrences, None)), ruta + o.Name + "/", prof + 1)
        for ruta, g in todos(oc.SubOccurrences, ""):
            gd = g.Definition
            hijos, mods = [], {}
            for o in inv._items(gd.Occurrences):
                hijos.append({"n": o.Name, "f": Path(arch(o) or "").name, "c": caja(o), "M_rel": S(lambda: mread(o.Transformation))})
                ap = next((c for c in its(S(lambda: o.Definition.Constraints, None)) if "apertura" in S(lambda: c.Name.lower(), "")), None)
                if ap is not None:
                    mods[o.Name] = {"apertura": S(lambda: ap.Name), "valor_mm": S(lambda: round(ap.Offset.Value * 10, 2)), "c": caja(o)}
            gr.append({"celda": celda, "ruta": ruta, "f": arch(g), "vis": S(lambda: g.Visible), "M_layout": mread(g.Transformation),
                       "caja_local": bx(gd.RangeBox), "hijos": hijos, "modulos": mods})
    res["grippers"] = gr
    # rejas de A y B (primer nivel de cada celda) + parámetros del panel
    rejas = []
    for celda, oc in (("A", occ["Celda_A_L3N:1"]), ("B", celB)):
        for o in inv._items(oc.SubOccurrences):
            f = Path(arch(o) or "").name
            if o.Name.startswith("Reja") or any(k in (o.Name + f).lower() for k in ("columna", "panel", "puerta", "cp1512")):
                rejas.append({"celda": celda, "n": o.Name, "f": arch(o), "M": mread(o.Transformation), "c": caja(o),
                              "vis": S(lambda: o.Visible), "sup": S(lambda: o.Suppressed)})
    res["rejas"] = rejas
    piezas = {}
    for r in rejas:
        f = r["f"]
        if f and f not in piezas:
            d = next((d for d in inv._items(app.Documents) if S(lambda: d.FullFileName == f, False)), None)
            if d is not None:
                piezas[f] = {"c_def": S(lambda: bx(d.ComponentDefinition.RangeBox)), "params": params(d) if f.lower().endswith(".ipt") else [],
                             "feats": feats(d) if f.lower().endswith(".ipt") else [],
                             "hijos": [{"n": o.Name, "f": arch(o), "M_rel": mread(o.Transformation), "c": caja(o)}
                                       for o in inv._items(d.ComponentDefinition.Occurrences)] if f.lower().endswith(".iam") else []}
    res["piezas_rejas"] = piezas
    res["n_docs_abiertos"] = app.Documents.Count
finally:
    S(lambda: setattr(app, "SilentOperation", False))
OUT.write_text(json.dumps(res, ensure_ascii=False), encoding="utf-8")
print(json.dumps({k: (len(v) if isinstance(v, (list, dict)) else v) for k, v in res.items()}, ensure_ascii=False))
