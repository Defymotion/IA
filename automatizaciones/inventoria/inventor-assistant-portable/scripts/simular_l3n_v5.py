"""L3N v5: renderiza la simulación de planta (celdas A y B) aplicando plan_l3n_v5.json sobre L3N_SIM5_Planta.iam
(armada con armar_l3n_sim5.py). No calcula nada: cada cuadro trae la cámara y los cambios (matrices 3x4 en mm,
visibilidad, garras 0..1 cerradas por gripper, giro 0..1 de cada mesa giratoria). Nada se guarda.
Garras: A por la restricción "Apertura" de cada módulo; B moviendo las piezas móviles (SIM_B_PM_*) sobre el eje del
apriete respecto del gripper.
Uso: python simular_l3n_v5.py <plan> [--desde N] [--hasta M] [--cuadros 0,120,500] [--ancho 1920 --alto 1080]
     [--carpeta Cuadros] [--zip nombre.zip] [--prueba-giratoria SIM_B_Gir_Deck:0,90] [--sin-pantalla]
"""
import argparse
import json
import math
import sys
import time
import traceback
import zipfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
import inventor_mcp as inv  # noqa: E402

a = argparse.ArgumentParser()
a.add_argument("plan")
a.add_argument("--desde", type=int, default=0)
a.add_argument("--hasta", type=int, default=10 ** 9)
a.add_argument("--cuadros", default="", help="sólo estos cuadros (pruebas)")
a.add_argument("--ancho", type=int, default=1920)
a.add_argument("--alto", type=int, default=1080)
a.add_argument("--carpeta", default="Cuadros")
a.add_argument("--zip", default="")
a.add_argument("--paso", type=int, default=1)
a.add_argument("--prueba-giratoria", default="", help="'SIM_B_Gir_Deck:th1,th2': fotos en planta de esa mesa y sale")
a.add_argument("--sin-pantalla", action="store_true")
a.add_argument("--camara", default="", help="'ex,ey,ez,tx,ty,tz,w': reemplaza la cámara del plan (fotos de detalle)")
x = a.parse_args()

S = inv._safe
T0 = time.time()
OUT = Path.home() / "Documents" / "InventorIA" / "Generados" / "L3N_SIM5"
ESC = OUT / "L3N_SIM5_Planta.iam"
AN = OUT / x.carpeta
AN.mkdir(parents=True, exist_ok=True)
plan = json.loads(Path(x.plan).read_text(encoding="utf-8"))
escj = json.loads((OUT / "escena.json").read_text(encoding="utf-8"))
app = inv._inventor(start_if_needed=False)
tg = app.TransientGeometry
log = {"avisos": []}
ANG = 0.52


def its(v):
    if v is None or isinstance(v, list):
        return v or []
    try:
        return inv._items(v)
    except Exception:  # noqa: BLE001
        return []


def mx(c):
    """3x4 plana (mm) -> Matrix; re-ortonormaliza (el plan redondea las rotaciones)."""
    ex = [c[0], c[4], c[8]]
    n = sum(v * v for v in ex) ** 0.5
    ex = [v / n for v in ex]
    ey = [c[1], c[5], c[9]]
    d = sum(a_ * b_ for a_, b_ in zip(ex, ey))
    ey = [b_ - d * a_ for a_, b_ in zip(ex, ey)]
    n = sum(v * v for v in ey) ** 0.5
    ey = [v / n for v in ey]
    ez = [ex[1] * ey[2] - ex[2] * ey[1], ex[2] * ey[0] - ex[0] * ey[2], ex[0] * ey[1] - ex[1] * ey[0]]
    m = tg.CreateMatrix()
    m.SetCoordinateSystem(tg.CreatePoint(c[3] / 10, c[7] / 10, c[11] / 10), tg.CreateVector(*ex),
                          tg.CreateVector(*ey), tg.CreateVector(*ez))
    return m


def mm(P, Q):
    """Producto de 3x4 planas (como 4x4 afines)."""
    out = []
    for i in range(3):
        for j in range(4):
            out.append(sum(P[i * 4 + k] * Q[k * 4 + j] for k in range(3)) + (P[i * 4 + 3] if j == 3 else 0.0))
    return out


def roty(deg, cx, cz):
    r = math.radians(deg)
    c, s = math.cos(r), math.sin(r)
    return [c, 0, s, cx - c * cx - s * cz, 0, 1, 0, 0, -s, 0, c, cz + s * cx - c * cz]


def abrir(p, visible=True):
    d = next((d for d in its(app.Documents) if S(lambda: Path(d.FullFileName).resolve() == Path(p).resolve(), False)), None)
    return d or app.Documents.Open(str(p), visible)


_TOP = {}
_SUBS = {}


