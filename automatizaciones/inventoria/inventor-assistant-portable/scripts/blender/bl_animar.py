"""(Corre DENTRO de Blender, sobre la escena de bl_armar_escena.py) Pasa el plan v5 a una animación con claves:
- cada objeto SIM (Empty "SIM:<nombre>") con claves de posición/giro donde cambia (interpolación lineal, con clave de
  espera antes de cada cambio) y visibilidad por escala 0/1 (constante);
- palas del gripper B (SIM_B_PM_*) hijas del gripper B y palas del gripper A (piezas que se mueven con "Apertura", de
  gripper_A_moviles.json) hijas del gripper A: claves sólo cuando cambia la garra;
- mesas giratorias, pallets de las pilas del robot aéreo (fijos que se ocultan) y cámara (ojo a 1,1032·ancho, como
  Inventor), cortes de cámara sin interpolar y obturador del desenfoque de movimiento según la velocidad del tramo.
Uso: blender -b L3N_SIM5.blend -P bl_animar.py -- <plan.json> <plan_meta.json> <escena.json de Inventor>
     <gripper_A_moviles.json> <salida_anim.blend> [--hasta N]
"""
import json
import math
import os
import sys
import time

import bpy
from mathutils import Matrix, Quaternion, Vector

T0 = time.time()
argv = sys.argv[sys.argv.index("--") + 1:]
PLANJ, METAJ, ESCI, GAJ, SALIDA = argv[:5]
HASTA = int(argv[argv.index("--hasta") + 1]) if "--hasta" in argv else None
plan = json.load(open(PLANJ, encoding="utf-8"))
meta = json.load(open(METAJ, encoding="utf-8"))
escI = json.load(open(ESCI, encoding="utf-8"))
GA_MOV = json.load(open(GAJ, encoding="utf-8")) if os.path.exists(GAJ) else {"moviles": {}}
sc = bpy.context.scene
C = Matrix(((1, 0, 0, 0), (0, 0, -1, 0), (0, 1, 0, 0), (0, 0, 0, 1)))
K_DIST = 1.1032
log = {"avisos": []}
bpy.context.preferences.edit.keyframe_new_interpolation_type = "LINEAR"


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
for o in OBJ.values():
    o.rotation_mode = "QUATERNION"
    o.hide_render = False                     # la visibilidad pasa a la escala del Empty (0 = oculto)
    for h in o.children_recursive:
        h.hide_render = False
FIJOS = [o for o in bpy.data.objects if "ruta" in o.keys()]
DIN = {"@" + r: [o for o in FIJOS if o["ruta"] == r or o["ruta"].startswith(r + "/")] for r in plan["proxy_dinamicos"]}
GB = plan["grippers"]["SIM_B_Gripper"]
GA = plan["grippers"]["SIM_A_Gripper"]
# palas B: hijas del gripper B (matriz local = traslado de cierre · M_rel)
gB = OBJ.get("SIM_B_Gripper")
PARTES_B = []
for p in escI.get("gripper_B_partes", []):
    o = OBJ.get(p["nombre"])
    if o is None or gB is None:
        continue
    o.parent = gB
    o.matrix_parent_inverse = Matrix.Identity(4)
    PARTES_B.append((o, p["garra"], p["M_rel"]))
# palas A: hijas ya del gripper A; se mueven sobre el eje medido (mm por cm de "Apertura")
gA = OBJ.get("SIM_A_Gripper")
V_A = {n: v for n, v in GA_MOV.get("moviles", {}).items()}
SIGNO = escI.get("signo_abre", -1)
PARTES_A = []
if gA is not None:
    for o in gA.children:
        seg = str(o.get("p", "")).split("/")
        if len(seg) >= 3 and seg[1].startswith("Modulo pala movil:") and seg[2] in V_A:
            k = int(seg[1].split(":")[-1]) - 1
            u = V_A[seg[2]]
            o.rotation_mode = "QUATERNION"
            PARTES_A.append((o, k, o.matrix_basis.copy(), u))
log["palas"] = {"A": len(PARTES_A), "B": len(PARTES_B)}
GIRS = {dk: {"M0": plan["objetos"][dk]["M"], "eje": gi["eje"], "th": gi.get("th", [0.0, 90.0])}
        for dk, gi in plan["giratorias"].items()}
