"""(Se corre del lado de la IA, sin Inventor; usa celda_kin.py) Planificador de la simulación completa L3N (Python puro, sin Inventor).
Lee sim_relevamiento.json y escribe plan_l3n.json: objetos dinámicos y, por cuadro, cámara + cambios de estado
(matrices 3x4 en mm, visibilidad, apertura de garras). El renderizador (simular_l3n_planta.py) sólo aplica el plan.

Proceso: cajas por la cinta de llegada (T1, Curva 1, T2a/T2b, Curva 2, T3) con acumulación -> pateador -> cinta
interna con acumulación contra el tope -> robot KR 180 (4 ejes) con gripper de 7 garras: por capa toma 3 y las deja
de a 1 (fila de 3, gripper a 90°) y toma 7 dos veces (filas de 7); capas impares/pares espejadas (patrón real del
Pallet_TBA250_17x8). El robot aéreo trae el pallet vacío desde la pila de buffer y lo apoya en la cama de ingreso;
las camas lo llevan a la estación y el centrador lo alinea. Al terminar: la mesa giratoria gira 90° hacia la
celda, el pallet sale, recorre la línea hasta la envolvedora MP402 y se envuelve con film.
Uso: python l3n_plan.py rel.json plan_l3n.json [--fps 30]
"""
import json
import math
import sys
import copy
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import celda_kin as K  # noqa: E402

REL = json.load(open(sys.argv[1], encoding="utf-8"))
OUT = Path(sys.argv[2])
FPS = 30
DIAG = {"avisos": []}


# ------------------------------------------------------------------ álgebra
def I4():
    return [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]


def mm(P, Q):
    return K.mmul(P, Q)


def inv(M):
    return K.inv_rt(M)


def tr(x, y, z):
    return K.tr(x, y, z)


def roty(deg, cx=0.0, cz=0.0):
    return K.rot_y(deg, (cx, cz))


def apply(M, p):
    return [sum(M[i][k] * p[k] for k in range(3)) + M[i][3] for i in range(3)]


def lerp(a, b, u):
    return a + (b - a) * u


def ease(u):
    u = max(0.0, min(1.0, u))
    return u * u * (3 - 2 * u)


def ease5(u):
    u = max(0.0, min(1.0, u))
    return u * u * u * (u * (6 * u - 15) + 10)


def comp(M):
    """3x4 redondeada para el plan."""
    return [round(M[i][j], 4 if j < 3 else 2) for i in range(3) for j in range(4)]


def yaw_of(M):
    """Giro sobre Y de la matriz (ángulo del eje X local en planta, convención rot_y)."""
    return math.degrees(math.atan2(-M[2][0], M[0][0]))


# ------------------------------------------------------------------ datos del relevamiento
celda = {e["n"]: e for e in REL["celda_A"]}
aereo = {e["n"]: e for e in REL["aereo"]}
linea = {e["n"]: e for e in REL["linea"]}
mp = {e["n"]: e for e in REL["mp402"]["hijos"]}
kuka = REL["kuka"]
links = {}
for n, v in kuka["links"].items():
    links["V0" + n.split("_V0")[-1][:1]] = v["M_rel"]
T_ROB = kuka["M_layout"]
G = REL["gripper"]
GRIP_LOCAL = G["caja_local"]          # [x0,y0,z0,x1,y1,z1]
BRIDA_G = (387.0, 546.0, -245.2)
R_WD = [[0, 1, 0], [0, 0, -1], [-1, 0, 0]]
MODS = sorted(G["modulos"].keys(), key=lambda s: int(s.split(":")[-1]))
APERT0 = G["modulos"][MODS[0]]["valor_mm"]

# robot: muñeca horizontal (phi0) y gripper en la brida (misma construcción que armar_l3n.py)
v5 = links["V05"]
nb = [-v5[i][2] for i in range(3)]
PHI0 = -90.0 - math.degrees(math.atan2(nb[1], nb[0]))
F_orig = apply(v5, (1850.0, 0.0, 1745.0))
F0 = apply(K.rot_z(PHI0, K.W), F_orig)
Rr = [row[:3] for row in T_ROB[:3]]
Rt = [[Rr[j][i] for j in range(3)] for i in range(3)]
R_G = [[sum(Rt[i][k] * R_WD[k][j] for k in range(3)) for j in range(3)] for i in range(3)]
t_g = [F0[i] - sum(R_G[i][k] * BRIDA_G[k] for k in range(3)) for i in range(3)]
CFG = {"T_robot": T_ROB, "phi0": PHI0, "M": {k: links[k] for k in ("V02", "V03", "V04", "V05")}, "brida_robot_q0": F0,
       "M_gripper_q0": [R_G[0] + [t_g[0]], R_G[1] + [t_g[1]], R_G[2] + [t_g[2]], [0, 0, 0, 1]]}


def brida(q):
    T1 = K.rot_y(q[0])
    T3 = K.mmul(K.mmul(T1, K.rot_z(q[1], K.A2)), K.rot_z(q[2], K.A3))
    Tg = K.mmul(K.mmul(T3, K.rot_z(PHI0 - q[1] - q[2], K.W)), K.inv_rt(K.rot_z(PHI0, K.W)))
    return apply(K.mmul(T_ROB, Tg), F0)


def solve3(A, b):
    M = [A[i][:] + [b[i]] for i in range(3)]
    for c in range(3):
        p = max(range(c, 3), key=lambda r: abs(M[r][c]))
        M[c], M[p] = M[p], M[c]
        for r in range(3):
            if r != c:
                f = M[r][c] / M[c][c]
                M[r] = [M[r][k] - f * M[c][k] for k in range(4)]
    return [M[i][3] / M[i][i] for i in range(3)]


def ik(target, q0):
    q = list(q0[:3])
    for _ in range(150):
        f = brida(q)
        r = [f[i] - target[i] for i in range(3)]
        e = math.sqrt(sum(v * v for v in r))
        if e < 0.05:
            break
        J = [[0.0] * 3 for _ in range(3)]
        for j in range(3):
            qq = q[:]
            qq[j] += 0.01
            fj = brida(qq)
            for i in range(3):
                J[i][j] = (fj[i] - f[i]) / 0.01
        dq = solve3(J, [-v for v in r])
        m = max(abs(v) for v in dq)
        if m > 8:
            dq = [v * 8 / m for v in dq]
        q = [q[i] + dq[i] for i in range(3)]
    return q, e


def poses(q):
    return K.poses(CFG, q[0], q[1], q[2], q[3])


def q_for_gripper(Mg, qprev):
    """Ángulos para que el gripper quede en la matriz Mg (sólo giro sobre Y + traslación)."""
    F = apply(Mg, BRIDA_G)
    q3, e = ik(F, qprev)
    if e > 0.2:
        for seed in ([qprev[0], -40.0, 90.0], [qprev[0], -70.0, 130.0], [qprev[0], -20.0, 60.0], q3):
            q3b, eb = ik(F, seed)
            if eb < e:
                q3, e = q3b, eb
            if e < 0.05:
                break
    psi = yaw_of(Mg)
    q6 = psi - PSI_G0 - q3[0]
    # continuidad de q6
    while q6 - qprev[3] > 180:
        q6 -= 360
    while q6 - qprev[3] < -180:
        q6 += 360
    return [q3[0], q3[1], q3[2], q6], e


# gripper a q = 0 y su giro base
P0 = poses([0, 0, 0, 0])
MG0 = P0["gripper"]
PSI_G0 = yaw_of(MG0)


def gripper_pose(psi, pos_origin):
    """Matriz del gripper con giro psi (convención yaw_of) y el origen local en pos_origin (mundo)."""
    R = mm(roty(psi - PSI_G0), [MG0[0][:3] + [0], MG0[1][:3] + [0], MG0[2][:3] + [0], [0, 0, 0, 1]])
    R[0][3], R[1][3], R[2][3] = pos_origin
    return R