def proxy(top_cd, ruta):
    """Ocurrencia por ruta 'A:1/B:1/C:1' (con caché de los hijos ya listados)."""
    if not _TOP:
        _TOP.update({o.Name: o for o in its(top_cd.Occurrences)})
    partes = ruta.split("/")
    o = _TOP.get(partes[0])
    clave = partes[0]
    for p in partes[1:]:
        if o is None:
            return None
        if clave not in _SUBS:
            _SUBS[clave] = {h.Name: h for h in its(o.SubOccurrences)}
        o = _SUBS[clave].get(p)
        clave += "/" + p
    return o


app.SilentOperation = True
doc = abrir(ESC, True)
doc.Activate()
time.sleep(1)
cd = doc.ComponentDefinition
occ = {o.Name: o for o in its(cd.Occurrences)}
falt = [n for n in plan["objetos"] if n not in occ]
if falt:
    log["avisos"].append(f"faltan objetos en la escena: {falt[:10]} ({len(falt)})")
dyn = {"@" + r: proxy(cd, r) for r in plan["proxy_dinamicos"]}
for r in plan["ocultar"]:
    o_ = proxy(cd, r)
    if o_ is not None and S(lambda: o_.Visible, False):
        S(lambda: setattr(o_, "Visible", False))

# ------------------------------------------------------------------ gripper A: restricción "Apertura" por módulo
GA = plan["grippers"]["SIM_A_Gripper"]
gA = occ["SIM_A_Gripper"]
gdocA = gA.Definition.Document
goccA = {o.Name: o for o in its(gdocA.ComponentDefinition.Occurrences)}
SIGNO = escj.get("signo_abre", 1)
V0A = escj["modulo_prueba"]["v0_mm"] / 10.0
MODS = []
for nm in GA["modulos"]:
    md = goccA[nm].Definition.Document
    ap = next(c for c in its(md.ComponentDefinition.Constraints) if "apertura" in c.Name.lower())
    MODS.append((md, ap))
CIERRE_A = GA["cierre_mm"]
# ------------------------------------------------------------------ gripper B: piezas móviles de primer nivel
GB = plan["grippers"]["SIM_B_Gripper"]
CIERRE_B = GB["cierre_mm"]
EJE_B = GB["eje_local"]
PARTES_B = [(p["nombre"], p["garra"], p["M_rel"]) for p in escj.get("gripper_B_partes", []) if p["nombre"] in occ]
if len(PARTES_B) < 5 * GB["n"]:
    log["avisos"].append(f"piezas móviles del gripper B en la escena: {len(PARTES_B)}")

# ------------------------------------------------------------------ mesas giratorias
GIRS = {}
for dk, gi in plan["giratorias"].items():
    GIRS[dk] = {"M0": plan["objetos"][dk]["M"], "eje": gi["eje"], "th": gi.get("th", [0.0, 90.0])}

vw = app.ActiveView
cam = vw.Camera
cs = app.ColorSchemes
for nombre in ("Presentation", "Presentación"):
    c_ = S(lambda: cs.Item(nombre), None)
    if c_ is not None:
        S(lambda: c_.Activate())
        break
S(lambda: setattr(cs, "BackgroundType", 52737))
ov = doc.ObjectVisibility
for p in ("Sketches", "Sketches3D", "SketchDimensions", "Annotations3D", "AllWorkFeatures", "ConstructionSurfaces",
          "UCSTriads", "UCSPlanes", "UCSAxes", "UCSPoints", "UserWorkPlanes", "OriginWorkPlanes"):
    S(lambda: setattr(ov, p, False))
for p, val in (("ShowAmbientShadows", True), ("ShowObjectShadows", True), ("ShowGroundShadows", True),
               ("ShowGroundPlane", False), ("ShowGroundReflections", False)):
    S(lambda: setattr(vw, p, val))
for nombre in ("Luz suave", "Soft Light"):
    luz = S(lambda: doc.LightingStyles.Item(nombre), None)
    if luz is not None:
        S(lambda: setattr(doc, "ActiveLightingStyle", luz))
        break
S(lambda: setattr(vw, "DisplayMode", 8452))
R = x.ancho / x.alto


def cam_set(c):
    ex, ey, ez, tx, ty, tz, w = c
    cam.Target = tg.CreatePoint(tx / 10, ty / 10, tz / 10)
    cam.Eye = tg.CreatePoint(ex / 10, ey / 10, ez / 10)
    cam.UpVector = tg.CreateUnitVector(0, 1, 0)
    cam.Perspective = True
    S(lambda: setattr(cam, "PerspectiveAngle", ANG))
    cam.SetExtents(w / 10, w / 10 / R)
    cam.Apply()


