"""Planificador v5 de la planta L3N (celdas A y B, robot aéreo, línea y MP402 compartidos). Python puro.
Uso: python plan5.py rel.json salida.json [--hasta T] [--sin-cuadros] [--capacidad-robot] [--capacidad-planta T]
"""
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from comun import (Trayectoria, box_M, comp, ease, ease5, inv, lerp, mm, tr, roty, apply)  # noqa: E402
from config5 import celda_A, celda_B  # noqa: E402
from celda5 import T_CIERRE  # noqa: E402
import ingreso5 as ING  # noqa: E402
from linea5 import Aereo, Giratoria, Linea, Y_LINEA, Y_MP, giro_pallet  # noqa: E402

REL = json.load(open(sys.argv[1], encoding="utf-8"))
OUT = Path(sys.argv[2])
ARG = sys.argv
T_FIN = float(ARG[ARG.index("--hasta") + 1]) if "--hasta" in ARG else 640.0
CAP_ROBOT = "--capacidad-robot" in ARG
CAP_PLANTA = float(ARG[ARG.index("--capacidad-planta") + 1]) if "--capacidad-planta" in ARG else None
if CAP_PLANTA:
    T_FIN = CAP_PLANTA
DT = 0.005
FPS = 30
DIAG = {"avisos": []}

A = celda_A(REL)
B = celda_B(REL)
CELDAS = [A, B]
for c in CELDAS:
    ING.preparar(c)
    c.pal_n = 0
    c.pal_actual = None
    c.placed_pal = {}
    c.cyc = None
aereo = {e["n"]: e for e in REL["aereo"]}
AER = Aereo(aereo)
gA = Giratoria("A", A.gir["X"], A.gir["Z"], modo0=0)
gB = Giratoria("B", B.gir["X"], B.gir["Z"], modo0=1)
LIN = Linea(gA, gB, z_x=A.PAL_O[2])
PALLETS = []


def pedir_pallet(c, t):
    s = AER.suministro(t, c.Z_DEP, c.PAL_O[1])
    d = c.PAL_O[0] - c.X_CARRO
    t_c0 = s["t_suelta"] + 0.5
    t_c1 = t_c0 + d / c.V_CAMA * 1.25
    t_cz1 = t_c1 + 0.8
    c.pal_n += 1
    pal = {"celda": c.n, "n": c.pal_n, "nombre": f"SIM_{c.n}_Pallet_{c.pal_n}", "pila": s["pila"], "t_agarra": s["t_agarra"],
           "t_suelta": s["t_suelta"], "t_cama": (t_c0, t_c1), "t_centra": (t_c1 + 0.1, t_cz1), "listo": t_cz1,
           "z_dep": c.Z_DEP, "x_carro": c.X_CARRO, "PAL_O": list(c.PAL_O), "swap": None, "salida": None}
    PALLETS.append(pal)
    c.pal_actual = pal
    c.placed_pal[c.pal_n] = 0
    return pal


if CAP_ROBOT:
    # cajas siempre disponibles en la toma y pallet siempre listo: mide sólo el robot
    for c in CELDAS:
        c.src_t0 = -1e9
        c.PASO_FUENTE = 0.05
        c.V_BANDA = 2000.0
        if c.freno:
            c.freno["v2"] = 2000.0
pedir_pallet(A, 0.6)
pedir_pallet(B, 0.6)

