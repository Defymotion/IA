"""Planificador v6 (etapa 1, layout v7): celda A paletizando con su robot real (celda5), salida de pallets de B y C,
robot aéreo con pallets y cartones, línea nueva (cruz A, T3, cruz S-11256, T2, MP402 girada, salida) y autoelevador.
Python puro. Usa los módulos de l3n_sim5 (robot, celda, ingreso) y linea6 (flujo).
Uso: python plan6.py rel.json salida.json [--hasta T] [--sin-cuadros] [--guion] [--max-cuadros N]
"""
import copy
import json
import math
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI.parent / "l3n_sim5"))
sys.path.insert(0, str(AQUI))
from comun import Trayectoria, comp, ease, inv, lerp, mm, tr, roty  # noqa: E402
from config5 import celda_A, celda_B  # noqa: E402
from celda5 import T_CIERRE  # noqa: E402
import ingreso5 as ING  # noqa: E402
import linea6 as L  # noqa: E402

ARG = sys.argv
REL0 = json.load(open(ARG[1], encoding="utf-8"))
OUT = Path(ARG[2])
T_FIN = float(ARG[ARG.index("--hasta") + 1]) if "--hasta" in ARG else 1260.0
MAX_CUADROS = int(ARG[ARG.index("--max-cuadros") + 1]) if "--max-cuadros" in ARG else None
DT = 0.005
FPS = 30
DIAG = {"avisos": []}

# ------------------------------------------------------------------ relevamiento con la celda A v6 (mesas, pallet, barrera y reja este -300)
MOVER = [["00.Ensamblaje Mesa de Rolos Completa", -300], ["IA_Pallet_TBA250", -300], ["Barrera_", -300], ["Reja_Este_", -300],
         ["Reja_Sur_col_5", -300], ["Reja_Norte_interna_col_5", -300], ["Reja_Sur_panel_bajo_4", -150],
         ["Reja_Sur_panel_alto_4", -150], ["Reja_Norte_interna_panel_bajo_4", -150], ["Reja_Norte_interna_panel_alto_4", -150]]
REL = copy.deepcopy(REL0)
if "--sin-mover" in ARG:
    MOVER = []
for e in REL["celda_A"]:
    for pref, dx in MOVER:
        if e["n"].startswith(pref):
            if e.get("M"):
                e["M"][0][3] += dx
            if e.get("c"):
                e["c"][0] += dx
                e["c"][3] += dx
            break
DXP = 0.0 if ("--sin-mover" in ARG or "--sin-mover-pal" in ARG) else -300.0
REL["pallet_lleno"]["M_layout"][0][3] += DXP
REL["pallet_lleno"]["c"][0] += DXP
REL["pallet_lleno"]["c"][3] += DXP

# ------------------------------------------------------------------ traslados: si el plano bajo choca (reja/barrera movidas -300), por arriba
import celda5 as _C5  # noqa: E402
_tras_orig = _C5.Celda.traslado
ALTOS = {"usados": 0, "fallas": 0}


def _traslado6(self, a, b, nota="traslado", garras=()):
    n0, tras0, psi0, aj0 = self.TRAS["sin_solucion"], dict(self.TRAS), list(self.PSI_U), len(self.AJUSTES)
    out = _tras_orig(self, a, b, nota, garras)
    if self.TRAS["sin_solucion"] == n0:
        return out
    for y_alto in (1600.0, 1900.0, 2150.0, 2350.0):
        self.TRAS, self.PSI_U = dict(tras0), list(psi0)
        del self.AJUSTES[aj0:]
        a2 = (a[0], [a[1][0], max(y_alto, a[1][1]), a[1][2]])
        b2 = (b[0], [b[1][0], max(y_alto, b[1][1]), b[1][2]])
        if not (self.robot.alcanza(a2) and self.robot.alcanza(b2)):
            continue
        pas = []
        if a2[1][1] - a[1][1] > 5:
            pas.append(self._paso(a, a2, "lin", 0.0, "sube_alto"))
        pas += self.cruce(a2, b2, list(garras), nota)
        if self.TRAS["sin_solucion"] == n0:
            if b2[1][1] - b[1][1] > 5:
                pas.append(self._paso(b2, b, "lin", 0.0, "baja_alto"))
            ALTOS["usados"] += 1
            ALTOS[str(int(y_alto))] = ALTOS.get(str(int(y_alto)), 0) + 1
            return pas
    ALTOS["fallas"] += 1
    self.TRAS, self.PSI_U = dict(tras0), list(psi0)
    del self.AJUSTES[aj0:]
    return _tras_orig(self, a, b, nota, garras)


if "--sin-altos" not in ARG:
    _C5.Celda.traslado = _traslado6

A = celda_A(REL)
B_cfg = celda_B(REL)          # sólo para medidas del pallet lleno de B (y C)
A.X_CARRO = L.X_RIEL
A.Z_DEP = L.EST["A"]["z_dep"]
if abs(A.PAL_O[0] - L.EST["A"]["est"][0]) > 1 or abs(A.PAL_O[2] - L.EST["A"]["est"][2]) > 1:
    DIAG["avisos"].append(f"PAL_O A {A.PAL_O} != linea6 {L.EST['A']['est']}")
ING.preparar(A)
A.pal_n = 0
A.placed_pal = {}
A.cyc = None
CELDAS = [A]
PL = L.Planta(ext_A=True)
PAL_DE_N = {}                 # pal_n de la celda A -> id de pallet de linea6