# ------------------------------------------------------------------ estado acumulado
estado_M = {n: o["M"] for n, o in plan["objetos"].items()}
estado_V = {n: o["vis"] for n, o in plan["objetos"].items()}
estado_G = {"SIM_A_Gripper": [0.0] * GA["n"], "SIM_B_Gripper": [0.0] * GB["n"]}
estado_gir = {dk: None for dk in GIRS}
aplic_M, aplic_V = {}, {}
aplic_GA = [None] * GA["n"]
aplic_B = {"M": None, "G": None}
aplic_gir = {dk: None for dk in GIRS}


def en_camara(c, p, margen=700.0):
    ex, ey, ez, tx, ty, tz, w = c
    f_ = [tx - ex, ty - ey, tz - ez]
    D = math.sqrt(sum(v * v for v in f_))
    f_ = [v / D for v in f_]
    r_ = [-f_[2], 0.0, f_[0]]
    nr = math.sqrt(sum(v * v for v in r_)) or 1.0
    r_ = [v / nr for v in r_]
    u_ = [r_[1] * f_[2] - r_[2] * f_[1], r_[2] * f_[0] - r_[0] * f_[2], r_[0] * f_[1] - r_[1] * f_[0]]
    v_ = [p[0] - ex, p[1] - ey, p[2] - ez]
    d = sum(a_ * b_ for a_, b_ in zip(v_, f_))
    if d <= 0:
        return False
    hx = (w / 2) / D * d + margen
    hy = (w / 2 / R) / D * d + margen
    return abs(sum(a_ * b_ for a_, b_ in zip(v_, r_))) <= hx and abs(sum(a_ * b_ for a_, b_ in zip(v_, u_))) <= hy


T_AP = {"cajas": 0.0, "otros": 0.0, "vis": 0.0, "garras_A": 0.0, "garras_B": 0.0, "gir": 0.0, "n_cajas": 0, "n_otros": 0,
        "n_omitidas": 0}


def aplicar(c=None):
    n_ = 0
    t_ = time.time()
    for nm, v in estado_V.items():
        if aplic_V.get(nm) != v:
            o = dyn.get(nm) if nm.startswith("@") else occ.get(nm)
            if o is not None:
                if v and nm in estado_M and aplic_M.get(nm) is not estado_M[nm]:
                    o.Transformation = mx(estado_M[nm])
                    aplic_M[nm] = estado_M[nm]
                S(lambda: setattr(o, "Visible", bool(v)))
            aplic_V[nm] = v
    T_AP["vis"] += time.time() - t_
    for nm, M in estado_M.items():
        if nm in GIRS or nm not in occ or aplic_M.get(nm) is M:
            continue
        liviano = "_Caja_" in nm or "_Film_" in nm
        if liviano and (not estado_V.get(nm, True) or (c is not None and not en_camara(c, (M[3], M[7], M[11])))):
            T_AP["n_omitidas"] += 1
            continue
        t_ = time.time()
        occ[nm].Transformation = mx(M)
        aplic_M[nm] = M
        n_ += 1
        T_AP["cajas" if liviano else "otros"] += time.time() - t_
        T_AP["n_cajas" if liviano else "n_otros"] += 1
    # garras A
    t_ = time.time()
    cambio = False
    for k, f in enumerate(estado_G["SIM_A_Gripper"]):
        if aplic_GA[k] != f:
            md, ap = MODS[k]
            ap.Offset.Value = V0A - SIGNO * (CIERRE_A / 10.0) * f
            md.Update()
            aplic_GA[k] = f
            cambio = True
    if cambio:
        gdocA.Update()
    T_AP["garras_A"] += time.time() - t_
    # garras B (piezas de primer nivel que acompañan al gripper)
    t_ = time.time()
    Mg = estado_M["SIM_B_Gripper"]
    GBv = estado_G["SIM_B_Gripper"]
    visible_B = c is None or en_camara(c, (Mg[3], Mg[7], Mg[11]), 1500.0)
    if visible_B and (aplic_B["M"] is not Mg or aplic_B["G"] is not GBv):
        for nm, gi, Mrel in PARTES_B:
            d = CIERRE_B * GBv[gi]
            T = [1, 0, 0, EJE_B[0] * d, 0, 1, 0, EJE_B[1] * d, 0, 0, 1, EJE_B[2] * d]
            occ[nm].Transformation = mx(mm(Mg, mm(T, Mrel)))
        aplic_B["M"], aplic_B["G"] = Mg, GBv
    T_AP["garras_B"] += time.time() - t_
    # mesas giratorias
    t_ = time.time()
    for dk, gi in GIRS.items():
        f = estado_gir[dk]
        if f is not None and aplic_gir[dk] != f:
            th = gi["th"][0] + (gi["th"][1] - gi["th"][0]) * f
            occ[dk].Transformation = mx(mm(roty(th, *gi["eje"]), gi["M0"]))
            aplic_gir[dk] = f
    T_AP["gir"] += time.time() - t_
    return n_