# ------------------------------------------------------------------ geometría de la tarea
Y_BANDA = 800.0
CAJA = (386.0, 149.0, 156.0)            # largo local X, alto, ancho local Z (origen centro de la base)
X_STOP = -7822.7                          # cara de tope en la cinta interna
Z_INT = -36697.0
X_INT0 = -11898.1
SLOT0 = X_STOP - CAJA[2] / 2
R_BOX_INT = [[0, 0, 1], [0, 1, 0], [-1, 0, 0]]          # caja en la cinta interna: 386 cruzado (Z), 156 en X


def box_M(R, c_base):
    return [R[0] + [c_base[0]], R[1] + [c_base[1]], R[2] + [c_base[2]], [0, 0, 0, 1]]


# caja tomada por la garra i (local del gripper): misma relación que la toma con palas 15 mm sobre la banda
G_ALTO_PALA = GRIP_LOCAL[5]               # z local de la punta de las palas
X_MED = (GRIP_LOCAL[0] + GRIP_LOCAL[3]) / 2
# relevado con la pose de toma del layout: centro de caja en x local 388,2; base de caja 15 mm bajo la punta
X_BOX_LOC = 388.18


def garra_y(i):
    return 78.0 + 156.0 * i


def M_box_en_gripper(i):
    """Matriz caja -> gripper (local) para la garra i, con la caja orientada como en la cinta interna."""
    # caja en el mundo con el gripper en MG_toma: obtengo R relativo con un gripper genérico
    Mg = gripper_pose(PSI_G0, (0, 0, 0))
    Rg = [r[:3] for r in Mg[:3]]
    Rgt = [[Rg[j][k] for j in range(3)] for k in range(3)]
    Rrel = [[sum(Rgt[a][k] * R_BOX_INT[k][b] for k in range(3)) for b in range(3)] for a in range(3)]
    base_local = [X_BOX_LOC, garra_y(i), G_ALTO_PALA + 15.0]
    return [Rrel[0] + [base_local[0]], Rrel[1] + [base_local[1]], Rrel[2] + [base_local[2]], [0, 0, 0, 1]]


LB = [M_box_en_gripper(i) for i in range(7)]


def gripper_para_caja(Mb, i):
    return mm(Mb, inv(LB[i]))


# pallet y patrón
PAL_O = [REL["pallet_lleno"]["M_layout"][i][3] for i in range(3)]          # centro de la base del pallet (estación)
PAT = []
for e in REL["pallet_lleno"]["hijos"][1:]:
    M = e["M_rel"]
    PAT.append({"R": [r[:3] for r in M[:3]], "p": [M[0][3], M[1][3], M[2][3]]})
CAPAS = sorted({round(b["p"][1]) for b in PAT})
# luz entre filas para las palas: el gripper aprieta de costado y cada pala mide 33,5 mm; el patrón del modelo no
# tiene luz entre filas, así que se abren 35 mm entre bandas (Z) y entre las 3 cajas de la fila transversal (X)
LUZ_PALA = 35.0
for y_ in CAPAS:
    cap = [b for b in PAT if round(b["p"][1]) == y_]
    bandas = sorted({round(b["p"][2]) for b in cap})
    for b in cap:
        b["p"][2] += (bandas.index(round(b["p"][2])) - (len(bandas) - 1) / 2) * LUZ_PALA
    r3 = sorted([b for b in cap if abs(b["R"][0][0]) > 0.5], key=lambda b: b["p"][0])
    for j, b in enumerate(r3):
        b["p"][0] += (j - (len(r3) - 1) / 2) * LUZ_PALA


def pat_world(b, origin=PAL_O):
    return box_M(b["R"], [origin[0] + b["p"][0], origin[1] + b["p"][1], origin[2] + b["p"][2]])


# ------------------------------------------------------------------ recorrido de la cinta de llegada
R_CURVA = 475.0
SEGS = []           # (tipo, datos, largo)


def seg_recta(a, b):
    L = math.dist(a, b)
    SEGS.append(("r", (a, b), L))


def seg_arco(c, a0, a1):
    L = abs(math.radians(a1 - a0)) * R_CURVA
    SEGS.append(("a", (c, a0, a1), L))


X_T1, Z_T1_0 = 4363.0, -25562.0
Z_T2 = -30894.0
X_T3 = -12134.0
seg_recta((X_T1, Z_T1_0), (X_T1, Z_T2 + R_CURVA))
seg_arco((X_T1 - R_CURVA, Z_T2 + R_CURVA), 0.0, -90.0)
seg_recta((X_T1 - R_CURVA, Z_T2), (X_T3 + R_CURVA, Z_T2))
seg_arco((X_T3 + R_CURVA, Z_T2 - R_CURVA), 90.0, 180.0)
seg_recta((X_T3, Z_T2 - R_CURVA), (X_T3, Z_INT))
L_PATH = sum(s[2] for s in SEGS)


def path_pt(s):
    """Punto (x, z) y rumbo (hx, hz) a la distancia s del inicio."""
    s = max(0.0, min(L_PATH, s))
    for tipo, d, L in SEGS:
        if s <= L + 1e-9:
            u = s / L
            if tipo == "r":
                (a, b) = d
                h = ((b[0] - a[0]) / L, (b[1] - a[1]) / L)
                return (lerp(a[0], b[0], u), lerp(a[1], b[1], u)), h
            c, a0, a1 = d
            ang = math.radians(lerp(a0, a1, u))
            p = (c[0] + R_CURVA * math.cos(ang), c[1] + R_CURVA * math.sin(ang))
            sg = 1 if a1 > a0 else -1
            h = (-math.sin(ang) * sg, math.cos(ang) * sg)
            return p, h
        s -= L
    raise ValueError


def box_on_path(s):
    (x, z), (hx, hz) = path_pt(s)
    # X local de la caja (386) a lo largo del rumbo; Z local = h x Y
    R = [[hx, 0, -hz], [0, 1, 0], [hz, 0, hx]]
    return box_M(R, [x, Y_BANDA, z])


# ------------------------------------------------------------------ parámetros de tiempo (segundos de simulación)
V_BANDA = 500.0                 # mm/s cinta de llegada e interna
PASO_FUENTE = 1.15              # s entre cajas que entrega la CP
GAP_ACUM = 8.0                  # luz entre cajas acumuladas
T_PATEO, T_RETORNO = 0.55, 0.4
CARRERA_PAT = 450.0             # recorrido de la chapa en la simulación (el modelo tiene 300: ver aviso)
PAT_CONTACTO = 163.7            # luz entre la chapa retraída y la caja sobre T3 (relevado)
X_PAT_FIN = X_T3 + CARRERA_PAT - PAT_CONTACTO  # centro de la caja al final del pateo
N_POOL = 232
T_FIN = 300.0


# ------------------------------------------------------------------ robot: trayectorias
A_OPEN = APERT0                 # valor relevado de la restricción "Apertura" (garras abiertas)
A_CLOSE = APERT0 + 22.0         # cerradas (sentido a verificar en la foto de prueba; --signo invierte)
LIFT = 260.0
VEL_CART = 1400.0               # mm/s en traslados
STACK_TOP = [PAL_O[1] + 152.0]  # altura actual de apoyo sobre el pallet (se actualiza por capa)


class Seg:
    """Segmento de movimiento del gripper en cartesianas: pose(t) -> (psi, origen)."""

    def __init__(self, t0, dur, a, b, arco=0.0, nota=""):
        self.t0, self.t1, self.a, self.b, self.arco, self.nota = t0, t0 + dur, a, b, arco, nota

    def pose(self, t):
        u = ease5((t - self.t0) / max(1e-6, self.t1 - self.t0))
        (pa, xa), (pb, xb) = self.a, self.b
        dpsi = pb - pa
        while dpsi > 180:
            dpsi -= 360
        while dpsi < -180:
            dpsi += 360
        p = [lerp(xa[i], xb[i], u) for i in range(3)]
        p[1] += self.arco * math.sin(math.pi * u)
        return pa + dpsi * u, p