def pal_A_actual():
    p = PL.estacion.get("A")
    if p is None or p.lleno is not None:
        return None
    if p.id not in PAL_DE_N.values():
        A.pal_n += 1
        PAL_DE_N[A.pal_n] = p.id
        A.placed_pal[A.pal_n] = 0
    return p


T_FIN_PAL = {}
SWAP_A = {}                   # id de pallet -> instante en que las cajas pasan a ser el objeto "pallet lleno"
pendientes = []
t = -70.0
k_lin = 0
while t < T_FIN:
    c = A
    if c.freno is None:
        idx = c.prog_i if (c.cyc is None or c.cyc.get("cajas") is not None) else c.prog_i - 1
        nec = sum(c.PROG[j % len(c.PROG)][0] for j in range(idx, idx + 2))
    else:
        nec = c.PROG[c.prog_i % len(c.PROG)][0]
    ING.paso_ingreso(c, t, DT, nec)
    if t >= 0:
        if k_lin % 10 == 0:
            PL.paso(t)
        k_lin += 1
    pal = pal_A_actual() if t >= 0 else None
    pn_act = A.pal_n
    if t >= 0 and c.cyc is None and pal is not None and t >= pal.listo - 2.5:
        n, toma, li = c.PROG[c.prog_i % len(c.PROG)]
        if ING.lista_para_tomar(c, n):
            cyc = c.plan_ciclo(t, toma)
            cyc["cajas"] = None
            cyc["pal"] = pn_act
            cyc["capa"] = li
            c.cyc = cyc
            c.prog_i += 1
    if c.cyc is not None:
        cyc = c.cyc
        if cyc["cajas"] is None and t >= cyc["t_contacto"]:
            n = cyc["n"]
            q = ING.cola_toma(c)
            tomadas = q[:n]
            del q[:n]
            cyc["cajas"] = {}
            ci = len(c.ciclos) - 1
            for j, b in enumerate(tomadas):
                g_ = c.pinza.n - 1 - j
                Mb = c.caja_en_cinta(c.pos[b])
                c.cajas[b].key(t, "int", c.pos[b])
                c.cajas[b].key(cyc["t_contacto"] + T_CIERRE * 0.5, "slide", (ci, g_, Mb, cyc["t_contacto"] + T_CIERRE * 0.5, cyc["t_cierra"]))
                c.cajas[b].key(cyc["t_cierra"], "held", (ci, g_))
                cyc["cajas"][g_] = b
        if cyc["cajas"] is not None:
            for (td, g_, M) in cyc["drops"]:
                b = cyc["cajas"].get(g_)
                if b is not None and t >= td and c.cajas[b].keys[-1][1] == "held":
                    c.cajas[b].key(td, "placed", M)
                    c.cajas[b].pal = cyc["pal"]
                    c.placed_pal[cyc["pal"]] += 1
        if t >= cyc["t1"]:
            c.cyc = None
            pn = cyc["pal"]
            if c.placed_pal[pn] >= c.n_cajas_pallet and pn not in T_FIN_PAL:
                T_FIN_PAL[pn] = t
                c.ir_a_casa(t)
                PL.lleno("A", t)
                SWAP_A[PAL_DE_N[pn]] = t + 0.3
                pendientes.append((t + 0.3, pn))
                c.prog_i = 0
    for ev in [p for p in pendientes if p[0] <= t]:
        pendientes.remove(ev)
        for b in c.cajas:
            if b.keys and b.keys[-1][1] == "placed":
                b.key(ev[0], "hide", None)
                c.libres.append(b.idx)
    t += DT

for b in A.cajas:
    if b.keys and b.keys[-1][1] in ("path", "int", "b2"):
        b.key(T_FIN, b.keys[-1][1], A.pos.get(b.idx, b.keys[-1][2]))
A.tray = Trayectoria([s for cy in A.ciclos for s in cy["segs"]])

PALS = PL.pallets
llenos = sorted([p for p in PALS if p.lleno is not None], key=lambda p: p.lleno)
DIAG["celda_A"] = {"T_fin_pallet": {k: round(v, 1) for k, v in T_FIN_PAL.items()}, "ciclos": len(A.ciclos), "max_cola": A.max_q,
                   "ajustes": A.AJUSTES[:10], "traslados": A.TRAS, "altos": ALTOS, "codo_abajo": A.robot.codo_abajo}
DIAG["llenos"] = [[p.id, p.celda, round(p.lleno, 1), p.t_env and round(p.t_env[0], 1), p.t_fin and round(p.t_fin, 1)] for p in llenos]
DIAG["aereo"] = [[round(a, 1), round(b, 1), s] for a, b, s in PL.aer.log]
DIAG["eventos"] = [[round(a, 1), s] for a, s in sorted(PL.eventos)]
if "--sin-cuadros" in ARG:
    print(json.dumps(DIAG, ensure_ascii=False, default=str, indent=1))
    sys.exit(0)


# ================================================================== muestreo por cuadro
def garra_eventos(c):
    ev = {g: [] for g in range(c.pinza.n)}
    for cy in c.ciclos:
        if not cy.get("cajas"):
            continue
        for g in cy["cajas"]:
            ev[g].append((cy["t_contacto"], cy["t_cierra"], 1))
        for (td, g, M) in cy["drops"]:
            if g in cy["cajas"]:
                ev[g].append((td, td + 0.25, 0))
    for g in ev:
        ev[g].sort()
    return ev


def garra_frac(evs, t):
    f = 0.0
    for (a_, b_, dst) in evs:
        if t >= b_:
            f = float(dst)
        elif t >= a_:
            u = ease((t - a_) / (b_ - a_))
            f = u if dst == 1 else 1 - u
    return f


