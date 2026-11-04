"""L3N: robots de las celdas B y C fijos para siempre. El KUKA y el gripper del CAD son subensambles flexibles que se
desarman al recalcular. En Celdas_IA\\Celda_B_existente.iam y Celda_C_existente.iam:
1) respaldo del .iam en Celdas_IA\\_respaldos\\ (antes de tocar nada);
2) agrega los eslabones V01..V05 del KR 140 como piezas sueltas y el gripper ADECO2 como ensamble rígido, todos
   empotrados (Grounded) en la pose de reposo de la simulación (gripper centrado sobre el pallet, 250 mm arriba de la
   carga), sin las bandejas del gripper;
3) borra el KUKA-...-ASM y el Gripper_ADECO2_V1 originales de la celda;
4) guarda la celda. Los layouts que la usan (v7, v9, ...) se actualizan solos.
Datos: Analisis\\L3N\\robots_bc_fijos.json (matrices en coordenadas de la celda, mm).
Uso: python l3n_robots_bc_fijos.py <resultado.json> [--celdas B,C] [--fotos <layout.iam>]
"""
import json
import shutil
import sys
import time
import traceback
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
import inventor_mcp as inv  # noqa: E402

S = inv._safe
T0 = time.time()
A = sys.argv
OUT = Path(A[1])
CELDAS = A[A.index("--celdas") + 1].split(",") if "--celdas" in A else ["B", "C"]
BASE = Path(r"C:\DEFYMOTION\L3N\Celdas_IA")
DATOS = json.loads((Path.home() / "Documents" / "InventorIA" / "Analisis" / "L3N" / "robots_bc_fijos.json").read_text(encoding="utf-8"))
app = inv._inventor(start_if_needed=False)
tg = app.TransientGeometry
log = {"avisos": [], "celdas": {}}


def orto(x_, y_):
    n = sum(v * v for v in x_) ** 0.5
    x_ = [v / n for v in x_]
    d = sum(a * b for a, b in zip(x_, y_))
    y_ = [b - d * a for a, b in zip(x_, y_)]
    n = sum(v * v for v in y_) ** 0.5
    y_ = [v / n for v in y_]
    z_ = [x_[1] * y_[2] - x_[2] * y_[1], x_[2] * y_[0] - x_[0] * y_[2], x_[0] * y_[1] - x_[1] * y_[0]]
    return x_, y_, z_


def mx(M):
    """Matriz (mm) a Inventor; re-ortonormaliza (las del plan vienen redondeadas y Add da E_INVALIDARG)."""
    ex, ey, ez = orto([M[0][0], M[1][0], M[2][0]], [M[0][1], M[1][1], M[2][1]])
    m = tg.CreateMatrix()
    m.SetCoordinateSystem(tg.CreatePoint(M[0][3] / 10, M[1][3] / 10, M[2][3] / 10), tg.CreateVector(*ex),
                          tg.CreateVector(*ey), tg.CreateVector(*ez))
    return m


def caja(o):
    b = o.RangeBox
    return [round(v * 10, 1) for v in (b.MinPoint.X, b.MinPoint.Y, b.MinPoint.Z, b.MaxPoint.X, b.MaxPoint.Y, b.MaxPoint.Z)]


def abierto(p):
    return next((d for d in inv._items(app.Documents) if S(lambda d=d: Path(d.FullFileName).resolve() == Path(p).resolve(), False)), None)


