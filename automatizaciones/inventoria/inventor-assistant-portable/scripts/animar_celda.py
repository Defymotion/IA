"""Anima la celda (robot + gripper) moviendo los eslabones por cinemática (celda_kin) y abriendo/cerrando el
gripper con la restricción "Apertura" del módulo. Captura un cuadro por paso. No guarda cambios en el modelo.

Uso: python animar_celda.py [--cuadros 10] [--programa programa.json]
programa: lista de poses {"q1","q2","q3","q6","pinza"(0 abierta / 1 cerrada), "pausa"(cuadros)}
Salida: Generados\\CELDA_KR140\\Animacion\\cuadro_###.png
"""
import argparse
import json
import math
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import inventor_mcp as inv  # noqa: E402
import celda_kin as K  # noqa: E402

a = argparse.ArgumentParser()
a.add_argument("--cuadros", type=int, default=10, help="cuadros por tramo")
a.add_argument("--programa", default="")
a.add_argument("--ancho", type=int, default=1920)
a.add_argument("--alto", type=int, default=1080)
x = a.parse_args()
S = inv._safe
DOC = Path.home() / "Documents" / "InventorIA" / "Generados" / "CELDA_KR140"
cfg = json.loads((DOC / "celda.json").read_text(encoding="utf-8"))
PROG = json.loads(Path(x.programa).read_text(encoding="utf-8")) if x.programa else [
    {"q1": 0, "q2": 0, "q3": 0, "q6": 0, "pinza": 0, "pausa": 4},
    {"q1": 70, "q2": -15, "q3": -20, "q6": 0, "pinza": 0, "pausa": 2},
    {"q1": 70, "q2": -15, "q3": -20, "q6": 0, "pinza": 1, "pausa": 3},
    {"q1": 70, "q2": 0, "q3": 5, "q6": 0, "pinza": 1, "pausa": 0},
    {"q1": -70, "q2": 0, "q3": 5, "q6": 90, "pinza": 1, "pausa": 0},
    {"q1": -70, "q2": -15, "q3": -20, "q6": 90, "pinza": 1, "pausa": 2},
    {"q1": -70, "q2": -15, "q3": -20, "q6": 90, "pinza": 0, "pausa": 3},
    {"q1": 0, "q2": 0, "q3": 0, "q6": 0, "pinza": 0, "pausa": 4},
]
T0 = time.time()
app = inv._inventor(start_if_needed=False)
tg = app.TransientGeometry
path = Path(cfg["celda"])
doc = next((d for d in inv._items(app.Documents)
            if S(lambda: Path(d.FullFileName).resolve() == path.resolve(), False)), None) or \
    app.Documents.Open(str(path), True)
doc.Activate()
acd = doc.ComponentDefinition
occ = {k: next(o for o in inv._items(acd.Occurrences) if o.Name == n) for k, n in cfg["occ"].items()}
mod = next(d for d in inv._items(doc.AllReferencedDocuments)
           if any(S(lambda: c.Name, "") == "Apertura"
                  for c in inv._items(S(lambda: d.ComponentDefinition.Constraints, []) or [])))
ap = next(c for c in inv._items(mod.ComponentDefinition.Constraints) if c.Name == "Apertura")
v_abierta = ap.Offset.Value
v_cerrada = v_abierta + 8.0          # carrera 80 mm del ADN-32 (ver animar_gripper)


def mmake(M):
    m = tg.CreateMatrix()
    m.SetCoordinateSystem(tg.CreatePoint(M[0][3] / 10, M[1][3] / 10, M[2][3] / 10),
                          tg.CreateVector(M[0][0], M[1][0], M[2][0]), tg.CreateVector(M[0][1], M[1][1], M[2][1]),
                          tg.CreateVector(M[0][2], M[1][2], M[2][2]))
    return m


def pose(p):
    P = K.poses(cfg, p["q1"], p["q2"], p["q3"], p["q6"])
    for k in ("V02", "V03", "V04", "V05", "gripper"):
        occ[k].Transformation = mmake(P[k])
    v = v_abierta + (v_cerrada - v_abierta) * p["pinza"]
    if abs(ap.Offset.Value - v) > 1e-6:
        ap.Offset.Value = v
        mod.Update()
    doc.Update()


# cámara: iso centrada en la envolvente de todas las poses
cajas = []
for p in PROG:
    pose(p)
    b = acd.RangeBox
    cajas.append((b.MinPoint.X, b.MinPoint.Y, b.MinPoint.Z, b.MaxPoint.X, b.MaxPoint.Y, b.MaxPoint.Z))
mn = [min(c[i] for c in cajas) for i in range(3)]
mx = [max(c[i + 3] for c in cajas) for i in range(3)]
pose(PROG[0])
cam = app.ActiveView.Camera
cam.ViewOrientationType = 10759
cam.Apply()
cam = app.ActiveView.Camera
d = [cam.Eye.X - cam.Target.X, cam.Eye.Y - cam.Target.Y, cam.Eye.Z - cam.Target.Z]
c = [(mn[i] + mx[i]) / 2 for i in range(3)]
cam.Target = tg.CreatePoint(*c)
cam.Eye = tg.CreatePoint(c[0] + d[0], c[1] + d[1], c[2] + d[2])
cam.UpVector = tg.CreateUnitVector(0, 1, 0)
S(lambda: setattr(cam, "Perspective", False))
diag = math.dist(mn, mx)
cam.SetExtents(diag * 0.62 * x.ancho / x.alto, diag * 0.62)
cam.Apply()

OUT = DOC / "Animacion"
OUT.mkdir(exist_ok=True)
for f in OUT.glob("cuadro_*.png"):
    f.unlink()
n = 0


def cuadro():
    global n
    app.ActiveView.SaveAsBitmap(str(OUT / f"cuadro_{n:03d}.png"), x.ancho, x.alto)
    n += 1


def mezcla(p, q, t):
    t = (1 - math.cos(math.pi * t)) / 2
    return {k: p[k] + (q[k] - p[k]) * t for k in ("q1", "q2", "q3", "q6", "pinza")}


for i, p in enumerate(PROG):
    if i > 0:
        prev = PROG[i - 1]
        pasos = x.cuadros if any(abs(p[k] - prev[k]) > 1e-6 for k in ("q1", "q2", "q3", "q6")) else x.cuadros // 2
        for j in range(1, pasos + 1):
            pose(mezcla(prev, p, j / pasos))
            cuadro()
    else:
        pose(p)
        cuadro()
    for _ in range(int(p.get("pausa", 0))):
        cuadro()
pose(PROG[0])
ap.Offset.Value = v_abierta
mod.Update()
pose({"q1": 0, "q2": 0, "q3": 0, "q6": 0, "pinza": 0})
import zipfile  # noqa: E402
with zipfile.ZipFile(OUT / "cuadros.zip", "w", zipfile.ZIP_STORED) as z:
    for f in sorted(OUT.glob("cuadro_*.png")):
        z.write(f, f.name)
res = {"cuadros": n, "carpeta": str(OUT), "zip": str(OUT / "cuadros.zip"), "tiempo_s": round(time.time() - T0, 1)}
print(json.dumps(res, ensure_ascii=False))