pendientes = []          # (t, función)
t = -70.0
while t < T_FIN:
    for c in CELDAS:
        # dosificación del pateador: cajas de la toma pendiente y la siguiente (A)
        if c.freno is None:
            idx = c.prog_i if (c.cyc is None or c.cyc.get("cajas") is not None) else c.prog_i - 1
            nec = sum(c.PROG[j % len(c.PROG)][0] for j in range(idx, idx + 2))
        else:
            nec = c.PROG[c.prog_i % len(c.PROG)][0]
        ING.paso_ingreso(c, t, DT, nec)
        pal = c.pal_actual
        if t >= 0 and c.cyc is None and pal is not None and t >= pal["listo"] - 2.5 and pal["salida"] is None:
            n, toma, li = c.PROG[c.prog_i % len(c.PROG)]
            if ING.lista_para_tomar(c, n):
                cyc = c.plan_ciclo(t, toma)
                cyc["cajas"] = None
                cyc["pal"] = pal["n"]
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
                fase = "int" if c.freno is None else "b2"
                for j, b in enumerate(tomadas):
                    g_ = c.pinza.n - 1 - j
                    Mb = c.caja_en_cinta(c.pos[b])
                    c.cajas[b].key(t, fase, c.pos[b])
                    c.cajas[b].key(cyc["t_contacto"] + T_CIERRE * 0.5, "slide", (ci, g_, Mb, cyc["t_contacto"] + T_CIERRE * 0.5, cyc["t_cierra"]))
                    c.cajas[b].key(cyc["t_cierra"], "held", (ci, g_))
                    cyc["cajas"][g_] = b
            if cyc["cajas"] is not None:
                for (td, g_, M) in cyc["drops"]:
                    b = cyc["cajas"].get(g_)
                    if b is not None and t >= td and c.cajas[b].keys[-1][1] == "held":
                        c.cajas[b].key(td, "placed", M)
                        c.placed_pal[cyc["pal"]] += 1
            if t >= cyc["t1"]:
                c.cyc = None
                pn = cyc["pal"]
                if c.placed_pal[pn] >= c.n_cajas_pallet and pal["salida"] is None:
                    c.T_FIN_PAL[pn] = t
                    c.ir_a_casa(t)
                    if CAP_ROBOT:
                        pal["salida"] = {"T_estacion_libre": t}
                        c.prog_i = 0
                        pedir_pallet(c, t)
                        c.pal_actual["listo"] = t + 0.1
                        continue
                    info = LIN.salida(pal["nombre"], c.n, t, c.PAL_O, None)
                    pal["salida"] = info
                    pal["swap"] = t + 0.3
                    pendientes.append((pal["swap"], ("swap", c, pn)))
                    pendientes.append((info["T_estacion_libre"] + 0.3, ("pedir", c, None)))
                    c.prog_i = 0
    for ev in [p for p in pendientes if p[0] <= t]:
        pendientes.remove(ev)
        tipo, c, pn = ev[1]
        if tipo == "swap":
            for b in c.cajas:
                if b.keys and b.keys[-1][1] == "placed":
                    b.key(ev[0], "hide", None)
                    c.libres.append(b.idx)
        elif tipo == "pedir":
            pedir_pallet(c, ev[0])
    t += DT

for c in CELDAS:
    for b in c.cajas:
        if b.keys and b.keys[-1][1] in ("path", "int", "b2"):
            b.key(T_FIN, b.keys[-1][1], c.pos.get(b.idx, b.keys[-1][2]))
    c.tray = Trayectoria([s for cy in c.ciclos for s in cy["segs"]])

DIAG["celdas"] = {}
for c in CELDAS:
    capas_t = {}
    for cy in c.ciclos:
        if cy.get("pal") == 1 and cy["tipo"] != "casa":
            capas_t.setdefault(cy["capa"], [cy["t0"], cy["t1"]])
            capas_t[cy["capa"]][1] = cy["t1"]
    DIAG["celdas"][c.n] = {"T_fin_pallet": {k: round(v, 2) for k, v in c.T_FIN_PAL.items()}, "ciclos": len(c.ciclos),
                           "cajas_generadas": c.src_i, "max_cola": c.max_q, "ajustes": c.AJUSTES[:10],
                           "traslados": c.TRAS, "codo_abajo": c.robot.codo_abajo,
                           "capas_pallet1": {k: [round(v[0], 1), round(v[1], 1)] for k, v in sorted(capas_t.items())},
                           "palas": c.PALA_LOG[:8]}
DIAG["pallets"] = [{k: (round(v, 2) if isinstance(v, float) else v) for k, v in p.items() if k in ("nombre", "listo", "swap", "t_agarra")}
                   for p in PALLETS]
DIAG["salidas"] = {k: {kk: round(vv, 2) for kk, vv in v.items() if isinstance(vv, float)} for k, v in LIN.salidas.items()}
DIAG["envueltos"] = [(round(a, 1), round(b, 1), c_, k) for (a, b, c_, k) in LIN.envueltos]

if CAP_ROBOT:
    out = {}
    for c in CELDAS:
        ks = sorted(c.T_FIN_PAL)
        cyc_cap = [cy for cy in c.ciclos if cy.get("pal") == 1 and cy["tipo"] != "casa"]
        T = cyc_cap[-1]["t1"] - cyc_cap[0]["t0"]
        out[c.n] = {"cajas": c.n_cajas_pallet, "segundos_pallet": round(T, 1), "cajas_por_min": round(c.n_cajas_pallet / T * 60, 1),
                    "s_por_caja": round(T / c.n_cajas_pallet, 2),
                    "ciclos": {tp: round(sum(cy["t1"] - cy["t0"] for cy in cyc_cap if cy["tipo"] == tp) /
                                         max(1, len([1 for cy in cyc_cap if cy["tipo"] == tp])), 2) for tp in ("una", "grupo")}}
    print(json.dumps(out, ensure_ascii=False, indent=1))
    sys.exit(0)