def org_de(Mg):
    return yaw_of(Mg), [Mg[0][3], Mg[1][3], Mg[2][3]]


def mover(t, a, b, arco=0.0, vmin=0.35, nota=""):
    d = math.dist(a[1], b[1])
    dpsi = abs(((b[0] - a[0]) + 180) % 360 - 180)
    dur = max(vmin, d / VEL_CART * 1.5, dpsi / 140.0)
    return Seg(t, dur, a, b, arco, nota)


def traslado(t, a, b, nota="traslado"):
    """Sube vertical a la altura mayor de las dos, cruza horizontal (girando) y baja vertical: las cajas colgadas
    nunca cruzan por debajo de la altura de llegada (que ya está LIFT sobre la capa)."""
    yv = max(a[1][1], b[1][1])
    out = []
    if yv - a[1][1] > 5:
        p = (a[0], [a[1][0], yv, a[1][2]])
        out.append(Seg(t, max(0.25, (yv - a[1][1]) / 1200.0), a, p, nota="sube"))
        a, t = p, out[-1].t1
    p = (b[0], [b[1][0], yv, b[1][2]])
    out.append(mover(t, a, p, vmin=0.8, nota=nota))
    if yv - b[1][1] > 5:
        out.append(Seg(out[-1].t1, max(0.25, (yv - b[1][1]) / 1200.0), p, b, nota="baja"))
    return out


def subir(p, dy):
    return (p[0], [p[1][0], p[1][1] + dy, p[1][2]])


AJUSTES = []
LIFT_MIN = 200.0          # cajas colgando: su base debe pasar 50 mm sobre las ya apoyadas (149 de alto)


def alcanza(p, q0=(0.0, -40.0, 90.0, 0.0)):
    _, e = q_for_gripper(gripper_pose(*p), list(q0))
    return e < 0.3


def arriba(p, dy):
    """Pose dy mm sobre p; si queda fuera del alcance del robot, baja la altura (mín. 60) y si hace falta se retira
    hacia la base del robot en planta."""
    for d in [dy] + [v for v in range(int(dy) - 20, int(min(dy, LIFT_MIN)) - 1, -20)]:
        c = subir(p, d)
        if alcanza(c):
            if d != dy:
                AJUSTES.append(("baja", round(dy - d), [round(v) for v in p[1]]))
            return c
    bx, bz = T_ROB[0][3], T_ROB[2][3]
    for r in range(50, 1001, 50):
        o = p[1]
        L = math.hypot(o[0] - bx, o[2] - bz)
        c = (p[0], [o[0] - (o[0] - bx) / L * r, o[1] + LIFT_MIN, o[2] - (o[2] - bz) / L * r])
        if alcanza(c):
            AJUSTES.append(("retira", r, [round(v) for v in p[1]]))
            return c
    AJUSTES.append(("sin_solucion", 0))
    return subir(p, LIFT_MIN)


# ------------------------------------------------------------------ simulación por eventos
DT = 0.005


class Box:
    def __init__(self, idx):
        self.idx = idx
        self.keys = []          # (t, fase, valor)  fase: 'path' s | 'kick' u | 'int' x | 'held' (ciclo, garra) | 'placed' M | 'hide'

    def key(self, t, fase, val):
        if self.keys and self.keys[-1][1] == fase and fase in ("path", "kick", "int") and abs(self.keys[-1][0] - t) < 1e-9:
            self.keys[-1] = (t, fase, val)
            return
        self.keys.append((t, fase, val))


boxes = [Box(i) for i in range(N_POOL)]
path_q, int_q = [], []          # cajas en la cinta de llegada / interna (frente primero)
pos = {}                        # idx -> s o x actual
vel = {}                        # idx -> velocidad actual (para registrar cambios)
src_next, src_i = -70.0, 0
kick = None                     # (idx, t0)
pat_events = []                 # (t0, t1) del pateador
robot_cycles = []               # lista de dicts
picked = 0
placed = 0
T_PAL_LISTO = None
robot_t_free = None
robot_last = None               # última pose (psi, origen)
ORDER = []                      # orden de colocación: (capa, tipo, [(caja_patron, garra)])


def build_order():
    out = []
    for li, y in enumerate(CAPAS):
        cap = [b for b in PAT if round(b["p"][1]) == y]
        row3 = sorted([b for b in cap if abs(b["R"][0][0]) > 0.5], key=lambda b: b["p"][0])
        rows7 = [b for b in cap if abs(b["R"][0][0]) < 0.5]
        zs = sorted({round(b["p"][2]) for b in rows7})
        z3 = row3[0]["p"][2]
        # filas de 7: primero la más alejada de la fila de 3, al final la vecina
        zs.sort(key=lambda z: -abs(z - z3))
        filas = [sorted([b for b in rows7 if round(b["p"][2]) == z], key=lambda b: b["p"][0]) for z in zs]
        out.append({"capa": li, "y": y, "row3": row3, "filas": filas, "z3": z3})
    return out


LAYERS = build_order()


def plan_ciclo(t, n, layer, kind, targets):
    """Arma el ciclo completo del robot desde la pose actual. kind: 'row3' (targets: 3 cajas del patrón) o 'row7'."""
    global robot_last
    segs = []
    # toma: garras 6..(7-n) sobre las posiciones de cabeza 0..n-1
    Mpick = gripper_para_caja(box_M(R_BOX_INT, [SLOT0, Y_BANDA, Z_INT]), 6)
    p_pick = org_de(Mpick)
    y_seg = max(STACK_TOP[0] + 300.0, Y_BANDA + 149 + 300.0) - Y_BANDA   # altura segura relativa a la toma
    above_pick = subir(p_pick, LIFT)
    cur = robot_last if robot_last else above_pick
    segs += traslado(t, cur, above_pick, nota="a_toma")
    s = Seg(segs[-1].t1, 0.45, above_pick, p_pick, nota="baja_toma"); segs.append(s)
    t_cierra = s.t1
    garras = list(range(7 - n, 7))
    s = Seg(s.t1 + 0.25, 0.45, p_pick, subir(p_pick, LIFT), nota="sube_toma"); segs.append(s)
    drops = []                                      # (t_abre, garra, M_caja_final)
    if kind == "row7":
        tgt = [pat_world(b) for b in targets]       # ordenadas por x creciente -> garra 0..6
        Mg = gripper_para_caja(tgt[0], 0)
        pl = org_de(Mg)
        ab = arriba(pl, LIFT)
        segs += traslado(s.t1, segs[-1].b, ab)
        s = segs[-1]
        s = Seg(s.t1, 0.5, ab, pl, nota="baja_deja"); segs.append(s)
        for g_, M in zip(range(7), tgt):
            drops.append((s.t1, g_, M))
        s = Seg(s.t1 + 0.25, 0.45, pl, arriba(pl, LIFT), nota="sube_deja"); segs.append(s)
    else:
        # fila de 3 dejada de a 1: gripper a 90°; las cajas que quedan en el gripper apuntan hacia la zona libre
        z_libre = -1.0 if layer["z3"] > 0 else 1.0           # sentido (Z del pallet) hacia las filas de 7 vacías
        orden = sorted(targets, key=lambda b: b["p"][0])
        orden = [orden[0], orden[2], orden[1]]               # extremos primero, la del medio al final
        prev = segs[-1].b
        for k, (b, g_) in enumerate(zip(orden, [4, 5, 6])):
            Mb = pat_world(b)
            cand = []
            for flip in (0, 1):
                Mb2 = mm(Mb, roty(180.0)) if flip else Mb
                Mg = gripper_para_caja(Mb2, g_)
                ydir = [Mg[0][1], Mg[1][1], Mg[2][1]]          # Y local del gripper (sentido de las garras)
                cand.append((ydir[2] * z_libre, Mg, Mb2))
            cand.sort(key=lambda c: -c[0])
            _, Mg, Mb2 = cand[0]
            pl = org_de(Mg)
            ab = arriba(pl, LIFT if k == 0 else LIFT_MIN)
            arco = max(0.0, (STACK_TOP[0] + 420.0) - ab[1][1]) + 120.0 if k == 0 else 0.0
            if k == 0:
                segs += traslado(segs[-1].t1, prev, ab)
            else:
                segs.append(mover(segs[-1].t1, prev, ab, vmin=0.5, nota="corre"))
            s = segs[-1]
            s = Seg(s.t1, 0.4, ab, pl, nota="baja_deja"); segs.append(s)
            drops.append((s.t1, g_, Mb2))
            s = Seg(s.t1 + 0.22, 0.32, pl, arriba(pl, LIFT_MIN if k < 2 else LIFT), nota="sube_deja"); segs.append(s)
            prev = s.b
    robot_last = segs[-1].b
    cyc = {"t0": t, "t1": segs[-1].t1, "segs": segs, "t_cierra": t_cierra, "garras": garras, "drops": drops,
           "n": n, "kind": kind, "capa": layer["capa"]}
    robot_cycles.append(cyc)
    return cyc



