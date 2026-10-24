"""Configuración de las celdas A y B desde los relevamientos (rel.json con celda_A, celda_B, kuka, kuka_B, gripper,
gripper_B, pallet_lleno, aereo, linea, mp402)."""
import math

from comun import box_M, roty, apply, mm, tr
from robot import Robot
from celda5 import Celda, Pinza

LUZ = 10.0
VEL_A = (137.0, 111.0, 119.0, 321.0)      # KR 180 R3200-2 PA (catálogo)
VEL_B = (105.0, 107.0, 114.0, 242.0)      # KR 180 R3200 PA generación anterior (conservador para el robot de B)


def _links(k):
    out = {}
    for n, v in k["links"].items():
        out["V0" + n.split("_V0")[-1][:1]] = v["M_rel"]
    return out


def _estaticos(listas, excluir, Z_INT, extra=()):
    E = []
    for lst in listas:
        for e in lst or []:
            c = list(e["c"] or [])
            n = e["n"]
            if not c or c == [0.0] * 6 or e.get("vis") is False:
                continue
            if "/" in n and not n.startswith("ADECOAGRO2_Layout"):
                continue
            if n.startswith("ADECOAGRO2_Layout") and e.get("nh", 0):
                continue                                   # sólo las piezas del cerco, no los ensambles que las agrupan
            if n.count("/") > 3:
                continue
            if n.startswith(excluir):
                continue
            E.append((n, c))
    return E + list(extra)