cam = sc.camera
cam.rotation_mode = "QUATERNION"

# ------------------------------------------------------------------ claves
ULT = {}        # objeto -> (último cuadro con clave, matriz local/mundo usada)
QPREV = {}
N_CLAVES = [0]


def clave_matriz(o, M_b, f, mundo=True):
    """Clave de posición y giro en el cuadro f (con clave de espera en f-1 si el objeto estaba quieto)."""
    ult = ULT.get(o.name)
    if ult is not None and ult[0] < f - 1:
        o.keyframe_insert("location", frame=f - 1)
        o.keyframe_insert("rotation_quaternion", frame=f - 1)
    if mundo:
        o.matrix_world = M_b
    else:
        o.matrix_basis = M_b
    q = o.rotation_quaternion.copy()
    qp = QPREV.get(o.name)
    if qp is not None and q.dot(qp) < 0:
        q.negate()
        o.rotation_quaternion = q
    QPREV[o.name] = q
    o.keyframe_insert("location", frame=f)
    o.keyframe_insert("rotation_quaternion", frame=f)
    ULT[o.name] = (f, None)
    N_CLAVES[0] += 1


def clave_visible(o, v, f):
    o.scale = (1.0, 1.0, 1.0) if v else (0.0, 0.0, 0.0)
    o.keyframe_insert("scale", frame=f)


estado_M = {n: o["M"] for n, o in plan["objetos"].items()}
estado_V = {n: o["vis"] for n, o in plan["objetos"].items()}
estado_G = {"SIM_A_Gripper": [0.0] * GA["n"], "SIM_B_Gripper": [0.0] * GB["n"]}
estado_gir = {dk: None for dk in GIRS}
aplic_V, aplic_gir, aplic_G = {}, {}, {}
FR = plan["cuadros"]
N = len(FR) if HASTA is None else min(len(FR), HASTA + 1)
LEY = {r[0]: r for r in meta["leyendas"]}
seg_prev = None
cam_cortes = []
for i in range(N):
    f = FR[i]
    cambiados = set()
    for nm, M in f["M"].items():
        estado_M[nm] = M
        cambiados.add(nm)
    for nm, v in f["V"].items():
        estado_V[nm] = v
    for gk, gv in f.get("G", {}).items():
        estado_G[gk] = gv
    for dk, gv in f.get("gir", {}).items():
        estado_gir[dk] = gv
    # visibilidad
    for nm, v in estado_V.items():
        if aplic_V.get(nm) == v:
            continue
        if nm.startswith("@"):
            for o in DIN.get(nm, []):
                o.hide_render = not v
                o.keyframe_insert("hide_render", frame=i)
        elif nm in OBJ:
            clave_visible(OBJ[nm], v, i)
        aplic_V[nm] = v
    # matrices
    for nm in (cambiados if i else set(estado_M)):
        if nm in GIRS or nm not in OBJ or nm.startswith("SIM_B_PM_"):
            continue
        clave_matriz(OBJ[nm], C @ Mm(estado_M[nm]), i)
    for dk, gi in GIRS.items():
        fr_ = estado_gir[dk]
        if fr_ is not None and aplic_gir.get(dk) != fr_ and dk in OBJ:
            th = gi["th"][0] + (gi["th"][1] - gi["th"][0]) * fr_
            clave_matriz(OBJ[dk], C @ Mm(mm(roty(th, *gi["eje"]), gi["M0"])), i)
            aplic_gir[dk] = fr_
    # garras
    Gb = estado_G["SIM_B_Gripper"]
    if aplic_G.get("B") != Gb:
        e = GB["eje_local"]
        for o, g, Mrel in PARTES_B:
            if aplic_G.get("B") is None or aplic_G["B"][g] != Gb[g]:
                d = GB["cierre_mm"] * Gb[g]
                clave_matriz(o, Mm(mm([1, 0, 0, e[0] * d, 0, 1, 0, e[1] * d, 0, 0, 1, e[2] * d], Mrel)), i, mundo=False)
        aplic_G["B"] = list(Gb)
    Ga = estado_G["SIM_A_Gripper"]
    if aplic_G.get("A") != Ga:
        for o, k, M0b, u in PARTES_A:
            if aplic_G.get("A") is None or aplic_G["A"][k] != Ga[k]:
                cm = -SIGNO * (GA["cierre_mm"] / 10.0) * Ga[k]            # cm de offset de "Apertura"
                T = Matrix.Translation(Vector((u[0] * cm / 1000.0, u[1] * cm / 1000.0, u[2] * cm / 1000.0)))
                clave_matriz(o, T @ M0b, i, mundo=False)
        aplic_G["A"] = list(Ga)
    # cámara
    ex, ey, ez, tx, ty, tz, w = f["cam"]
    ojo = (C @ Vector((ex / 1000.0, ey / 1000.0, ez / 1000.0, 1.0))).to_3d()
    obj = (C @ Vector((tx / 1000.0, ty / 1000.0, tz / 1000.0, 1.0))).to_3d()
    d = obj - ojo
    D = K_DIST * w / 1000.0
    cam.location = obj - d.normalized() * D
    q = d.to_track_quat("-Z", "Y")
    if "cam" in QPREV and q.dot(QPREV["cam"]) < 0:
        q.negate()
    QPREV["cam"] = q
    cam.rotation_quaternion = q
    cam.data.sensor_fit = "HORIZONTAL"
    cam.data.angle = 2.0 * math.atan((w / 1000.0) / 2.0 / D)
    cam.keyframe_insert("location", frame=i)
    cam.keyframe_insert("rotation_quaternion", frame=i)
    cam.data.keyframe_insert("lens", frame=i)
    seg = LEY.get(i, [i, None, 1.0])[1]
    vel = LEY.get(i, [i, None, 1.0])[2]
    if seg != seg_prev:
        if seg_prev is not None:
            cam_cortes.append(i - 1)
        try:
            sc.render.motion_blur_shutter = min(0.5, 0.5 / max(1.0, vel))
            sc.render.keyframe_insert("motion_blur_shutter", frame=i)
        except Exception as e_:  # noqa: BLE001
            if "obturador" not in log:
                log["obturador"] = repr(e_)[:200]
        seg_prev = seg
    if i % 500 == 0:
        print(f"[{time.time() - T0:6.1f} s] cuadro {i}/{N} claves {N_CLAVES[0]}", flush=True)