# ------------------------------------------------------------------ programa del robot: pallet 1 completo y pallet 2
PROG = []
for pal_n in (1, 2):
    for L_ in LAYERS:
        PROG.append((3, "row3", L_["row3"], L_, pal_n))
        for f in L_["filas"]:
            PROG.append((7, "row7", f, L_, pal_n))
prog_i = 0
cyc_act = None

# ---- robot aéreo y pallets (tiempos absolutos)
Z_PILA1, X_PILA = -32274.0, -10635.0
Z_PARK = -33039.0
X_CARRO = -10582.0
Z_CARRO0 = -36100.0                    # z del carro en el modelo
Z_DEP = (-36438.8 + -34940.4) / 2
Y_PAL_TOP_PILA = [1368.0 + 152.0, 1216.0 + 152.0]      # pallet 10 y 9 de la pila 1
AER = []                    # tramos (t0, t1, campo, a, b)


def aer(t0, dur, campo, a, b):
    AER.append((t0, t0 + dur, campo, a, b))
    return t0 + dur


def aer_val(campo, t, inicial):
    v = inicial
    for (t0, t1, c, a, b) in AER:
        if c != campo:
            continue
        if t >= t1:
            v = b
        elif t >= t0:
            v = lerp(a, b, ease5((t - t0) / (t1 - t0)))
    return v


def suministro(t, k):
    """El robot aéreo toma el pallet k (0: pallet 10, 1: pallet 9) de la pila 1 y lo deja en la cama de ingreso."""
    z_ini = aer_val("z", t, Z_PARK)
    t = aer(t, 1.4, "z", z_ini, Z_PILA1)
    dy_pick = Y_PAL_TOP_PILA[k] - 1680.0
    t = aer(t, 1.1, "dy", 0.0, dy_pick)
    t_agarra = t + 0.3
    t = aer(t_agarra, 1.1, "dy", dy_pick, 0.0)
    t = aer(t + 0.1, 4.0, "z", Z_PILA1, Z_DEP)
    dy_dep = PAL_O[1] - 1528.0
    t = aer(t, 2.4, "dy", 0.0, dy_dep)
    t_suelta = t + 0.3
    t = aer(t_suelta, 2.0, "dy", dy_dep, 0.0)
    aer(t + 0.2, 3.2, "z", Z_DEP, Z_PARK)
    return t_agarra, t_suelta


PALLETS = {}
V_CAMA = 420.0


def pallet_supply(nombre, k, t0):
    t_ag, t_su = suministro(t0, k)
    d = PAL_O[0] - X_CARRO
    t_c0 = t_su + 0.5
    t_c1 = t_c0 + d / V_CAMA * 1.25
    t_cz1 = t_c1 + 0.8
    PALLETS[nombre] = {"k": k, "t_agarra": t_ag, "t_suelta": t_su, "t_cama": (t_c0, t_c1), "t_centra": (t_c1 + 0.1, t_cz1),
                       "listo": t_cz1, "pila_M": tr(X_PILA, Y_PAL_TOP_PILA[k] - 152.0, Z_PILA1)}
    return t_cz1


T_PAL_LISTO = {1: pallet_supply("SIM_Pallet_1", 0, 0.6)}


# ---- salida del pallet lleno: giratoria, traslado a la MP402, envuelto y salida
def trapecio(D, v=450.0, a=300.0):
    ta = v / a
    da = 0.5 * a * ta * ta
    if 2 * da > D:
        ta = math.sqrt(D / a)
        T = 2 * ta
        vmax = a * ta

        def pos(t):
            t = max(0.0, min(T, t))
            return 0.5 * a * t * t if t < ta else D - 0.5 * a * (T - t) ** 2
        return T, pos
    T = 2 * ta + (D - 2 * da) / v

    def pos(t):
        t = max(0.0, min(T, t))
        if t < ta:
            return 0.5 * a * t * t
        if t < T - ta:
            return da + v * (t - ta)
        return D - 0.5 * a * (T - t) ** 2
    return T, pos


def t_de_pos(T, pos, x):
    lo, hi = 0.0, T
    for _ in range(60):
        m = (lo + hi) / 2
        if pos(m) < x:
            lo = m
        else:
            hi = m
    return hi


X_MP, X_GIR, Z_GIR = 9865.8, -6538.2351, -35622.3429
X_SALIDA_FIN = 12600.0
N_VUELTAS = 6.0
T_ENV = 30.0
ROTOR_EJE = (X_MP, PAL_O[2])
# alturas de apoyo (base del pallet) por tramo; se ajustan con el relevamiento de rodillos de la escena
APOYOS = [(-1e9, -7528.2, PAL_O[1]), (-7528.2, -5548.3, PAL_O[1]), (-5618.2, 8419.8, 626.8), (8419.8, 11465.8, 501.3),
          (11465.8, 1e9, 626.8)]
EXIT = {}


def _base(x):
    for (a_, b_, y_) in APOYOS:
        if a_ <= x < b_:
            return y_
    return APOYOS[-1][2]


def y_apoyo(x):
    """Base del pallet según el transportador bajo su centro, suavizada en ±150 mm (promedio móvil)."""
    return sum(_base(x - 150.0 + 10.0 * i) for i in range(31)) / 31.0


def planear_salida(t_fin):
    e = {"T_GIR0": t_fin + 0.3}
    e["T_GIR1"] = e["T_GIR0"] + 3.0
    e["T_MOV0"] = e["T_GIR1"] + 0.6
    D = X_MP - PAL_O[0]
    e["T_mov"], pos = trapecio(D)
    e["pos"] = pos
    e["T_ARR"] = e["T_MOV0"] + e["T_mov"]
    t_libre = e["T_MOV0"] + t_de_pos(e["T_mov"], pos, (-6538.2 + 990.0 + 620.0) - PAL_O[0])
    e["T_GIRB0"] = t_libre + 0.3
    e["T_GIRB1"] = e["T_GIRB0"] + 3.0
    e["T_ESTACION_LIBRE"] = e["T_MOV0"] + t_de_pos(e["T_mov"], pos, (-7400.0 + 650.0) - PAL_O[0])
    e["T_W0"] = e["T_ARR"] + 1.0
    e["T_W1"] = e["T_W0"] + T_ENV
    e["T_S0"] = e["T_W1"] + 1.5
    e["T_s"], e["pos_s"] = trapecio(X_SALIDA_FIN - X_MP)
    e["T_S1"] = e["T_S0"] + e["T_s"]
    return e


