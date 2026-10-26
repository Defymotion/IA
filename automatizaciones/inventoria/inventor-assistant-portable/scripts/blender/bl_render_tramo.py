"""(Corre DENTRO de Blender, con la escena de bl_armar_escena.py) Aplica el plan v5 cuadro a cuadro y renderiza.
Mismo estado acumulado que simular_l3n_v5.py: matrices 3x4 (mm, Inventor), visibilidad, garras del gripper B
(piezas SIM_B_PM_* trasladadas sobre su eje), giro de las mesas giratorias y cámara (ojo, objetivo, ancho).
Uso: blender -b L3N_SIM5.blend -P bl_render_tramo.py -- <plan.json> <escena.json de Inventor> <carpeta_salida>
     <desde> <hasta> [--paso N] [--cuadros a,b,c] [--muestras 32]
"""
import json
import math
import os
import sys
import time

import bpy
from mathutils import Matrix, Vector

T0 = time.time()
argv = sys.argv[sys.argv.index("--") + 1:]
PLANJ, ESCI, SAL, DESDE, HASTA = argv[0], argv[1], argv[2], int(argv[3]), int(argv[4])
PASO = int(argv[argv.index("--paso") + 1]) if "--paso" in argv else 1
LISTA = [int(v) for v in argv[argv.index("--cuadros") + 1].split(",")] if "--cuadros" in argv else None
MUESTRAS = int(argv[argv.index("--muestras") + 1]) if "--muestras" in argv else None
os.makedirs(SAL, exist_ok=True)
plan = json.load(open(PLANJ, encoding="utf-8"))
escI = json.load(open(ESCI, encoding="utf-8"))
sc = bpy.context.scene
if MUESTRAS:
    try:
        sc.eevee.taa_render_samples = MUESTRAS
    except Exception:  # noqa: BLE001
        pass
C = Matrix(((1, 0, 0, 0), (0, 0, -1, 0), (0, 1, 0, 0), (0, 0, 0, 1)))
R = sc.render.resolution_x / sc.render.resolution_y


def Mm(M):
    return Matrix(((M[0], M[1], M[2], M[3] / 1000.0), (M[4], M[5], M[6], M[7] / 1000.0),
                   (M[8], M[9], M[10], M[11] / 1000.0), (0, 0, 0, 1)))


def mm(P, Q):
    out = []
    for i in range(3):
        for j in range(4):
            out.append(sum(P[i * 4 + k] * Q[k * 4 + j] for k in range(3)) + (P[i * 4 + 3] if j == 3 else 0.0))
    return out


def roty(deg, cx, cz):
    r = math.radians(deg)
    c, s = math.cos(r), math.sin(r)
    return [c, 0, s, cx - c * cx - s * cz, 0, 1, 0, 0, -s, 0, c, cz + s * cx - c * cz]


OBJ = {o.name[4:]: o for o in bpy.data.objects if o.name.startswith("SIM:")}
HIJOS = {}
for o in bpy.data.objects:
    if o.parent is not None and o.parent.name.startswith("SIM:"):
        HIJOS.setdefault(o.parent.name[4:], []).append(o)
FIJOS = [o for o in bpy.data.objects if "ruta" in o.keys()]
DIN = {}
for r in plan["proxy_dinamicos"]:
    DIN["@" + r] = [o for o in FIJOS if o["ruta"] == r or o["ruta"].startswith(r + "/")]
GB = plan["grippers"]["SIM_B_Gripper"]
PARTES_B = [(p["nombre"], p["garra"], p["M_rel"]) for p in escI.get("gripper_B_partes", []) if p["nombre"] in OBJ]
GIRS = {dk: {"M0": plan["objetos"][dk]["M"], "eje": gi["eje"], "th": gi.get("th", [0.0, 90.0])}
        for dk, gi in plan["giratorias"].items()}
cam = sc.camera
log = {"avisos": [], "faltan": [n for n in plan["objetos"] if n not in OBJ][:20], "partes_B": len(PARTES_B),
       "dinamicos": {k: len(v) for k, v in DIN.items()}}

estado_M = {n: o["M"] for n, o in plan["objetos"].items()}
estado_V = {n: o["vis"] for n, o in plan["objetos"].items()}
estado_G = {"SIM_B_Gripper": [0.0] * GB["n"]}
estado_gir = {dk: None for dk in GIRS}
aplic_M, aplic_V, aplic_gir = {}, {}, {}
aplic_B = [None, None]