app.SilentOperation = True
try:
    for c in CELDAS:
        nombre = f"Celda_{c}_existente"
        ruta = BASE / f"{nombre}.iam"
        D = DATOS[nombre]
        L = {"avisos": []}
        log["celdas"][nombre] = L
        doc = abierto(ruta)
        if doc is not None and S(lambda: doc.Dirty, False) and not any(
                o.Name.startswith(("KUKA_fijo_", "Gripper_fijo")) for o in inv._items(doc.ComponentDefinition.Occurrences)):
            L["avisos"].append("la celda estaba abierta con cambios sin guardar: no la toco")
            continue
        resp = BASE / "_respaldos"
        resp.mkdir(exist_ok=True)
        dst = resp / f"{nombre}_antes_robot_fijo_{time.strftime('%Y%m%d_%H%M%S')}.iam"
        shutil.copy2(ruta, dst)
        L["respaldo"] = str(dst)
        doc = doc or app.Documents.Open(str(ruta), False)
        cd = doc.ComponentDefinition
        occ = {o.Name: o for o in inv._items(cd.Occurrences)}
        ya = [n for n in occ if n.startswith(("KUKA_fijo_", "Gripper_fijo"))]
        if ya:
            L["avisos"].append(f"ya tenía {ya}: los reemplazo")
            for n in ya:
                S(lambda n=n: occ[n].Delete())
        L["nuevos"] = {}
        for p in D["piezas"]:
            o = cd.Occurrences.Add(p["f"], mx(p["M"]))
            S(lambda: setattr(o, "Name", p["n"]))
            S(lambda: setattr(o, "Grounded", True))
            S(lambda: setattr(o, "Flexible", False))
            for pref in p.get("ocultar_hijos", []):
                for h in inv._items(o.SubOccurrences):
                    if h.Name.startswith(pref.rstrip("*")):
                        S(lambda h=h: setattr(h, "Visible", False))
            L["nuevos"][p["n"]] = S(lambda: caja(o))
        L["borrados"] = []
        for n in D["borrar"]:
            o = occ.get(n)
            if o is None:
                L["avisos"].append(f"no estaba {n}")
                continue
            o.Delete()
            L["borrados"].append(n)
        doc.Update()
        doc.Save()
        L["guardado"] = str(ruta)
        print(nombre, json.dumps(L, ensure_ascii=False)[:800], flush=True)
    if "--fotos" in A:
        lay = Path(A[A.index("--fotos") + 1])
        d = abierto(lay) or app.Documents.Open(str(lay), True)
        d.Update()
        ocultar = [o for o in inv._items(d.ComponentDefinition.Occurrences) if o.Name.startswith(("Robot_Aereo", "Paredes"))
                   and S(lambda o=o: o.Visible, False)]
        for o in ocultar:
            S(lambda o=o: setattr(o, "Visible", False))
        d.Activate()
        time.sleep(2)
        v = app.ActiveView
        cam = v.Camera
        c0 = (cam.Eye, cam.Target, cam.UpVector, S(lambda: cam.Perspective, False))
        carpeta = Path.home() / "Documents" / "InventorIA" / "Analisis" / "L3N" / "robots_bc_fijos"
        carpeta.mkdir(parents=True, exist_ok=True)
        log["fotos"] = []
        try:
            for nm, (x, z) in (("B", (-8108.0, -42051.0)), ("C", (-8167.0, -52719.0))):
                for k, (ex, ey, ez) in enumerate(((5200, 4200, 4200), (-4800, 3800, -4600))):
                    cam.Target = tg.CreatePoint((x - 600) / 10, 150.0, (z - 900) / 10)
                    cam.Eye = tg.CreatePoint((x - 600 + ex) / 10, ey / 10, (z - 900 + ez) / 10)
                    cam.UpVector = tg.CreateUnitVector(0, 1, 0)
                    cam.Perspective = True
                    cam.SetExtents(560, 350)
                    cam.Apply()
                    r = carpeta / f"robot_{nm}_{k + 1}.png"
                    for _ in range(2):
                        v.Update()
                        v.SaveAsBitmap(str(r), 1600, 1000)
                    log["fotos"].append(str(r))
        finally:
            for o in ocultar:
                S(lambda o=o: setattr(o, "Visible", True))
            S(lambda: setattr(cam, "Perspective", c0[3]))
            cam.Eye, cam.Target, cam.UpVector = c0[0], c0[1], c0[2]
            S(lambda: cam.Apply())
except Exception as exc:  # noqa: BLE001
    log["error"] = repr(exc)
    log["traza"] = traceback.format_exc()[-2500:]
finally:
    S(lambda: setattr(app, "SilentOperation", False))
log["s"] = round(time.time() - T0, 1)
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(log, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps(log, ensure_ascii=False, indent=1)[:5000])
