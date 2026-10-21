"""Arma la celda robot + base + gripper como ensamble NUEVO que sólo referencia archivos existentes:
- base_principal_circular.iam (ya trae el pie del robot, V01)
- eslabones V02..V05 del KUKA KR 140 R3200-2 PA (12_ADECO2\\KUKA)
- gripper generado (Gripper_GRIPPER_4x12kg_C250.iam), abulonado a la brida del robot (PCD 160)
No crea ni modifica piezas. La posición de cada eslabón la calcula celda_kin (ver ahí los ejes).
Salida: Generados\\CELDA_KR140\\Celda_KR140_Gripper4x12.iam, celda.json (datos para animar), imágenes.
"""
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

S = inv._safe
DOC = Path.home() / "Documents" / "InventorIA"
ROBOT = DOC / "12_ADECO2" / "KUKA" / "KUKA-KR_140_R3200_2_PA-ASM.iam"
BASE = DOC / "12_ADECO2" / "base_del_robot" / "base_principal_circular.iam"
GRIP = DOC / "Generados" / "GRIPPER_4x12kg_C250" / "Ensamble" / "Gripper_GRIPPER_4x12kg_C250.iam"
OUT = DOC / "Generados" / "CELDA_KR140"
OUT.mkdir(parents=True, exist_ok=True)
CELDA = OUT / "Celda_KR140_Gripper4x12.iam"
T0 = time.time()
app = inv._inventor(start_if_needed=False)
tg = app.TransientGeometry
app.SilentOperation = True


def mread(m):
    return [[m.Cell(r, c) * (10 if (c == 4 and r < 4) else 1) for c in range(1, 5)] for r in range(1, 5)]


def mmake(M):
    m = tg.CreateMatrix()
    m.SetCoordinateSystem(tg.CreatePoint(M[0][3] / 10, M[1][3] / 10, M[2][3] / 10),
                          tg.CreateVector(M[0][0], M[1][0], M[2][0]), tg.CreateVector(M[0][1], M[1][1], M[2][1]),
                          tg.CreateVector(M[0][2], M[1][2], M[2][2]))
    return m


def abrir(p, visible=False):
    for d in inv._items(app.Documents):
        if S(lambda: Path(d.FullFileName).resolve() == p.resolve(), False):
            return d
    return app.Documents.Open(str(p), visible)


rd = abrir(ROBOT)
links = {}
for o in inv._items(rd.ComponentDefinition.Occurrences):
    for k in ("V01", "V02", "V03", "V04", "V05"):
        if k in o.Name:
            links[k] = {"M": mread(o.Transformation), "archivo": o.Definition.Document.FullFileName}
bd = abrir(BASE)
v01_base = next(o for o in inv._items(bd.ComponentDefinition.Occurrences) if "V01" in o.Name)
T_robot = K.mmul(mread(v01_base.Transformation), K.inv_rt(links["V01"]["M"]))

# muñeca: brida mirando hacia abajo
F_orig = (1655.59, 1199.18, 4.5)
n_orig = (0.7249, -0.6889)
phi0 = -90.0 - math.degrees(math.atan2(n_orig[1], n_orig[0]))
R0 = K.rot_z(phi0, K.W)
F = [sum(R0[i][k] * (list(F_orig) + [1])[k] for k in range(4)) for i in range(3)]
# gripper: brida (centro de la cara de apoyo) en el centro de la brida del robot; su -Z hacia arriba
Cg = (324.24, 400.0, -245.24)
Rg = [[1, 0, 0], [0, 0, -1], [0, 1, 0]]
t = [F[i] - sum(Rg[i][k] * Cg[k] for k in range(3)) for i in range(3)]
M_g0 = [Rg[0] + [t[0]], Rg[1] + [t[1]], Rg[2] + [t[2]], [0, 0, 0, 1]]
cfg = {"T_robot": T_robot, "phi0": phi0, "M": {k: v["M"] for k, v in links.items()},
       "archivos": {k: v["archivo"] for k, v in links.items()}, "brida_robot_q0": F, "M_gripper_q0": M_g0,
       "gripper": str(GRIP), "base": str(BASE), "celda": str(CELDA)}

# ---------------------------------------------------------------- ensamble
for d in inv._items(app.Documents):
    if S(lambda: Path(d.FullFileName).resolve() == CELDA.resolve(), False):
        S(lambda: d.Close(True))
if CELDA.exists():
    CELDA.unlink()
cd_doc = app.Documents.Add(inv.K_ASSEMBLY_DOCUMENT, app.FileManager.GetTemplateFile(inv.K_ASSEMBLY_DOCUMENT), True)
acd = cd_doc.ComponentDefinition
ob = acd.Occurrences.Add(str(BASE), mmake(K.tr(0, 0, 0)))
S(lambda: setattr(ob, "Grounded", True))
P0 = K.poses(cfg)
nombres = {}
for k in ("V02", "V03", "V04", "V05"):
    o = acd.Occurrences.Add(links[k]["archivo"], mmake(P0[k]))
    nombres[k] = o.Name
og = acd.Occurrences.Add(str(GRIP), mmake(P0["gripper"]))
nombres["gripper"] = og.Name
nombres["base"] = ob.Name
cfg["occ"] = nombres
cd_doc.Update()
inv._iprop(cd_doc, "Design Tracking Properties", "Part Number", "Celda KR140 Gripper")
cd_doc.SaveAs(str(CELDA), False)
res = {"phi0": round(phi0, 2), "brida_q0": [round(v, 1) for v in F], "occ": nombres}
b = acd.RangeBox
res["caja_mm"] = [[round(b.MinPoint.X * 10), round(b.MinPoint.Y * 10), round(b.MinPoint.Z * 10)],
                  [round(b.MaxPoint.X * 10), round(b.MaxPoint.Y * 10), round(b.MaxPoint.Z * 10)]]
# interferencia gripper - robot (control de montaje)
try:
    c1 = app.TransientObjects.CreateObjectCollection()
    c1.Add(og)
    c2 = app.TransientObjects.CreateObjectCollection()
    for k in ("V04", "V05"):
        c2.Add(next(o for o in inv._items(acd.Occurrences) if o.Name == nombres[k]))
    res["interferencias_gripper_robot"] = S(lambda: acd.AnalyzeInterference(c1, c2).Count)
except Exception as exc:  # noqa: BLE001
    res["interferencias_gripper_robot"] = str(exc)
for vista, cod in (("iso", 10759), ("frente", 10764)):
    try:
        cd_doc.Activate()
        cam = app.ActiveView.Camera
        cam.ViewOrientationType = cod
        cam.Fit()
        cam.Apply()
        app.ActiveView.SaveAsBitmap(str(OUT / f"celda_{vista}.png"), 1400, 1000)
    except Exception as exc:  # noqa: BLE001
        res[f"img_{vista}"] = str(exc)
(OUT / "celda.json").write_text(json.dumps(cfg, ensure_ascii=False, indent=1), encoding="utf-8")
res["tiempo_s"] = round(time.time() - T0, 1)
app.SilentOperation = False
print(json.dumps(res, ensure_ascii=False, indent=1))
