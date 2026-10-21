"""Relevamiento (SÓLO LECTURA) del ensamble ACTIVO en Inventor: ruta, proyecto, componentes de primer y segundo
nivel (archivo, matriz, caja, visibilidad, fijo), restricciones con su valor, parámetros, representaciones y
3 imágenes (ISO, planta, frente). La cámara del usuario se restituye al final. No guarda nada.
Uso: python relevar_activo.py [--nombre NEWPACK2]   ->  Documents\\InventorIA\\Analisis\\<nombre>\\
"""
import argparse
import json
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
import inventor_mcp as inv  # noqa: E402

a = argparse.ArgumentParser()
a.add_argument("--nombre", default="ACTIVO")
a.add_argument("--max-hijos", type=int, default=120)
x = a.parse_args()
S = inv._safe
T0 = time.time()
app = inv._inventor(start_if_needed=False, visible=False)
doc = app.ActiveDocument
if doc is None or doc.DocumentType != inv.K_ASSEMBLY_DOCUMENT:
    sys.exit("El documento activo no es un ensamble")
OUT = Path.home() / "Documents" / "InventorIA" / "Analisis" / x.nombre
OUT.mkdir(parents=True, exist_ok=True)


def r(v):
    return round(v * 10, 2)


def box(b):
    return [[r(b.MinPoint.X), r(b.MinPoint.Y), r(b.MinPoint.Z)], [r(b.MaxPoint.X), r(b.MaxPoint.Y), r(b.MaxPoint.Z)]]


def mat(m):
    return [[round(m.Cell(i, j) * (10 if (j == 4 and i < 4) else 1), 4) for j in range(1, 5)] for i in range(1, 4)]


def occ_info(o, nivel):
    d = {"nombre": o.Name, "archivo": S(lambda: o.Definition.Document.FullFileName, "?"),
         "tipo": "iam" if S(lambda: o.DefinitionDocumentType) == inv.K_ASSEMBLY_DOCUMENT else "ipt",
         "visible": S(lambda: o.Visible), "suprimido": S(lambda: o.Suppressed), "fijo": S(lambda: o.Grounded),
         "adaptivo": S(lambda: o.Adaptive), "M": S(lambda: mat(o.Transformation)),
         "caja": S(lambda: box(o.RangeBox))}
    if d["tipo"] == "iam":
        hijos = list(inv._items(S(lambda: o.SubOccurrences, []) or []))
        d["n_hijos"] = len(hijos)
        d["restricciones_internas"] = S(lambda: o.Definition.Constraints.Count, 0)
        d["joints_internos"] = S(lambda: o.Definition.Joints.Count, 0)
        if nivel < 2 and len(hijos) <= x.max_hijos:
            d["hijos"] = [occ_info(h, nivel + 1) for h in hijos]
        elif hijos:
            cuenta = {}
            for h in hijos:
                k = Path(S(lambda: h.Definition.Document.FullFileName, "?")).name
                cuenta[k] = cuenta.get(k, 0) + 1
            d["hijos_por_archivo"] = cuenta
    return d


cd = doc.ComponentDefinition
res = {"documento": doc.FullFileName, "proyecto": S(lambda: app.DesignProjectManager.ActiveDesignProject.FullFileName),
       "caja_total": box(cd.RangeBox), "unidades": S(lambda: doc.UnitsOfMeasure.LengthUnits),
       "componentes": [occ_info(o, 1) for o in inv._items(cd.Occurrences)]}
TIPOS = {100665088: "Ensamblar/Coincidir", 100665344: "Ángulo", 100665600: "Tangente", 100665856: "Insertar",
         100666112: "Flush", 100666880: "Movimiento", 100667136: "Transicional"}
cons = []
for c in inv._items(cd.Constraints):
    cons.append({"nombre": c.Name, "tipo": TIPOS.get(S(lambda: c.Type), S(lambda: c.Type)),
                 "suprimida": S(lambda: c.Suppressed),
                 "valor": S(lambda: c.Offset.Expression) or S(lambda: c.Angle.Expression),
                 "occ1": S(lambda: c.OccurrenceOne.Name), "occ2": S(lambda: c.OccurrenceTwo.Name),
                 "estado": S(lambda: c.HealthStatus)})
res["restricciones"] = cons
res["joints"] = [{"nombre": j.Name, "tipo": S(lambda: j.Definition.JointType), "occ1": S(lambda: j.OccurrenceOne.Name),
                  "occ2": S(lambda: j.OccurrenceTwo.Name)} for j in inv._items(S(lambda: cd.Joints, []) or [])]
res["parametros_usuario"] = [{"n": p.Name, "v": S(lambda: p.Expression)}
                             for p in inv._items(S(lambda: cd.Parameters.UserParameters, []) or [])]
res["parametros_modelo_con_nombre"] = [{"n": p.Name, "v": S(lambda: p.Expression)}
                                       for p in inv._items(S(lambda: cd.Parameters.ModelParameters, []) or [])
                                       if not p.Name.startswith("d")][:80]
res["vistas_diseno"] = [v.Name for v in inv._items(S(lambda: cd.RepresentationsManager.DesignViewRepresentations,
                                                       []) or [])]
res["posicionales"] = [v.Name for v in inv._items(S(lambda: cd.RepresentationsManager.PositionalRepresentations,
                                                    []) or [])]
res["referencias"] = len(list(inv._items(doc.AllReferencedDocuments)))
# imágenes (restituye la cámara del usuario)
try:
    v = app.ActiveView
    cam = v.Camera
    guardo = (cam.Eye, cam.Target, cam.UpVector, cam.Perspective)
    imgs = {}
    for nombre, orient in (("iso", 10759), ("planta", 10754), ("frente", 10764)):
        cam.ViewOrientationType = orient
        cam.Fit()
        cam.Apply()
        p = OUT / f"{nombre}.png"
        v.SaveAsBitmap(str(p), 1600, 1000)
        imgs[nombre] = str(p)
    cam.Eye, cam.Target, cam.UpVector = guardo[0], guardo[1], guardo[2]
    cam.Perspective = guardo[3]
    cam.Apply()
    res["imagenes"] = imgs
except Exception as exc:  # noqa: BLE001
    res["imagenes_error"] = repr(exc)
res["segundos"] = round(time.time() - T0, 1)
(OUT / "relevamiento.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps({k: v for k, v in res.items() if k != "componentes"}, ensure_ascii=False, indent=1)[:20000])
print("COMPONENTES", len(res["componentes"]))
