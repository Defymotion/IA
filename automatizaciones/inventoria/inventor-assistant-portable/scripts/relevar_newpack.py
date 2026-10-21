"""Relevamiento detallado (sin guardar) de la celda NewPack2 abierta en Inventor:
- gripper: componentes (cajas en el MUNDO), restricciones con valores y PRUEBA de cada restricción con desfase o
  ángulo (se cambia un poco, se mide qué componentes se mueven y cuánto, y se vuelve al valor original);
- centrador, topes del almacén de pallets: componentes y cajas;
- robot: eslabones (matriz local) y lo mismo del robot de ADECO2 para comparar.
No guarda nada; los valores cambiados se restituyen.
Uso: python relevar_newpack.py   ->  Analisis\\NEWPACK2_paletizado\\detalle.json
"""
import json
import math
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
import inventor_mcp as inv  # noqa: E402

S = inv._safe
T0 = time.time()
app = inv._inventor(start_if_needed=False, visible=False)
app.SilentOperation = True
LAYOUT = Path.home() / "Documents" / "InventorIA" / "Simulacion NewPack2" / "Layout" / "Paletizado.iam"
activo = S(lambda: app.ActiveDocument.FullFileName)
doc = next((d for d in inv._items(app.Documents)
            if S(lambda: Path(d.FullFileName).resolve() == LAYOUT.resolve(), False)), None)
if doc is None:
    doc = app.Documents.Open(str(LAYOUT), False)
OUT = Path.home() / "Documents" / "InventorIA" / "Analisis" / "NEWPACK2_paletizado"
cd = doc.ComponentDefinition
top = {o.Name: o for o in inv._items(cd.Occurrences)}


def r(v):
    return round(v * 10, 1)


def box(b):
    return [[r(b.MinPoint.X), r(b.MinPoint.Y), r(b.MinPoint.Z)], [r(b.MaxPoint.X), r(b.MaxPoint.Y), r(b.MaxPoint.Z)]]


def mat(m):
    return [[round(m.Cell(i, j) * (10 if (j == 4 and i < 4) else 1), 3) for j in range(1, 5)] for i in range(1, 4)]


def hojas(occ, out, path=""):
    for o in inv._items(S(lambda: occ.SubOccurrences, []) or []):
        p = f"{path}/{o.Name}"
        if S(lambda: o.DefinitionDocumentType) == inv.K_ASSEMBLY_DOCUMENT:
            out.append({"ruta": p, "tipo": "iam", "archivo": Path(S(lambda: o.Definition.Document.FullFileName, "")).name,
                        "caja": S(lambda: box(o.RangeBox))})
            hojas(o, out, p)
        else:
            out.append({"ruta": p, "tipo": "ipt", "archivo": Path(S(lambda: o.Definition.Document.FullFileName, "")).name,
                        "caja": S(lambda: box(o.RangeBox)), "M": S(lambda: mat(o.Transformation))})
    return out


res = {}
res["activo"] = activo
res["top"] = sorted(top)
for clave in [n for n in top if n.split(":")[0] in ("Gripper", "Ensamble centrador", "topes delantero derecho",
                                                     "topes traseros")]:
    if clave in top:
        res[clave] = {"caja": box(top[clave].RangeBox), "M": mat(top[clave].Transformation),
                      "componentes": hojas(top[clave], [])}

# ---- restricciones del gripper y prueba de movimiento
g = next(o for o in top.values() if Path(S(lambda: o.Definition.Document.FullFileName, "")).stem == "Gripper")
gdoc = g.Definition.Document
gcd = gdoc.ComponentDefinition


def posiciones():
    pos = {}
    for h in hojas(g, []):
        if h["tipo"] == "ipt" and h["caja"]:
            b = h["caja"]
            pos[h["ruta"]] = [(b[0][i] + b[1][i]) / 2 for i in range(3)] + [b[1][i] - b[0][i] for i in range(3)]
    return pos


def restricciones(defn, prefijo):
    out = []
    for c in inv._items(defn.Constraints):
        par, unidad = S(lambda: c.Offset), "cm"
        if par is None:
            par, unidad = S(lambda: c.Angle), "rad"
        out.append({"doc": prefijo, "nombre": c.Name, "tipo": S(lambda: c.Type), "suprimida": S(lambda: c.Suppressed),
                    "valor": S(lambda: par.Expression) if par is not None else None,
                    "occ1": S(lambda: c.OccurrenceOne.Name), "occ2": S(lambda: c.OccurrenceTwo.Name),
                    "_c": c, "_p": par, "_u": unidad})
    return out