if CAP_PLANTA or "--sin-cuadros" in ARG:
    print(json.dumps(DIAG, ensure_ascii=False, default=str, indent=1))
    if "--sin-cuadros" in ARG or CAP_PLANTA:
        sys.exit(0)

# ================================================================== muestreo por cuadro
from comun import ease as _ease  # noqa: E402


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
            u = _ease((t - a_) / (b_ - a_))
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
            u = _ease((t - ts0) / max(1e-6, ts1 - ts0))
            M = [r[:] for r in Mb]
            for i in range(3):
                M[i][3] = lerp(Mb[i][3], Mh[i][3], u)
            return True, M
        if fase == "held":
            return True, mm(Gt, c.pinza.LB[val[1]])
        if fase == "placed":
            return True, val
        return False, None


for c in CELDAS:
    c.cursores = [Cursor(c, b) for b in c.cajas]
    c.G_EV = garra_eventos(c)


def pallet_M(p, t):
    """Pallet vacío: pila -> robot aéreo -> camas -> estación."""
    c = A if p["celda"] == "A" else B
    pila = p["pila"]
    if t < p["t_agarra"]:
        return tr(pila["M"][0][3], pila["M"][1][3], pila["M"][2][3])
    if t < p["t_suelta"]:
        return tr(AER.X, 1528.0 + AER.val("dy", t, 0.0), AER.val("z", t, AER.Z_PARK))
    c0, c1 = p["t_cama"]
    z0, z1 = p["t_centra"]
    x = lerp(p["x_carro"], p["PAL_O"][0], ease5((t - c0) / (c1 - c0))) if t >= c0 else p["x_carro"]
    z = lerp(p["z_dep"], p["PAL_O"][2], _ease((t - z0) / (z1 - z0))) if t >= z0 else p["z_dep"]
    return tr(x, p["PAL_O"][1], z)


APOYOS_X = [(-1e9, -7528.2, None), (-7528.2, -5548.3, None), (-5618.2, 8419.8, Y_LINEA), (8419.8, 11465.8, Y_MP),
            (11465.8, 1e9, Y_LINEA)]


def y_apoyo(x, z, y_est):
    """Altura de la base del pallet según el transportador bajo su centro (suavizada ±150 mm)."""
    def base(xx, zz):
        if zz < -36600.0:                       # línea en Z (B -> A) y giratoria B
            if zz < -42900.0 and xx > -7600.0:
                return y_est
            return Y_LINEA if xx > -7300.0 else y_est
        for (a_, b_, y_) in APOYOS_X:
            if a_ <= xx < b_:
                return y_est if y_ is None else y_
        return Y_LINEA
    return sum(base(x - 150.0 + 10.0 * i, z) for i in range(31)) / 31.0


def lleno_M(c, info, t):
    if info is None:
        return tr(*c.PAL_O)
    p = info["mov"].xz(t)
    if p is None:
        return tr(*c.PAL_O)
    M = tr(p[0], y_apoyo(p[0], p[1], c.PAL_O[1]), p[1])
    ang = giro_pallet(info, t)
    return mm(M, roty(ang)) if abs(ang) > 1e-6 else M


# envolvedora
mp = {e["n"]: e for e in REL["mp402"]["hijos"]}
M_ROTOR = mp["MP402_Rotor:1"]["M"]
M_CARRO_MP = mp["MP402_Carro:1"]["M"]
ROTOR_EJE = (9865.8363, -35615.1739)
N_FILM, H_FILM, N_VUELTAS = 8, 200.0, 6.0


def env_estado(t):
    """(ángulo, subida del carro, bandas visibles, celda, clave) del envuelto en curso o el último."""
    act = None
    for (w0, w1, cel, clave) in LIN.envueltos:
        if t >= w0:
            act = (w0, w1, cel, clave)
    if act is None:
        return 0.0, 0.0, 0, None, None
    w0, w1, cel, clave = act
    T_ENV = w1 - w0
    u = min(1.0, (t - w0) / T_ENV)
    ta = 0.1
    if u < ta:
        f = 0.5 * u * u / ta
    elif u < 1 - ta:
        f = 0.5 * ta + (u - ta)
    else:
        f = 1 - ta - 0.5 * (1 - u) ** 2 / ta
    f /= (1 - ta)
    ang = -360.0 * N_VUELTAS * f
    c = A if cel == "A" else B
    dy_max = (Y_MP + c.H_CARGA + 30.0) - mp["MP402_Carro:1"]["c"][4]
    h = _ease(u / 0.5) if u < 0.5 else (1.0 if u < 0.58 else 1.0 - _ease((u - 0.58) / 0.42))
    nb = sum(1 for k in range(N_FILM) if u >= 0.03 + 0.45 * (k + 0.5) / N_FILM)
    return ang, dy_max * h, nb, cel, clave