# ---------------------------------------------------------------------------- celda A
def celda_A(R, fuente_t0=-58.0, paso=2.5):
    cel = R["celda_A"]
    T_ROB = R["kuka"]["M_layout"]
    G = R["gripper"]
    GL = G["caja_local"]
    rob = Robot("A", T_ROB, _links(R["kuka"]), (387.0, 546.0, -245.2), [[0, 1, 0], [0, 0, -1], [-1, 0, 0]], VEL_A, GL)
    L, H, W = 386.0, 149.0, 156.0
    X_GOMA_FIJA, X_GOMA_MOVIL = 169.0, 600.5
    z_base = GL[5] + 15.0
    # caja -> gripper: X caja (386) = X gripper; Y caja (arriba) = -Z gripper; Z caja = Y gripper
    R_box_g = [[1, 0, 0], [0, 0, 1], [0, -1, 0]]
    pinza = Pinza(GL, R_box_g, lambda i: [X_GOMA_FIJA + L / 2, 78.0 + 156.0 * i, z_base], (1.0, 0.0, 0.0),
                  X_GOMA_MOVIL - (X_GOMA_FIJA + L), 7, 45.3, (0.0, 1.0, 0.0))
    Z_INT = -36697.0
    PAL_O = [R["pallet_lleno"]["M_layout"][i][3] for i in range(3)]
    # patrón real (Pallet_TBA250_17x8) con luz entre filas para la pala fija
    PAT = []
    for e in R["pallet_lleno"]["hijos"][1:]:
        M = e["M_rel"]
        PAT.append({"R": [r[:3] for r in M[:3]], "p": [M[0][3], M[1][3], M[2][3]]})
    CAPAS = sorted({round(b["p"][1]) for b in PAT})
    capas = []
    for y_ in CAPAS:
        cap = [b for b in PAT if round(b["p"][1]) == y_]
        bandas = sorted({round(b["p"][2]) for b in cap})
        for b in cap:
            b["p"][2] += (bandas.index(round(b["p"][2])) - (len(bandas) - 1) / 2) * LUZ
        r3 = sorted([b for b in cap if abs(b["R"][0][0]) > 0.5], key=lambda b: b["p"][0])
        for j, b in enumerate(r3):
            b["p"][0] += (j - (len(r3) - 1) / 2) * LUZ
        rows7 = [b for b in cap if abs(b["R"][0][0]) < 0.5]
        z3 = r3[0]["p"][2]
        zs = sorted({round(b["p"][2]) for b in rows7}, key=lambda z: abs(z - z3))     # primero la del medio
        tomas = [{"tipo": "una", "cajas": [(b["R"], b["p"]) for b in r3], "dir": (0.0, 0.0, -1.0 if z3 > 0 else 1.0)}]
        for z in zs:
            fila = [b for b in rows7 if round(b["p"][2]) == z]
            tomas.append({"tipo": "grupo", "cajas": [(b["R"], b["p"]) for b in fila], "dir": (0.0, 0.0, 1.0 if z > z3 else -1.0)})
        capas.append({"y": y_, "tomas": tomas})
    # recorrido de la cinta de llegada (T1, Curva 1, T2, Curva 2, T3)
    R_CURVA = 475.0
    X_T1, Z_T1_0, Z_T2, X_T3 = 4363.0, -25562.0, -30894.0, -12134.0
    segs = [("r", ((X_T1, Z_T1_0), (X_T1, Z_T2 + R_CURVA)), None), ("a", ((X_T1 - R_CURVA, Z_T2 + R_CURVA), 0.0, -90.0), R_CURVA),
            ("r", ((X_T1 - R_CURVA, Z_T2), (X_T3 + R_CURVA, Z_T2)), None), ("a", ((X_T3 + R_CURVA, Z_T2 - R_CURVA), 90.0, 180.0), R_CURVA),
            ("r", ((X_T3, Z_T2 - R_CURVA), (X_T3, Z_INT)), None)]
    excl = ("IA_", "KUKA", "Riel", "00.Ensamblaje Mesa", "roller conveyor", "Pasarela", "Cinta_Llegada_A", "chapa tope",
            "soporte bandejas", "Empujador 01", "Carro", "Torre", "Barra", "Sujecion", "Pallet_en", "Columna_1", "Travesano_1",
            "Paredes", "Ensamble pateador")
    ESTAT = []
    for n, c in _estaticos([cel, R["aereo"], R["linea"], R["cinta_llegada"]], excl, Z_INT):
        if n.startswith("Cinta_Interna"):
            c = list(c)
            c[4] = 800.0
            ESTAT.append(("Cajas_en_cola_interna", [c[0], 800.0, Z_INT - 193.0, c[3], 949.0, Z_INT + 193.0]))
        if n.startswith(("Barrera_brazo", "Barrera_sensor")) and c[1] > 650:
            c = list(c)
            c[1] -= 140.0
            c[4] -= 140.0
        ESTAT.append((n, c))
    X_STOP = -7822.7
    PAT_CONTACTO = 43.7                 # pateador corrido 120 mm (l3n_infeed_v5): chapa a 44 mm de la caja
    return Celda("A", {
        "robot": rob, "pinza": pinza, "L": L, "H": H, "W": W, "R_BOX_INT": [[0, 0, 1], [0, 1, 0], [-1, 0, 0]],
        "Y_BANDA": 800.0, "Y_LLEGADA": 800.0, "Z_INT": Z_INT, "X_STOP": X_STOP, "PAL_O": PAL_O, "capas": capas, "n_cajas_pallet": 136,
        "H_CARGA": 152.0 + 8 * H, "path_segs": segs, "V_BANDA": 500.0, "PASO_FUENTE": paso, "src_t0": fuente_t0,
        "X_KICK0": X_T3, "CARRERA": 300.0, "CONTACTO": PAT_CONTACTO, "T_PATEO": 0.55, "T_RETORNO": 0.4,
        "freno": None, "ESTATICOS": ESTAT, "N_POOL": 240, "pat_piezas": "Ensamble pateador adeco:1",
        "Z_DEP": (-36438.8 + -34940.4) / 2, "X_CARRO": -10582.0, "V_CAMA": 420.0,
        "gir": {"X": -6538.2351, "Z": -35622.3429}, "bandas_film": (1216.0, 1016.0),
    })