cons = restricciones(gcd, "Gripper")
# también las de los subensambles del gripper (garras, ejes, palas)
subdocs = {}
for o in inv._items(gcd.Occurrences):
    if S(lambda: o.DefinitionDocumentType) == inv.K_ASSEMBLY_DOCUMENT:
        d = o.Definition.Document
        if d.FullFileName not in subdocs:
            subdocs[d.FullFileName] = d
            cons += restricciones(d.ComponentDefinition, Path(d.FullFileName).stem)
base = posiciones()
pruebas = []
for c in cons:
    if c["suprimida"] or c["_p"] is None:
        continue
    par = c["_p"]
    v0 = S(lambda: par.Value)
    if v0 is None:
        continue
    delta = 0.5 if c["_u"] == "cm" else math.radians(5)
    d_ = gdoc if c["doc"] == "Gripper" else next(sd for fn, sd in subdocs.items() if Path(fn).stem == c["doc"])
    try:
        par.Value = v0 + delta
        S(lambda: d_.Update())
        S(lambda: gdoc.Update())
        S(lambda: doc.Update())
        nuevo = posiciones()
        mov = {}
        for k, v in nuevo.items():
            if k in base:
                dd = math.dist(v[:3], base[k][:3])
                dg = max(abs(v[3 + i] - base[k][3 + i]) for i in range(3))
                if dd > 0.3 or dg > 0.3:
                    mov[k] = {"desplaz_mm": round(dd, 1), "d": [round(v[i] - base[k][i], 1) for i in range(3)],
                              "cambio_caja": round(dg, 1)}
        pruebas.append({"doc": c["doc"], "nombre": c["nombre"], "valor": c["valor"],
                        "delta": "5 mm" if c["_u"] == "cm" else "5°", "se_mueven": len(mov),
                        "movimientos": dict(sorted(mov.items(), key=lambda kv: -kv[1]["desplaz_mm"])[:12])})
    except Exception as exc:  # noqa: BLE001
        pruebas.append({"doc": c["doc"], "nombre": c["nombre"], "error": repr(exc)})
    finally:
        S(lambda: setattr(par, "Value", v0))
        S(lambda: d_.Update())
        S(lambda: gdoc.Update())
S(lambda: doc.Update())
res["gripper_restricciones"] = [{k: v for k, v in c.items() if not k.startswith("_")} for c in cons]
res["gripper_pruebas"] = [p for p in pruebas if p.get("se_mueven") or p.get("error")]
res["gripper_pruebas_sin_mov"] = [p["doc"] + "/" + p["nombre"] for p in pruebas if not p.get("se_mueven")
                                  and not p.get("error")]
# ---- robot: eslabones de esta celda y del robot de ADECO2
kuka = next(o for n, o in top.items() if n.startswith("KUKA"))
res["robot_eslabones"] = {o.Name: {"M_local": mat(o.Transformation),
                                   "archivo": Path(o.Definition.Document.FullFileName).name}
                          for o in inv._items(kuka.Definition.Occurrences)}
res["robot_restricciones"] = [{"n": c.Name, "valor": S(lambda: c.Offset.Expression) or S(lambda: c.Angle.Expression),
                               "o1": S(lambda: c.OccurrenceOne.Name), "o2": S(lambda: c.OccurrenceTwo.Name)}
                              for c in inv._items(kuka.Definition.Constraints)]
adeco = Path.home() / "Documents" / "InventorIA" / "12_ADECO2" / "KUKA" / "KUKA-KR_140_R3200_2_PA-ASM.iam"
if adeco.exists():
    ya = any(S(lambda: Path(d.FullFileName).resolve() == adeco.resolve(), False) for d in inv._items(app.Documents))
    ad = app.Documents.Open(str(adeco), False)
    res["robot_adeco_eslabones"] = {o.Name: mat(o.Transformation) for o in inv._items(ad.ComponentDefinition.Occurrences)}
    if not ya:
        S(lambda: ad.Close(True))
res["gripper_restricciones_al_robot"] = [
    {"n": c.Name, "tipo": S(lambda: c.Type), "e1": S(lambda: c.EntityOne.Type), "o1": S(lambda: c.OccurrenceOne.Name),
     "o2": S(lambda: c.OccurrenceTwo.Name), "valor": S(lambda: c.Offset.Expression) or S(lambda: c.Angle.Expression)}
    for c in inv._items(cd.Constraints) if "Gripper" in (S(lambda: c.OccurrenceOne.Name, "") or "")
    + (S(lambda: c.OccurrenceTwo.Name, "") or "")]
res["segundos"] = round(time.time() - T0, 1)
S(lambda: setattr(app, "SilentOperation", False))
(OUT / "detalle.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps({"pruebas_con_movimiento": len(res["gripper_pruebas"]), "segundos": res["segundos"]}))