def x_lleno(t):
    e = EXIT
    if t < e["T_MOV0"]:
        return PAL_O[0]
    if t < e["T_S0"]:
        return PAL_O[0] + e["pos"](t - e["T_MOV0"])
    return X_MP + e["pos_s"](t - e["T_S0"])


def gir_frac(t):
    """0: rodillos de la giratoria transportan hacia B (Z); 1: orientada hacia la celda (X)."""
    if not EXIT or t < EXIT["T_GIR0"]:
        return 0.0
    if t < EXIT["T_GIRB0"]:
        return ease5((t - EXIT["T_GIR0"]) / 3.0)
    return 1.0 - ease5((t - EXIT["T_GIRB0"]) / 3.0)


H_CARGA = 1344.0
N_FILM = 8
H_FILM = 200.0
DY_CARRO_MAX = 0.0          # se calcula en armar_frames


def env_estado(t):
    """(ángulo del rotor, subida del carro, bandas visibles) durante el envuelto."""
    if not EXIT or t < EXIT["T_W0"]:
        return 0.0, 0.0, 0
    u = min(1.0, (t - EXIT["T_W0"]) / T_ENV)
    # ángulo: aceleración y frenado suaves (perfil trapezoidal en velocidad angular)
    ta = 0.1
    if u < ta:
        f = 0.5 * u * u / ta
    elif u < 1 - ta:
        f = 0.5 * ta + (u - ta)
    else:
        f = 1 - ta - 0.5 * (1 - u) ** 2 / ta
    f /= (1 - ta)
    ang = -360.0 * N_VUELTAS * f
    # carro: sube en el 50 %, arriba un 8 %, baja en el resto (doble capa)
    if u < 0.5:
        h = ease(u / 0.5)
    elif u < 0.58:
        h = 1.0
    else:
        h = 1.0 - ease((u - 0.58) / 0.42)
    dy = DY_CARRO_MAX * h
    nb = 0
    for k in range(N_FILM):
        uk = 0.03 + 0.45 * (k + 0.5) / N_FILM
        if u >= uk:
            nb = k + 1
    return ang, dy, nb


# ------------------------------------------------------------------ bucle de simulación de cintas + robot
t = -70.0
max_q = 0
T_FIN_PAL = {}
held = {}
libres = []                 # cajas del pallet 1 que vuelven a la fuente después del canje
placed_pal = {1: 0, 2: 0}
pal_de_ciclo = {}
T_SWAP = None
canjeado = False
while t < T_FIN:
    # fuente (CP): una caja cada PASO_FUENTE si hay lugar al inicio
    if t >= src_next and (src_i < N_POOL or libres):
        libre = (not path_q) or pos[path_q[-1]] >= CAJA[0] + GAP_ACUM
        if libre:
            if src_i < N_POOL:
                b = src_i
                src_i += 1
            else:
                b = libres.pop(0)
            path_q.append(b)
            pos[b] = 0.0
            vel[b] = None
            boxes[b].key(t, "path", 0.0)
            src_next = t + PASO_FUENTE
    # cinta de llegada con acumulación
    lim = L_PATH
    for b in path_q:
        s0 = pos[b]
        s1 = min(s0 + V_BANDA * DT, lim)
        v = (s1 - s0) / DT
        mov = v > 1e-6
        if vel.get(b) is None or (vel[b] > 1e-6) != mov:
            boxes[b].key(t, "path", s0)
            vel[b] = v
        pos[b] = s1
        lim = s1 - (CAJA[0] + GAP_ACUM)
    # pateador
    if kick is None and path_q and pos[path_q[0]] >= L_PATH - 0.01:
        tail_ok = (not int_q) or pos[int_q[-1]] >= X_PAT_FIN + CAJA[2] + 2.0
        if tail_ok:
            b = path_q.pop(0)
            boxes[b].key(t, "path", L_PATH)
            boxes[b].key(t, "kick", t)
            kick = (b, t)
            pat_events.append((t, t + T_PATEO, t + T_PATEO + T_RETORNO))
    if kick is not None and len(kick) == 2 and t >= kick[1] + T_PATEO:
        b = kick[0]
        boxes[b].key(t, "int", X_PAT_FIN)
        int_q.append(b)
        pos[b] = X_PAT_FIN
        vel[b] = None
        kick = (None, kick[1], "ret")
    if kick is not None and t >= kick[1] + T_PATEO + T_RETORNO:
        kick = None
    # cinta interna con acumulación contra el tope
    lim = SLOT0
    for b in int_q:
        x0 = pos[b]
        x1 = min(x0 + V_BANDA * DT, lim)
        v = (x1 - x0) / DT
        mov = v > 1e-6
        if vel.get(b) is None or (vel[b] > 1e-6) != mov:
            boxes[b].key(t, "int", x0)
            vel[b] = v
        pos[b] = x1
        lim = x1 - CAJA[2]
    max_q = max(max_q, len(int_q))
    # robot
    if t >= 0 and cyc_act is None and prog_i < len(PROG):
        n, kind, targets, L_, pal_n = PROG[prog_i]
        listo = len(int_q) >= n and all(abs(pos[int_q[j]] - (SLOT0 - CAJA[2] * j)) < 0.05 for j in range(n))
        pal_ok = pal_n in T_PAL_LISTO and t >= T_PAL_LISTO[pal_n] - 2.5
        if listo and pal_ok:
            STACK_TOP[0] = PAL_O[1] + L_["y"]
            cyc_act = plan_ciclo(t, n, L_, kind, targets)
            cyc_act["cajas"] = None
            cyc_act["pal"] = pal_n
            prog_i += 1
    if cyc_act is not None:
        if cyc_act["cajas"] is None and t >= cyc_act["t_cierra"]:
            n = cyc_act["n"]
            tomadas = int_q[:n]
            del int_q[:n]
            cyc_act["cajas"] = {}
            for j, b in enumerate(tomadas):
                g_ = 6 - j
                boxes[b].key(t, "int", pos[b])
                boxes[b].key(t, "held", (len(robot_cycles) - 1, g_))
                cyc_act["cajas"][g_] = b
                picked += 1
        if cyc_act["cajas"] is not None:
            for (td, g_, M) in cyc_act["drops"]:
                b = cyc_act["cajas"].get(g_)
                if b is not None and t >= td and boxes[b].keys[-1][1] == "held":
                    boxes[b].key(td, "placed", M)
                    placed += 1
                    placed_pal[cyc_act["pal"]] += 1
        if t >= cyc_act["t1"]:
            pal_n = cyc_act["pal"]
            cyc_act = None
            if placed_pal[pal_n] >= 136 and pal_n not in T_FIN_PAL:
                T_FIN_PAL[pal_n] = t
                if pal_n == 1:
                    # el robot vuelve a esperar sobre la toma; la giratoria se orienta y sale el pallet
                    Mpick = gripper_para_caja(box_M(R_BOX_INT, [SLOT0, Y_BANDA, Z_INT]), 6)
                    home = subir(org_de(Mpick), LIFT)
                    s_h = traslado(t, robot_last, home, nota="espera")
                    robot_cycles.append({"t0": t, "t1": s_h[-1].t1, "segs": s_h, "t_cierra": None, "garras": [], "drops": [],
                                         "n": 0, "kind": "home", "capa": -1, "cajas": {}, "pal": 1})
                    robot_last = home
                    EXIT.update(planear_salida(t))
                    T_SWAP = EXIT["T_GIR0"]
                    T_PAL_LISTO[2] = pallet_supply("SIM_Pallet_2", 1, EXIT["T_ESTACION_LIBRE"] + 0.3)
    if T_SWAP is not None and t >= T_SWAP and not canjeado:
        canjeado = True
        for b in boxes:
            if b.keys and b.keys[-1][1] == "placed":
                b.key(T_SWAP, "hide", None)
                libres.append(b.idx)
    t += DT

for b in boxes:                      # cierre de los tramos abiertos al final
    if b.keys and b.keys[-1][1] in ("path", "int"):
        b.key(T_FIN, b.keys[-1][1], pos.get(b.idx, b.keys[-1][2]))