def poner_constante(idb, rutas, cuadros=None):
    ad = getattr(idb, "animation_data", None)
    if ad is None or ad.action is None:
        return
    fcs = getattr(ad.action, "fcurves", None)
    if fcs is None:                       # acciones por capas (Blender 4.4+): canales en layers/strips/channelbags
        fcs = []
        for ly in getattr(ad.action, "layers", []):
            for st in ly.strips:
                for cb in getattr(st, "channelbags", []):
                    fcs += list(cb.fcurves)
    for fc in fcs:
        if fc.data_path in rutas:
            for kp in fc.keyframe_points:
                if cuadros is None or int(round(kp.co[0])) in cuadros:
                    kp.interpolation = "CONSTANT"


for o in OBJ.values():
    poner_constante(o, ("scale",))
for lst in DIN.values():
    for o in lst:
        poner_constante(o, ("hide_render",))
cortes = set(cam_cortes)
poner_constante(cam, ("location", "rotation_quaternion"), cortes)
poner_constante(cam.data, ("lens",), cortes)
poner_constante(sc, ("render.motion_blur_shutter",))
sc.frame_start, sc.frame_end = 0, N - 1
sc.render.fps = plan.get("fps", 30)
try:
    sc.render.use_motion_blur = True
    sc.render.motion_blur_position = "START"
except Exception as e_:  # noqa: BLE001
    log["avisos"].append(f"motion blur: {e_!r}"[:200])
sc.render.use_overwrite = False
sc.render.use_placeholder = True
sc.frame_set(0)
bpy.ops.wm.save_as_mainfile(filepath=SALIDA, compress=False)
log["cuadros"] = N
log["claves_matriz"] = N_CLAVES[0]
log["cortes_camara"] = len(cam_cortes)
log["tiempo_s"] = round(time.time() - T0, 1)
print("RESULTADO " + json.dumps(log, ensure_ascii=False), flush=True)