def poner(nm, M):
    o = OBJ.get(nm)
    if o is not None:
        o.matrix_world = C @ Mm(M)


def visible(nm, v):
    if nm.startswith("@"):
        for o in DIN.get(nm, []):
            o.hide_render = not v
        return
    o = OBJ.get(nm)
    if o is None:
        return
    o.hide_render = not v
    for h in HIJOS.get(nm, []):
        h.hide_render = not v


def aplicar():
    for nm, v in estado_V.items():
        if aplic_V.get(nm) != v:
            visible(nm, v)
            aplic_V[nm] = v
    for nm, M in estado_M.items():
        if nm in GIRS or aplic_M.get(nm) is M:
            continue
        poner(nm, M)
        aplic_M[nm] = M
    Mg, Gv = estado_M["SIM_B_Gripper"], estado_G["SIM_B_Gripper"]
    if aplic_B[0] is not Mg or aplic_B[1] is not Gv:
        e = GB["eje_local"]
        for nm, gi, Mrel in PARTES_B:
            d = GB["cierre_mm"] * Gv[gi]
            T = [1, 0, 0, e[0] * d, 0, 1, 0, e[1] * d, 0, 0, 1, e[2] * d]
            poner(nm, mm(Mg, mm(T, Mrel)))
        aplic_B[0], aplic_B[1] = Mg, Gv
    for dk, gi in GIRS.items():
        f = estado_gir[dk]
        if f is not None and aplic_gir.get(dk) != f:
            th = gi["th"][0] + (gi["th"][1] - gi["th"][0]) * f
            poner(dk, mm(roty(th, *gi["eje"]), gi["M0"]))
            aplic_gir[dk] = f


K_DIST = float(argv[argv.index("--k-dist") + 1]) if "--k-dist" in argv else 1.1032


def camara(c):
    """Como Inventor (camara_inventor.py): mismo objetivo y dirección, pero el ojo a K_DIST·ancho del objetivo y el
    ancho pedido visible en el plano del objetivo."""
    ex, ey, ez, tx, ty, tz, w = c
    ojo = (C @ Vector((ex / 1000.0, ey / 1000.0, ez / 1000.0, 1.0))).to_3d()
    obj = (C @ Vector((tx / 1000.0, ty / 1000.0, tz / 1000.0, 1.0))).to_3d()
    d = obj - ojo
    D = K_DIST * w / 1000.0 if K_DIST > 0 else d.length
    cam.location = obj - d.normalized() * D
    cam.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    cam.data.sensor_fit = "HORIZONTAL"
    cam.data.angle = 2.0 * math.atan((w / 1000.0) / 2.0 / D)


tiempos = []
FR = plan["cuadros"]
ultimo = max(LISTA) if LISTA else min(HASTA, len(FR) - 1)
for i, f in enumerate(FR):
    if i > ultimo:
        break
    for nm, M in f["M"].items():
        estado_M[nm] = M
    estado_V.update(f["V"])
    for gk, gv in f.get("G", {}).items():
        if gk in estado_G:
            estado_G[gk] = gv
    for dk, gv in f.get("gir", {}).items():
        estado_gir[dk] = gv
    if (LISTA and i not in LISTA) or (not LISTA and (i < DESDE or (i - DESDE) % PASO)):
        continue
    t1 = time.time()
    aplicar()
    camara(f["cam"])
    sc.render.filepath = os.path.join(SAL, f"c{i:05d}.png")
    bpy.ops.render.render(write_still=True)
    tiempos.append(round(time.time() - t1, 2))
    if len(tiempos) % 10 == 1:
        print(f"[{time.time() - T0:7.1f} s] cuadro {i} ({tiempos[-1]} s)", flush=True)
log["cuadros"] = len(tiempos)
log["s_por_cuadro"] = round(sum(tiempos) / max(1, len(tiempos)), 2)
log["tiempos_primeros"] = tiempos[:5]
log["tiempo_s"] = round(time.time() - T0, 1)
log["motor"] = sc.render.engine
print("RESULTADO " + json.dumps(log, ensure_ascii=False), flush=True)
