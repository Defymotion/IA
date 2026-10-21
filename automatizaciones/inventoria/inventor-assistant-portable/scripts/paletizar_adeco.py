"""Simulación de paletizado en el layout ADECO2 (2 pisos del patrón de Pallet_Completo).

Escena: COPIA del ensamble general (ADECOAGRO_Chivilcoy.iam -> Generados\\ADECO_SIM\\ADECO_simulacion.iam).
En la copia se ocultan el robot armado, el gripper, el pallet completo y las bandejas sueltas; se agregan:
eslabones del KUKA (V01..V05) en la misma ubicación que el robot del layout, el gripper de bandejas
(Gripper_ADECO2_V1, abulonado a la brida), un pallet europeo vacío donde estaba el pallet completo y las
bandejas que se van a paletizar. No se crea ni modifica ninguna pieza; el original no se toca.

Ciclo: llegan 6 bandejas por el freno de cajas hasta el tope; el robot toma 6 (columnas del patrón) o 3
(las 3 bandejas giradas de cada piso, que deja de a una). Patrón y posiciones: Pallet_Completo.iam.
Uso: python paletizar_adeco.py [--rearmar] [--pisos 2] [--sin-animar]
Salida: Generados\\ADECO_SIM\\Animacion\\cuadros.zip + escena.json + resultado.json
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
a.add_argument("--rearmar", action="store_true")
a.add_argument("--sin-animar", action="store_true")
a.add_argument("--pisos", type=int, default=2)
a.add_argument("--ancho", type=int, default=1280)
a.add_argument("--alto", type=int, default=720)
a.add_argument("--max-cuadros", type=int, default=0, help="cortar después de N cuadros (vista previa)")
a.add_argument("--vista", default="-0.35,1,0.95", help="dirección desde la que se mira (x,y,z)")
a.add_argument("--alto-vista", type=float, default=310.0, help="alto visible en cm")
a.add_argument("--luz", default="Luz suave", help="estilo de iluminación ('' = el del documento)")
a.add_argument("--sin-sombras", action="store_true")
a.add_argument("--ocultar", default="Protector de puerta,Pared", help="componentes a ocultar durante el video")
x = a.parse_args()

S = inv._safe
DOCS = Path.home() / "Documents" / "InventorIA"
ADECO = DOCS / "12_ADECO2"
GENERAL = ADECO / "ADECOAGRO_Chivilcoy.iam"
ROBOT = ADECO / "KUKA" / "KUKA-KR_140_R3200_2_PA-ASM.iam"
GRIP = ADECO / "Gripper" / "Gripper_ADECO2_V1.iam"
PCOMP = ADECO / "Pallet_Completo.iam"
OUTD = DOCS / "Generados" / "ADECO_SIM"
OUTD.mkdir(parents=True, exist_ok=True)
ESC = OUTD / "ADECO_simulacion.iam"
AN = OUTD / "Animacion"
AN.mkdir(exist_ok=True)
log = {"avisos": []}
T0 = time.time()
app = inv._inventor(start_if_needed=False)
tg = app.TransientGeometry
app.SilentOperation = True

BRIDA_G = (877.5, -438.8, 51.95)        # centro de la cara superior de la brida del gripper (coord. gripper)
R_G = [[0, 0, -1], [0, 1, 0], [1, 0, 0]]  # gripper -> robot (q=0): X_g -> Z_r, Y_g -> Y_r, Z_g -> -X_r


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


def stem(o):
    return Path(S(lambda: o.Definition.Document.FullFileName, "") or "").stem


# ============================================================================ datos de referencia
rd = abrir(ROBOT)
links = {}
for o in inv._items(rd.ComponentDefinition.Occurrences):
    for k in ("V01", "V02", "V03", "V04", "V05"):
        if k in o.Name:
            links[k] = {"M": mread(o.Transformation), "archivo": o.Definition.Document.FullFileName}
pcd = abrir(PCOMP).ComponentDefinition
pc_local = {o.Name: mread(o.Transformation) for o in inv._items(pcd.Occurrences)}
pallet_file = next(o.Definition.Document.FullFileName for o in inv._items(pcd.Occurrences) if "Pallet" in o.Name)
tray_file = next(o.Definition.Document.FullFileName for o in inv._items(pcd.Occurrences) if "Bandeja" in o.Name)


def armar():
    etapa("Armando escena (copia del ensamble general)")
    gd = abrir(GENERAL, True)
    for d in inv._items(app.Documents):
        if S(lambda: Path(d.FullFileName).resolve() == ESC.resolve(), False):
            S(lambda: d.Close(True))
    if ESC.exists():
        ESC.unlink()
    gd.SaveAs(str(ESC), False)                  # desde acá gd es la copia; el original queda igual
    acd = gd.ComponentDefinition
    occs = list(inv._items(acd.Occurrences))
    esc = {}
    kuka = next(o for o in occs if stem(o).startswith("KUKA"))
    pcomp = next(o for o in occs if stem(o) == "Pallet_Completo")
    grip_old = next(o for o in occs if stem(o) == "Gripper_ADECO2_V1")
    esc["T_robot"] = mread(kuka.Transformation)
    esc["T_pcomp"] = mread(pcomp.Transformation)
    trays = [o for o in occs if stem(o).startswith("Bandeja_24x200")]
    # slots de toma: las bandejas paradas contra el tope (la de mayor Y primero)
    tope = sorted([o for o in trays if abs(mread(o.Transformation)[0][3] - 1431.85) < 5],
                  key=lambda o: -mread(o.Transformation)[1][3])
    esc["slots"] = [mread(o.Transformation) for o in tope[:6]]
    for o in [kuka, pcomp, grip_old] + trays:
        S(lambda: setattr(o, "Visible", False))
    T = esc["T_robot"]
    nombres = {}
    for k in ("V01", "V02", "V03", "V04", "V05"):
        n_ = acd.Occurrences.Add(links[k]["archivo"], mmake(K.mmul(T, links[k]["M"])))
        S(lambda: setattr(n_, "Grounded", k == "V01"))
        nombres[k] = n_.Name
    og = acd.Occurrences.Add(str(GRIP), mmake(K.tr(0, 0, 0)))
    nombres["gripper"] = og.Name
    pl_m = K.mmul(esc["T_pcomp"], pc_local["European Pallet:1"])
    op = acd.Occurrences.Add(pallet_file, mmake(pl_m))
    S(lambda: setattr(op, "Grounded", True))
    esc["pallet"] = op.Name
    bandejas = []
    for i in range(6 * 2 + 21 * x.pisos):             # sobran: las de la cinta y las del pallet
        o = acd.Occurrences.Add(tray_file, mmake(esc["slots"][0]))
        S(lambda: setattr(o, "Visible", False))
        bandejas.append(o.Name)
    esc["bandejas"] = bandejas
    esc["occ"] = nombres
    gd.Update()
    gd.Save()
    (AN / "escena.json").write_text(json.dumps(esc, ensure_ascii=False, indent=1), encoding="utf-8")
    return gd, esc


if x.rearmar or not ESC.exists() or not (AN / "escena.json").exists():
    doc, esc = armar()
else:
    doc = abrir(ESC, True)
    esc = json.loads((AN / "escena.json").read_text(encoding="utf-8"))
doc.Activate()
acd = doc.ComponentDefinition
by_name = {o.Name: o for o in inv._items(acd.Occurrences)}
occ = {k: by_name[n] for k, n in esc["occ"].items()}
bandejas = [by_name[n] for n in esc["bandejas"]]

# ============================================================================ cinemática
T = esc["T_robot"]
Tinv = K.inv_rt(T)
F_orig = (1655.59, 1199.18, 4.5)
phi0 = -90.0 - math.degrees(math.atan2(-0.6889, 0.7249))
F0 = apply(K.rot_z(phi0, K.W), F_orig)
t_g = [F0[i] - sum(R_G[i][k] * BRIDA_G[k] for k in range(3)) for i in range(3)]
cfg = {"T_robot": T, "phi0": phi0, "M": {k: v["M"] for k, v in links.items()}, "brida_robot_q0": F0,
       "M_gripper_q0": [R_G[0] + [t_g[0]], R_G[1] + [t_g[1]], R_G[2] + [t_g[2]], [0, 0, 0, 1]]}
a_vec = (K.A3[0] - K.A2[0], K.A3[1] - K.A2[1])
b_vec = (K.W[0] - K.A3[0], K.W[1] - K.A3[1])
L2, L3 = math.hypot(*a_vec), math.hypot(*b_vec)
FW = (F0[0] - K.W[0], F0[1] - K.W[1])


def ik_gripper(G):
    """Ángulos para que el gripper quede en la pose G (coordenadas de la escena; Y_g vertical)."""
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
    xg = rotv(Tinv, rotv(G, (1, 0, 0)))                 # X_g en coordenadas del robot
    q6 = math.degrees(math.atan2(xg[0], xg[2])) - q1
    norm = lambda t: (t + 180) % 360 - 180  # noqa: E731
    return {"q1": norm(q1), "q2": norm(q2), "q3": norm(q3), "q6": norm(q6)}


def pose_gripper(q):
    return K.poses(cfg, q["q1"], q["q2"], q["q3"], q["q6"])["gripper"]


# ============================================================================ bandejas y patrón
tray_doc = abrir(Path(by_name[esc["bandejas"][0]].Definition.Document.FullFileName))
UPZ = [0, 0, 1]
ROT180 = [[-1, 0, 0, 0], [0, 1, 0, 0], [0, 0, -1, 0], [0, 0, 0, 1]]     # 180° alrededor del eje Y local (vertical)
RX180 = [[1, 0, 0, 0], [0, -1, 0, 0], [0, 0, -1, 0], [0, 0, 0, 1]]
H2 = 65.0                                   # mitad del alto de la bandeja (130)


def canon(M):
    """Marco canónico de una bandeja: centro del cuerpo, Y local hacia arriba (Z de la escena)."""
    C = K.mmul(M, K.tr(0, H2, 0))
    return K.mmul(C, RX180) if rotv(M, (0, 1, 0))[2] < 0 else C


def pieza(C):
    return K.mmul(C, K.tr(0, -H2, 0))


slots = [canon(m) for m in esc["slots"]]
patron = {}
for nm, M in pc_local.items():
    if "Bandeja" not in nm:
        continue
    cl = K.mmul(M, K.tr(0, H2, 0))                       # canónico en coordenadas del pallet (Y arriba)
    if rotv(M, (0, 1, 0))[1] < 0:
        cl = K.mmul(cl, RX180)
    patron.setdefault(round(cl[1][3]), []).append({"M": canon(K.mmul(esc["T_pcomp"], M)), "loc": cl})
pisos = sorted(patron)[:x.pisos]
Tp = esc["T_pcomp"]
programa = []
for ip, pz in enumerate(pisos):
    cols = {}
    for t_ in patron[pz]:
        clave = (round(t_["loc"][0][3]), abs(t_["loc"][0][0]) > 0.5)
        cols.setdefault(clave, []).append(t_)
    sueltas = [c_ for c_ in cols if len(cols[c_]) < 6]
    columnas = [c_ for c_ in cols if len(cols[c_]) >= 6]
    xs = sueltas[0][0] if sueltas else min(c_[0] for c_ in columnas)
    signo = -1 if all(c_[0] < xs for c_ in columnas) else 1           # las columnas avanzan alejándose
    d_cols = rotv(Tp, (signo, 0, 0))                                  # dirección libre (coord. escena)
    d_sue = rotv(Tp, (0, 0, 1))
    for c_ in sueltas:                                                # 1) las sueltas, a lo largo de z local
        grupo = sorted(cols[c_], key=lambda t_: t_["loc"][2][3])
        programa.append({"tipo": "sueltas", "destinos": [g["M"] for g in grupo], "n": len(grupo), "libre": d_sue,
                         "piso": ip + 1})
    for c_ in sorted(columnas, key=lambda c_: signo * c_[0]):         # 2) columnas desde las sueltas hacia afuera
        grupo = sorted(cols[c_], key=lambda t_: t_["loc"][2][3])
        programa.append({"tipo": "columna", "destinos": [g["M"] for g in grupo[:6]], "n": 6, "libre": d_cols,
                         "piso": ip + 1})
log["programa"] = [(p["tipo"], p["n"], p["piso"]) for p in programa]


def G_para(dest, Brel, todos=None, libre=None):
    """Pose del gripper que lleva la bandeja (relativa Brel) a dest. Prueba la bandeja girada 180° y, si se
    pasan todos los pares (destino, Brel) de una fila, elige la que mejor ubica la fila completa.
    libre: dirección hacia donde todavía no hay bandejas; las palas móviles (lado -Z del gripper) van hacia ahí."""
    sols = []
    anclas = [(dest, Brel)] if not todos else [todos[0], (todos[-1][0], todos[0][1])]
    for d_, b_ in anclas:
        for R in (K.tr(0, 0, 0), ROT180):
            G = K.mmul(K.mmul(d_, R), K.inv_rt(b_))
            try:
                q = ik_gripper(G)
            except ValueError:
                continue
            err = 0.0
            if todos:
                err = sum(min(math.dist(apply(K.mmul(G, bb), (0, 0, 0)), [dd[i][3] for i in range(3)])
                              for dd, _ in todos) for _, bb in todos)
            mal_lado = 0
            if libre is not None:
                zg_ = rotv(G, (0, 0, 1))
                mal_lado = 1 if sum(zg_[i] * libre[i] for i in range(3)) > 0 else 0
            sols.append((round(err / 30), mal_lado, abs(q["q6"]), G, q))
    if not sols:
        raise ValueError("Destino fuera de alcance")
    s_ = min(sols, key=lambda t: (t[0], t[1], t[2]))
    if s_[1]:
        log["avisos"].append("Una dejada quedó con las palas móviles del lado ocupado")
    return s_[3], s_[4]


def subir(G, dz):
    return K.mmul(K.tr(0, 0, dz), G)


# palas móviles del gripper: rango en X del gripper y restricción del gripper que mueve cada una sola
PALAS = {"pala_movil_apriete:1": (408.1, 548.1, None), "pala_movil_apriete:2": (568.1, 708.1, None),
         "pala_movil_apriete:6": (728.1, 868.1, "Nivelación:74"), "pala_movil_apriete:3": (888.1, 1028.1, "Nivelación:75"),
         "pala_movil_apriete:4": (1048.1, 1188.1, "Nivelación:76"), "pala_movil_apriete:5": (1208.1, 1348.1, "Nivelación:77")}
TCP_G = (878.1, -688.8 - H2, 243.5 - 156.5)
s0, s5 = [slots[0][i][3] for i in range(3)], [slots[5][i][3] for i in range(3)]
centro = [(s0[i] + s5[i]) / 2 for i in range(3)]
ux = [s5[i] - s0[i] for i in range(3)]
ln = math.hypot(*ux)
ux = [v / ln for v in ux]


def pose_toma(u):
    zg = [u[1] * UPZ[2] - u[2] * UPZ[1], u[2] * UPZ[0] - u[0] * UPZ[2], u[0] * UPZ[1] - u[1] * UPZ[0]]
    Rg = [[u[i], UPZ[i], zg[i]] for i in range(3)]
    tp = [centro[i] - sum(Rg[i][k] * TCP_G[k] for k in range(3)) for i in range(3)]
    return [Rg[0] + [tp[0]], Rg[1] + [tp[1]], Rg[2] + [tp[2]], [0, 0, 0, 1]]


def pala_de(Br):
    xg = Br[0][3]
    return next((k for k, (a_, b_, _) in PALAS.items() if a_ - 10 <= xg <= b_ + 10), None)


# toma: se elige el sentido del gripper en el que las 3 primeras bandejas caen en palas independientes
G_toma = None
for u in (ux, [-v for v in ux]):
    G_ = pose_toma(u)
    Br_ = [K.mmul(K.inv_rt(G_), sl) for sl in slots]
    pal = [pala_de(b) for b in Br_[:3]]
    if all(PALAS.get(k, (0, 0, None))[2] for k in pal):
        G_toma, Brel, PALA_SLOT = G_, Br_, [pala_de(b) for b in Br_]
        break
if G_toma is None:
    G_toma = pose_toma(ux)
    Brel = [K.mmul(K.inv_rt(G_toma), sl) for sl in slots]
    PALA_SLOT = [pala_de(b) for b in Brel]
    log["avisos"].append("Las 3 bandejas sueltas no caen en palas independientes")
log["pala_por_slot"] = PALA_SLOT
try:
    q_toma = ik_gripper(G_toma)
    G_chk = pose_gripper(q_toma)
    log["ik_error_toma_mm"] = round(math.dist(apply(G_chk, TCP_G), apply(G_toma, TCP_G)), 2)
except ValueError as exc:
    log["avisos"].append(f"Toma: {exc}")
    q_toma = None
for p in programa:
    p["G"] = []
    try:
        if p["tipo"] == "columna":
            p["G"].append(G_para(None, None, list(zip(p["destinos"], Brel[:6])), p["libre"]))
        else:
            for j, dest in enumerate(p["destinos"]):
                p["G"].append(G_para(dest, Brel[j], None, p["libre"]))
    except ValueError as exc:
        log["avisos"].append(f"{p['tipo']}: {exc}")
log["q_toma"] = {k: round(v, 1) for k, v in (q_toma or {}).items()}
log["q_destinos"] = [[{k: round(v, 1) for k, v in q.items()} for _, q in p["G"]] for p in programa]
if x.sin_animar or q_toma is None:
    (AN / "resultado.json").write_text(json.dumps(log, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print(json.dumps(log, ensure_ascii=False, indent=1, default=str))
    sys.exit(0)

# ============================================================================ animación
etapa("Animando")
FR = AN / "cuadros"
FR.mkdir(exist_ok=True)
for f in FR.glob("*.png"):
    f.unlink()
n = 0
estado = {"q": None}
llevando = []
pool = list(bandejas)
cinta = []          # [occ, M_final, avance (0..1)]
LLEGADA = 1600.0    # mm de recorrido en el freno de cajas


def aplicar(q):
    P = K.poses(cfg, q["q1"], q["q2"], q["q3"], q["q6"])
    for kk in ("V02", "V03", "V04", "V05", "gripper"):
        occ[kk].Transformation = mmake(P[kk])
    for o, Br in llevando:
        o.Transformation = mmake(pieza(K.mmul(P["gripper"], Br)))
    estado["q"] = q


def cinta_paso(frac):
    for it in cinta:
        if it[2] >= 1:
            continue
        it[2] = min(1.0, it[2] + frac)
        M = [row[:] for row in it[1]]
        M[0][3] += ux[0] * LLEGADA * (1 - it[2])
        M[1][3] += ux[1] * LLEGADA * (1 - it[2])
        it[0].Transformation = mmake(pieza(M))


class Fin(Exception):
    pass


def cuadro():
    global n
    if x.max_cuadros and n >= x.max_cuadros:
        raise Fin()
    doc.Update()
    app.ActiveView.SaveAsBitmap(str(FR / f"c{n:04d}.png"), x.ancho, x.alto)
    n += 1


def mover(q_fin, pasos=10, cinta_frac=0.0):
    q_ini = estado["q"]
    d6 = (q_fin["q6"] - q_ini["q6"] + 180) % 360 - 180
    for i in range(1, pasos + 1):
        t = (1 - math.cos(math.pi * i / pasos)) / 2
        q = {kk: q_ini[kk] + (q_fin[kk] - q_ini[kk]) * t for kk in ("q1", "q2", "q3")}
        q["q6"] = q_ini["q6"] + d6 * t
        aplicar(q)
        cinta_paso(cinta_frac)
        cuadro()


def esperar(k, cinta_frac=0.0):
    for _ in range(k):
        cinta_paso(cinta_frac)
        cuadro()


# ---- palas móviles: cierre de todas (restricción interna del cilindro) y apertura individual (restricción
#      de cada pala en el gripper). Sólo en memoria; al final se restituyen los valores.
gdoc = occ["gripper"].Definition.Document
gcons = {c.Name: c for c in inv._items(gdoc.ComponentDefinition.Constraints)}
pdoc = next(o for o in inv._items(gdoc.ComponentDefinition.Occurrences)
            if o.Name.startswith("pala_movil_apriete")).Definition.Document
c_cil = next(c for c in inv._items(pdoc.ComponentDefinition.Constraints) if c.Name == "Coincidencia:17")
CIERRE = 6.55                                 # cm: de la posición guardada (abierta) al contacto con la bandeja
v_cil0 = c_cil.Offset.Value
v_pala0 = {k: gcons[cn].Offset.Value for k, (_, _, cn) in PALAS.items() if cn}
pinza = {"cil": 0.0, "palas": {k: 0.0 for k in v_pala0}}     # 0 abierto ... 1 cerrado / 0 ... 1 abierta extra


def set_pinza(cil, palas_abiertas):
    if abs(c_cil.Offset.Value - (v_cil0 + CIERRE * cil)) > 1e-6:
        c_cil.Offset.Value = v_cil0 + CIERRE * cil
        pdoc.Update()
    cambio = False
    for k, f in palas_abiertas.items():
        v = v_pala0[k] - CIERRE * f
        if abs(gcons[PALAS[k][2]].Offset.Value - v) > 1e-6:
            gcons[PALAS[k][2]].Offset.Value = v
            cambio = True
    if cambio or True:
        gdoc.Update()
    pinza["cil"], pinza["palas"] = cil, dict(palas_abiertas)


def mover_pinza(cil, palas_abiertas, pasos=3):
    c0, p0 = pinza["cil"], dict(pinza["palas"])
    for i in range(1, pasos + 1):
        t = i / pasos
        set_pinza(c0 + (cil - c0) * t, {k: p0.get(k, 0) + (palas_abiertas.get(k, 0) - p0.get(k, 0)) * t
                                        for k in v_pala0})
        cuadro()


def llegan(nb):
    """Entran nb bandejas por el freno de cajas hasta los slots del tope."""
    cinta.clear()
    for j in range(nb):
        o = pool.pop(0)
        cinta.append([o, slots[j], 0.0])
        S(lambda: setattr(o, "Visible", True))
    cinta_paso(0.0)


# planos de trabajo y bocetos ocultos (el plano verde del layout)
for wp in inv._items(acd.WorkPlanes):
    S(lambda: setattr(wp, "Visible", False))
ov = S(lambda: doc.ObjectVisibility)
for prop in ("AllWorkFeatures", "UserWorkPlanes", "OriginWorkPlanes", "Sketches", "Sketches3D"):
    S(lambda: setattr(ov, prop, False))
# cámara: toma + pallet (y un poco el robot), vista desde las camas de rolo, Z vertical
pts = [apply(T, (0, 0, 0)), [slots[0][i][3] for i in range(3)], [slots[5][i][3] for i in range(3)],
       [esc["T_pcomp"][i][3] for i in range(3)], [esc["T_pcomp"][i][3] for i in range(3)]]
c = [sum(p[i] for p in pts) / len(pts) for i in range(3)]
c[2] = 1000.0
cam = app.ActiveView.Camera
cam.Target = tg.CreatePoint(c[0] / 10, c[1] / 10, c[2] / 10)
dirv = tuple(float(v) for v in x.vista.split(","))
ocultos = []
for o in inv._items(acd.Occurrences):
    if any(o.Name.startswith(t.strip()) for t in x.ocultar.split(",") if t.strip()) and S(lambda: o.Visible):
        S(lambda: setattr(o, "Visible", False))
        ocultos.append(o)
cam.Eye = tg.CreatePoint(c[0] / 10 + dirv[0] * 800, c[1] / 10 + dirv[1] * 800, c[2] / 10 + dirv[2] * 800)
cam.UpVector = tg.CreateUnitVector(0, 0, 1)
S(lambda: setattr(cam, "Perspective", False))
cam.SetExtents(x.alto_vista * x.ancho / x.alto, x.alto_vista)
cam.Apply()
vw = app.ActiveView
if not x.sin_sombras:
    for prop in ("ShowAmbientShadows", "ShowObjectShadows", "ShowGroundShadows"):
        S(lambda: setattr(vw, prop, True))
    S(lambda: setattr(vw, "ShowGroundPlane", False))
if x.luz:
    S(lambda: setattr(doc, "ActiveLightingStyle", doc.LightingStyles.Item(x.luz)))

home = {"q1": q_toma["q1"] - 40, "q2": 0.0, "q3": 0.0, "q6": q_toma["q6"]}
for o in bandejas:
    S(lambda: setattr(o, "Visible", False))
aplicar(home)
q_toma_up = ik_gripper(subir(G_toma, 350))
try:
    llegan(programa[0]["n"])
    esperar(14, 1 / 14)
    for ip, p in enumerate(programa):
        etapa(f"  toma {ip + 1}/{len(programa)} ({p['tipo']}, {p['n']})")
        nb = p["n"]
        mover(q_toma_up, 12)
        mover(q_toma, 6)
        mover_pinza(1.0, {k: 0 for k in v_pala0}, 3)              # cierran las palas
        llevando = [(cinta[j][0], Brel[j]) for j in range(nb)]
        resto = cinta[nb:]
        mover(q_toma_up, 6)
        # las que quedaron (si toma 3 de 6) se descartan de la vista; entran las siguientes
        for it in resto:
            S(lambda: setattr(it[0], "Visible", False))
            pool.insert(0, it[0])
        if ip + 1 < len(programa):
            llegan(programa[ip + 1]["n"])
        for j, (G, q) in enumerate(p["G"]):
            q_up = ik_gripper(subir(G, 300))
            mover(q_up, 14 if j == 0 else 8, 1 / 30)
            mover(q, 6, 1 / 30)
            if p["tipo"] == "columna":
                mover_pinza(0.0, {k: 0 for k in v_pala0}, 3)          # abren todas (hacia el lado libre)
                llevando = []
            else:
                k_ = PALA_SLOT[j]                                     # abre sólo la pala de esa bandeja
                abiertas = dict(pinza["palas"])
                abiertas[k_] = 1.0
                mover_pinza(1.0, abiertas, 3)
                llevando = llevando[1:]
            mover(q_up, 6, 1 / 30)
        if p["tipo"] != "columna":
            mover_pinza(0.0, {k: 0 for k in v_pala0}, 2)              # todas abiertas otra vez
    mover(home, 12)
    esperar(8)
except Fin:
    log["corte"] = f"vista previa: {n} cuadros"
except Exception as exc:  # noqa: BLE001
    log["error_animacion"] = repr(exc)
    log["traza"] = traceback.format_exc()[-1500:]
finally:
    c_cil.Offset.Value = v_cil0
    for k_, v_ in v_pala0.items():
        gcons[PALAS[k_][2]].Offset.Value = v_
    S(lambda: pdoc.Update())
    S(lambda: gdoc.Update())
for o in ocultos:
    S(lambda: setattr(o, "Visible", True))
with zipfile.ZipFile(AN / "cuadros.zip", "w", zipfile.ZIP_STORED) as z:
    for f in sorted(FR.glob("c*.png")):
        z.write(f, f.name)
log["cuadros"] = n
log["tiempo_s"] = round(time.time() - T0, 1)
app.SilentOperation = False
(AN / "resultado.json").write_text(json.dumps(log, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
print(json.dumps(log, ensure_ascii=False, indent=1, default=str))
