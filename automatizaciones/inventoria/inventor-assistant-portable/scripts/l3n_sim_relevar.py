"""Sólo lectura: relevamiento para la simulación completa de planta L3N (LayoutL3N_Celdas.iam).
Escribe Analisis\\L3N\\sim_relevamiento.json con matrices (mm, coordenadas del layout salvo que se indique) y cajas:
ocurrencias de primer nivel del layout; de Celda_A, Linea_Pallets, Robot_Aereo_Pallets y Cinta_Llegada_A (2 niveles);
robot armado (matriz y eslabones), gripper (archivo, matriz, caja local, módulos con su restricción de apertura),
patrón del pallet lleno (cajas relativas al pallet), mesa giratoria A y MP402 (hijos).
Uso: python l3n_sim_relevar.py
"""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
import inventor_mcp as inv  # noqa: E402

S = inv._safe
TOP = Path(r"C:\DEFYMOTION\L3N\Celdas_IA\LayoutL3N_Celdas.iam")
OUT = Path.home() / "Documents" / "InventorIA" / "Analisis" / "L3N" / "sim_relevamiento.json"
app = inv._inventor(start_if_needed=False)
res = {"avisos": []}


def mread(m):
    return [[round(m.Cell(r, c) * (10 if (c == 4 and r < 4) else 1), 4) for c in range(1, 5)] for r in range(1, 5)]


def caja(o):
    b = S(lambda: o.RangeBox, None)
    if b is None:
        return None
    return [round(v * 10, 1) for v in (b.MinPoint.X, b.MinPoint.Y, b.MinPoint.Z, b.MaxPoint.X, b.MaxPoint.Y, b.MaxPoint.Z)]


def arch(o):
    return S(lambda: o.Definition.Document.FullFileName, None)


def lista(occs, prof=1, maxprof=1, ruta=""):
    out = []
    for o in inv._items(occs):
        e = {"n": ruta + o.Name, "f": arch(o), "M": S(lambda: mread(o.Transformation)), "c": caja(o),
             "vis": S(lambda: o.Visible), "sup": S(lambda: o.Suppressed), "nh": S(lambda: o.SubOccurrences.Count, 0)}
        out.append(e)
        if prof < maxprof and e["nh"]:
            out += lista(o.SubOccurrences, prof + 1, maxprof, ruta + o.Name + "/")
    return out