# ---------------------------------------------------------------------------- celda B
def celda_B(R, fuente_t0=-58.0, paso=2.5):
    cel = R["celda_B"]
    by = {e["n"]: e for e in cel}
    T_ROB = R["kuka_B"]["M_layout"]
    G = R["gripper_B"]
    GL = list(G["caja_local"])
    GL[1] = -852.0                  # sin las bandejas que trae el CAD del gripper: punta de las palas
    # brida del gripper ADECO2 (cara superior de "Brida nueva", local Y arriba); gripper colgado con Y arriba
    rob = Robot("B", T_ROB, _links(R["kuka_B"]), (877.5, -438.8, 52.0), [[1, 0, 0], [0, 1, 0], [0, 0, 1]], VEL_B, GL)
    L, H, W = 313.0, 130.0, 161.0
    Z_GOMA_FIJA, Z_GOMA_MOVIL = 243.4, -135.0
    y_base = -883.8
    # caja -> gripper: X caja (313) = -Z gripper; Y caja = +Y; Z caja (161) = +X gripper (eje de garras)
    R_box_g = [[0, 0, 1], [0, 1, 0], [-1, 0, 0]]
    pinza = Pinza(GL, R_box_g, lambda i: [478.6 + 161.0 * i, y_base, Z_GOMA_FIJA - L / 2], (0.0, 0.0, -1.0),
                  (Z_GOMA_FIJA - L) - Z_GOMA_MOVIL, 6, 65.2, (1.0, 0.0, 0.0))
    pal = by["Pallet_Completo:2/European Pallet:1"]["c"] if "Pallet_Completo:2/European Pallet:1" in by else [-8739.8, 531.8, -44370.4, -7539.8, 683.8, -43370.4]
    PAL_O = [(pal[0] + pal[3]) / 2, pal[1], (pal[2] + pal[5]) / 2]
    # patrón de la ficha (21 x 9): franja de 3 (313 a lo largo de Z) + 3 columnas de 6 (313 a lo largo de X)
    XT = W + 3 * L + 3 * LUZ
    R_strip = [[0, 0, 1], [0, 1, 0], [-1, 0, 0]]        # X caja -> -Z mundo
    R_col = [[1, 0, 0], [0, 1, 0], [0, 0, 1]]
    capas = []
    for k in range(9):
        s = 1.0 if k % 2 == 0 else -1.0                   # capa 1 con la franja en +X (como el CAD), después alterna
        y_ = 152.0 + k * H
        xs = s * (XT / 2 - W / 2)
        strip = [(R_strip, [xs, y_, z]) for z in (-(L + LUZ), 0.0, L + LUZ)]
        tomas = [{"tipo": "una", "cajas": strip, "dir": (-s, 0.0, 0.0)}]
        for j in range(3):
            xc = s * (XT / 2 - W - LUZ - L / 2 - j * (L + LUZ))
            col = [(R_col, [xc, y_, (i - 2.5) * W]) for i in range(6)]
            tomas.append({"tipo": "grupo", "cajas": col, "dir": (-s, 0.0, 0.0)})
        capas.append({"y": y_, "tomas": tomas})
    # recorrido: recta 14 (a lo largo de X) -> curva 90° -> recta 13 (a lo largo de Z) hasta el tope de la cinta Tetra
    X13 = -12213.7
    Z_STOP_C = -42768.2 - L / 2                         # cara del tope (Chapa tope2)
    Z14 = -46243.0
    Rc = X13 - (-13213.7)
    segs = [("r", ((-15214.0, Z14), (-13213.7, Z14)), None), ("a", ((-13213.7, Z14 + Rc), -90.0, 0.0), Rc),
            ("r", ((X13, Z14 + Rc), (X13, Z_STOP_C)), None)]
    excl = ("KUKA", "base_principal", "Gripper", "Pallet_Completo", "Bandeja", "bandeja1000", "soporte bandejas",
            "Empujador 01", "Ensamble pateador", "roller conveyor", "00.Ensamblaje Mesa", "BM2000", "Correa", "Cinta",
            "Tope cinta tetra", "chapa tope", "IA_Freno")
    ESTAT = _estaticos([cel], excl, Z_STOP_C)
    # cintas internas como volumen (banda a 800) para los cruces del gripper con cajas
    bm = [by.get("BM2000_CeldaB_1"), by.get("BM2000_CeldaB_2")]
    for e in bm:
        if e and e["c"]:
            c = list(e["c"])
            ESTAT.append((e["n"], [c[0], c[1], c[2], c[3], 800.0, c[5]]))
    fr = by.get("IA_Freno_contador_B")
    X_FRENO = (fr["c"][3] - 8.0) if fr else -9439.5
    bm2 = by.get("BM2000_CeldaB_2")
    X_STOP = -7808.6
    return Celda("B", {
        "robot": rob, "pinza": pinza, "L": L, "H": H, "W": W, "R_BOX_INT": [[0, 0, 1], [0, 1, 0], [-1, 0, 0]],
        "Y_BANDA": 800.0, "Y_LLEGADA": 840.0, "Z_INT": Z_STOP_C, "X_STOP": X_STOP, "PAL_O": PAL_O, "capas": capas, "n_cajas_pallet": 189,
        "H_CARGA": 152.0 + 9 * H, "path_segs": segs, "V_BANDA": 500.0, "PASO_FUENTE": paso, "src_t0": fuente_t0,
        "X_KICK0": X13, "CARRERA": 300.0, "CONTACTO": 36.3, "T_PATEO": 0.55, "T_RETORNO": 0.4,
        "freno": {"x": X_FRENO, "v2": 600.0}, "ESTATICOS": ESTAT, "N_POOL": 260, "pat_piezas": "Ensamble pateador adeco:1",
        "Z_DEP": (-44692.2 + -43193.7) / 2, "X_CARRO": -10582.0, "V_CAMA": 420.0,
        "gir": {"X": -6530.735, "Z": -43982.2999}, "bandas_film": (1216.0, 1016.0),
    })