class Cursor:
    def __init__(self, c, b):
        self.c, self.b, self.i = c, b, 0

    def estado(self, t, Gt):
        c, k = self.c, self.b.keys
        if not k or t < k[0][0]:
            return False, None
        while self.i + 1 < len(k) and k[self.i + 1][0] <= t:
            self.i += 1
        t0, fase, val = k[self.i]
        nxt = k[self.i + 1] if self.i + 1 < len(k) else None
        if fase in ("path", "int", "b2"):
            v = val
            if nxt is not None and nxt[1] == fase and nxt[0] > t0:
                v = lerp(val, nxt[2], (t - t0) / (nxt[0] - t0))
            if fase == "path":
                return True, ING.caja_en_recorrido(c, v)
            return True, c.caja_en_cinta(v)
        if fase == "kick":
            d = ING.pat_d(c, t)
            x = c.X_KICK0 + max(0.0, min(c.CARRERA, d) - c.CONTACTO)
            u = max(0.0, min(1.0, (x - c.X_KICK0) / max(1.0, c.X_PAT_FIN - c.X_KICK0)))
            M = c.caja_en_cinta(x)
            M[1][3] = lerp(c.Y_LLEGADA, c.Y_BANDA, u)
            M[2][3] = c.Z_INT
            return True, M
        if fase == "slide":
            ci, g, Mb, ts0, ts1 = val
            Mh = mm(Gt, c.pinza.LB[g])
            u = ease((t - ts0) / max(1e-6, ts1 - ts0))
            M = [r[:] for r in Mb]
            for i in range(3):
                M[i][3] = lerp(Mb[i][3], Mh[i][3], u)
            return True, M
        if fase == "held":
            return True, mm(Gt, c.pinza.LB[val[1]])
        if fase == "placed":
            return True, val
        return False, None


A.cursores = [Cursor(A, b) for b in A.cajas]
A.G_EV = garra_eventos(A)

# ------------------------------------------------------------------ geometría de los equipos de la escena
aereo = {e["n"]: e for e in REL["aereo"]}
PAL_F = aereo["Pila1_pallet_10"]["f"]
mp = {e["n"]: e for e in REL["mp402"]["hijos"]}
M_MP_VIEJA = REL["mp402"]["M_layout"]
M_MP_NUEVA = [[0, 1, 0, 10627.7], [0, 0, 1, 0.0], [1, 0, 0, -32863.6], [0, 0, 0, 1]]      # plan_liviano_v7 "archivos"
REL_MP = mm(M_MP_NUEVA, inv(M_MP_VIEJA))
M_ROTOR = mm(REL_MP, mp["MP402_Rotor:1"]["M"])
M_CARRO_MP = mm(REL_MP, mp["MP402_Carro:1"]["M"])
_ej = [9865.8363, 0.0, -35615.1739]
_ej2 = [sum(REL_MP[i][k] * _ej[k] for k in range(3)) + REL_MP[i][3] for i in range(3)]
ROTOR_EJE = (_ej2[0], _ej2[2])
Y_CARRO_TOPE = mp["MP402_Carro:1"]["c"][4]
N_FILM, H_FILM, N_VUELTAS = 8, 200.0, 6.0
H_CARGA = {"A": A.H_CARGA, "B": B_cfg.H_CARGA, "C": B_cfg.H_CARGA}
TIPO = {"A": "A", "B": "B", "C": "B"}        # la celda C usa el pallet lleno de B (mismo formato de salida)


def env_de(t):
    """(ángulo, subida del carro, bandas, pid) del envuelto en curso o el último."""
    act = None
    for (w0, w1, pid) in PL.envueltos:
        if t >= w0:
            act = (w0, w1, pid)
    if act is None:
        return 0.0, 0.0, 0, None
    w0, w1, pid = act
    u = min(1.0, (t - w0) / (w1 - w0))
    ta = 0.1
    if u < ta:
        f = 0.5 * u * u / ta
    elif u < 1 - ta:
        f = 0.5 * ta + (u - ta)
    else:
        f = 1 - ta - 0.5 * (1 - u) ** 2 / ta
    f /= (1 - ta)
    p = PALS[pid]
    dy_max = (L.ZONAS["Env"][2] + H_CARGA[p.celda] + 30.0) - Y_CARRO_TOPE
    h = ease(u / 0.5) if u < 0.5 else (1.0 if u < 0.58 else 1.0 - ease((u - 0.58) / 0.42))
    nb = sum(1 for k in range(N_FILM) if u >= 0.03 + 0.45 * (k + 0.5) / N_FILM)
    return -360.0 * N_VUELTAS * f, dy_max * h, nb, pid


def film_rel(cel, k):
    hc = H_CARGA[cel]
    yk = 20.0 + k * (hc - 40.0 - H_FILM) / (N_FILM - 1) + H_FILM / 2
    return [[1, 0, 0, 0], [0, 0, 1, yk], [0, -1, 0, 0], [0, 0, 0, 1]]


def pose_pal(p, t):
    r = PL.pallet_pose(p, t)
    if r is None:
        return None
    x, y, z, ang, vis, en_aer = r
    M = tr(x, y, z)
    return mm(M, roty(ang)) if abs(ang) > 1e-6 else M


# ------------------------------------------------------------------ objetos de la escena
OBJ = {}


def obj(nombre, archivo, M, vis=True, rol=""):
    OBJ[nombre] = {"f": archivo, "M": comp(M), "vis": vis, "rol": rol}