def film_rel(c, k):
    yk = 20.0 + k * (c.H_CARGA - 40.0 - H_FILM) / (N_FILM - 1) + H_FILM / 2
    return [[1, 0, 0, 0], [0, 0, 1, yk], [0, -1, 0, 0], [0, 0, 0, 1]]


# ------------------------------------------------------------------ objetos de la escena
CELDA_P = {"A": "Celda_A_L3N:1/", "B": "Celda_B_existente:1/"}
AEREO_P, LINEA_P = "Robot_Aereo_Pallets:1/", "Linea_Pallets:1/"
OBJ = {}


def obj(nombre, archivo, M, vis=True, rol=""):
    OBJ[nombre] = {"f": archivo, "M": comp(M), "vis": vis, "rol": rol}


celA = {e["n"]: e for e in REL["celda_A"]}
celB = {e["n"]: e for e in REL["celda_B"]}
PAT_PIEZAS = ["chapa pateador:2", "chapa refuerzo:1", "soporte a piston:1", "soporte a piston:2", "eje cromado 500:1",
              "eje cromado 500:2", "SHF16:1", "SHF16:2"]
CAJA_F = {"A": celA["IA_Caja_en_cinta"]["f"], "B": "CAJA_B_SIM"}
PAL_F = aereo["Pila1_pallet_10"]["f"]
OCULTAR = ["Paredes:1"]
for c, cel in ((A, celA), (B, celB)):
    P0 = c.robot.poses([0, 0, 0, 0])
    if c.n == "A":
        for k_ in ("V02", "V03", "V04", "V05"):
            obj(f"SIM_A_{k_}", REL["robot_ia"][f"IA_Robot_{k_}"]["f"], P0[k_], rol="robot")
        obj("SIM_A_Gripper", "GRIPPER_A_SIM", P0["gripper"], rol="gripper")
    else:
        kb = REL["kuka_B"]
        for n_, v in kb["links"].items():
            k_ = "V0" + n_.split("_V0")[-1][:1]
            if k_ in ("V02", "V03", "V04", "V05"):
                obj(f"SIM_B_{k_}", v["f"], P0[k_], rol="robot")
                OCULTAR.append(CELDA_P["B"] + kb["n"] + "/" + n_)
        obj("SIM_B_Gripper", "GRIPPER_B_SIM", P0["gripper"], rol="gripper")
    for i in range(c.N_POOL):
        obj(f"SIM_{c.n}_Caja_{i:03d}", CAJA_F[c.n], ING.caja_en_recorrido(c, 0.0), vis=False, rol="caja")
    for n_ in PAT_PIEZAS:
        e = cel.get("Ensamble pateador adeco:1/" + n_)
        if e:
            obj(f"SIM_{c.n}_Pat_" + n_.replace(" ", "_").replace(":", "_"), e["f"], e["M"], rol="pateador")
            OCULTAR.append(CELDA_P[c.n] + "Ensamble pateador adeco:1/" + n_)
for p in PALLETS:
    obj(p["nombre"], PAL_F, tr(p["pila"]["M"][0][3], p["pila"]["M"][1][3], p["pila"]["M"][2][3]), vis=False, rol="pallet")
for c in CELDAS:
    obj(f"SIM_{c.n}_Lleno", f"PALLET_LLENO_{c.n}", tr(*c.PAL_O), vis=False, rol="pallet_lleno")
    for k in range(N_FILM):
        obj(f"SIM_{c.n}_Film_{k}", "FILM_A" if k % 2 == 0 else "FILM_B", mm(tr(*c.PAL_O), film_rel(c, k)), vis=False, rol="film")
for n_, nn in (("Carro", "SIM_Aereo_Carro"), ("Torre_elevacion", "SIM_Aereo_Torre"), ("Sujecion_pallet", "SIM_Aereo_Sujecion")):
    obj(nn, aereo[n_]["f"], aereo[n_]["M"], rol="aereo")
for j in range(3):
    obj(f"SIM_Aereo_Barra_{j}", aereo["Barra_elevacion"]["f"], aereo["Barra_elevacion"]["M"], rol="aereo")
GIR = {}
GIR_A = REL["giratoria_A"]["hijos"][0]
obj("SIM_A_Gir_Deck", GIR_A["f"], GIR_A["M"], rol="giratoria")
GIR["A"] = ("SIM_A_Gir_Deck", gA, CELDA_P["A"] + "roller conveyor - rotating:1/" + GIR_A["n"])
gir_B_hijos = [e for e in REL["celda_B"] if e["n"].startswith("roller conveyor - rotating:1/")]
if gir_B_hijos:
    GIR_B = gir_B_hijos[0]
    obj("SIM_B_Gir_Deck", GIR_B["f"], GIR_B["M"], rol="giratoria")
    GIR["B"] = ("SIM_B_Gir_Deck", gB, CELDA_P["B"] + GIR_B["n"])
