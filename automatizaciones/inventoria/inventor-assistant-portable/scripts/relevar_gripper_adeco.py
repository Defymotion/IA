"""Sólo lectura: gripper de bandejas de ADECO2 y patrón del pallet completo.
- Gripper_ADECO2_V1.iam: componentes (archivo, caja, fijo), restricciones (tipo, valor), parámetros, caras planas
  grandes horizontales (para hallar la brida) e imágenes.
- Pallet_Completo.iam: componentes con matriz y caja (patrón de bandejas por piso).
- Ensamble general: matriz de la base y del V01 dentro de ella (para ubicar el robot).
Salida: Documents\\InventorIA\\Analisis\\gripper_adeco.json"""
import json
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
import inventor_mcp as inv  # noqa: E402

S = inv._safe
ROOT = Path.home() / "Documents" / "InventorIA" / "12_ADECO2"
AN = ROOT.parent / "Analisis"
T0 = time.time()
app = inv._inventor(start_if_needed=False)
app.SilentOperation = True


def r3(p):
    return [round(p.X * 10, 1), round(p.Y * 10, 1), round(p.Z * 10, 1)]


def mat(m):
    return [[round(m.Cell(r, c) * (10 if c == 4 and r < 4 else 1), 3) for c in range(1, 5)] for r in range(1, 4)]


def caja(o):
    b = o.RangeBox
    return [r3(b.MinPoint), r3(b.MaxPoint)]


def imagen(doc, nombre, cod=10759):
    try:
        doc.Activate()
        cam = app.ActiveView.Camera
        cam.ViewOrientationType = cod
        cam.Fit()
        cam.Apply()
        app.ActiveView.SaveAsBitmap(str(AN / nombre), 1400, 1000)
    except Exception as exc:  # noqa: BLE001
        return str(exc)


res = {}
gd = app.Documents.Open(str(ROOT / "Gripper" / "Gripper_ADECO2_V1.iam"), True)
cd = gd.ComponentDefinition
res["gripper"] = {
    "caja": caja(cd),
    "componentes": [{"nombre": o.Name, "archivo": Path(S(lambda: o.Definition.Document.FullFileName, "") or "").name,
                     "fijo": S(lambda: o.Grounded), "adaptativo": S(lambda: o.Adaptive), "caja": caja(o),
                     "matriz": mat(o.Transformation), "n_sub": S(lambda: o.SubOccurrences.Count, 0)}
                    for o in inv._items(cd.Occurrences)],
    "restricciones": [{"nombre": c.Name, "tipo": S(lambda: c.Type), "sup": S(lambda: c.Suppressed),
                       "a": S(lambda: c.OccurrenceOne.Name), "b": S(lambda: c.OccurrenceTwo.Name),
                       "offset": S(lambda: round(c.Offset.Value * 10, 2)),
                       "angulo": S(lambda: round(c.Angle.Value * 57.29578, 2))}
                      for c in inv._items(cd.Constraints)],
    "uniones": [{"nombre": j.Name} for j in inv._items(S(lambda: cd.Joints) or app.TransientObjects.CreateObjectCollection())],
    "parametros_usuario": [(p.Name, S(lambda: p.Expression))
                           for p in inv._items(S(lambda: cd.Parameters.UserParameters)
                                               or app.TransientObjects.CreateObjectCollection())],
    "posicionales": [v.Name for v in inv._items(S(lambda: cd.RepresentationsManager.PositionalRepresentations)
                                                 or app.TransientObjects.CreateObjectCollection())],
}
# cara superior (brida): caras planas horizontales grandes y círculos en la cara más alta
planos = []
for o in inv._items(cd.Occurrences):
    for body in inv._items(S(lambda: o.SurfaceBodies) or app.TransientObjects.CreateObjectCollection()):
        for f in inv._items(body.Faces):
            if S(lambda: f.SurfaceType) != 5890:
                continue
            n = f.Geometry.Normal
            if max(abs(n.X), abs(n.Y), abs(n.Z)) < 0.999:
                continue
            b = f.Evaluator.RangeBox
            planos.append({"occ": o.Name, "n": [round(n.X), round(n.Y), round(n.Z)],
                           "caja": [r3(b.MinPoint), r3(b.MaxPoint)], "area": round(f.Evaluator.Area * 100)})
planos.sort(key=lambda p: -p["area"])
res["gripper"]["planos_grandes"] = planos[:40]
res["gripper"]["img_iso"] = imagen(gd, "gripper_adeco_iso.png")
res["gripper"]["img_frente"] = imagen(gd, "gripper_adeco_frente.png", 10764)
# pallet completo
pd = app.Documents.Open(str(ROOT / "Pallet_Completo.iam"), False)
res["pallet_completo"] = {"caja": caja(pd.ComponentDefinition),
                          "componentes": [{"nombre": o.Name,
                                           "archivo": Path(S(lambda: o.Definition.Document.FullFileName, "") or "").name,
                                           "matriz": mat(o.Transformation), "caja": caja(o)}
                                          for o in inv._items(pd.ComponentDefinition.Occurrences)]}
res["tiempo_s"] = round(time.time() - T0, 1)
app.SilentOperation = False
(AN / "gripper_adeco.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps({"componentes_gripper": len(res["gripper"]["componentes"]),
                  "restricciones": len(res["gripper"]["restricciones"]),
                  "pallet": len(res["pallet_completo"]["componentes"]), "tiempo_s": res["tiempo_s"]}))