def pool(intervalos):
    """Asigna intervalos (a, b, clave) a ranuras sin solaparse -> {clave: ranura}, n ranuras."""
    fin, asig = [], {}
    for a_, b_, k in sorted(intervalos):
        for i, f in enumerate(fin):
            if f < a_ - 0.5:
                fin[i] = b_
                asig[k] = i
                break
        else:
            fin.append(b_)
            asig[k] = len(fin) - 1
    return asig, len(fin)


CELDA_P = "Celda_A_L3N:1/"
AEREO_P = "Robot_Aereo_Pallets:1/"
celA = {e["n"]: e for e in REL["celda_A"]}
PAT_PIEZAS = ["chapa pateador:2", "chapa refuerzo:1", "soporte a piston:1", "soporte a piston:2", "eje cromado 500:1",
              "eje cromado 500:2", "SHF16:1", "SHF16:2"]
CAJA_F = celA["IA_Caja_en_cinta"]["f"]
OCULTAR = []
P0 = A.robot.poses([0, 0, 0, 0])
for k_ in ("V02", "V03", "V04", "V05"):
    obj(f"SIM_A_{k_}", REL["robot_ia"][f"IA_Robot_{k_}"]["f"], P0[k_], rol="robot")
obj("SIM_A_Gripper", "GRIPPER_A_SIM", P0["gripper"], rol="gripper")
for i in range(A.N_POOL):
    obj(f"SIM_A_Caja_{i:03d}", CAJA_F, ING.caja_en_recorrido(A, 0.0), vis=False, rol="caja")
for n_ in PAT_PIEZAS:
    e = celA.get("Ensamble pateador adeco:1/" + n_)
    if e:
        obj("SIM_A_Pat_" + n_.replace(" ", "_").replace(":", "_"), e["f"], e["M"], rol="pateador")
        OCULTAR.append(CELDA_P + "Ensamble pateador adeco:1/" + n_)
# pallets vacíos: uno por pallet de linea6 que aparece en la ventana
for p in PALS:
    M0 = pose_pal(p, 0.0) or tr(L.X_RIEL, 0, -33000)
    obj(f"SIM_Pal_{p.id:03d}", PAL_F, M0, vis=False, rol="pallet")
# pallets llenos (piezas simplificadas) y films, en ranuras reutilizables
INT_LL, INT_FILM = {"A": [], "B": []}, {"A": [], "B": []}
for p in llenos:
    tp = TIPO[p.celda]
    t_ap = SWAP_A.get(p.id, p.lleno) if p.celda == "A" else p.lleno
    INT_LL[tp].append((t_ap, p.t_fin or 1e9, p.id))
    if p.t_env:
        INT_FILM[tp].append((p.t_env[0], p.t_fin or 1e9, p.id))
RAN_LL, RAN_FILM = {}, {}
for tp in ("A", "B"):
    asig, n = pool(INT_LL[tp])
    RAN_LL.update({pid: f"SIM_Lleno_{tp}_{i}" for pid, i in asig.items()})
    for i in range(n):
        obj(f"SIM_Lleno_{tp}_{i}", f"PALLET_LLENO_{tp}", tr(0, -5000, -40000), vis=False, rol="pallet_lleno")
    asig, n = pool(INT_FILM[tp])
    RAN_FILM.update({pid: f"SIM_Film_{tp}_{i}" for pid, i in asig.items()})
    for i in range(n):
        for k in range(N_FILM):
            obj(f"SIM_Film_{tp}_{i}_{k}", "FILM_A" if tp == "A" else "FILM_B", tr(0, -5000, -40000), vis=False, rol="film")
# cartones
CARTONES = {}
for c_ in PL.aer.cartones:
    CARTONES[c_["id"]] = c_
for p in PALS:
    if p.carton is not None and p.carton not in CARTONES:
        CARTONES[p.carton] = {"id": p.carton, "t_toma": -1e9, "t_deja": -1e9, "pallet": p.id}
for cid in CARTONES:
    obj(f"SIM_Carton_{cid + 1000:04d}", "CARTON_SIM", tr(0, -5000, -40000), vis=False, rol="carton")
# robot aéreo
for n_, nn in (("Carro", "SIM_Aereo_Carro"), ("Torre_elevacion", "SIM_Aereo_Torre"), ("Sujecion_pallet", "SIM_Aereo_Sujecion")):
    obj(nn, aereo[n_]["f"], aereo[n_]["M"], rol="aereo")
for j in range(3):
    obj(f"SIM_Aereo_Barra_{j}", aereo["Barra_elevacion"]["f"], aereo["Barra_elevacion"]["M"], rol="aereo")
# giratorias B (existente) y C (copia de la de B)
GIR = {}
girB = [e for e in REL["celda_B"] if e["n"].startswith("roller conveyor - rotating:1/")]
girB_base = next(e for e in REL["celda_B"] if e["n"] == "roller conveyor - rotating:1")
DXC, DZC = L.ZONAS["GirC"][0] - L.ZONAS["GirB"][0], L.ZONAS["GirC"][1] - L.ZONAS["GirB"][1]
if girB:
    GB = girB[0]
    obj("SIM_B_Gir_Deck", GB["f"], GB["M"], rol="giratoria")
    OCULTAR.append("Celda_B_existente:1/" + GB["n"])
    GIR["SIM_B_Gir_Deck"] = ("GirB", L.ZONAS["GirB"][0:2])
    obj("SIM_C_Gir_Base", girB_base["f"], mm(tr(DXC, 0, DZC), girB_base["M"]), rol="giratoria_base")
    obj("SIM_C_Gir_Deck", GB["f"], mm(tr(DXC, 0, DZC), GB["M"]), rol="giratoria")
    GIR["SIM_C_Gir_Deck"] = ("GirC", L.ZONAS["GirC"][0:2])