fr = celB.get("IA_Freno_contador_B_tope")
if fr:
    obj("SIM_B_Freno", fr["f"], fr["M"], rol="freno")
    OCULTAR.append(CELDA_P["B"] + "IA_Freno_contador_B_tope")
obj("SIM_MP402_Rotor", mp["MP402_Rotor:1"]["f"], M_ROTOR, rol="envolvedora")
obj("SIM_MP402_Carro", mp["MP402_Carro:1"]["f"], M_CARRO_MP, rol="envolvedora")
OCULTAR += [CELDA_P["A"] + n_ for n_ in ("IA_Robot_V02", "IA_Robot_V03", "IA_Robot_V04", "IA_Robot_V05", "IA_Gripper_7xTBA250",
                                         "IA_Pallet_TBA250", "IA_Caja_en_cinta", "KUKA-KR_140_R3200_2_PA-ASM:1",
                                         "chapa tope derecha:1", "soporte bandejas:14", "soporte bandejas:15", "Empujador 01:1")]
OCULTAR += [v[2] for v in GIR.values()]
OCULTAR += [CELDA_P["B"] + n_ for n_ in ("Gripper_ADECO2_V1:1", "Pallet_Completo:2", "Empujador 01:1")]
OCULTAR += [CELDA_P["A"] + "Ensamble pateador adeco:1/chapa nueva 2:2"]
OCULTAR += [CELDA_P["B"] + e["n"] for e in REL["celda_B"] if e["n"].startswith("Bandeja_") and "/" not in e["n"]]
OCULTAR += [AEREO_P + n_ for n_ in ("Carro", "Torre_elevacion", "Barra_elevacion", "Sujecion_pallet", "Pallet_en_sujecion")]
OCULTAR += [LINEA_P + "MP402:1/MP402_Rotor:1", LINEA_P + "MP402:1/MP402_Carro:1"]
# lo oculto dentro de los archivos de celda no se ve oculto en el layout: se repite en la escena
_oc = Path(__file__).resolve().parent / "ocultos_celdas.json"
if _oc.exists():
    for k_, lst in json.load(open(_oc, encoding="utf-8")).items():
        OCULTAR += [k_ + "/" + n_ for n_ in lst if k_ + "/" + n_ not in OCULTAR]
PROXY_DIN = {AEREO_P + p["pila"]["nombre"]: p["t_agarra"] for p in PALLETS}
M_PROX = {"aereo/" + n_: aereo[n_]["M"] for n_ in ("Carro", "Torre_elevacion", "Barra_elevacion", "Sujecion_pallet")}
Z_CARRO0 = aereo["Carro"]["M"][2][3]


