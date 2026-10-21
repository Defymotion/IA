"""Simulación NewPack2 sobre la escena COPIA (Generados\\NEWPACK2_SIM\\NewPack2_simulacion.iam; ver armar_newpack.py).

Fase "palet": el KUKA toma el pallet de arriba del almacén (garras abiertas -> cerradas), lo levanta por encima de los
topes y lo deja en el centrador contra el tope del fondo. (Fase "paquetes": se agrega después.)
Robot: misma cinemática que ADECO (celda_kin). Gripper: Y_g hacia arriba, brida (oculta) en la brida del robot.
Nada se guarda: al final todo vuelve a su lugar.
Uso: python simular_newpack.py [--fases palet] [--sin-animar] [--max-cuadros 1] [--ancho 1920 --alto 1080]
Salida: Generados\\NEWPACK2_SIM\\Animacion\\cuadros.zip + resultado.json
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
sys.path.insert(0, str(Path(__file__).resolve().parent))
import inventor_mcp as inv  # noqa: E402
import celda_kin as K  # noqa: E402

a = argparse.ArgumentParser()
a.add_argument("--fases", default="palet,paquetes")
a.add_argument("--pisos", type=int, default=2)
a.add_argument("--paquete", default="Cartom 43x55 - copia", help="pieza del paquete (Simulacion NewPack2\\Layout)")
a.add_argument("--sin-animar", action="store_true")
a.add_argument("--ancho", type=int, default=1920)
a.add_argument("--alto", type=int, default=1080)
a.add_argument("--max-cuadros", type=int, default=0)
a.add_argument("--vista", default="0.35,-1,0.75", help="dirección desde la que se mira (x,y,z)")
a.add_argument("--alto-vista", type=float, default=330.0, help="alto visible en cm")
a.add_argument("--centro-vista", default="-1150,-700,900", help="punto al que mira la cámara (mm)")
a.add_argument("--luz", default="Luz suave")
a.add_argument("--sin-sombras", action="store_true")
a.add_argument("--garra-abierta", type=float, default=-28.0)
a.add_argument("--garra-plegada", type=float, default=90.0, help="garras recogidas hacia adentro (paletizado)")
a.add_argument("--garra-cerrada", type=float, default=-7.0, help="garras apretando los extremos del pallet")
a.add_argument("--luz-palas-pallet", type=float, default=51.0, help="palas sobre la tabla del pallet al engancharlo (mm)")
a.add_argument("--test-agarre", action="store_true", help="sólo imágenes del enganche del pallet")
a.add_argument("--sin-centrador", action="store_true")
a.add_argument("--solo-centrador", action="store_true",
               help="sólo graba el tramo del centrador (mismos números de cuadro) para reemplazarlo en el video")
a.add_argument("--diag", action="store_true", help="sin grabar: mide pallet/chapa/vástagos e interferencias en el centrador")
a.add_argument("--zoom-escala", type=float, default=1.0, help="multiplica el alto visible de los zooms (vertical: ~1.7)")
a.add_argument("--prueba-vistas", default="", help="'cx,cy,cz,alto,dx,dy,dz;...' sólo fotos fijas de encuadre")
a.add_argument("--montaje", action="store_true", help="video 'editado': cortes y cambios de cámara entre planos")
a.add_argument("--dron", action="store_true", help="como --montaje pero SIN cortes: la cámara viaja suave entre planos")
a.add_argument("--prueba-calidad", action="store_true", help="un cuadro con distintas opciones de calidad y sale")
a.add_argument("--supermuestreo", type=float, default=1.0, help="renderiza a N veces la resolución y achica (Pillow)")
a.add_argument("--modo", type=int, default=0, help="View.DisplayMode (0 = no tocar)")
a.add_argument("--calidad-pantalla", type=int, default=0, help="DisplayOptions.DisplayQuality (0 = no tocar)")
a.add_argument("--reflejos", action="store_true", help="reflejos en el piso")
a.add_argument("--prueba-planos", action="store_true", help="fotos fijas de cada plano del montaje y sale")
a.add_argument("--velocidad", type=float, default=1.0, help="multiplica la cantidad de cuadros de cada movimiento")
x = a.parse_args()
if x.dron:
    x.montaje = True

S = inv._safe
T0 = time.time()
OUT = Path.home() / "Documents" / "InventorIA" / "Generados" / "NEWPACK2_SIM"
ESC = OUT / "NewPack2_simulacion.iam"
AN = OUT / "Animacion"
AN.mkdir(exist_ok=True)
esc = json.loads((OUT / "escena.json").read_text(encoding="utf-8"))
app = inv._inventor(start_if_needed=False)
tg = app.TransientGeometry
app.SilentOperation = True
log = {"avisos": []}


def etapa(t):
    print(f"[{time.time() - T0:6.1f} s] {t}", flush=True)


def mmake(M):
    m = tg.CreateMatrix()
    m.SetCoordinateSystem(tg.CreatePoint(M[0][3] / 10, M[1][3] / 10, M[2][3] / 10),
                          tg.CreateVector(M[0][0], M[1][0], M[2][0]), tg.CreateVector(M[0][1], M[1][1], M[2][1]),
                          tg.CreateVector(M[0][2], M[1][2], M[2][2]))
    return m


def mread(m):
    return [[m.Cell(r, c) * (10 if (c == 4 and r < 4) else 1) for c in range(1, 5)] for r in range(1, 5)]


def apply(M, p):
    return [sum(M[i][k] * (list(p) + [1])[k] for k in range(4)) for i in range(3)]


def rotv(M, v):
    return [sum(M[i][k] * v[k] for k in range(3)) for i in range(3)]


def abrir(p, visible=False):
    for d in inv._items(app.Documents):
        if S(lambda: Path(d.FullFileName).resolve() == Path(p).resolve(), False):
            return d
    return app.Documents.Open(str(p), visible)


doc = abrir(ESC, True)
doc.Activate()
acd = doc.ComponentDefinition
by = {o.Name: o for o in inv._items(acd.Occurrences)}
links = {k: by[n] for k, n in esc["links"].items()}
for o in by.values():                                   # el robot armado del layout no se muestra (van los eslabones)
    if Path(S(lambda: o.Definition.Document.FullFileName, "") or "").stem.startswith("KUKA"):
        S(lambda: setattr(o, "Visible", False))
grip = by[esc["gripper_occ"]]
gdoc = grip.Definition.Document
gby = {o.Name: o for o in inv._items(gdoc.ComponentDefinition.Occurrences)}
cj = esc["gripper_cajas"]

# ============================================================================ cinemática (como ADECO)
T = esc["T_robot"]
Tinv = K.inv_rt(T)
F_orig = (1655.59, 1199.18, 4.5)
phi0 = -90.0 - math.degrees(math.atan2(-0.6889, 0.7249))
F0 = apply(K.rot_z(phi0, K.W), F_orig)
BRIDA_G = (7.8, 128.5, 0.0)                         # centro de la cara superior de la brida del gripper (oculta)
R_G = [[0, 0, -1], [0, 1, 0], [1, 0, 0]]            # q=0: X_g -> Z_r, Y_g -> Y_r (arriba), Z_g -> -X_r
t_g = [F0[i] - sum(R_G[i][k] * BRIDA_G[k] for k in range(3)) for i in range(3)]
cfg = {"T_robot": T, "phi0": phi0, "M": {k: esc["M_links"][k] for k in ("V02", "V03", "V04", "V05")},
       "brida_robot_q0": F0, "M_gripper_q0": [R_G[0] + [t_g[0]], R_G[1] + [t_g[1]], R_G[2] + [t_g[2]], [0, 0, 0, 1]]}
a_vec = (K.A3[0] - K.A2[0], K.A3[1] - K.A2[1])
b_vec = (K.W[0] - K.A3[0], K.W[1] - K.A3[1])
L2, L3 = math.hypot(*a_vec), math.hypot(*b_vec)
FW = (F0[0] - K.W[0], F0[1] - K.W[1])


def ik(G):
    F = apply(Tinv, apply(G, BRIDA_G))
    q1 = math.degrees(math.atan2(-F[2], F[0]))
    r = math.hypot(F[0], F[2])
    Wr, Wy = r - FW[0], F[1] - FW[1]
    d = (Wr - K.A2[0], Wy - K.A2[1])
    D = math.hypot(*d)
    cg = (D * D - L2 * L2 - L3 * L3) / (2 * L2 * L3)
    if abs(cg) > 1:
        raise ValueError(f"Fuera de alcance (r={r:.0f}, y={F[1]:.0f})")
    g = -math.acos(cg)
    aa, ab = math.atan2(a_vec[1], a_vec[0]), math.atan2(b_vec[1], b_vec[0])
    q3 = math.degrees(aa + g - ab)
    v = (a_vec[0] + L3 * math.cos(aa + g), a_vec[1] + L3 * math.sin(aa + g))
    q2 = math.degrees(math.atan2(d[1], d[0]) - math.atan2(v[1], v[0]))
    xg = rotv(Tinv, rotv(G, (1, 0, 0)))
    q6 = math.degrees(math.atan2(xg[0], xg[2])) - q1
    norm = lambda t: (t + 180) % 360 - 180  # noqa: E731
    return {"q1": norm(q1), "q2": norm(q2), "q3": norm(q3), "q6": norm(q6)}


def pose(q):
    return K.poses(cfg, q["q1"], q["q2"], q["q3"], q["q6"])


def G_en(p_local, p_mundo, yaw_deg):
    """Pose del gripper (Y_g vertical) con el punto local p_local en p_mundo; yaw: ángulo de Z_g en planta."""
    c, s = math.cos(math.radians(yaw_deg)), math.sin(math.radians(yaw_deg))
    zg, yg = (c, s, 0.0), (0.0, 0.0, 1.0)
    xg = (yg[1] * zg[2] - yg[2] * zg[1], yg[2] * zg[0] - yg[0] * zg[2], yg[0] * zg[1] - yg[1] * zg[0])
    R = [[xg[i], yg[i], zg[i]] for i in range(3)]
    t = [p_mundo[i] - sum(R[i][k] * p_local[k] for k in range(3)) for i in range(3)]
    return [R[0] + [t[0]], R[1] + [t[1]], R[2] + [t[2]], [0, 0, 0, 1]]


def subir(G, dz):
    return K.mmul(K.tr(0, 0, dz), G)


# ============================================================================ geometría de la tarea
PAL_MIN_LY = min(v[0][1] for k, v in cj.items() if k.startswith("Pala"))          # fondo de las palas (local)
XC = sum(cj["Chapa principal:1"][i][0] for i in (0, 1)) / 2
TCP_PAL = (XC, PAL_MIN_LY - x.luz_palas_pallet, 0.0)   # tabla superior del pallet (como en el modelo: 51 mm)
pallets = esc["pallets"]
top_name = max(pallets, key=lambda n: pallets[n][2][3])
P0 = pallets[top_name]
H_PAL = 152.0
pal_c = [P0[0][3], P0[1][3], P0[2][3]]           # centro inferior del pallet (origen de la pieza)
cen = esc["cajas"]["Ensamble centrador:1"]
# centrador: cadenas (z = 360) y tope del fondo en x = -566.4 (ver relevamiento); pallet 1000 en X, 1200 en Y
Z_CEN = 360.0 + 2.0
X_TOPE = -566.4
Y_CEN = (-2321.2 + -1121.2) / 2
dest_c = [X_TOPE - 500.0, Y_CEN, Z_CEN]              # pallet centrado (contra el tope del fondo y el lateral)
DX_CEN, DY_CEN = (0.0, 0.0) if x.sin_centrador else (-250.0, -40.0)   # el robot lo deja corrido; el centrador lo acomoda
drop_c = [dest_c[0] + DX_CEN, dest_c[1] + DY_CEN, dest_c[2]]
Z_SEG = 1504.8 + 120.0                           # el pallet pasa 120 mm por encima de los topes del almacén
log["pallet"] = {"toma": top_name, "centro_toma": pal_c, "centro_destino": dest_c}


def G_palet(c, yaw):
    """Gripper apoyado (palas 5 mm arriba) sobre un pallet cuyo centro inferior es c."""
    return G_en(TCP_PAL, (c[0], c[1], c[2] + H_PAL), yaw)


def elegir_yaw(c):
    best = None
    for yaw in (0.0, 180.0):
        try:
            q = ik(G_palet(c, yaw))
            if best is None or abs(q["q6"]) < abs(best[1]["q6"]):
                best = (yaw, q)
        except ValueError:
            pass
    if best is None:
        raise ValueError(f"Pallet fuera de alcance en {c}")
    return best[0]


yaw_t, yaw_d = elegir_yaw(pal_c), elegir_yaw(drop_c)
G_toma = G_palet(pal_c, yaw_t)
G_deja = G_palet(drop_c, yaw_d)
alto_lev = Z_SEG - pal_c[2]
q_toma, q_deja = ik(G_toma), ik(G_deja)
q_toma_up, q_deja_up = ik(subir(G_toma, alto_lev)), ik(subir(G_deja, Z_SEG - drop_c[2]))
q_toma_ap = ik(subir(G_toma, 250))
q_deja_sal = ik(subir(G_deja, 300))
for k_, G_ in (("toma", G_toma), ("deja", G_deja)):
    q_ = ik(G_)
    log[f"ik_error_{k_}_mm"] = round(math.dist(apply(pose(q_)["gripper"], TCP_PAL), apply(G_, TCP_PAL)), 2)
# ---------------------------------------------------------------- paquetes (fase 2)
PKG_FILE = Path.home() / "Documents" / "InventorIA" / "Simulacion NewPack2" / "Layout" / f"{x.paquete}.ipt"
paq_occ = [o for o in inv._items(acd.Occurrences) if Path(S(lambda: o.Definition.Document.FullFileName, "")).stem
           == x.paquete]
N_PAQ = 4 * x.pisos + 1
if "paquetes" in x.fases and len(paq_occ) < N_PAQ:
    for _ in range(N_PAQ - len(paq_occ)):
        o = acd.Occurrences.Add(str(PKG_FILE), mmake(K.tr(0, 0, 0)))
        paq_occ.append(o)
    doc.Save()                                   # la escena es nuestra copia
for nm in esc.get("paquetes", []):              # los paquetes de 600x720 del modelo no se usan
    if nm in by:
        S(lambda: setattr(by[nm], "Visible", False))
pk_box = None
if paq_occ:
    b = paq_occ[0].Definition.Document.ComponentDefinition.RangeBox
    pk_box = [[b.MinPoint.X * 10, b.MinPoint.Y * 10, b.MinPoint.Z * 10], [b.MaxPoint.X * 10, b.MaxPoint.Y * 10,
                                                                           b.MaxPoint.Z * 10]]
dims = [pk_box[1][i] - pk_box[0][i] for i in range(3)] if pk_box else [430, 165, 550]
log["paquete_dims_local"] = [round(v, 1) for v in dims]
# marco canónico del paquete: origen en el centro de la base, X_p = lado de 430, Y_p arriba, Z_p = lado de 550
i430 = min((0, 2), key=lambda i: abs(dims[i] - 430))
i550 = 2 if i430 == 0 else 0
iup = 1


def canon_paq():
    """Matriz pieza -> marco canónico (en coordenadas de la pieza)."""
    c = [(pk_box[0][i] + pk_box[1][i]) / 2 for i in range(3)]
    c[iup] = pk_box[0][iup]
    ex, ey = [0, 0, 0], [0, 0, 0]
    ex[i430], ey[iup] = 1, 1
    ez = [ex[1] * ey[2] - ex[2] * ey[1], ex[2] * ey[0] - ex[0] * ey[2], ex[0] * ey[1] - ex[1] * ey[0]]
    return [[ex[0], ey[0], ez[0], c[0]], [ex[1], ey[1], ez[1], c[1]], [ex[2], ey[2], ez[2], c[2]], [0, 0, 0, 1]]


C_PAQ = canon_paq() if pk_box else K.tr(0, 0, 0)
C_PAQ_INV = K.inv_rt(C_PAQ)


def M_pieza(C):
    """Del marco canónico en el mundo a la matriz de la pieza."""
    return K.mmul(C, C_PAQ_INV)


def marco(cx, cy, z, ang_deg):
    """Marco canónico con X_p girado ang en planta (0: X_p = +X del mundo)."""
    c, s_ = math.cos(math.radians(ang_deg)), math.sin(math.radians(ang_deg))
    # X_p = (c, s, 0); Y_p = (0, 0, 1); Z_p = X_p x Y_p
    return [[c, 0, s_, cx], [s_, 0, -c, cy], [0, 1, 0, z], [0, 0, 0, 1]]


# toma: en la cinta de entrada, donde está el paquete del modelo (centro de su base), lado de 430 a lo largo de X
pc = esc["paquete_caja"]
TOMA_PAQ = marco((pc[0][0] + pc[1][0]) / 2, (pc[0][1] + pc[1][1]) / 2, pc[0][2], 0.0)
for o in paq_occ:                                     # ocultos y sobre la cinta (no debajo del piso: sombras)
    S(lambda: setattr(o, "Visible", False))
    S(lambda: setattr(o, "Transformation", mmake(M_pieza(TOMA_PAQ))))
LLEGADA = 1400.0                                  # recorrido visible sobre la cinta (hacia +Y)
# paquete dentro del gripper: 430 entre palas (Z_g), base a la altura del fondo de las palas
Z_FIJA = max(v[1][2] for k, v in cj.items() if k.startswith("Pala fija"))         # cara interior de la pala fija
LZ_PAQ = Z_FIJA + 430.0 / 2 + 1.0
M_REL_PAQ = [[0, 0, -1, XC], [0, 1, 0, PAL_MIN_LY + 2.0], [1, 0, 0, LZ_PAQ], [0, 0, 0, 1]]   # canónico en gripper
PALA_MOV0 = min(v[0][2] for k, v in cj.items() if k.startswith("Pala movil"))     # cara interior abierta
CIERRE_PALA = PALA_MOV0 - (Z_FIJA + 430.0 + 2.0)
log["pala_movil_cierre_mm"] = round(CIERRE_PALA, 1)
# patrón (imagen del usuario, pallet 1000 en X x 1200 en Y; medidas desde la esquina -X,+Y)
PAT = [(221, 311, 0), (722, 250, 90), (282, 948, 90), (782, 877, 0)]   # 0: 430 a lo largo de X   # (x, y desde arriba, giro de X_p)
x0p, y0p = dest_c[0] - 500.0, dest_c[1] + 600.0
z_pal_top = dest_c[2] + H_PAL
destinos = []
for piso in range(x.pisos):
    for (px, py, ang) in PAT:
        if piso % 2:                              # pisos pares: patrón espejado (trabado)
            px = 1000.0 - px
        destinos.append({"piso": piso + 1, "C": marco(x0p + px, y0p - py, z_pal_top + piso * 165.0 + 1.0, ang)})
P_CEN = [dest_c[0], dest_c[1]]


def opcion_dejar(C, rot):
    Cr = K.mmul(C, [[math.cos(math.radians(rot)), 0, math.sin(math.radians(rot)), 0], [0, 1, 0, 0],
                    [-math.sin(math.radians(rot)), 0, math.cos(math.radians(rot)), 0], [0, 0, 0, 1]])
    G = K.mmul(Cr, K.inv_rt(M_REL_PAQ))
    q = ik(G)
    return G, q, Cr


def rect_paq(C):
    """Rectángulo en planta (xmin, ymin, xmax, ymax) del paquete con marco C (X_p = 430, Z_p = 550)."""
    ex, ez = rotv(C, (1, 0, 0)), rotv(C, (0, 0, 1))
    hx = abs(ex[0]) * 215 + abs(ez[0]) * 275
    hy = abs(ex[1]) * 215 + abs(ez[1]) * 275
    return (C[0][3] - hx, C[1][3] - hy, C[0][3] + hx, C[1][3] + hy)


def franja(C, signo, largo):
    """Zona en planta que ocupa una pala del lado signo*X_p del paquete (X_p = dirección de apriete = Z_g)."""
    ex, ez = rotv(C, (1, 0, 0)), rotv(C, (0, 0, 1))
    cx, cy = C[0][3] + signo * ex[0] * (215 + largo / 2), C[1][3] + signo * ex[1] * (215 + largo / 2)
    hx = abs(ex[0]) * largo / 2 + abs(ez[0]) * 270
    hy = abs(ex[1]) * largo / 2 + abs(ez[1]) * 270
    return (cx - hx, cy - hy, cx + hx, cy + hy)


def solapa(r1, r2, tol=5.0):
    return r1[0] < r2[2] - tol and r2[0] < r1[2] - tol and r1[1] < r2[3] - tol and r2[1] < r1[3] - tol


def plan_piso(lista):
    """Orden y giro de cada paquete del piso para que la pala MÓVIL (lado +Z_g) abra hacia donde no hay cajas.
    Costo: pala móvil contra caja = 10, pala fija contra caja = 1; desempate: menor giro de A6."""
    import itertools
    ops = []
    for d_ in lista:
        o = {}
        for rot in (0.0, 180.0):
            try:
                G, q, Cr = opcion_dejar(d_["C"], rot)
            except ValueError:
                continue
            zg = rotv(G, (0, 0, 1))
            ex = rotv(Cr, (1, 0, 0))
            s_mov = 1 if (zg[0] * ex[0] + zg[1] * ex[1]) > 0 else -1      # lado de la pala móvil respecto de X_p
            o[rot] = {"G": G, "q": q, "Cr": Cr, "mov": franja(Cr, s_mov, 160.0), "fija": franja(Cr, -s_mov, 60.0)}
        ops.append(o)
    mejor = None
    for orden in itertools.permutations(range(len(lista))):
        for rots in itertools.product((0.0, 180.0), repeat=len(lista)):
            if any(r not in ops[i] for i, r in zip(orden, rots)):
                continue
            puestos, costo, a6 = [], 0, 0.0
            for i, r in zip(orden, rots):
                op = ops[i][r]
                costo += 10 * sum(solapa(op["mov"], p) for p in puestos) + sum(solapa(op["fija"], p) for p in puestos)
                a6 += abs(op["q"]["q6"])
                puestos.append(rect_paq(op["Cr"]))
            if mejor is None or (costo, a6) < mejor[0]:
                mejor = ((costo, a6), orden, rots)
    (costo, _), orden, rots = mejor
    out = []
    for i, r in zip(orden, rots):
        d_ = dict(lista[i])
        d_.update(ops[i][r])
        d_["costo_piso"] = costo
        out.append(d_)
    return out


G_toma_paq = K.mmul(TOMA_PAQ, K.inv_rt(M_REL_PAQ))
plan_paq = []
Z_SEG_P0 = TOMA_PAQ[2][3] + 165.0 + 250.0
q_tp_up_g = ik(subir(G_toma_paq, Z_SEG_P0 - TOMA_PAQ[2][3]))
if "paquetes" in x.fases:
    q_tp = ik(G_toma_paq)
    for piso in range(1, x.pisos + 1):
        plan_paq += plan_piso([d_ for d_ in destinos if d_["piso"] == piso])
    log["paquetes_plan"] = [{"piso": d_["piso"], "centro": [round(d_["C"][0][3]), round(d_["C"][1][3])],
                             "q": {k: round(v, 1) for k, v in d_["q"].items()}, "costo_piso": d_["costo_piso"]}
                            for d_ in plan_paq]
    log["q_toma_paquete"] = {k: round(v, 1) for k, v in q_tp.items()}
log["q"] = {"toma": q_toma, "toma_arriba": q_toma_up, "deja": q_deja, "deja_arriba": q_deja_up}
log["yaw"] = {"toma": yaw_t, "deja": yaw_d}
if x.sin_animar:
    (AN / "resultado.json").write_text(json.dumps(log, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print(json.dumps(log, ensure_ascii=False, indent=1, default=str))
    sys.exit(0)

# ============================================================================ animación
FR = AN / "cuadros"
FR.mkdir(exist_ok=True)
for f in FR.glob("*.png"):
    f.unlink()
n = 0
estado = {"q": None, "garra": 0.0}
llevando = []                   # [(occ, M_rel)]
EJES = {}
for nm in [k for k in esc["gripper_libres"] if k.startswith("Ensamble eje")]:
    cz = sum(cj[nm][i][2] for i in (0, 1)) / 2
    uc = [[sum(v[i][j] for i in (0, 1)) / 2 for j in range(3)] for k, v in cj.items() if k.startswith("ucfl")]
    piv = [p for p in uc if (p[2] > 0) == (cz > 0)]
    EJES[nm] = (sum(p[1] for p in piv) / len(piv), sum(p[2] for p in piv) / len(piv), esc["gripper_libres"][nm])


# garras simétricas: la del lado +Z_g es la del lado -Z_g girada 180° alrededor del eje vertical del gripper
EJE_REF = next(nm for nm, v in EJES.items() if v[1] < 0)
EJE_ESP = [nm for nm in EJES if nm != EJE_REF]
R180 = [[-1, 0, 0, 2 * XC], [0, 1, 0, 0], [0, 0, -1, 0], [0, 0, 0, 1]]


def set_garras(ang):
    ly, lz, M0 = EJES[EJE_REF]
    c, s = math.cos(math.radians(-ang)), math.sin(math.radians(-ang))
    Rx = K.mmul(K.mmul(K.tr(0, ly, lz), [[1, 0, 0, 0], [0, c, -s, 0], [0, s, c, 0], [0, 0, 0, 1]]), K.tr(0, -ly, -lz))
    M = K.mmul(Rx, M0)
    gby[EJE_REF].Transformation = mmake(M)
    for nm in EJE_ESP:
        gby[nm].Transformation = mmake(K.mmul(R180, M))
    gdoc.Update()
    estado["garra"] = ang


PALA_OCC = [nm for nm in esc["gripper_libres"] if nm.split(":")[0] in ("Pala movil", "Ensamble empuje")]
estado["pala"] = 0.0


def set_pala(f):
    """f = 0 abierta (como en el modelo) ... 1 cerrada sobre el paquete de 430."""
    for nm in PALA_OCC:
        gby[nm].Transformation = mmake(K.mmul(K.tr(0, 0, -CIERRE_PALA * f), esc["gripper_libres"][nm]))
    gdoc.Update()
    estado["pala"] = f


def pala(f, k=4):
    f0 = estado["pala"]
    kk = pasos(k)
    for i in range(1, kk + 1):
        set_pala(f0 + (f - f0) * i / kk)
        cuadro()


cinta = {"occ": None, "t": 1.0}


def cinta_paso(frac):
    if cinta["occ"] is None or cinta["t"] >= 1:
        return
    cinta["t"] = min(1.0, cinta["t"] + frac)
    C = [r[:] for r in TOMA_PAQ]
    C[1][3] -= LLEGADA * (1 - cinta["t"])
    cinta["occ"].Transformation = mmake(M_pieza(C))


def llega(o):
    cinta["occ"], cinta["t"] = o, 0.0
    S(lambda: setattr(o, "Visible", True))
    cinta_paso(0.0)


def aplicar(q):
    P = pose(q)
    for k in ("V02", "V03", "V04", "V05"):
        links[k].Transformation = mmake(P[k])
    grip.Transformation = mmake(P["gripper"])
    for o, Mr in llevando:
        o.Transformation = mmake(K.mmul(P["gripper"], Mr))
    estado["q"] = q
    estado["G"] = P["gripper"]


class Fin(Exception):
    pass


TWEENS = []                 # [inicio, cantidad, f(t)] animaciones que corren en paralelo a los movimientos
GRABAR = {"on": not (x.solo_centrador or x.diag)}
MARCAS = {}


def cuadro():
    global n
    if x.max_cuadros and n >= x.max_cuadros:
        raise Fin()
    for tw in TWEENS:
        if tw[0] <= n < tw[0] + tw[1]:
            tw[2]((n - tw[0] + 1) / tw[1])
    if not GRABAR["on"]:
        n += 1
        return
    doc.Update()
    if "cam_set" in globals() and cam_estado.get("v"):
        cam_set(cam_estado["v"])                        # la cámara no se puede escapar (Fit automático, clics)
    app.ActiveView.SaveAsBitmap(str(FR / f"c{n:04d}.png"), x.ancho, x.alto)
    n += 1


def pasos(k):
    return max(1, int(round(k * x.velocidad)))


def mover(q_fin, k=10):
    q_ini = estado["q"]
    d6 = (q_fin["q6"] - q_ini["q6"] + 180) % 360 - 180
    kk = pasos(k)
    for i in range(1, kk + 1):
        t = (1 - math.cos(math.pi * i / kk)) / 2
        q = {j: q_ini[j] + (q_fin[j] - q_ini[j]) * t for j in ("q1", "q2", "q3")}
        q["q6"] = q_ini["q6"] + d6 * t
        aplicar(q)
        cinta_paso(estado.get("cinta_frac", 0.0))
        cuadro()


def mover_lineal(G_fin, k=8):
    """Movimiento recto (vertical) del gripper: interpola la pose y resuelve la IK en cada cuadro."""
    G_ini = estado["G"]
    kk = pasos(k)
    for i in range(1, kk + 1):
        t = (1 - math.cos(math.pi * i / kk)) / 2
        G = [row[:] for row in G_fin]
        for r in range(3):
            G[r][3] = G_ini[r][3] + (G_fin[r][3] - G_ini[r][3]) * t
        aplicar(ik(G))
        cinta_paso(estado.get("cinta_frac", 0.0))
        cuadro()


def garras(ang, k=5):
    a0 = estado["garra"]
    kk = pasos(k)
    for i in range(1, kk + 1):
        set_garras(a0 + (ang - a0) * i / kk)
        cuadro()


def esperar(k):
    for _ in range(pasos(k)):
        cinta_paso(estado.get("cinta_frac", 0.0))
        cuadro()


# vista y calidad
for wp in inv._items(acd.WorkPlanes):
    S(lambda: setattr(wp, "Visible", False))
ov = S(lambda: doc.ObjectVisibility)
for prop in ("AllWorkFeatures", "UserWorkPlanes", "OriginWorkPlanes", "Sketches", "Sketches3D"):
    S(lambda: setattr(ov, prop, False))
vw = app.ActiveView
cam = vw.Camera
VISTA_GRAL = ([float(v) for v in x.centro_vista.split(",")], x.alto_vista, [float(v) for v in x.vista.split(",")])
VISTA_CEN = ([dest_c[0] - 150, dest_c[1] - 150, 420.0], 190.0 * x.zoom_escala, [0.55, -1.0, 0.95])
VISTA_TOMA = ([TOMA_PAQ[0][3], TOMA_PAQ[1][3], TOMA_PAQ[2][3] + 330.0], 150.0 * x.zoom_escala, [0.75, -1.0, 0.55])
cam_estado = {"v": VISTA_GRAL}
# planos del montaje (centro mm, alto visible cm, dirección desde donde se mira); pensados para 1080x1920
ZE = x.zoom_escala
PLANOS = {
    "general": VISTA_GRAL,
    "toma_pallet": ([pal_c[0], pal_c[1], pal_c[2] + H_PAL + 150.0], 165.0 * ZE, [0.3, -1.0, 0.35]),
    "traslado": ([(pal_c[0] + dest_c[0]) / 2, (pal_c[1] + dest_c[1]) / 2, 900.0], 420.0 * ZE, [-0.55, -1.0, 0.9]),
    "deja": ([dest_c[0] - 100.0, dest_c[1] - 100.0, 700.0], 250.0 * ZE, [-0.5, -1.0, 0.7]),
    "centrador": VISTA_CEN,
    "cinta": ([TOMA_PAQ[0][3], TOMA_PAQ[1][3], TOMA_PAQ[2][3] + 300.0], 280.0 * ZE, [-0.6, -1.0, 0.75]),
    "toma_paquete": ([TOMA_PAQ[0][3], TOMA_PAQ[1][3], TOMA_PAQ[2][3] + 220.0], 150.0 * ZE, [-0.8, -1.0, 0.6]),
    "palet_a": ([dest_c[0], dest_c[1], z_pal_top + 350.0], 250.0 * ZE, [0.35, -1.0, 1.1]),
    "medio": ([(dest_c[0] + TOMA_PAQ[0][3]) / 2, (dest_c[1] + TOMA_PAQ[1][3]) / 2 - 200.0, 900.0], 420.0 * ZE,
              [0.15, -1.0, 1.15]),
    "palet_b": ([dest_c[0], dest_c[1], z_pal_top + 350.0], 250.0 * ZE, [-0.6, -1.0, 0.9]),
}
log["planos"] = {k: [[round(c) for c in v[0]], round(v[1]), v[2]] for k, v in PLANOS.items()}


def corte(nombre, k=16):
    """Modo montaje: corte seco a otro plano. Modo dron: viaje suave de k cuadros en paralelo al movimiento."""
    if x.dron:
        zoom_paralelo(nombre, k)
    elif x.montaje:
        cam_set(PLANOS[nombre])


def cam_interp(v0, v1, t):
    t = (1 - math.cos(math.pi * t)) / 2
    return ([v0[0][j] + (v1[0][j] - v0[0][j]) * t for j in range(3)], v0[1] + (v1[1] - v0[1]) * t,
            [v0[2][j] + (v1[2][j] - v0[2][j]) * t for j in range(3)])


def zoom_paralelo(nombre, k):
    """Zoom de cámara que corre EN PARALELO con el movimiento siguiente (tween), sólo en modo montaje."""
    if x.montaje:
        v0, v1, kk = cam_estado["v"], PLANOS[nombre], pasos(k)
        TWEENS.append([n, kk, lambda t, v0=v0, v1=v1: cam_set(cam_interp(v0, v1, t))])


def cam_set(v):
    c, alto, dv = v
    nrm = math.sqrt(sum(q * q for q in dv))
    cam.Target = tg.CreatePoint(c[0] / 10, c[1] / 10, c[2] / 10)
    cam.Eye = tg.CreatePoint(c[0] / 10 + dv[0] / nrm * 1000, c[1] / 10 + dv[1] / nrm * 1000, c[2] / 10 + dv[2] / nrm * 1000)
    cam.UpVector = tg.CreateUnitVector(0, 0, 1)
    S(lambda: setattr(cam, "Perspective", False))
    cam.SetExtents(alto * x.ancho / x.alto, alto)
    cam.Apply()
    cam_estado["v"] = v


def cam_mover(v_fin, k=14):
    v0 = cam_estado["v"]
    kk = pasos(k)
    for i in range(1, kk + 1):
        t = (1 - math.cos(math.pi * i / kk)) / 2
        cam_set(([v0[0][j] + (v_fin[0][j] - v0[0][j]) * t for j in range(3)], v0[1] + (v_fin[1] - v0[1]) * t,
                 [v0[2][j] + (v_fin[2][j] - v0[2][j]) * t for j in range(3)]))
        cuadro()
    cam_estado["v"] = v_fin


cam_set(VISTA_GRAL)
if not x.sin_sombras:
    for prop in ("ShowAmbientShadows", "ShowObjectShadows", "ShowGroundShadows"):
        S(lambda: setattr(vw, prop, True))
    S(lambda: setattr(vw, "ShowGroundPlane", False))
if x.luz:
    S(lambda: setattr(doc, "ActiveLightingStyle", doc.LightingStyles.Item(x.luz)))
for _w in range(3):                                   # calentamiento: que las sombras estén desde el primer cuadro
    doc.Update()
    S(lambda: app.ActiveView.SaveAsBitmap(str(AN / "calentamiento.png"), 640, 360))

if x.prueba_calidad:
    import time as _t
    log["prueba_calidad"] = []
    cam_set(PLANOS["toma_pallet"])
    do_ = app.DisplayOptions
    dq0, dm0 = S(lambda: do_.DisplayQuality), S(lambda: vw.DisplayMode)

    def foto(nombre, ss=1.0):
        doc.Update()
        cam_set(PLANOS["toma_pallet"])
        t0 = _t.time()
        pth = AN / f"calidad_{nombre}.png"
        if ss > 1:
            from PIL import Image
            tmp = AN / "_ss.png"
            app.ActiveView.SaveAsBitmap(str(tmp), int(x.ancho * ss), int(x.alto * ss))
            Image.open(tmp).convert("RGB").resize((x.ancho, x.alto), Image.LANCZOS).save(pth)
        else:
            app.ActiveView.SaveAsBitmap(str(pth), x.ancho, x.alto)
        log["prueba_calidad"].append({"nombre": nombre, "s": round(_t.time() - t0, 2),
                                      "modo": S(lambda: vw.DisplayMode), "dq": S(lambda: do_.DisplayQuality)})
    foto("base")
    foto("ss2", 2.0)
    for dq in (58881, 58882, 58883, 58885, 58886):
        if S(lambda: setattr(do_, "DisplayQuality", dq) or True, False):
            foto(f"dq{dq}")
    S(lambda: setattr(do_, "DisplayQuality", dq0))
    for dm in (8711, 8713, 8715, 8716, 8717):
        if S(lambda: setattr(vw, "DisplayMode", dm) or True, False):
            foto(f"modo{dm}")
    S(lambda: setattr(vw, "DisplayMode", dm0))
    S(lambda: setattr(vw, "ShowGroundReflections", True))
    foto("reflejos")
    S(lambda: setattr(vw, "ShowGroundReflections", False))
    print(json.dumps(log["prueba_calidad"], ensure_ascii=False), flush=True)
    # trazado de rayos: calidad borrador, primero con 1 argumento y después con opciones de tamaño
    log["rt"] = []
    for q in (95745, 95746):
        if not S(lambda: setattr(vw, "RayTracingQuality", q) or True, False):
            log["rt"].append({"q": q, "error": "no acepta"})
            continue
        for modo_ in ("1arg", "nvm"):
            pth = AN / f"calidad_rt{q}_{modo_}.png"
            cam_set(PLANOS["toma_pallet"])
            t0 = _t.time()
            try:
                if modo_ == "1arg":
                    vw.SaveAsBitmapWithRayTracing(str(pth))
                else:
                    nv = app.TransientObjects.CreateNameValueMap()
                    nv.Add("Width", x.ancho)
                    nv.Add("Height", x.alto)
                    vw.SaveAsBitmapWithRayTracing(str(pth), nv)
                log["rt"].append({"q": q, "modo": modo_, "s": round(_t.time() - t0, 1)})
            except Exception as exc:  # noqa: BLE001
                log["rt"].append({"q": q, "modo": modo_, "error": repr(exc)[:300]})
            print(json.dumps(log["rt"][-1]), flush=True)
    S(lambda: setattr(vw, "RayTracingQuality", 95748))
    app.SilentOperation = False
    print(json.dumps(log, ensure_ascii=False, indent=1, default=str)[-4000:])
    sys.exit(0)
if x.prueba_planos:
    log["prueba_planos"] = []
    for k_, v_ in PLANOS.items():
        cam_set(v_)
        doc.Update()
        pth = AN / f"plano_{k_}.png"
        app.ActiveView.SaveAsBitmap(str(pth), x.ancho, x.alto)
        log["prueba_planos"].append(pth.name)
    app.SilentOperation = False
    print(json.dumps(log, ensure_ascii=False, indent=1, default=str)[-3000:])
    sys.exit(0)
if x.prueba_vistas:                                   # fotos fijas para elegir el encuadre (no anima nada)
    log["prueba_vistas"] = []
    log["toma_paquete"] = [round(TOMA_PAQ[i][3]) for i in range(3)]
    log["robot_base"] = [round(esc["T_robot"][i][3]) for i in range(3)]
    for k_, txt in enumerate(x.prueba_vistas.split(";")):
        v_ = [float(t) for t in txt.split(",")]
        cam_set((v_[0:3], v_[3], v_[4:7]))
        doc.Update()
        pth = AN / f"prueba_vista_{k_}.png"
        app.ActiveView.SaveAsBitmap(str(pth), x.ancho, x.alto)
        log["prueba_vistas"].append([txt, pth.name])
    app.SilentOperation = False
    print(json.dumps(log, ensure_ascii=False, indent=1, default=str))
    sys.exit(0)

# ---- centrador: chapa de los pistones (dentro de la copia Tope_pistones_sim) y deslizamiento del pallet
CEN = esc.get("centrador")
PIST = {}
if CEN and not x.sin_centrador:
    cen_occ = by[CEN["occ"]]
    tp_c = next(o for o in inv._items(cen_occ.Definition.Occurrences) if o.Name == CEN["pistones_occ"])
    pdoc_c = tp_c.Definition.Document
    pby = {o.Name: o for o in inv._items(pdoc_c.ComponentDefinition.Occurrences)}
    Mw = K.mmul(CEN["M_cen"], CEN["M_pist"])                     # pistones -> mundo
    # Tope_pistones es FLEXIBLE en el centrador: la chapa se mueve por su proxy (coord. del centrador), no en su .iam
    chp = {o.Name: o for o in inv._items(tp_c.SubOccurrences) if o.Name in CEN["chapas"]}
    PIST = {"doc": pdoc_c, "occ": chp, "M0": {nm: mread(o.Transformation) for nm, o in chp.items()},
            "uy": rotv(K.inv_rt(CEN["M_cen"]), (0, 1, 0)), "cdoc": cen_occ.Definition.Document}
    VAS = CEN.get("vastagos")
    if VAS:
        e1 = pby[VAS["ensamblajes"][0]]
        edoc_c = e1.Definition.Document
        adn_o = next(o for o in inv._items(edoc_c.ComponentDefinition.Occurrences) if "ADN" in o.Name)
        adoc_c = adn_o.Definition.Document
        aby = {o.Name: o for o in inv._items(adoc_c.ComponentDefinition.Occurrences)}
        Mw_adn = K.mmul(K.mmul(Mw, VAS["ensamblajes_M"][VAS["ensamblajes"][0]]), VAS["adn_M"])
        PIST["rods"] = {nm: (aby[nm], M0r) for nm, M0r in VAS["rod_M"].items()}
        PIST["uy_rod"] = rotv(K.inv_rt(Mw_adn), (0, 1, 0))
        PIST["docs_rod"] = [adoc_c, edoc_c]
Y_CHAPA = Y_CEN - 600.0                                           # cara de la chapa con los pistones extendidos
CARRERA_PIST = 60.0                                               # retraído = -60 mm en Y
estado["pist"] = 0.0


def set_pist(d):
    """d = desplazamiento de la chapa en +Y del mundo respecto del modelo (0 = apoyada en el pallet centrado)."""
    if not PIST:
        return
    for nm, o in PIST["occ"].items():
        T_ = K.tr(*[PIST["uy"][i] * d for i in range(3)])
        o.Transformation = mmake(K.mmul(T_, PIST["M0"][nm]))
    for nm, (o, M0r) in PIST.get("rods", {}).items():
        o.Transformation = mmake(K.mmul(K.tr(*[PIST["uy_rod"][i] * d for i in range(3)]), M0r))
    for dd in PIST.get("docs_rod", []):
        dd.Update()
    PIST["cdoc"].Update()
    estado["pist"] = d


def centrar(pal_o, k_cad=30, k_pist=10):
    """Las cadenas llevan el pallet hasta el tope del fondo (+X); los pistones lo empujan contra el tope lateral."""
    M = [r[:] for r in pal_o_M[0]]
    doc.Update()
    b0 = _bx(pal_o)
    dx = X_TOPE - b0[1][0]                                       # hasta tocar el tope del fondo (medido, no supuesto)
    y0 = b0[0][1]                                                # cara del pallet del lado de los pistones
    kk = pasos(k_cad)
    for i in range(1, kk + 1):
        t = i / kk
        Mi = [r[:] for r in M]
        Mi[0][3] = M[0][3] + dx * t
        pal_o.Transformation = mmake(Mi)
        cuadro()
    M[0][3] += dx
    diag("cadenas: contra el tope del fondo")
    esperar(4)
    kk = pasos(k_pist)
    for i in range(1, kk + 1):                                   # extienden: -60 -> 0; tocan el pallet a -60+20
        d = -CARRERA_PIST + CARRERA_PIST * i / kk
        set_pist(d)
        Mi = [r[:] for r in M]
        Mi[1][3] = M[1][3] + max(0.0, Y_CHAPA + d - y0)              # la chapa empuja desde que toca la cara
        pal_o.Transformation = mmake(Mi)
        cuadro()
        if i == kk // 2:
            diag("pistones a mitad de carrera")
    M[1][3] += max(0.0, Y_CHAPA - y0)
    pal_o_M[0] = M
    esperar(6)
    esperar(k_pist)                                              # quedan extendidos sosteniendo el pallet
    diag("final: pistones extendidos")


def _bx(o):
    b = o.RangeBox
    return [[round(b.MinPoint.X * 10, 1), round(b.MinPoint.Y * 10, 1), round(b.MinPoint.Z * 10, 1)],
            [round(b.MaxPoint.X * 10, 1), round(b.MaxPoint.Y * 10, 1), round(b.MaxPoint.Z * 10, 1)]]


def _hojas_cen(o, out, p=""):
    for h in inv._items(S(lambda: o.SubOccurrences, []) or []):
        q = f"{p}/{h.Name}"
        if any(k in h.Name for k in ("Chapa tope", "ADN", "Fijacion", "Cadena")):
            out[q] = S(lambda: _bx(h))
        _hojas_cen(h, out, q)
    return out


DIAG = []


def diag(etq):
    if not x.diag:
        return
    doc.Update()
    d = {"etapa": etq, "cuadro": n, "pist": estado.get("pist"), "pallet": _bx(pal_occ),
         "pallet_M": [[round(v, 4) for v in r] for r in mread(pal_occ.Transformation)[:3]]}
    if CEN and not x.sin_centrador:
        cen_o = by[CEN["occ"]]
        d["centrador"] = _hojas_cen(cen_o, {})
    imgs = []
    v_ant = cam_estado["v"]
    for nm_v, v in (("usuario", ([dest_c[0] - 300, dest_c[1] - 500, 400.0], 120.0, [0.25, -1.0, 0.45])),
                    ("costado", ([dest_c[0] - 450, dest_c[1] - 560, 410.0], 60.0, [-1.0, 0.0, 0.05])),
                    ("planta", ([dest_c[0] - 450, dest_c[1] - 560, 410.0], 60.0, [0.0, -0.001, 1.0]))):
        cam_set(v)
        pth = AN / f"diag_{len(DIAG):02d}_{nm_v}.png"
        app.ActiveView.SaveAsBitmap(str(pth), 1600, 900)
        imgs.append(pth.name)
    cam_set(v_ant)
    d["imagenes"] = imgs
    DIAG.append(d)
    log["diag"] = DIAG
    (AN / "diag.json").write_text(json.dumps(DIAG, ensure_ascii=False, indent=1, default=str), encoding="utf-8")


pal_occ = by[top_name]
pal_o_M = [None]
home = dict(q_toma_up)
home["q1"] = (q_toma_up["q1"] + q_deja_up["q1"]) / 2
home["q2"], home["q3"] = q_toma_up["q2"] - 10, q_toma_up["q3"]
if x.test_agarre:
    etapa("Prueba de enganche del pallet")
    ocu = []
    for o in inv._items(acd.Occurrences):
        if (o.Name.split(":")[0] in ("topes delantero derecho", "topes delantero izquierdo", "topes trasero izquierdo",
                                     "topes traseros") or (o.Name.startswith("European Pallet") and o.Name != top_name)) \
                and S(lambda: o.Visible):
            S(lambda: setattr(o, "Visible", False))
            ocu.append(o)
    aplicar(q_toma)
    imgs = []
    for ang in (x.garra_abierta, x.garra_cerrada, x.garra_plegada):
        set_garras(ang)
        for nm_v, dvv in (("costado", [0.0, -1.0, 0.0]), ("abajo", [-0.6, -1.0, -0.35]), ("iso", [0.7, -1.0, 0.5])):
            cam_set(([pal_c[0], pal_c[1], pal_c[2] + H_PAL + 200], 110.0, dvv))
            doc.Update()
            pth = AN / f"agarre_{int(ang):+04d}_{nm_v}.png"
            app.ActiveView.SaveAsBitmap(str(pth), 1600, 900)
            imgs.append(str(pth))
    for nm in EJES:
        gby[nm].Transformation = mmake(EJES[nm][2])
    gdoc.Update()
    for o in ocu:
        S(lambda: setattr(o, "Visible", True))
    S(lambda: setattr(grip, "Transformation", mmake(esc["G0"])))
    log["imagenes_agarre"] = imgs
    (AN / "resultado.json").write_text(json.dumps(log, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print(json.dumps(log, ensure_ascii=False, indent=1, default=str)[-3000:])
    sys.exit(0)
etapa("Animando fase palet")
try:
    set_pist(0.0)
    set_garras(x.garra_abierta)
    aplicar(home)
    corte("general")
    esperar(6)
    zoom_paralelo("toma_pallet", 14)                                       # zoom a la toma del pallet
    mover(q_toma_up, 14)
    mover_lineal(subir(G_toma, 250), 10)
    mover_lineal(G_toma, 8)
    garras(x.garra_cerrada, 6)                                             # cierran: aprietan el pallet
    llevando = [(pal_occ, K.mmul(K.inv_rt(estado["G"]), pallets[top_name]))]
    esperar(2 if not x.montaje else 6)
    corte("traslado", 30)
    mover_lineal(subir(G_toma, alto_lev), 14)                              # sale del almacén por arriba
    MARCAS["seg_ini"] = n
    TWEENS.append([n, pasos(18), lambda t: set_pist(-CARRERA_PIST * t)])   # se retraen mientras llega el pallet
    GRABAR["on"] = not x.diag
    mover(q_deja_up, 18)
    corte("deja", 14)
    mover_lineal(G_deja, 14)                                               # baja al centrador
    garras(x.garra_abierta, 6)
    llevando = []
    pal_o_M[0] = mread(pal_occ.Transformation)
    diag("pallet recién apoyado (pistones retraídos)")
    mover_lineal(subir(G_deja, 300), 8)
    garras(x.garra_plegada, 8)                                             # las garras se recogen
    if PIST:
        if x.montaje:
            zoom_paralelo("centrador", 16)                                 # zoom mientras el robot se aparta
            mover(q_tp_up_g, 16)
            esperar(3)
            centrar(pal_occ)
            corte("cinta" if x.dron else "general", 26)          # dron: viaja hacia la cinta de paquetes
            esperar(4)
        else:
            mover(q_tp_up_g, 16)                                           # el robot se aparta hacia la cinta
            cam_mover(VISTA_CEN, 16)                                       # zoom al centrador
            centrar(pal_occ)
            cam_mover(VISTA_GRAL, 16)
        MARCAS["seg_fin"] = n
        if x.solo_centrador or x.diag:
            raise Fin()
    if "paquetes" in x.fases:
        etapa("Animando paquetes")
        for o in paq_occ:
            S(lambda: setattr(o, "Visible", False))
        Z_SEG_P = TOMA_PAQ[2][3] + 165.0 + 250.0
        pool = list(paq_occ)
        llega(pool.pop(0))
        estado["cinta_frac"] = 1 / 20
        q_tp_up = ik(subir(G_toma_paq, Z_SEG_P - TOMA_PAQ[2][3]))
        mover(q_tp_up, 18)
        for j, d_ in enumerate(plan_paq):
            etapa(f"  paquete {j + 1}/{len(plan_paq)} (piso {d_['piso']})")
            while cinta["t"] < 1:
                esperar(1)
            if j == 0 and x.dron:
                corte("toma_paquete", 20)                  # se acerca mientras llega el paquete y baja
                esperar(4)
                mover_lineal(G_toma_paq, 14)
                esperar(3)
                pala(1.0, 10)
                esperar(5)
            elif j == 0:
                corte("cinta")
                cam_mover(PLANOS["toma_paquete"] if x.montaje else VISTA_TOMA, 16)   # zoom: agarre del paquete
                esperar(4)
                mover_lineal(G_toma_paq, 14)
                esperar(3)
                pala(1.0, 10)
                esperar(5)
            else:
                mover_lineal(G_toma_paq, 8)
                pala(1.0, 4)
            o = cinta["occ"]
            llevando = [(o, K.mmul(K.inv_rt(estado["G"]), M_pieza(TOMA_PAQ)))]
            cinta["occ"] = None
            mover_lineal(subir(G_toma_paq, Z_SEG_P - TOMA_PAQ[2][3]), 14 if j == 0 else 8)
            if j == 0 and not x.montaje:
                cam_mover(VISTA_GRAL, 16)
            if pool and j + 1 < len(plan_paq):
                llega(pool.pop(0))                     # llega el siguiente (cada 8 s en la realidad)
            alto_d = max(Z_SEG_P, d_["Cr"][2][3] + 165.0 + 250.0) - d_["Cr"][2][3]
            if x.dron:
                corte("palet_a" if d_["piso"] == 1 else "palet_b", 16)
            else:
                corte("palet_a" if (j % 2 == 0) else "palet_b")
            mover(ik(subir(d_["G"], alto_d)), 16)
            mover_lineal(d_["G"], 9)
            pala(0.0, 4)
            llevando = []
            mover_lineal(subir(d_["G"], alto_d), 8)
            if x.dron:
                corte("general" if j + 1 == len(plan_paq) else "medio", 16)
            else:
                corte("general" if (j % 3 == 2 or j + 1 == len(plan_paq)) else "cinta")
            mover(q_tp_up, 16)
    corte("general", 14)
    mover(home, 14)
    esperar(8)
except Fin:
    log["corte"] = f"vista previa: {n} cuadros"
except Exception as exc:  # noqa: BLE001
    log["error_animacion"] = repr(exc)
    log["traza"] = traceback.format_exc()[-1500:]
finally:
    S(lambda: [setattr(gby[nm], "Transformation", mmake(EJES[nm][2])) for nm in EJES])
    S(lambda: gdoc.Update())
    S(lambda: set_pala(0.0))
    S(lambda: set_pist(0.0))
    S(lambda: setattr(pal_occ, "Transformation", mmake(pallets[top_name])))
    S(lambda: setattr(grip, "Transformation", mmake(esc["G0"])))
    S(lambda: doc.Update())
with zipfile.ZipFile(AN / "cuadros.zip", "w", zipfile.ZIP_STORED) as z:
    for f in sorted(FR.glob("c*.png")):
        z.write(f, f.name)
log["cuadros"] = n
log["marcas"] = MARCAS
log["tiempo_s"] = round(time.time() - T0, 1)
app.SilentOperation = False
(AN / "resultado.json").write_text(json.dumps(log, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
print(json.dumps(log, ensure_ascii=False, indent=1, default=str))