OCULTAR_EN_OBJ = {"SIM_C_Gir_Base": [GB["n"].split("/", 1)[1]]} if girB else {}
# robots de las celdas B y C (no se mueven): en una pose de reposo armada sobre su pallet, con el gripper en la brida.
# En el CAD de las celdas existentes el KUKA y el gripper quedan desarmados (subensambles flexibles): se ocultan.
from robot import Robot  # noqa: E402
from config5 import _links, VEL_B  # noqa: E402
from comun import yaw_of  # noqa: E402
RBC = {}
_rbc = Path(ARG[ARG.index("--robots-bc") + 1]) if "--robots-bc" in ARG else AQUI / "robots_bc.json"
if _rbc.exists():
    RBC = json.load(open(_rbc, encoding="utf-8"))
KB = REL["kuka_B"]
GBF = REL["gripper_B"]
DCEL = {"B": (0.0, 0.0), "C": (L.EST["C"]["est"][0] - L.EST["B"]["est"][0], L.EST["C"]["est"][2] - L.EST["B"]["est"][2])}
for cel, top in (("B", "Celda_B_existente"), ("C", "Celda_C_existente")):
    info = next((v for k, v in RBC.items() if k.startswith(top)), None)
    kuka = next((r for r in (info or {}).get("robots", []) if r["n"].upper().startswith("KUKA")), None)
    grip = next((r for r in (info or {}).get("robots", []) if r["n"].upper().startswith("GRIPPER")), None)
    if kuka:
        T = kuka["M"] + [[0, 0, 0, 1]]
        kname = kuka["n"]
        links_n = [h["n"] for h in kuka["hijos"]]
    else:
        T = mm(tr(DCEL[cel][0], 0, DCEL[cel][1]), KB["M_layout"])
        kname = KB["n"]
        links_n = list(KB["links"])
        DIAG["avisos"].append(f"robot {cel}: sin relevamiento, uso el de B corrido")
    rob = Robot(cel, T, _links(KB), (877.5, -438.8, 52.0), [[1, 0, 0], [0, 1, 0], [0, 0, 1]], VEL_B, B_cfg.robot.GL if hasattr(B_cfg.robot, "GL") else None)
    pal = L.EST[cel]["est"]
    q0 = [0.0, -40.0, 90.0, 0.0]
    psi0 = yaw_of(rob.poses(q0)["gripper"])
    GLb = GBF["caja_local"]                 # caja del gripper en sus coordenadas: se centra sobre el pallet, 250 mm arriba
    obj_ = [pal[0], pal[1] + 152.0 + H_CARGA[cel] + 1100.0, pal[2]]
    for _it in range(4):
        q, e = rob.q_para(rob.gripper_pose(psi0, obj_), q0)
        Mg = rob.poses(q)["gripper"]
        esq = [[sum(Mg[i][k] * c[k] for k in range(3)) + Mg[i][3] for i in range(3)]
               for c in [[x, y, z] for x in (GLb[0], GLb[3]) for y in (GLb[1], GLb[4]) for z in (GLb[2], GLb[5])]]
        cx = sum(p_[0] for p_ in esq) / 8
        cz = sum(p_[2] for p_ in esq) / 8
        ymin = min(p_[1] for p_ in esq)
        obj_ = [obj_[0] + pal[0] - cx, obj_[1] + (pal[1] + 152.0 + H_CARGA[cel] + 250.0) - ymin, obj_[2] + pal[2] - cz]
    q, e = rob.q_para(rob.gripper_pose(psi0, obj_), q0)
    if e > 1.0:
        q = q0
        DIAG["avisos"].append(f"robot {cel}: no llego al reposo sobre el pallet (error {e:.1f}), uso q0")
    P = rob.poses(q)
    DIAG.setdefault("robots_reposo", {})[cel] = {"q": [round(v, 1) for v in q], "gripper": [round(P["gripper"][i][3]) for i in range(3)]}
    for n_, v in KB["links"].items():
        k_ = "V0" + n_.split("_V0")[-1][:1]
        if k_ in ("V02", "V03", "V04", "V05"):
            obj(f"SIM_{cel}_{k_}", v["f"], P[k_], rol="robot_fijo")
    for n_ in links_n:
        if any(f"_V0{k}" in n_ for k in (2, 3, 4, 5)):
            OCULTAR.append(f"{top}:1/{kname}/{n_}")
    obj(f"SIM_{cel}_Gripper", GBF["f"], P["gripper"], rol="gripper_fijo")
    OCULTAR_EN_OBJ[f"SIM_{cel}_Gripper"] = ["Bandeja*"]
    OCULTAR.append(f"{top}:1/{grip['n'] if grip else 'Gripper_ADECO2_V1:1'}")