app.SilentOperation = True
try:
    top = next((d for d in inv._items(app.Documents) if S(lambda: Path(d.FullFileName).resolve() == TOP.resolve(), False)), None)
    top = top or app.Documents.Open(str(TOP), False)
    tcd = top.ComponentDefinition
    occ = {o.Name: o for o in inv._items(tcd.Occurrences)}
    res["top"] = lista(tcd.Occurrences)
    cel = occ["Celda_A_L3N:1"]
    res["celda_A"] = lista(cel.SubOccurrences, 1, 2)
    res["linea"] = lista(occ["Linea_Pallets:1"].SubOccurrences, 1, 1)
    res["aereo"] = lista(occ["Robot_Aereo_Pallets:1"].SubOccurrences, 1, 1)
    sub = {o.Name: o for o in inv._items(cel.SubOccurrences)}
    res["cinta_llegada"] = lista(sub["Cinta_Llegada_A"].SubOccurrences, 1, 1) if "Cinta_Llegada_A" in sub else None
    # robot armado
    kuka = next((o for n, o in sub.items() if n.startswith("KUKA")), None)
    if kuka is not None:
        res["kuka"] = {"n": kuka.Name, "M_layout": mread(kuka.Transformation),
                       "links": {o.Name: {"f": arch(o), "M_rel": mread(o.Transformation)} for o in inv._items(kuka.Definition.Occurrences)}}
    res["robot_ia"] = {n: {"f": arch(o), "M": mread(o.Transformation)} for n, o in sub.items() if n.startswith("IA_Robot_V")}
    # gripper
    g = next((o for n, o in sub.items() if n.startswith("IA_Gripper")), None)
    if g is not None:
        gd = g.Definition
        b = gd.RangeBox
        mods = {}
        for o in inv._items(gd.Occurrences):
            if o.Name.startswith("Modulo pala movil"):
                ap = next((c for c in inv._items(o.Definition.Constraints) if "apertura" in c.Name.lower()), None)
                mods[o.Name] = {"f": arch(o), "M_rel": mread(o.Transformation), "apertura": S(lambda: ap.Name),
                                "valor_mm": S(lambda: round(ap.Offset.Value * 10, 2)), "c_local": [round(v * 10, 1) for v in (
                                    o.RangeBox.MinPoint.X, o.RangeBox.MinPoint.Y, o.RangeBox.MinPoint.Z,
                                    o.RangeBox.MaxPoint.X, o.RangeBox.MaxPoint.Y, o.RangeBox.MaxPoint.Z)]}
        res["gripper"] = {"n": g.Name, "f": arch(g), "M_layout": mread(g.Transformation),
                          "caja_local": [round(v * 10, 1) for v in (b.MinPoint.X, b.MinPoint.Y, b.MinPoint.Z, b.MaxPoint.X, b.MaxPoint.Y, b.MaxPoint.Z)],
                          "modulos": mods, "hijos": [o.Name for o in inv._items(gd.Occurrences)]}
    # patrón del pallet
    p = next((o for n, o in sub.items() if n.startswith("IA_Pallet_TBA250")), None)
    if p is not None:
        res["pallet_lleno"] = {"n": p.Name, "f": arch(p), "M_layout": mread(p.Transformation), "c": caja(p),
                               "hijos": [{"n": o.Name, "f": Path(arch(o) or "").name, "M_rel": mread(o.Transformation),
                                          "c_rel": [round(v * 10, 1) for v in (o.RangeBox.MinPoint.X, o.RangeBox.MinPoint.Y, o.RangeBox.MinPoint.Z,
                                                                               o.RangeBox.MaxPoint.X, o.RangeBox.MaxPoint.Y, o.RangeBox.MaxPoint.Z)]}
                                         for o in inv._items(p.Definition.Occurrences)]}
    # giratoria A y posibles pateador / centrador
    gir = next((o for n, o in sub.items() if n.startswith("roller conveyor - rotating")), None)
    if gir is not None:
        res["giratoria_A"] = {"n": gir.Name, "M_layout": mread(gir.Transformation), "c": caja(gir),
                              "hijos": lista(gir.SubOccurrences, 1, 1)}
    claves = ("pate", "empuj", "centr", "freno", "tope", "barrera", "camas", "mesa de rolos")
    res["celda_claves"] = [e for e in res["celda_A"] if any(k in e["n"].lower() for k in claves)]
    lin = {o.Name: o for o in inv._items(occ["Linea_Pallets:1"].SubOccurrences)}
    mp = next((o for n, o in lin.items() if n.startswith("MP402")), None)
    if mp is not None:
        res["mp402"] = {"n": mp.Name, "M_layout": mread(mp.Transformation), "c": caja(mp), "hijos": lista(mp.SubOccurrences, 1, 2)}
    # celda B (v5): primer nivel + lo que anima la simulación
    if "Celda_B_existente:1" in occ:
        celB = occ["Celda_B_existente:1"]
        res["celda_B"] = lista(celB.SubOccurrences, 1, 1)
        subB = {o.Name: o for o in inv._items(celB.SubOccurrences)}
        extra = []
        for nm in ("Ensamble pateador adeco:1", "roller conveyor - rotating:1", "Pallet_Completo:2", "BM2000_CeldaB_1",
                   "BM2000_CeldaB_2"):
            if nm in subB:
                extra += lista(subB[nm].SubOccurrences, 1, 1, nm + "/")
        if "ADECOAGRO2_Layout[Fademaq]:1" in subB:
            extra += lista(subB["ADECOAGRO2_Layout[Fademaq]:1"].SubOccurrences, 1, 2, "ADECOAGRO2_Layout[Fademaq]:1/")
        res["celda_B"] += extra
        kb = subB.get("KUKA-KR_140_R3200_2_PA-ASM:1")
        if kb is not None:
            res["kuka_B"] = {"n": kb.Name, "M_layout": mread(kb.Transformation),
                             "links": {o.Name: {"f": arch(o), "M_rel": mread(o.Transformation)} for o in inv._items(kb.Definition.Occurrences)}}
        gb = subB.get("Gripper_ADECO2_V1:1")
        if gb is not None:
            gd = gb.Definition
            b = gd.RangeBox
            res["gripper_B"] = {"n": gb.Name, "f": arch(gb), "M_layout": mread(gb.Transformation),
                                "caja_local": [round(v * 10, 1) for v in (b.MinPoint.X, b.MinPoint.Y, b.MinPoint.Z, b.MaxPoint.X, b.MaxPoint.Y, b.MaxPoint.Z)],
                                "hijos": [{"n": o.Name, "f": arch(o), "M_rel": mread(o.Transformation),
                                           "c_local": [round(v * 10, 1) for v in (o.RangeBox.MinPoint.X, o.RangeBox.MinPoint.Y, o.RangeBox.MinPoint.Z,
                                                                                  o.RangeBox.MaxPoint.X, o.RangeBox.MaxPoint.Y, o.RangeBox.MaxPoint.Z)]}
                                          for o in inv._items(gd.Occurrences)]}
    # camara actual para referencia
    res["n_docs_abiertos"] = app.Documents.Count
finally:
    S(lambda: setattr(app, "SilentOperation", False))
OUT.write_text(json.dumps(res, ensure_ascii=False), encoding="utf-8")
print(json.dumps({k: (len(v) if isinstance(v, (list, dict)) else v) for k, v in res.items()}, ensure_ascii=False))
