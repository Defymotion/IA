"""Sólo lectura: cara de montaje de la brida del robot (eslabón V05) y de la brida del gripper.
Salida: Documents\\InventorIA\\Analisis\\bridas.json"""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
import inventor_mcp as inv  # noqa: E402

S = inv._safe
ROOT = Path.home() / "Documents" / "InventorIA"
ROBOT = ROOT / "12_ADECO2" / "KUKA" / "KUKA-KR_140_R3200_2_PA-ASM.iam"
GRIP = ROOT / "Generados" / "GRIPPER_4x12kg_C250" / "Ensamble" / "Gripper_GRIPPER_4x12kg_C250.iam"
app = inv._inventor(start_if_needed=False)
app.SilentOperation = True


def r3(p):
    return [round(p.X * 10, 2), round(p.Y * 10, 2), round(p.Z * 10, 2)]


def v3(v):
    return [round(v.X, 4), round(v.Y, 4), round(v.Z, 4)]


def caras(o, eje=None, nmax=30):
    planos, circ = [], []
    for body in inv._items(S(lambda: o.SurfaceBodies, []) or []):
        for f in inv._items(body.Faces):
            if S(lambda: f.SurfaceType) != 5890:
                continue
            n = f.Geometry.Normal
            if eje and abs(abs(n.X * eje[0] + n.Y * eje[1] + n.Z * eje[2]) - 1) > 1e-3:
                continue
            b = f.Evaluator.RangeBox
            planos.append({"n": v3(n), "centro": [round((b.MinPoint.X + b.MaxPoint.X) * 5, 2),
                                                  round((b.MinPoint.Y + b.MaxPoint.Y) * 5, 2),
                                                  round((b.MinPoint.Z + b.MaxPoint.Z) * 5, 2)],
                           "caja": [r3(b.MinPoint), r3(b.MaxPoint)], "area": round(f.Evaluator.Area * 100)})
        for e in inv._items(body.Edges):
            g = S(lambda: e.Geometry)
            if g is None or S(lambda: g.Radius) is None or S(lambda: g.StartAngle) is not None:
                continue
            nn = g.Normal
            if eje and abs(abs(nn.X * eje[0] + nn.Y * eje[1] + nn.Z * eje[2]) - 1) > 1e-3:
                continue
            circ.append([*r3(g.Center), round(g.Radius * 20, 2)])
    planos.sort(key=lambda p: -p["area"])
    return {"planos": planos[:nmax], "circulos": sorted({tuple(c) for c in circ})[:200]}


res = {}
rd = app.Documents.Open(str(ROBOT), False)
v5 = next(o for o in inv._items(rd.ComponentDefinition.Occurrences) if "V05" in o.Name)
res["V05"] = caras(v5, eje=(-0.7249, 0.6889, 0.0))
gd = app.Documents.Open(str(GRIP), False)
occs = list(inv._items(gd.ComponentDefinition.Occurrences))
res["gripper"] = {"caja": [r3(gd.ComponentDefinition.RangeBox.MinPoint), r3(gd.ComponentDefinition.RangeBox.MaxPoint)],
                  "componentes": [{"nombre": o.Name, "caja": [r3(o.RangeBox.MinPoint), r3(o.RangeBox.MaxPoint)]}
                                  for o in occs]}
br = [o for o in occs if "brida" in o.Name.lower()]
res["gripper"]["brida"] = [dict(nombre=o.Name, **caras(o)) for o in br]
app.SilentOperation = False
out = ROOT / "Analisis" / "bridas.json"
out.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
print("ok", len(br))
