"""L3N: renderiza la simulación completa de planta aplicando plan_l3n.json sobre la escena copia L3N_SIM_Planta.iam
(armada con armar_l3n_sim.py). No calcula nada: cada cuadro trae la cámara y los cambios (matrices 3x4 en mm,
visibilidad, garras 0..1 cerradas, giro de la mesa giratoria 0..1). Nada se guarda.
Uso: python simular_l3n_planta.py <plan_l3n.json> [--desde N] [--hasta M] [--cuadros 0,120,500] [--ancho 1920 --alto 1080]
     [--carpeta Animacion] [--zip nombre.zip]
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
a.add_argument("--carpeta", default="Animacion")
a.add_argument("--zip", default="")
a.add_argument("--paso", type=int, default=1, help="renderiza 1 de cada N cuadros (el estado se acumula igual)")
a.add_argument("--apertura", type=float, default=25.0, help="mm que abre la pala móvil")
a.add_argument("--gir-th", default="", help="'thZ,thX': giro (grados, respecto del modelo) para transportar en Z y en X")
a.add_argument("--prueba-giratoria", default="", help="'th1,th2,...': sólo fotos en planta de la mesa giratoria y sale")
a.add_argument("--sin-pantalla", action="store_true", help="ScreenUpdating=False mientras se mueven las piezas")
x = a.parse_args()

S = inv._safe
T0 = time.time()
OUT = Path.home() / "Documents" / "InventorIA" / "Generados" / "L3N_SIM2"
ESC = OUT / "L3N_SIM_Planta.iam"
AN = OUT / x.carpeta
AN.mkdir(parents=True, exist_ok=True)
plan = json.loads(Path(x.plan).read_text(encoding="utf-8"))
escj = json.loads((OUT / "escena.json").read_text(encoding="utf-8"))
app = inv._inventor(start_if_needed=False)
tg = app.TransientGeometry
log = {"avisos": [], "cuadros": []}
ANG = 0.52


def mx(c):
    """3x4 plana (mm) -> Matrix; re-ortonormaliza (el plan redondea las rotaciones a 4 decimales)."""
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
            v = sum(P[i * 4 + k] * Q[k * 4 + j] for k in range(3)) + (P[i * 4 + 3] if j == 3 else 0.0)
            out.append(v)
    return out


def roty(deg, cx, cz):
    r = math.radians(deg)
    c, s = math.cos(r), math.sin(r)
    # T(c) R T(-c)
    return [c, 0, s, cx - c * cx - s * cz, 0, 1, 0, 0, -s, 0, c, cz + s * cx - c * cz]


def abrir(p, visible=True):
    d = next((d for d in inv._items(app.Documents) if S(lambda: Path(d.FullFileName).resolve() == Path(p).resolve(), False)), None)
    return d or app.Documents.Open(str(p), visible)


def proxy(top_cd, ruta):
    partes = ruta.split("/")
    o = next((o for o in inv._items(top_cd.Occurrences) if o.Name == partes[0]), None)
    for p in partes[1:]:
        if o is None:
            return None
        o = next((h for h in inv._items(o.SubOccurrences) if h.Name == p), None)
    return o


app.SilentOperation = True
doc = abrir(ESC, True)
doc.Activate()
time.sleep(1)
cd = doc.ComponentDefinition
occ = {o.Name: o for o in inv._items(cd.Occurrences)}
falt = [n for n in plan["objetos"] if n not in occ]
if falt:
    log["avisos"].append(f"faltan objetos en la escena: {falt[:10]} ({len(falt)})")
dyn = {"@" + r: proxy(cd, r) for r in plan["proxy_dinamicos"]}
for r in plan["ocultar"]:                      # por si la escena se armó con un plan anterior (p. ej. paredes)
    o_ = proxy(cd, r)
    if o_ is not None and S(lambda: o_.Visible, False):
        S(lambda: setattr(o_, "Visible", False))
# garras: un módulo por archivo en Gripper_SIM
grip = occ["SIM_Gripper"]
gdoc = grip.Definition.Document
gocc = {o.Name: o for o in inv._items(gdoc.ComponentDefinition.Occurrences)}
MODS = []
for nm in plan["gripper"]["modulos"]:
    o = gocc.get(nm)
    md = o.Definition.Document
    ap = next(c for c in inv._items(md.ComponentDefinition.Constraints) if "apertura" in c.Name.lower())
    MODS.append((md, ap, ap.Offset.Value))
SIGNO = escj.get("signo_abre", 1)
# mesa giratoria: ángulo para "transporta en Z" (rodillos a lo largo de X) y "transporta en X"
deck0 = plan["objetos"]["SIM_Gir_Deck"]["M"]
def _hojas(o, out):
    subs = S(lambda: inv._items(o.SubOccurrences), []) or []
    if not subs:
        out.append(o)
    for h in subs:
        _hojas(h, out)
    return out


# eje de los rodillos del deck: hojas alargadas (largo > 600 y 6 veces el ancho), en coordenadas del deck
votos = {0: 0, 1: 0, 2: 0}
for o in inv._items(occ["SIM_Gir_Deck"].Definition.Document.ComponentDefinition.Occurrences):
    for h in _hojas(o, []):
        b = S(lambda: h.RangeBox, None)
        if b is None:
            continue
        L = [abs(b.MaxPoint.X - b.MinPoint.X) * 10, abs(b.MaxPoint.Y - b.MinPoint.Y) * 10, abs(b.MaxPoint.Z - b.MinPoint.Z) * 10]
        k = L.index(max(L))
        if L[k] > 600 and L[k] > 6 * sorted(L)[1]:
            votos[k] += 1
col = max(votos, key=votos.get)
EJE_L = "XYZ"[col]
log["giratoria_votos"] = votos
ax_w = (deck0[col], deck0[4 + col], deck0[8 + col])          # eje del rodillo en el mundo, en la pose del modelo
ang_ax = math.degrees(math.atan2(-ax_w[2], ax_w[0]))          # ángulo en planta (convención rot_y)
th_z = -ang_ax                                                # girar para que el eje quede sobre +X (transporta en Z)
th_z = (th_z + 90) % 180 - 90
th_x = th_z + 90.0 if th_z < 0 else th_z - 90.0
if plan["giratoria"].get("th"):                 # verificado con --prueba-giratoria (fotos en planta)
    th_z, th_x = plan["giratoria"]["th"]
if x.gir_th:
    th_z, th_x = (float(v) for v in x.gir_th.split(","))
GX, GZ = plan["giratoria"]["eje"]
log["giratoria"] = {"eje_rodillo_local": EJE_L, "th_transporta_Z": round(th_z, 2), "th_transporta_X": round(th_x, 2)}

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
estado_G = [1.0] * 7
estado_gir = 0.0
aplic_M, aplic_V, aplic_G, aplic_gir = {}, {}, [None] * 7, None


def en_camara(c, p, margen=700.0):
    """¿El punto p (mm) cae en el encuadre de la cámara c (ojo, objetivo, ancho) con un margen?"""
    ex, ey, ez, tx, ty, tz, w = c
    f_ = [tx - ex, ty - ey, tz - ez]
    D = math.sqrt(sum(v * v for v in f_))
    f_ = [v / D for v in f_]
    r_ = [f_[1] * 0 - f_[2] * 1, f_[2] * 0 - f_[0] * 0, f_[0] * 1 - f_[1] * 0]      # f x (0,1,0)
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


T_AP = {"cajas": 0.0, "otros": 0.0, "vis": 0.0, "garras": 0.0, "gir": 0.0, "n_cajas": 0, "n_otros": 0, "n_omitidas": 0}


def aplicar(c=None):
    global aplic_gir
    n_ = 0
    t_ = time.time()
    for nm, v in estado_V.items():
        if aplic_V.get(nm) != v:
            o = dyn.get(nm) if nm.startswith("@") else occ.get(nm)
            if o is not None:
                if v and nm in estado_M and aplic_M.get(nm) is not estado_M[nm]:
                    o.Transformation = mx(estado_M[nm])          # se mueve antes de mostrarla
                    aplic_M[nm] = estado_M[nm]
                S(lambda: setattr(o, "Visible", bool(v)))
            aplic_V[nm] = v
    T_AP["vis"] += time.time() - t_
    for nm, M in estado_M.items():
        if nm == "SIM_Gir_Deck" or nm not in occ or aplic_M.get(nm) is M:
            continue
        caja_ = nm.startswith("SIM_Caja_") or nm.startswith("SIM_Film_")
        if caja_ and (not estado_V.get(nm, True) or (c is not None and not en_camara(c, (M[3], M[7], M[11])))):
            T_AP["n_omitidas"] += 1
            continue                                   # oculta o fuera de cuadro: se acomoda cuando haga falta
        t_ = time.time()
        occ[nm].Transformation = mx(M)
        aplic_M[nm] = M
        n_ += 1
        T_AP["cajas" if caja_ else "otros"] += time.time() - t_
        T_AP["n_cajas" if caja_ else "n_otros"] += 1
    t_ = time.time()
    cambio_g = False
    for k, f in enumerate(estado_G):
        if aplic_G[k] != f:
            md, ap, v0 = MODS[k]
            ap.Offset.Value = v0 + SIGNO * (x.apertura / 10.0) * (1.0 - f)
            md.Update()
            aplic_G[k] = f
            cambio_g = True
    if cambio_g:
        gdoc.Update()
    T_AP["garras"] += time.time() - t_
    t_ = time.time()
    if aplic_gir != estado_gir:
        th = th_z + (th_x - th_z) * estado_gir
        occ["SIM_Gir_Deck"].Transformation = mx(mm(roty(th, GX, GZ), deck0))
        aplic_gir = estado_gir
    T_AP["gir"] += time.time() - t_
    return n_


lista = [int(v) for v in x.cuadros.split(",")] if x.cuadros else None
FR = plan["cuadros"]
hasta = min(x.hasta, len(FR) - 1)
ultimo = max(lista) if lista else hasta
hechos = []
tiempos = []
if x.prueba_giratoria:
    fotos = []
    occ["SIM_Gir_Deck"].Visible = True
    for th in (float(v) for v in x.prueba_giratoria.split(",")):
        occ["SIM_Gir_Deck"].Transformation = mx(mm(roty(th, GX, GZ), deck0))
        doc.Update()
        cam.Target = tg.CreatePoint(GX / 10, 30.0, GZ / 10)
        cam.Eye = tg.CreatePoint(GX / 10, 900.0, GZ / 10)
        cam.UpVector = tg.CreateUnitVector(-1, 0, 0)
        cam.Perspective = False
        cam.SetExtents(420.0, 420.0 / R)
        cam.Apply()
        vw.Update()
        vw.SaveAsBitmap(str(AN / "calentamiento.png"), 640, 360)
        pth = AN / f"giratoria_th{int(round(th)):+04d}.png"
        vw.SaveAsBitmap(str(pth), 1600, 900)
        fotos.append(pth.name)
    log["prueba_giratoria"] = fotos
    print(json.dumps(log, ensure_ascii=False, indent=1))
    S(lambda: setattr(app, "SilentOperation", False))
    sys.exit(0)
try:
    t_render = 0.0
    calentado = False
    for i, f in enumerate(FR):
        if i > ultimo:
            break
        for nm, M in f["M"].items():
            estado_M[nm] = M
        estado_V.update(f["V"])
        if "G" in f:
            estado_G = f["G"]
        if "gir" in f:
            estado_gir = f["gir"]
        if (lista and i not in lista) or (not lista and (i < x.desde or (i - x.desde) % x.paso)):
            continue
        t1 = time.time()
        if x.sin_pantalla:
            S(lambda: setattr(app, "ScreenUpdating", False))
        n_ = aplicar(f["cam"])
        t2 = time.time()
        doc.Update()
        if x.sin_pantalla:
            S(lambda: setattr(app, "ScreenUpdating", True))
        t3 = time.time()
        cam_set(f["cam"])
        if not calentado or lista:
            for _ in range(2):
                vw.Update()
                vw.SaveAsBitmap(str(AN / "calentamiento.png"), 640, 360)
            cam_set(f["cam"])
            calentado = True
        ruta = AN / f"c{i:05d}.png"
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
    for md, ap, v0 in MODS:                                    # garras como estaban (no se guarda nada)
        S(lambda: setattr(ap.Offset, "Value", v0))
        S(lambda: md.Update())
    S(lambda: gdoc.Update())
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