def estado(t, qs):
    M, V, G = {}, {}, {}
    for c in CELDAS:
        psi, org = c.tray.pose(t)
        q, e = c.robot.q_para(c.robot.gripper_pose(psi, org), qs[c.n])
        qs[c.n] = q
        P = c.robot.poses(q)
        for k_ in ("V02", "V03", "V04", "V05"):
            M[f"SIM_{c.n}_{k_}"] = P[k_]
        Gt = P["gripper"]
        M[f"SIM_{c.n}_Gripper"] = Gt
        for cur in c.cursores:
            v, Mb = cur.estado(t, Gt)
            nm = f"SIM_{c.n}_Caja_{cur.b.idx:03d}"
            V[nm] = v
            if Mb is not None:
                M[nm] = Mb
        d = ING.pat_d(c, t)
        for n_ in PAT_PIEZAS:
            key = f"SIM_{c.n}_Pat_" + n_.replace(" ", "_").replace(":", "_")
            if key in OBJ:
                base = (celA if c.n == "A" else celB)["Ensamble pateador adeco:1/" + n_]["M"]
                M[key] = mm(tr(d, 0, 0), base)
        G[f"SIM_{c.n}_Gripper"] = [round(garra_frac(c.G_EV[g], t), 3) for g in range(c.pinza.n)]
    for p in PALLETS:
        M[p["nombre"]] = pallet_M(p, t)
        V[p["nombre"]] = t >= p["t_agarra"] and not (p["swap"] is not None and t >= p["swap"])
    for c in CELDAS:
        info, sw = None, None
        for p in PALLETS:
            if p["celda"] == c.n and p["swap"] is not None and t >= p["swap"]:
                info, sw = p["salida"], p["swap"]
        Ml = lleno_M(c, info, t)
        M[f"SIM_{c.n}_Lleno"] = Ml
        visible = info is not None and t < info["T_s1"] + 2.0
        V[f"SIM_{c.n}_Lleno"] = visible
        ang, dyc, nb, cel_env, clave = env_estado(t)
        for k in range(N_FILM):
            M[f"SIM_{c.n}_Film_{k}"] = mm(Ml, film_rel(c, k))
            env_este = info is not None and clave is not None and LIN.salidas.get(clave) is info
            V[f"SIM_{c.n}_Film_{k}"] = bool(visible and env_este and (k < nb or t >= info["T_w1"]))
    z, dy = AER.val("z", t, AER.Z_PARK), AER.val("dy", t, 0.0)
    T_z = tr(0, 0, z - Z_CARRO0)
    M["SIM_Aereo_Carro"] = mm(T_z, M_PROX["aereo/Carro"])
    M["SIM_Aereo_Torre"] = mm(T_z, M_PROX["aereo/Torre_elevacion"])
    M["SIM_Aereo_Sujecion"] = mm(tr(0, dy, z - Z_CARRO0), M_PROX["aereo/Sujecion_pallet"])
    for j in range(3):
        M[f"SIM_Aereo_Barra_{j}"] = mm(tr(0, dy * j / 2.0, z - Z_CARRO0), M_PROX["aereo/Barra_elevacion"])
    ang, dyc, nb, cel_env, clave = env_estado(t)
    R_ = roty(ang, ROTOR_EJE[0], ROTOR_EJE[1])
    M["SIM_MP402_Rotor"] = mm(R_, M_ROTOR)
    M["SIM_MP402_Carro"] = mm(R_, mm(tr(0, dyc, 0), M_CARRO_MP))
    if "SIM_B_Freno" in OBJ:
        abierto = any(a_ - 0.15 <= t <= b_ for (a_, b_) in B.freno_events) or (B.freno_abierto is not None and t >= B.freno_abierto - 0.15)
        M["SIM_B_Freno"] = mm(tr(0, -70.0 if abierto else 40.0, 0), celB["IA_Freno_contador_B_tope"]["M"])
    for pth, ta in PROXY_DIN.items():
        V["@" + pth] = t < ta
    gir = {v[0]: round(v[1].frac(t), 4) for v in GIR.values()}
    return M, V, G, gir


# ================================================================== guion del video
def ciclos_pal1(c, tipo=None):
    return [cy for cy in c.ciclos if cy.get("pal") == 1 and cy["tipo"] != "casa" and (tipo is None or cy["tipo"] == tipo)]