# envolvedora
obj("SIM_MP402_Rotor", mp["MP402_Rotor:1"]["f"], M_ROTOR, rol="envolvedora")
obj("SIM_MP402_Carro", mp["MP402_Carro:1"]["f"], M_CARRO_MP, rol="envolvedora")
OCULTAR += ["Envolvedora_MP402:1/MP402_Rotor:1", "Envolvedora_MP402:1/MP402_Carro:1"]
OCULTAR += [CELDA_P + n_ for n_ in ("IA_Robot_V02", "IA_Robot_V03", "IA_Robot_V04", "IA_Robot_V05", "IA_Gripper_7xTBA250",
                                    "IA_Pallet_TBA250", "IA_Caja_en_cinta", "KUKA-KR_140_R3200_2_PA-ASM:1",
                                    "chapa tope derecha:1", "soporte bandejas:14", "soporte bandejas:15", "Empujador 01:1",
                                    "roller conveyor - rotating:1", "Ensamble pateador adeco:1/chapa nueva 2:2")]
OCULTAR += ["Celda_B_existente:1/Pallet_Completo:2", "Celda_C_existente:1/Pallet_Completo:2"]
OCULTAR += ["Linea_Pallets:1/MP402:1", "Linea_Pallets:1/roller conveyor - rotating:2", "Linea_Pallets:1/Pasarela:1"]
OCULTAR += [AEREO_P + n_ for n_ in ("Carro", "Torre_elevacion", "Barra_elevacion", "Sujecion_pallet", "Pallet_en_sujecion")]
OCULTAR += [AEREO_P + f"Pila{k}_pallet_{j}" for k in (1, 2) for j in range(1, 11)]
_oc = AQUI.parent / "l3n_sim5" / "ocultos_celdas.json"
if _oc.exists():
    for k_, lst in json.load(open(_oc, encoding="utf-8")).items():
        if k_.startswith("Celda_A"):
            OCULTAR += [k_ + "/" + n_ for n_ in lst if k_ + "/" + n_ not in OCULTAR]
M_PROX = {n_: aereo[n_]["M"] for n_ in ("Carro", "Torre_elevacion", "Barra_elevacion", "Sujecion_pallet")}
Z_CARRO0 = aereo["Carro"]["M"][2][3]
MODOS_GIR = ["Z", "X"]        # th = 0 en el CAD (rodillos en Z), 90 hacia la celda


def estado(t, qs):
    M, V, G = {}, {}, {}
    psi, org = A.tray.pose(t)
    q, e = A.robot.q_para(A.robot.gripper_pose(psi, org), qs["A"])
    qs["A"] = q
    P = A.robot.poses(q)
    for k_ in ("V02", "V03", "V04", "V05"):
        M[f"SIM_A_{k_}"] = P[k_]
    Gt = P["gripper"]
    M["SIM_A_Gripper"] = Gt
    for cur in A.cursores:
        v, Mb = cur.estado(t, Gt)
        nm = f"SIM_A_Caja_{cur.b.idx:03d}"
        V[nm] = v
        if Mb is not None:
            M[nm] = Mb
    d = ING.pat_d(A, t)
    for n_ in PAT_PIEZAS:
        key = "SIM_A_Pat_" + n_.replace(" ", "_").replace(":", "_")
        if key in OBJ:
            M[key] = mm(tr(d, 0, 0), celA["Ensamble pateador adeco:1/" + n_]["M"])
    G["SIM_A_Gripper"] = [round(garra_frac(A.G_EV[g], t), 3) for g in range(A.pinza.n)]
    # pallets
    usados_ll, usados_film = set(), set()
    for p in PALS:
        Mp = pose_pal(p, t)
        nm = f"SIM_Pal_{p.id:03d}"
        t_ll = (SWAP_A.get(p.id, 1e9) if p.celda == "A" else p.lleno) if p.lleno is not None else None
        lleno = t_ll is not None and t >= t_ll
        V[nm] = Mp is not None and not lleno
        if Mp is not None:
            M[nm] = Mp
        if lleno and Mp is not None and p.id in RAN_LL:
            rl = RAN_LL[p.id]
            M[rl] = Mp
            V[rl] = True
            usados_ll.add(rl)
            if p.t_env and t >= p.t_env[0] and p.id in RAN_FILM:
                rf = RAN_FILM[p.id]
                usados_film.add(rf)
                _, _, nb, pid_env = env_de(t)
                for k in range(N_FILM):
                    M[f"{rf}_{k}"] = mm(Mp, film_rel(p.celda, k))
                    V[f"{rf}_{k}"] = (k < nb) if (pid_env == p.id and t < p.t_env[1]) else True
    for nm, ob in OBJ.items():
        if ob["rol"] == "pallet_lleno" and nm not in usados_ll:
            V[nm] = False
        if ob["rol"] == "film" and nm.rsplit("_", 1)[0] not in usados_film:
            V[nm] = False
    # cartones
    for cid, c_ in CARTONES.items():
        nm = f"SIM_Carton_{cid + 1000:04d}"
        p = PALS[c_["pallet"]]
        oculto = p.lleno is not None and t >= ((SWAP_A.get(p.id, p.lleno) if p.celda == "A" else p.lleno) - 0.05)
        r = PL.carton_pose(c_, t) if cid >= 0 or True else None
        if t < c_["t_toma"] or oculto or r is None:
            V[nm] = False
            continue
        Mp = pose_pal(p, t) if t >= c_["t_deja"] else None
        if Mp is not None:
            M[nm] = mm(Mp, tr(0, 152.0, 0))
        else:
            M[nm] = tr(r[0], r[1], r[2])
        V[nm] = True
    # robot aéreo
    z, dy = PL.aer.val("z", t), PL.aer.val("dy", t)
    T_z = tr(0, 0, z - Z_CARRO0)
    M["SIM_Aereo_Carro"] = mm(T_z, M_PROX["Carro"])
    M["SIM_Aereo_Torre"] = mm(T_z, M_PROX["Torre_elevacion"])
    M["SIM_Aereo_Sujecion"] = mm(tr(0, dy, z - Z_CARRO0), M_PROX["Sujecion_pallet"])
    for j in range(3):
        M[f"SIM_Aereo_Barra_{j}"] = mm(tr(0, dy * j / 2.0, z - Z_CARRO0), M_PROX["Barra_elevacion"])
    ang, dyc, nb, pid = env_de(t)
    R_ = roty(ang, ROTOR_EJE[0], ROTOR_EJE[1])
    M["SIM_MP402_Rotor"] = mm(R_, M_ROTOR)
    M["SIM_MP402_Carro"] = mm(R_, mm(tr(0, dyc, 0), M_CARRO_MP))
    gir = {nm: round(PL.dev[dn].frac(t, MODOS_GIR), 4) for nm, (dn, _) in GIR.items()}
    return M, V, G, gir