DIAG.update({"picked": picked, "placed": placed, "max_cola_interna": max_q, "T_pallet_listo": T_PAL_LISTO,
             "T_fin_paletizado": T_FIN_PAL, "ciclos": len(robot_cycles), "cajas_generadas": src_i,
             "salida": {k: round(v, 2) for k, v in EXIT.items() if isinstance(v, float)}})
DIAG["avisos"].append("pateador: con la chapa retraída queda a 164 mm de la caja sobre T3; con los 300 mm de carrera del "
                      "DSBC-32-300 la caja no llega a la cinta interna (queda casi toda sobre T3). En la simulación se usan "
                      "450 mm: acercar el pateador a T3 o usar un cilindro de 450-500 mm")

if "--ciclos" in sys.argv:
    for c in robot_cycles:
        print(c.get("pal"), c["capa"], c["kind"], round(c["t0"], 2), round(c["t1"], 2), round(c["t1"] - c["t0"], 2))
    print({k: {kk: (round(vv, 2) if isinstance(vv, float) else vv) for kk, vv in v.items() if kk != "pila_M"} for k, v in PALLETS.items()})
    print(json.dumps(DIAG, ensure_ascii=False, default=str))
    sys.exit(0)

# ================================================================== muestreo por cuadro
SEGS_R = sorted([s for c in robot_cycles for s in c["segs"]], key=lambda s: s.t0)


def robot_target(t):
    """(psi, origen) del gripper pedido por el programa en el instante t."""
    prev = None
    for s in SEGS_R:
        if s.t0 > t:
            break
        prev = s
    if prev is None:
        return SEGS_R[0].a
    return prev.pose(t) if t < prev.t1 else prev.b


# garras: eventos (t, +1 cierra / -1 abre) por garra
G_EV = {g: [] for g in range(7)}
for ci, c in enumerate(robot_cycles):
    if not c.get("cajas"):
        continue
    for g in c["cajas"]:
        G_EV[g].append((c["t_cierra"] - 0.2, c["t_cierra"], 1))
    for (td, g, M) in c["drops"]:
        if g in c["cajas"]:
            G_EV[g].append((td, td + 0.25, 0))


def garra_frac(g, t):
    f = 0.0
    for (a_, b_, dst) in G_EV[g]:
        if t >= b_:
            f = float(dst)
        elif t >= a_:
            u = ease((t - a_) / (b_ - a_))
            f = u if dst == 1 else 1 - u
    return f


def pat_d(t):
    for (a_, b_, c_) in pat_events:
        if a_ <= t < b_:
            return CARRERA_PAT * ease5((t - a_) / T_PATEO)
        if b_ <= t < c_:
            return CARRERA_PAT * (1 - ease5((t - b_) / T_RETORNO))
    return 0.0


class BoxCursor:
    def __init__(self, b):
        self.b, self.i = b, 0

    def state(self, t, Gt):
        k = self.b.keys
        if not k or t < k[0][0]:
            return False, box_on_path(0.0)
        while self.i + 1 < len(k) and k[self.i + 1][0] <= t:
            self.i += 1
        t0, fase, val = k[self.i]
        nxt = k[self.i + 1] if self.i + 1 < len(k) else None
        if fase in ("path", "int"):
            v = val
            if nxt is not None and nxt[1] == fase and nxt[0] > t0:
                v = lerp(val, nxt[2], (t - t0) / (nxt[0] - t0))
            if fase == "path":
                return True, box_on_path(v)
            return True, box_M(R_BOX_INT, [v, Y_BANDA, Z_INT])
        if fase == "kick":
            x = X_T3 + max(0.0, min(CARRERA_PAT, pat_d(t)) - PAT_CONTACTO)
            return True, box_M(R_BOX_INT, [x, Y_BANDA, Z_INT])
        if fase == "held":
            return True, mm(Gt, LB[val[1]])
        if fase == "placed":
            return True, val
        return False, None                      # hide


def pallet_M(nombre, t):
    P = PALLETS[nombre]
    if t < P["t_agarra"]:
        return P["pila_M"]
    if t < P["t_suelta"]:
        x = lerp(X_PILA, X_CARRO, ease((t - P["t_agarra"]) / 2.5))
        return tr(x, 1528.0 + aer_val("dy", t, 0.0), aer_val("z", t, Z_PARK))
    c0, c1 = P["t_cama"]
    z0, z1 = P["t_centra"]
    x = lerp(X_CARRO, PAL_O[0], ease5((t - c0) / (c1 - c0))) if t >= c0 else X_CARRO
    z = lerp(Z_DEP, PAL_O[2], ease((t - z0) / (z1 - z0))) if t >= z0 else Z_DEP
    return tr(x, PAL_O[1], z)


M_PROX = {}                 # matrices del relevamiento (layout) de lo que se mueve
for n_ in ("Carro", "Torre_elevacion", "Barra_elevacion", "Sujecion_pallet"):
    M_PROX["aereo/" + n_] = aereo[n_]["M"]
PAT_PIEZAS = ["chapa pateador:2", "chapa refuerzo:1", "soporte a piston:1", "soporte a piston:2", "eje cromado 500:1",
              "eje cromado 500:2", "SHF16:1", "SHF16:2"]
for n_ in PAT_PIEZAS:
    M_PROX["pat/" + n_] = celda["Ensamble pateador adeco:1/" + n_]["M"]
M_ROTOR = mp["MP402_Rotor:1"]["M"]
M_CARRO_MP = mp["MP402_Carro:1"]["M"]
ROTOR_EJE = (9865.8363, -35615.1739)          # origen de MP402_Estructura (eje de giro del brazo)
DY_CARRO_MAX = (y_apoyo(X_MP) + H_CARGA + 30.0) - mp["MP402_Carro:1"]["c"][4]


def film_rel(k):
    yk = 20.0 + k * (H_CARGA - 40.0 - H_FILM) / (N_FILM - 1) + H_FILM / 2
    return [[1, 0, 0, 0], [0, 0, 1, yk], [0, -1, 0, 0], [0, 0, 0, 1]]


def lleno_M(t):
    x = x_lleno(t) if EXIT else PAL_O[0]
    return tr(x, y_apoyo(x), PAL_O[2])


# ------------------------------------------------------------------ objetos de la escena de simulación
CELDA_P, AEREO_P, LINEA_P = "Celda_A_L3N:1/", "Robot_Aereo_Pallets:1/", "Linea_Pallets:1/"
OBJ = {}


def obj(nombre, archivo, M, vis=True, rol=""):
    OBJ[nombre] = {"f": archivo, "M": comp(M), "vis": vis, "rol": rol}


for k_ in ("V02", "V03", "V04", "V05"):
    obj(f"SIM_{k_}", REL["robot_ia"][f"IA_Robot_{k_}"]["f"], REL["robot_ia"][f"IA_Robot_{k_}"]["M"], rol="robot")
obj("SIM_Gripper", G["f"], G["M_layout"], rol="gripper")
CAJA_F = REL["celda_A"][[e["n"] for e in REL["celda_A"]].index("IA_Caja_en_cinta")]["f"]
for i in range(N_POOL):
    obj(f"SIM_Caja_{i:03d}", CAJA_F, box_on_path(0.0), vis=False, rol="caja")
PAL_F = aereo["Pila1_pallet_10"]["f"]
obj("SIM_Pallet_1", PAL_F, PALLETS["SIM_Pallet_1"]["pila_M"], vis=False, rol="pallet")
obj("SIM_Pallet_2", PAL_F, PALLETS["SIM_Pallet_2"]["pila_M"], vis=False, rol="pallet")
obj("SIM_Pallet_lleno", "PALLET_LLENO_SIM", tr(*PAL_O), vis=False, rol="pallet_lleno")
for n_ in PAT_PIEZAS:
    obj("SIM_Pat_" + n_.replace(" ", "_").replace(":", "_"), celda["Ensamble pateador adeco:1/" + n_]["f"], M_PROX["pat/" + n_], rol="pateador")