SA = LIN.salidas["SIM_A_Pallet_1"]
SB = LIN.salidas["SIM_B_Pallet_1"]
tA_f3_0 = ciclos_pal1(A, "una")[0]["t0"]
tA_f3_1 = ciclos_pal1(A, "una")[0]["t1"] + 0.6
tA_c1 = max(cy["t1"] for cy in ciclos_pal1(A) if cy["capa"] == 0) + 0.4
tB_c0 = ciclos_pal1(B)[0]["t0"]
tB_f3_1 = ciclos_pal1(B, "una")[0]["t1"] + 0.6
tB_c1 = max(cy["t1"] for cy in ciclos_pal1(B) if cy["capa"] == 0) + 0.4
tA_full, tB_full = A.T_FIN_PAL[1], B.T_FIN_PAL[1]
CA = [A.PAL_O[0], A.PAL_O[1] + 152.0 + 75.0, A.PAL_O[2] + A.capas[0]["tomas"][0]["cajas"][0][1][2]]
PB = B.PAL_O
SEG_V = [
    ("general", -12.0, -6.0, 1.0, [(0.0, (22000, 30000, -14000), (-4500, 0, -41000), 44000),
                                   (1.0, (3500, 9500, -27500), (-8600, 600, -38500), 17500)],
     "Planta Las Tres Niñas · celda A (nueva) y celda B (existente) con robot aéreo, línea y envolvedora compartidos"),
    ("pateador", -6.0, 0.0, 1.0, [(0.0, (-13900, 5300, -38300), (-12050, 800, -36600), 4200),
                                  (1.0, (-13700, 5000, -38200), (-11850, 800, -36650), 3900)],
     "Celda A: 1 caja cada 2,5 s · pateador corrido 120 mm: con su carrera de 300 la caja entra a la cinta interna"),
    ("aereo", 0.0, tA_f3_0 - 0.5, 2.0, [(0.0, (-2500, 6500, -29000), (-10300, 1200, -33800), 9500),
                                        (0.55, (-2800, 6200, -29800), (-10000, 1000, -34800), 9000),
                                        (1.0, (-3200, 5600, -31000), (-9000, 800, -35700), 8000)],
     "Robot aéreo: lleva un pallet vacío de la pila a la cama de ingreso de la celda A (×2)"),
    ("fila3", tA_f3_0 - 0.5, tA_f3_1, 1.0, [(0.0, (-4600, 4300, -32300), (CA[0], CA[1], CA[2] - 250), 4300),
                                             (0.3, (CA[0] + 2300, CA[1] + 2200, CA[2] + 2600), (CA[0], CA[1], CA[2] - 100), 2700),
                                             (1.0, (CA[0] + 2100, CA[1] + 2300, CA[2] + 2700), (CA[0], CA[1], CA[2] - 100), 2600)],
     "Toma real: el gripper baja centrado y la pala móvil empuja la caja contra la fija · fila de 3 de a una"),
    ("ambas", tA_f3_1, tB_c0 - 0.5, 2.0, [(0.0, (CA[0] + 2100, CA[1] + 2300, CA[2] + 2700), (CA[0], CA[1], CA[2] - 100), 2600),
                                          (0.3, (-1500, 9800, -34500), (-9800, 900, -40000), 15000),
                                          (1.0, (-1800, 9000, -36500), (-9800, 900, -41800), 14000)],
     "Mientras A paletiza, el robot aéreo lleva otro pallet a la celda B pasando sobre las rejas bajadas a 1400 (×2)"),
    ("ingreso_B", tB_c0 - 0.5, tB_f3_1, 1.0, [(0.0, (-6800, 5200, -39800), (-10200, 900, -43200), 7600),
                                              (1.0, (-6400, 4600, -40600), (-9300, 900, -43400), 6400)],
     "Celda B: pateador → cinta 1 → freno con contador (deja pasar sólo las cajas de la toma) → cinta 2 → robot"),
    ("capa1_B", tB_f3_1, tB_c1, 2.0, [(0.0, (-6400, 4600, -40600), (-9300, 900, -43400), 6400),
                                      (1.0, (-5200, 4300, -40900), (PB[0], PB[1] + 300, PB[2]), 5200)],
     "Celda B: franja de 3 de a una y columnas de 6 desde la franja hacia afuera (×2)"),
    ("capas", tB_c1, tA_full, 15.0, [(0.0, (-5200, 4300, -40900), (PB[0], PB[1] + 300, PB[2]), 5200),
                                     (0.12, (-1200, 9500, -38800), (-8400, 1100, -39800), 14500),
                                     (0.55, (-500, 8800, -45200), (-8400, 1100, -39800), 14500),
                                     (1.0, (-2400, 6300, -33200), (-8000, 1000, -36200), 8200)],
     "Las dos celdas paletizan en paralelo (×15)"),
    ("salida", tA_full, SA["T_mov0"] + 9.0, 1.5, [(0.0, (-2600, 4400, -31600), (-7200, 700, -35900), 7600),
                                                  (1.0, (-600, 4400, -31200), (-5200, 700, -35700), 7600)],
     "Pallet A completo: la giratoria se orienta hacia la celda y el pallet sale por la barrera IFM (muting)"),
    ("traslado", SA["T_mov0"] + 9.0, SA["T_arr"], 8.0, ("seguir", "A"),
     "Traslado por la línea hasta la envolvedora MP402 (×8)"),
    ("envuelto", SA["T_arr"], SA["T_w1"] + 0.5, 3.0, [(0.0, (14800, 4600, -30800), (9866, 1250, -35617), 6800),
                                                     (1.0, (12600, 5200, -29900), (9866, 1250, -35617), 6800)],
     "Envolvedora MP402: film estirable en espiral (×3)"),
    ("vuelta_B", SA["T_w1"] + 0.5, tB_full, 4.0, [(0.0, (-1200, 9500, -38800), (-8400, 1100, -39800), 14500),
                                                  (1.0, (-4800, 6200, -39400), (PB[0], PB[1] + 500, PB[2]), 7800)],
     "La celda B termina su pallet y la A ya recibió el pallet siguiente (×4)"),
    ("salida_B", tB_full, SB["T_arr"], 5.0, ("seguir", "B"),
     "Pallet B completo: giratoria B → línea en Z → giratoria A → línea hasta la MP402 (×5)"),
    ("envuelto_B", SB["T_arr"], SB["T_w1"] + 0.5, 3.0, [(0.0, (14800, 4600, -30800), (9866, 1250, -35617), 6800),
                                                         (1.0, (12600, 5200, -29900), (9866, 1250, -35617), 6800)],
     "Envolvedora MP402: el pallet de la celda B (×3)"),
    ("final", SB["T_w1"] + 0.5, SB["T_s1"] + 3.0, 1.0, [(0.0, (12600, 5200, -29900), (9866, 1250, -35617), 6800),
                                                        (0.35, (13500, 6000, -29000), (10500, 1100, -35617), 8000),
                                                        (1.0, (9000, 19000, -18000), (-2500, 0, -40000), 36000)],
     "Pallets envueltos a despacho · las dos celdas siguen paletizando"),
]