# ================================================================== guion del video
EV = {}
for p in llenos:
    EV.setdefault(p.celda, []).append(p)
C1, B1, A1 = EV["C"][0], EV["B"][0], EV["A"][0]
T_A1 = SWAP_A[A1.id] - 0.3
viaje_C1 = next(x for x in PL.aer.log if "celda C" in x[2])
viaje_A1 = next(x for x in PL.aer.log if "celda A" in x[2] and x[0] >= T_A1 - 1)
c0 = PL.aer.log[0]
PA = A.PAL_O
CA = [PA[0], PA[1] + 152.0 + 75.0, PA[2] + A.capas[0]["tomas"][0]["cajas"][0][1][2]]
retiro1 = PL.av["retiros"][0][0]
GEN = ((26000, 34000, -12000), (-1500, 0, -42000), 46000)


def seg(nombre, t0, t1, vel, keys, ley):
    return (nombre, t0, max(t1, t0 + 0.5), vel, keys, ley)


def fija(eye, tgt, w):
    return [(0.0, eye, tgt, w)]


SEG_V = [
    seg("general", -5.0, 0.0, 1.0, [(0.0, *GEN), (1.0, (9000, 17000, -20000), (-6500, 0, -40000), 26000)],
        "Planta L3N · etapa 1: celda A nueva paletizando, salidas de B y C, robot aéreo, línea nueva, MP402 y salida"),
    seg("celda_A", 0.0, 14.0, 1.0, [(0.0, (-4600, 4300, -32300), (CA[0], CA[1], CA[2] - 250), 4600),
                                    (1.0, (-4000, 5200, -31500), (PA[0], PA[1] + 500, PA[2]), 6200)],
        "Celda A en régimen: 1 caja cada 2,5 s · el robot paletiza sobre el pallet con cartón"),
    seg("carton", 14.0, c0[1] + 1.0, 3.0, ("aereo",),
        "Robot aéreo libre: va al buffer de cartones, toma una hoja y la deja sobre el pallet de arriba del buffer 1 (×3)"),
    seg("espera", c0[1] + 1.0, C1.lleno - 2.0, 6.0, [(0.0, (9000, 17000, -20000), (-6500, 0, -40000), 26000),
                                                     (1.0, (6000, 15000, -30000), (-7500, 0, -45000), 22000)],
        "La celda A paletiza; las celdas B y C sólo se simulan como salida de pallets (B cada ~9 min, C cada ~5 min) (×6)"),
    seg("salida_C", C1.lleno - 2.0, viaje_C1[1] + 2.0, 2.0, [(0.0, (-1500, 7000, -44500), (-8200, 600, -50500), 9500),
                                                             (1.0, (-1500, 7500, -44000), (-8500, 600, -49500), 11000)],
        "Celda C: pallet completo → giratoria C → camas · el robot aéreo le repone un pallet vacío con cartón (×2)"),
    seg("camas", viaje_C1[1] + 2.0, C1.t_env[0] - 2.0, 6.0, ("seguir", C1.id),
        "Camas en Z → cruz A (rodillos arriba) → T3 sobre cadenas → cruz S-11256 → T2 (×6)"),
    seg("envuelto", C1.t_env[0] - 2.0, C1.t_env[1] + 6.0, 3.0, [(0.0, (16500, 5200, -27500), (L.X_T2, 1250, -32880), 7600),
                                                                (1.0, (15000, 5600, -26800), (L.X_T2, 1250, -32500), 8200)],
        "MP402 girada 90° sobre la T2 S-11259: envuelve con la T2 anterior y la salida 1 vacías (barrido del brazo) (×3)"),
    seg("a_salida", C1.t_env[1] + 6.0, T_A1 - 3.0, 6.0, [(0.0, (15000, 5600, -26800), (L.X_T2, 1250, -32500), 8200),
                                                         (0.4, (14000, 9000, -24000), (8000, 600, -33000), 15000),
                                                         (1.0, (2000, 6500, -29500), (-7000, 800, -35800), 11000)],
        "Salida S-11219 → S-11226: el autoelevador retira el pallet envuelto (en el video desaparece) (×6)"),
    seg("cambio_A", T_A1 - 3.0, viaje_A1[1] + 2.0, 1.5, [(0.0, (-2600, 5200, -30600), (-7600, 700, -35700), 8600),
                                                          (1.0, (-2200, 5600, -30000), (-8300, 700, -35000), 9800)],
        "Pallet A completo: sale por la cruz A y entra el que esperaba en la cama de ingreso; el robot aéreo trae el siguiente (×1,5)"),
    seg("A_linea", viaje_A1[1] + 2.0, A1.t_env[0] - 2.0, 6.0, ("seguir", A1.id),
        "El pallet de la celda A se suma a la T3 detrás de los de B y C (×6)"),
    seg("final", A1.t_env[0] - 2.0, T_FIN - 5.0, 16.0, [(0.0, (12000, 18000, -20000), (0, 0, -38000), 30000),
                                                        (0.3, (*GEN[0],), GEN[1], GEN[2]),
                                                        (1.0, (*GEN[0],), GEN[1], GEN[2])],
        "Régimen de la etapa 1: ~30 pallets/h entre A, B y C; la línea y el robot aéreo acompañan sin frenar a las celdas (×16)"),
]