for n_, nn in (("Carro", "SIM_Aereo_Carro"), ("Torre_elevacion", "SIM_Aereo_Torre"), ("Sujecion_pallet", "SIM_Aereo_Sujecion")):
    obj(nn, aereo[n_]["f"], aereo[n_]["M"], rol="aereo")
for j in range(3):
    obj(f"SIM_Aereo_Barra_{j}", aereo["Barra_elevacion"]["f"], aereo["Barra_elevacion"]["M"], rol="aereo")
GIR_DECK = REL["giratoria_A"]["hijos"][0]
obj("SIM_Gir_Deck", GIR_DECK["f"], GIR_DECK["M"], rol="giratoria")
obj("SIM_MP402_Rotor", mp["MP402_Rotor:1"]["f"], M_ROTOR, rol="envolvedora")
obj("SIM_MP402_Carro", mp["MP402_Carro:1"]["f"], M_CARRO_MP, rol="envolvedora")
for k in range(N_FILM):
    obj(f"SIM_Film_{k}", "FILM_A" if k % 2 == 0 else "FILM_B", mm(tr(*PAL_O), film_rel(k)), vis=False, rol="film")

OCULTAR = ["Paredes:1"] + [CELDA_P + n_ for n_ in ("IA_Robot_V02", "IA_Robot_V03", "IA_Robot_V04", "IA_Robot_V05", "IA_Gripper_7xTBA250",
                                    "IA_Pallet_TBA250", "IA_Caja_en_cinta")]
OCULTAR += [CELDA_P + "Ensamble pateador adeco:1/" + n_ for n_ in PAT_PIEZAS]
OCULTAR += [CELDA_P + "roller conveyor - rotating:1/" + GIR_DECK["n"]]
OCULTAR += [AEREO_P + n_ for n_ in ("Carro", "Torre_elevacion", "Barra_elevacion", "Sujecion_pallet", "Pallet_en_sujecion")]
OCULTAR += [LINEA_P + "MP402:1/MP402_Rotor:1", LINEA_P + "MP402:1/MP402_Carro:1"]
PROXY_DIN = {AEREO_P + "Pila1_pallet_10": PALLETS["SIM_Pallet_1"]["t_agarra"],
             AEREO_P + "Pila1_pallet_9": PALLETS["SIM_Pallet_2"]["t_agarra"]}


def estado(t, qprev):
    """Estado completo en t: matrices, visibilidad, garras, giro de la giratoria."""
    M, V = {}, {}
    psi, org = robot_target(t)
    Mg_req = gripper_pose(psi, org)
    q, e = q_for_gripper(Mg_req, qprev)
    P = poses(q)
    for k_ in ("V02", "V03", "V04", "V05"):
        M[f"SIM_{k_}"] = P[k_]
    Gt = P["gripper"]
    M["SIM_Gripper"] = Gt
    for cur in CURSORES:
        v, Mb = cur.state(t, Gt)
        nm = f"SIM_Caja_{cur.b.idx:03d}"
        V[nm] = v
        if Mb is not None:
            M[nm] = Mb
    for nm in ("SIM_Pallet_1", "SIM_Pallet_2"):
        P_ = PALLETS[nm]
        M[nm] = pallet_M(nm, t)
        V[nm] = t >= P_["t_agarra"] and not (nm == "SIM_Pallet_1" and T_SWAP is not None and t >= T_SWAP)
    Ml = lleno_M(t)
    M["SIM_Pallet_lleno"] = Ml
    V["SIM_Pallet_lleno"] = T_SWAP is not None and t >= T_SWAP
    d = pat_d(t)
    for n_ in PAT_PIEZAS:
        M["SIM_Pat_" + n_.replace(" ", "_").replace(":", "_")] = mm(tr(d, 0, 0), M_PROX["pat/" + n_])
    z, dy = aer_val("z", t, Z_PARK), aer_val("dy", t, 0.0)
    T_z = tr(0, 0, z - Z_CARRO0)
    M["SIM_Aereo_Carro"] = mm(T_z, M_PROX["aereo/Carro"])
    M["SIM_Aereo_Torre"] = mm(T_z, M_PROX["aereo/Torre_elevacion"])
    M["SIM_Aereo_Sujecion"] = mm(tr(0, dy, z - Z_CARRO0), M_PROX["aereo/Sujecion_pallet"])
    for j in range(3):
        M[f"SIM_Aereo_Barra_{j}"] = mm(tr(0, dy * j / 2.0, z - Z_CARRO0), M_PROX["aereo/Barra_elevacion"])
    ang, dyc, nb = env_estado(t)
    R_ = K.rot_y(ang, ROTOR_EJE)
    M["SIM_MP402_Rotor"] = mm(R_, M_ROTOR)
    M["SIM_MP402_Carro"] = mm(R_, mm(tr(0, dyc, 0), M_CARRO_MP))
    for k in range(N_FILM):
        M[f"SIM_Film_{k}"] = mm(Ml, film_rel(k))
        V[f"SIM_Film_{k}"] = k < nb or (EXIT and t >= EXIT["T_W1"])
    for pth, ta in PROXY_DIN.items():
        V["@" + pth] = t < ta
    gar = [round(garra_frac(g, t), 3) for g in range(7)]
    return M, V, gar, round(gir_frac(t), 4), q, e


CURSORES = [BoxCursor(b) for b in boxes]

# ------------------------------------------------------------------ verificación de consistencia (saltos al tomar/dejar)
chk = {"toma_max_mm": 0.0, "deja_max_mm": 0.0, "ik_max_mm": 0.0}
qv = [0.0, 0.0, 0.0, 0.0]
for ci, c in enumerate(robot_cycles):
    if not c.get("cajas"):
        continue
    psi, org = robot_target(c["t_cierra"])
    Mg = gripper_pose(psi, org)
    for g, b in c["cajas"].items():
        j = 6 - g
        want = box_M(R_BOX_INT, [SLOT0 - CAJA[2] * j, Y_BANDA, Z_INT])
        got = mm(Mg, LB[g])
        chk["toma_max_mm"] = max(chk["toma_max_mm"], math.dist([got[i][3] for i in range(3)], [want[i][3] for i in range(3)]))
    for (td, g, Mt) in c["drops"]:
        psi, org = robot_target(td)
        got = mm(gripper_pose(psi, org), LB[g])
        chk["deja_max_mm"] = max(chk["deja_max_mm"], math.dist([got[i][3] for i in range(3)], [Mt[i][3] for i in range(3)]))
DIAG["consistencia"] = {k: round(v, 2) for k, v in chk.items()}
DIAG["ajustes_alcance"] = AJUSTES