def cam_seguir(cel, t):
    info = SA if cel == "A" else SB
    p = info["mov"].xz(t)
    x, z = p
    return (x + 3000.0, 4300.0, z + 4800.0), (x + 300.0, 900.0, z), 8000.0


def cam_en(seg, t):
    nombre, t0, t1, vel_, keys, _ = seg
    if isinstance(keys, tuple):
        return cam_seguir(keys[1], t)
    u = (t - t0) / (t1 - t0)
    if u <= keys[0][0]:
        return keys[0][1:]
    for a_, b_ in zip(keys, keys[1:]):
        if u <= b_[0]:
            w = _ease((u - a_[0]) / (b_[0] - a_[0]))
            return (tuple(lerp(a_[1][i], b_[1][i], w) for i in range(3)), tuple(lerp(a_[2][i], b_[2][i], w) for i in range(3)),
                    lerp(a_[3], b_[3], w))
    return keys[-1][1:]


def capa_en(c, t):
    c_ = [cy for cy in c.ciclos if cy.get("pal") == 1 and cy["tipo"] != "casa" and cy["t0"] <= t]
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
            txt = f"Las dos celdas en paralelo (×15) · A: capa {max(1, capa_en(A, t_))} de 8 · B: capa {max(1, capa_en(B, t_))} de 9"
        FRAMES.append({"t": t_, "seg": nombre, "vel": vel_, "eye": eye, "tgt": tgt, "w": w, "ley": txt})
DIAG["cuadros"] = len(FRAMES)
DIAG["segmentos"] = {s[0]: [int(round((s[2] - s[1]) / s[3] * FPS)), round(s[1], 2), round(s[2], 2)] for s in SEG_V}
if "--guion" in ARG:
    print(json.dumps(DIAG["segmentos"], indent=1), len(FRAMES))
    sys.exit(0)

# ------------------------------------------------------------------ estados por cuadro (sólo cambios)
qs = {c.n: [0.0, -40.0, 90.0, 0.0] for c in CELDAS}
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


def cajas_rel(c, pal_n=1):
    out = []
    for b in c.cajas:
        ks = [k for k in b.keys if k[1] == "placed"]
        if ks:
            out.append(comp(mm(inv(tr(*c.PAL_O)), ks[0][2])))
        if len(out) >= c.n_cajas_pallet:
            break
    return out


plan = {"version": 5, "fps": FPS, "objetos": OBJ, "ocultar": OCULTAR, "proxy_dinamicos": list(PROXY_DIN),
        "grippers": {"SIM_A_Gripper": {"tipo": "restriccion", "f": REL["gripper"]["f"], "n": A.pinza.n, "cierre_mm": A.pinza.cierre,
                                       "modulos": sorted(REL["gripper"]["modulos"], key=lambda s_: int(s_.split(":")[-1]))},
                     "SIM_B_Gripper": {"tipo": "traslado", "f": REL["gripper_B"]["f"], "n": B.pinza.n, "cierre_mm": B.pinza.cierre,
                                       "eje_local": [0, 0, 1], "modulo": "pala_movil_apriete",
                                       "moviles": ["Pala movil 2 cajas", "Goma pala movil 2 cajas", "part_empuje", "empuja pala"],
                                       "ocultar_hijos": ["Bandeja_24x200_con_sorbete"], "x_garra0": 478.6, "paso_garras": 161.0}},
        "giratorias": {v[0]: {"eje": [v[1].x, v[1].z], "th": [0.0, 90.0], "proxy": v[2]} for v in GIR.values()},
        "film": {"A": [1216.0, 1016.0], "B": [1222.0, 1022.0], "espesor": 3.0, "alto": H_FILM},
        "pallets_llenos": {c.n: {"pallet": PAL_F, "caja": CAJA_F[c.n], "cajas_rel": cajas_rel(c)} for c in CELDAS},
        "caja_B": {"L": B.L, "H": B.H, "W": B.W},
        "cuadros": out_frames, "diag": DIAG}
OUT.write_text(json.dumps(plan, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
meta = {"leyendas": [[i, f["seg"], f["vel"], f["ley"], round(f["t"], 3)] for i, f in enumerate(FRAMES)], "diag": DIAG}
OUT.with_name(OUT.stem + "_meta.json").write_text(json.dumps(meta, ensure_ascii=False, default=str), encoding="utf-8")
print(json.dumps({k: v for k, v in DIAG.items() if k in ("cuadros", "segmentos")}, ensure_ascii=False, default=str, indent=1))
print("bytes", OUT.stat().st_size)