lista = [int(v) for v in x.cuadros.split(",")] if x.cuadros else None
FR = plan["cuadros"]
hasta = min(x.hasta, len(FR) - 1)
ultimo = max(lista) if lista else hasta
hechos = []
tiempos = []
if x.prueba_giratoria:
    dk, ths = x.prueba_giratoria.split(":")
    gi = GIRS[dk]
    fotos = []
    occ[dk].Visible = True
    GX, GZ = gi["eje"]
    for th in (float(v) for v in ths.split(",")):
        occ[dk].Transformation = mx(mm(roty(th, GX, GZ), gi["M0"]))
        doc.Update()
        cam.Target = tg.CreatePoint(GX / 10, 30.0, GZ / 10)
        cam.Eye = tg.CreatePoint(GX / 10, 900.0, GZ / 10)
        cam.UpVector = tg.CreateUnitVector(-1, 0, 0)
        cam.Perspective = False
        cam.SetExtents(420.0, 420.0 / R)
        cam.Apply()
        vw.Update()
        vw.SaveAsBitmap(str(AN / "calentamiento.png"), 640, 360)
        pth = AN / f"giratoria_{dk}_th{int(round(th)):+04d}.png"
        vw.SaveAsBitmap(str(pth), 1600, 900)
        fotos.append(pth.name)
    log["prueba_giratoria"] = fotos
    print(json.dumps(log, ensure_ascii=False, indent=1))
    S(lambda: setattr(app, "SilentOperation", False))
    sys.exit(0)
camara_fija = [float(v) for v in x.camara.split(",")] if x.camara else None
try:
    t_render = 0.0
    calentado = False
    for i, f in enumerate(FR):
        if i > ultimo:
            break
        for nm, M in f["M"].items():
            estado_M[nm] = M
        estado_V.update(f["V"])
        for gk, gv in f.get("G", {}).items():
            estado_G[gk] = gv
        for dk, gv in f.get("gir", {}).items():
            estado_gir[dk] = gv
        if (lista and i not in lista) or (not lista and (i < x.desde or (i - x.desde) % x.paso)):
            continue
        cam_f = camara_fija or f["cam"]
        t1 = time.time()
        if x.sin_pantalla:
            S(lambda: setattr(app, "ScreenUpdating", False))
        n_ = aplicar(cam_f)
        t2 = time.time()
        doc.Update()
        if x.sin_pantalla:
            S(lambda: setattr(app, "ScreenUpdating", True))
        t3 = time.time()
        cam_set(cam_f)
        if not calentado or lista:
            for _ in range(2):
                vw.Update()
                vw.SaveAsBitmap(str(AN / "calentamiento.png"), 640, 360)
            cam_set(cam_f)
            calentado = True
        ruta = AN / (f"c{i:05d}.png" if not camara_fija else f"det_c{i:05d}.png")
        t4 = time.time()
        vw.SaveAsBitmap(str(ruta), x.ancho, x.alto)
        hechos.append(ruta)
        dt = time.time() - t1
        tiempos.append([round(t2 - t1, 2), round(t3 - t2, 2), round(t4 - t3, 2), round(time.time() - t4, 2)])
        t_render += dt
        if len(hechos) % 25 == 1 or lista:
            print(f"[{time.time() - T0:7.1f} s] cuadro {i} ({n_} movidos, {dt:.2f} s)", flush=True)
except Exception as exc:  # noqa: BLE001
    log["error"] = repr(exc)
    log["traza"] = traceback.format_exc()[-2000:]
finally:
    for md, ap in MODS:                                         # garras A como en el modelo (no se guarda nada)
        S(lambda: setattr(ap.Offset, "Value", V0A))
        S(lambda: md.Update())
    S(lambda: gdocA.Update())
    S(lambda: setattr(app, "SilentOperation", False))
log["hechos"] = len(hechos)
log["s_por_cuadro"] = round(t_render / max(1, len(hechos)), 2)
log["aplicar_desglose_s"] = {k: round(v, 2) for k, v in T_AP.items()}
if tiempos:
    log["tiempos_medios_aplicar_update_camara_guardar"] = [round(sum(t[k] for t in tiempos) / len(tiempos), 2) for k in range(4)]
if x.zip and hechos:
    with zipfile.ZipFile(AN / x.zip, "w", zipfile.ZIP_STORED) as z:
        for r in hechos:
            z.write(r, r.name)
    log["zip"] = str(AN / x.zip)
log["tiempo_s"] = round(time.time() - T0, 1)
log["primero"], log["ultimo"] = (hechos[0].name, hechos[-1].name) if hechos else (None, None)
(AN / f"resultado_{x.desde}_{hasta}.json").write_text(json.dumps(log, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps(log, ensure_ascii=False, indent=1))