# ------------------------------------------------------------------ guion del video (segmentos, cámara, leyendas)
E_ = EXIT
T_CAPA1 = [c for c in robot_cycles if c.get("pal") == 1 and c["capa"] == 0][-1]["t1"] + 0.4
SEG_V = [
    # (nombre, t0, t1, velocidad, claves de cámara [(u, ojo, objetivo, ancho)], leyenda)
    ("general", -12.0, -6.0, 1.0, [(0.0, (21000, 26000, -16000), (-3500, 0, -38500), 38000),
                                   (1.0, (2500, 8000, -28500), (-8200, 600, -35800), 13500)],
     "Planta Las Tres Niñas · Celda A de paletizado (nueva)"),
    ("pateador", -6.0, 0.0, 1.0, [(0.0, (-14500, 4600, -39700), (-12100, 800, -36400), 4600),
                                  (1.0, (-14300, 4300, -39500), (-11900, 800, -36500), 4200)],
     "Cinta de llegada → pateador → cinta interna (acumula contra el tope)"),
    ("aereo", 0.0, 17.0, 2.0, [(0.0, (-2500, 6500, -29000), (-10300, 1200, -33800), 9500),
                               (0.55, (-2800, 6200, -29800), (-10000, 1000, -34800), 9000),
                               (1.0, (-3200, 5600, -31000), (-9000, 800, -35700), 8000)],
     "Robot aéreo: toma un pallet vacío del buffer y lo apoya en la cama de ingreso (×2)"),
    ("capa1", 17.0, T_CAPA1, 1.0, [(0.0, (-3600, 4900, -32200), (-8500, 1000, -36400), 6200),
                                   (1.0, (-4100, 5300, -31700), (-8400, 1050, -36400), 6600)],
     "Capa 1: toma 3 cajas y las deja de a una (fila transversal); después dos tomas de 7"),
    ("capas", T_CAPA1, E_["T_GIR0"], 7.0, [(0.0, (-3600, 6200, -32200), (-8500, 1150, -36600), 6800),
                                           (0.5, (-1800, 6600, -36600), (-8500, 1150, -36600), 7200),
                                           (1.0, (-2600, 6300, -40200), (-8500, 1150, -36600), 6800)],
     "Capas 2 a 8 (×7)"),
    ("salida", E_["T_GIR0"], E_["T_MOV0"] + 9.0, 1.5, [(0.0, (-2600, 4400, -31600), (-7200, 700, -35900), 7600),
                                                      (1.0, (-600, 4400, -31200), (-5200, 700, -35700), 7600)],
     "Pallet completo: la mesa giratoria se orienta hacia la celda y el pallet sale por la barrera IFM (muting)"),
    ("traslado", E_["T_MOV0"] + 9.0, E_["T_ARR"], 8.0, "seguir",
     "Traslado por la línea de pallets hasta la envolvedora MP402 (×8)"),
    ("envuelto", E_["T_ARR"], E_["T_W1"] + 0.5, 3.0, [(0.0, (14800, 4600, -30800), (9866, 1250, -35617), 6800),
                                                      (1.0, (12600, 5200, -29900), (9866, 1250, -35617), 6800)],
     "Envolvedora MP402: film estirable en espiral (×3)"),
    ("final", E_["T_W1"] + 0.5, E_["T_S1"] + 3.0, 1.0, [(0.0, (12600, 5200, -29900), (9866, 1250, -35617), 6800),
                                                        (0.35, (13500, 6000, -29000), (10500, 1100, -35617), 8000),
                                                        (1.0, (9000, 17000, -17000), (-1500, 0, -37000), 30000)],
     "Pallet envuelto a despacho · en la celda ya se apoyó el pallet siguiente y el robot sigue paletizando"),
]


def cam_seguir(t):
    x = x_lleno(t)
    return (x + 3000.0, 4300.0, -30800.0), (x + 300.0, 900.0, -35617.0), 8000.0


def cam_en(seg, t):
    nombre, t0, t1, vel_, keys, _ = seg
    if keys == "seguir":
        return cam_seguir(t)
    u = (t - t0) / (t1 - t0)
    if u <= keys[0][0]:
        return keys[0][1:]
    for a_, b_ in zip(keys, keys[1:]):
        if u <= b_[0]:
            w = ease((u - a_[0]) / (b_[0] - a_[0]))
            return (tuple(lerp(a_[1][i], b_[1][i], w) for i in range(3)), tuple(lerp(a_[2][i], b_[2][i], w) for i in range(3)),
                    lerp(a_[3], b_[3], w))
    return keys[-1][1:]


def capa_en(t):
    """Capa (1..8) del pallet 1 que se está armando en t."""
    c_ = [c for c in robot_cycles if c.get("pal") == 1 and c["capa"] >= 0 and c["t0"] <= t]
    return (c_[-1]["capa"] + 1) if c_ else 0


FRAMES = []
for seg in SEG_V:
    nombre, t0, t1, vel_, keys, ley = seg
    nf = int(round((t1 - t0) / vel_ * FPS))
    for i in range(nf):
        t_ = t0 + i * vel_ / FPS
        eye, tgt, w = cam_en(seg, t_)
        txt = ley
        if nombre == "capas":
            txt = f"Capas 2 a 8 (×7) · armando la capa {max(2, capa_en(t_))} de 8"
        if nombre == "aereo" and t_ >= PALLETS["SIM_Pallet_1"]["t_cama"][0]:
            txt = "Las camas llevan el pallet a la estación y el centrador lo alinea (×2)"
        FRAMES.append({"t": t_, "seg": nombre, "vel": vel_, "eye": eye, "tgt": tgt, "w": w, "ley": txt})
DIAG["cuadros"] = len(FRAMES)
DIAG["segmentos"] = {s[0]: int(round((s[2] - s[1]) / s[3] * FPS)) for s in SEG_V}

if "--sin-cuadros" in sys.argv:
    print(json.dumps(DIAG, ensure_ascii=False, default=str, indent=1))
    sys.exit(0)

# ------------------------------------------------------------------ estados por cuadro (sólo cambios)
q = [0.0, 0.0, 0.0, 0.0]
prevM, prevV, prevG, prevGir = {}, {}, None, None
out_frames = []
ik_max = 0.0
for fi, fr in enumerate(FRAMES):
    M, V, gar, gir, q, e = estado(fr["t"], q)
    ik_max = max(ik_max, e)
    dM = {}
    for nm, Mx in M.items():
        c_ = comp(Mx)
        p_ = prevM.get(nm)
        if p_ is None or max(abs(a_ - b_) for a_, b_ in zip(c_, p_)) > 0.02:
            dM[nm] = c_
            prevM[nm] = c_
    dV = {nm: v for nm, v in V.items() if prevV.get(nm) != v}
    prevV.update(dV)
    rec = {"t": round(fr["t"], 3), "cam": [round(v, 1) for v in (*fr["eye"], *fr["tgt"], fr["w"])], "M": dM, "V": dV}
    if gar != prevG:
        rec["G"] = gar
        prevG = gar
    if gir != prevGir:
        rec["gir"] = gir
        prevGir = gir
    out_frames.append(rec)
DIAG["consistencia"]["ik_max_mm"] = round(ik_max, 3)

plan = {"version": 2, "fps": FPS, "objetos": OBJ, "ocultar": OCULTAR, "proxy_dinamicos": list(PROXY_DIN),
        "gripper": {"modulos": MODS, "apertura_mm": APERT0, "carrera_cierre_mm": 22.0},
        "giratoria": {"deck": GIR_DECK["n"], "eje": [X_GIR, Z_GIR], "th": [0.0, 90.0]},
        "film": {"A": [1216.0, 1016.0], "B": [1222.0, 1022.0], "espesor": 3.0, "alto": H_FILM},
        "pallet_lleno": {"pallet": PAL_F, "caja": CAJA_F,
                         "cajas_rel": [comp(mm(inv(tr(*PAL_O)), b.keys[[k[1] for k in b.keys].index("placed")][2]))
                                       for b in boxes if "placed" in [k[1] for k in b.keys]
                                       and next(c for c in robot_cycles if c.get("cajas") and b.idx in c["cajas"].values()).get("pal") == 1]},
        "cuadros": out_frames, "diag": DIAG}
OUT.write_text(json.dumps(plan, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
meta = {"leyendas": [[i, f["seg"], f["vel"], f["ley"], round(f["t"], 3)] for i, f in enumerate(FRAMES)], "diag": DIAG,
        "capas_pal1": [[c["capa"], c["kind"], round(c["t0"], 2), round(c["t1"], 2)] for c in robot_cycles if c.get("pal") == 1]}
OUT.with_name(OUT.stem + "_meta.json").write_text(json.dumps(meta, ensure_ascii=False, default=str), encoding="utf-8")
print(json.dumps(DIAG, ensure_ascii=False, default=str, indent=1))
print("bytes", OUT.stat().st_size)
