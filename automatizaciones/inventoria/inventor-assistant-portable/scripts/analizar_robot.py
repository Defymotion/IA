"""Relevamiento (sólo lectura) del robot KUKA, la base del robot y su ubicación en el ensamble general ADECO2.

- Robot: componentes (eslabones), matrices, cajas, restricciones existentes y cilindros grandes de cada eslabón
  (candidatos a ejes de articulación), en coordenadas del ensamble del robot.
- Base: componentes, caja, cara plana superior más grande.
- Ensamble general (opcional, --general): dónde están robot, base y gripper (matrices de nivel superior).
Salida: Documents\\InventorIA\\Analisis\\robot.json (+ imágenes iso del robot y la base)
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
a.add_argument("--general", action="store_true")
x = a.parse_args()
S = inv._safe
ROOT = Path.home() / "Documents" / "InventorIA" / "12_ADECO2"
ROBOT = ROOT / "KUKA" / "KUKA-KR_140_R3200_2_PA-ASM.iam"
BASE = ROOT / "base_del_robot" / "base_principal_circular.iam"
GENERAL = ROOT / "ADECOAGRO_Chivilcoy.iam"
OUTD = Path.home() / "Documents" / "InventorIA" / "Analisis"
OUTD.mkdir(exist_ok=True)
T0 = time.time()
app = inv._inventor(start_if_needed=False)
app.SilentOperation = True


def r3(p):
    return [round(p.X * 10, 2), round(p.Y * 10, 2), round(p.Z * 10, 2)]


def v3(v):
    return [round(v.X, 4), round(v.Y, 4), round(v.Z, 4)]


def box(b):
    return [r3(b.MinPoint), r3(b.MaxPoint)]


def mat(m):
    return [[round(m.Cell(r, c) * (10 if c == 4 and r < 4 else 1), 4) for c in range(1, 5)] for r in range(1, 4)]


def cilindros(o, rmin_mm=40, n=12):
    out = []
    for body in inv._items(S(lambda: o.SurfaceBodies, []) or []):
        for f in inv._items(body.Faces):
            if S(lambda: f.SurfaceType) != 5891:
                continue
            g = S(lambda: f.Geometry)
            if g is None or g.Radius * 10 < rmin_mm:
                continue
            out.append({"d": round(g.Radius * 20, 1), "eje": v3(g.AxisVector), "base": r3(g.BasePoint),
                        "caja": box(f.Evaluator.RangeBox), "area": round(f.Evaluator.Area * 100)})
    out.sort(key=lambda c: -c["area"])
    return out[:n]


def imagen(doc, nombre):
    try:
        doc.Activate() if S(lambda: doc.Views.Count, 0) else doc.Views.Add()
        cam = app.ActiveView.Camera
        cam.ViewOrientationType = 10759
        cam.Fit()
        cam.Apply()
        app.ActiveView.SaveAsBitmap(str(OUTD / nombre), 1200, 900)
        return str(OUTD / nombre)
    except Exception as exc:  # noqa: BLE001
        return f"error: {exc}"


res = {}
# ------------------------------------------------------------------ robot
rd = app.Documents.Open(str(ROBOT), True)
cd = rd.ComponentDefinition
res["robot"] = {
    "archivo": str(ROBOT), "caja": box(cd.RangeBox),
    "componentes": [{"nombre": o.Name, "archivo": Path(o.Definition.Document.FullFileName).name,
                     "fijo": S(lambda: o.Grounded), "matriz": mat(o.Transformation), "caja": box(o.RangeBox),
                     "masa_kg": S(lambda: round(o.MassProperties.Mass, 1)), "cilindros": cilindros(o)}
                    for o in inv._items(cd.Occurrences)],
    "restricciones": [{"nombre": c.Name, "tipo": S(lambda: c.Type), "sup": S(lambda: c.Suppressed),
                       "a": S(lambda: c.OccurrenceOne.Name), "b": S(lambda: c.OccurrenceTwo.Name),
                       "valor": S(lambda: round(c.Offset.Value * 10, 3)) if S(lambda: c.Offset) else
                       S(lambda: round(c.Angle.Value * 57.29578, 3))}
                      for c in inv._items(cd.Constraints)],
    "joints": [{"nombre": j.Name, "tipo": S(lambda: j.Definition.JointType)}
               for j in inv._items(S(lambda: cd.Joints, []) or [])],
    "parametros_usuario": [(p.Name, S(lambda: p.Expression)) for p in inv._items(S(lambda: cd.Parameters.UserParameters, []) or [])],
}
res["robot"]["imagen"] = imagen(rd, "robot_iso.png")
# ------------------------------------------------------------------ base
bd = app.Documents.Open(str(BASE), True)
cdb = bd.ComponentDefinition
planos = []
for o in inv._items(cdb.Occurrences):
    for body in inv._items(S(lambda: o.SurfaceBodies, []) or []):
        for f in inv._items(body.Faces):
            if S(lambda: f.SurfaceType) == 5890 and abs(abs(S(lambda: f.Geometry.Normal.Z, 0)) - 1) < 1e-3 \
                    or S(lambda: f.SurfaceType) == 5890 and abs(abs(S(lambda: f.Geometry.Normal.Y, 0)) - 1) < 1e-3:
                planos.append({"occ": o.Name, "n": v3(f.Geometry.Normal), "caja": box(f.Evaluator.RangeBox),
                               "area": round(f.Evaluator.Area * 100)})
planos.sort(key=lambda p: -p["area"])
res["base"] = {
    "archivo": str(BASE), "caja": box(cdb.RangeBox),
    "componentes": [{"nombre": o.Name, "archivo": Path(o.Definition.Document.FullFileName).name,
                     "matriz": mat(o.Transformation), "caja": box(o.RangeBox),
                     "cilindros": cilindros(o, 20, 8)} for o in inv._items(cdb.Occurrences)],
    "planos_horizontales": planos[:25],
}
res["base"]["imagen"] = imagen(bd, "base_robot_iso.png")
# ------------------------------------------------------------------ ensamble general
if x.general:
    gd = app.Documents.Open(str(GENERAL), False)
    lst = []
    for o in inv._items(gd.ComponentDefinition.Occurrences):
        fn = S(lambda: o.Definition.Document.FullFileName, "") or ""
        k = fn.lower()
        if any(t in k for t in ("kuka", "kr_140", "base_principal", "gripper", "robot")):
            lst.append({"nombre": o.Name, "archivo": fn, "matriz": mat(o.Transformation), "caja": box(o.RangeBox)})
    res["general"] = {"archivo": str(GENERAL), "componentes": lst}
    S(lambda: gd.Close(True))
res["tiempo_s"] = round(time.time() - T0, 1)
app.SilentOperation = False
(OUTD / "robot.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps({k: (v if k == "tiempo_s" else "ok") for k, v in res.items()}, ensure_ascii=False))