def cam_en(sg, t):
    nombre, t0, t1, vel_, keys, _ = sg
    if isinstance(keys, tuple):
        if keys[0] == "seguir":
            r = PL.pallet_pose(PALS[keys[1]], t)
            x, z = (r[0], r[2]) if r else (0.0, -36000.0)
            return (x + 3500.0, 4800.0, z + 5200.0), (x + 300.0, 900.0, z), 9000.0
        z = PL.aer.val("z", t)
        return (-1500.0, 8000.0, z + 7000.0), (-10582.0, 900.0, z), 12000.0
    u = (t - t0) / (t1 - t0)
    if u <= keys[0][0]:
        return keys[0][1:]
    for a_, b_ in zip(keys, keys[1:]):
        if u <= b_[0]:
            w = ease((u - a_[0]) / (b_[0] - a_[0]))
            return (tuple(lerp(a_[1][i], b_[1][i], w) for i in range(3)), tuple(lerp(a_[2][i], b_[2][i], w) for i in range(3)),
                    lerp(a_[3], b_[3], w))
    return keys[-1][1:]


FRAMES = []
for sg in SEG_V:
    nombre, t0, t1, vel_, keys, ley = sg
    nf = int(round((t1 - t0) / vel_ * FPS))
    for i in range(nf):
        t_ = t0 + i * vel_ / FPS
        eye, tgt, w = cam_en(sg, t_)
        FRAMES.append({"t": t_, "seg": nombre, "vel": vel_, "eye": eye, "tgt": tgt, "w": w, "ley": ley})
DIAG["cuadros"] = len(FRAMES)
DIAG["segmentos"] = {s[0]: [int(round((s[2] - s[1]) / s[3] * FPS)), round(s[1], 1), round(s[2], 1), s[3]] for s in SEG_V}
if "--guion" in ARG:
    print(json.dumps(DIAG["segmentos"], indent=1), len(FRAMES), "cuadros =", round(len(FRAMES) / FPS, 1), "s")
    sys.exit(0)
if MAX_CUADROS:
    paso_ = max(1, len(FRAMES) // MAX_CUADROS)
    FRAMES = FRAMES[::paso_][:MAX_CUADROS]

# ------------------------------------------------------------------ estados por cuadro (sólo cambios)
qs = {"A": [0.0, -40.0, 90.0, 0.0]}
prevM, prevV, prevG, prevGir = {}, {}, {}, {}
out_frames = []
for fi, fr in enumerate(FRAMES):
    M, V, G, gir = estado(fr["t"], qs)
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
    dG = {k: v for k, v in G.items() if prevG.get(k) != v}
    if dG:
        rec["G"] = dG
        prevG.update(dG)
    dgir = {k: v for k, v in gir.items() if prevGir.get(k) != v}
    if dgir:
        rec["gir"] = dgir
        prevGir.update(dgir)
    out_frames.append(rec)


def cajas_rel_A():
    out = []
    for b in A.cajas:
        ks = [k for k in b.keys if k[1] == "placed"]
        if ks:
            out.append(comp(mm(inv(tr(*A.PAL_O)), ks[0][2])))
        if len(out) >= A.n_cajas_pallet:
            break
    return out


plan = {"version": 6, "fps": FPS, "objetos": OBJ, "ocultar": OCULTAR, "ocultar_en_objeto": OCULTAR_EN_OBJ, "proxy_dinamicos": [],
        "grippers": {"SIM_A_Gripper": {"tipo": "restriccion", "f": REL["gripper"]["f"], "n": A.pinza.n, "cierre_mm": A.pinza.cierre,
                                       "modulos": sorted(REL["gripper"]["modulos"], key=lambda s_: int(s_.split(":")[-1]))}},
        "giratorias": {nm: {"eje": list(eje), "th": [0.0, 90.0]} for nm, (dn, eje) in GIR.items()},
        "film": {"A": [1216.0, 1016.0], "B": [1222.0, 1022.0], "espesor": 3.0, "alto": H_FILM},
        "carton": {"L": 1180.0, "W": 980.0, "E": L.E_CARTON},
        "pallets_llenos": {"A": {"cajas_rel_n": len(cajas_rel_A())}},
        "cuadros": out_frames, "diag": DIAG}
OUT.write_text(json.dumps(plan, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
meta = {"leyendas": [[i, f["seg"], f["vel"], f["ley"], round(f["t"], 3)] for i, f in enumerate(FRAMES)], "diag": DIAG}
OUT.with_name(OUT.stem + "_meta.json").write_text(json.dumps(meta, ensure_ascii=False, default=str), encoding="utf-8")
print(json.dumps({k: v for k, v in DIAG.items() if k in ("cuadros", "segmentos", "avisos")}, ensure_ascii=False, default=str, indent=1))
print("bytes", OUT.stat().st_size)
