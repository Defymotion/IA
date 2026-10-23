"""L3N: buffers de pallets vacíos al inicio del riel del robot aéreo (Robot_Aereo_Pallets.iam, archivo propio) y
puerta de paso del operario en la pared junto a la Curva_2 (Celda_A_L3N.iam, archivo propio).

Buffers (pedido 23/10): 2 pilas de 15 pallets, más separadas de la reja de la cinta para cargarlas cómodo con
autoelevador desde el lado abierto (+X). Cada pila: 4 columnas guía 80x80 blancas (luz 60 mm por lado: quedan
por fuera del bastidor de sujeción del robot, 1300 x 1100) con placa de anclaje, de 1900 de alto (por debajo del
riel, cara inferior 1980). Pórtico de soporte del riel al inicio y entre pilas (como los pórticos del robot,
columnas 150x150 hasta el riel; la del lado pared corrida para no tocar la pared, cara este X -11664).
Puerta: vano en la pared (X -11814..-11664) entre el pasillo de mantenimiento y el lado de T3: marco 900 x 2100
(jambas + dintel del espesor de la pared) y hoja de 800; la hoja abre hacia afuera (el motor de T2b está del lado
del pasillo).
Coordenadas: layout (mm); los dos ensambles tienen su origen en la giratoria A (ORG_A).
Uso: python l3n_buffers.py [--zt2 -30894] [--pallets 15]
"""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import inventor_mcp as inv  # noqa: E402
from cinta_modular import Gen  # noqa: E402

S = inv._safe
BASE = Path(r"C:\DEFYMOTION\L3N\Celdas_IA")
ROBOT = BASE / "Robot_Aereo" / "Robot_Aereo_Pallets.iam"
CELDA = BASE / "Celda_A_L3N.iam"
PIEZAS = BASE / "Buffers"
PALLET_IPT = Path(r"C:\DEFYMOTION\L3N\ADECO 12-12-25\European Pallet_3BC37FCD47819CDEC205D0C1A80F9DF2.ipt")
ORG_A = (-6503.2, 0.0, -35622.3)
Z_T2 = float(sys.argv[sys.argv.index("--zt2") + 1]) if "--zt2" in sys.argv else -30894.0
N_PAL = int(sys.argv[sys.argv.index("--pallets") + 1]) if "--pallets" in sys.argv else 15
# ---- buffers
X_PILA = -10635.0                       # entre los rieles (X -9797 / -11367)
PAL = (1200.0, 1000.0)                  # pallet en X, Z
LUZ, GUIA, H_GUIA = 60.0, 80.0, 1900.0
Z_REJA = Z_T2 - 350.0                   # eje de columnas de la reja de la cinta
Z_NORTE_INT = ORG_A[2] + 866.0          # reja norte interna de la celda A
SEP_REJA, SEP_PILAS = 300.0, 250.0      # libres entre caras de guías y reja / entre pilas
MEDIO_Z = PAL[1] / 2 + LUZ + GUIA       # del centro de la pila a la cara exterior de las guías (Z)
MEDIO_X = PAL[0] / 2 + LUZ + GUIA
Z1 = Z_REJA - 90.0 - SEP_REJA - MEDIO_Z
Z2 = Z1 - 2 * MEDIO_Z - SEP_PILAS
PILAS = ((X_PILA, Z1), (X_PILA, Z2))
# pórticos de soporte del riel
Y_RIEL_INF = 1980.0
COL = 150.0
X_COL = (-11664.0 + 5.0 + COL / 2, -9617.0)      # la del lado pared, corrida contra la pared
Z_PORT = (-31350.0 - COL / 2, (Z1 - MEDIO_Z + Z2 + MEDIO_Z) / 2)
# ---- puerta
X_PARED = (-11814.2, -11664.2)
Z_PARED_PASILLO = -29790.2              # cara interior de la pared a lo largo del pasillo
ANCHO_VANO, ALTO_VANO, JAMBA = 900.0, 2100.0, 50.0
app = inv._inventor(start_if_needed=False)
tg = app.TransientGeometry
log = {"avisos": [], "pilas_centro": [list(p) for p in PILAS]}


def mmake(M):
    m = tg.CreateMatrix()
    m.SetCoordinateSystem(tg.CreatePoint(M[0][3] / 10, M[1][3] / 10, M[2][3] / 10),
                          tg.CreateVector(M[0][0], M[1][0], M[2][0]), tg.CreateVector(M[0][1], M[1][1], M[2][1]),
                          tg.CreateVector(M[0][2], M[1][2], M[2][2]))
    return m


def rel(x, y, z):
    return [[1, 0, 0, x - ORG_A[0]], [0, 1, 0, y - ORG_A[1]], [0, 0, 1, z - ORG_A[2]]]


def abrir(p):
    d = next((d for d in inv._items(app.Documents) if S(lambda: Path(d.FullFileName).resolve() == p.resolve(), False)), None)
    return d or app.Documents.Open(str(p), False)


def caja(o):
    b = o.RangeBox
    return [round(v * 10, 1) for v in (b.MinPoint.X, b.MinPoint.Y, b.MinPoint.Z, b.MaxPoint.X, b.MaxPoint.Y, b.MaxPoint.Z)]


app.SilentOperation = True
try:
    g = Gen(app, PIEZAS)
    guia = g.caja(f"Guia_buffer_{GUIA:g}x{GUIA:g}_H{H_GUIA:g}", GUIA, H_GUIA, GUIA,
                  f"Columna guía de pila de pallets, caño {GUIA:g}x{GUIA:g}, H={H_GUIA:g}", ["blanco"])
    placa = g.caja("Placa_anclaje_200x200x10", 200.0, 10.0, 200.0, "Placa de anclaje 200x200x10 (4 brocas)", ["gris", "acero"])
    col = g.caja(f"Columna_portico_buffer_H{Y_RIEL_INF:g}", COL, Y_RIEL_INF - COL, COL, "Columna de pórtico 150x150", ["acero"])
    L_tr = abs(X_COL[1] - X_COL[0]) + COL
    trav = g.caja(f"Travesano_portico_buffer_L{round(L_tr)}", L_tr, COL, COL, f"Travesaño de pórtico 150x150 L={L_tr:.0f}", ["acero"])
    jamba = g.caja(f"Puerta_jamba_{X_PARED[1] - X_PARED[0]:.0f}x{JAMBA:g}_H{ALTO_VANO:g}", X_PARED[1] - X_PARED[0], ALTO_VANO,
                   JAMBA, "Marco de puerta de paso (jamba)", ["gris oscuro", "gris"])
    dintel = g.caja(f"Puerta_dintel_{X_PARED[1] - X_PARED[0]:.0f}x{JAMBA:g}_L{ANCHO_VANO:g}", X_PARED[1] - X_PARED[0], JAMBA,
                    ANCHO_VANO, "Marco de puerta de paso (dintel)", ["gris oscuro", "gris"])
    hoja = g.caja(f"Puerta_hoja_40x{ALTO_VANO - JAMBA - 10:g}x{ANCHO_VANO - 2 * JAMBA:g}", 40.0, ALTO_VANO - JAMBA - 10,
                  ANCHO_VANO - 2 * JAMBA, "Hoja de puerta de paso 800 (abre hacia afuera)", ["azul", "gris"])

    # ------------------------------------------------------------ buffers en el robot aéreo
    rob = abrir(ROBOT)
    rcd = rob.ComponentDefinition
    quit_ = 0
    for o in list(inv._items(rcd.Occurrences)):
        if o.Name.startswith(("Pila", "Guia_buffer", "Placa_buffer", "Portico_buffer")):
            o.Delete()
            quit_ += 1
    log["robot_quitadas"] = quit_
    tmp = rcd.Occurrences.Add(str(PALLET_IPT), mmake([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0]]))
    rob.Update()
    b = caja(tmp)
    off = (-(b[0] + b[3]) / 2, -b[1], -(b[2] + b[5]) / 2)
    ph = b[4] - b[1]
    tmp.Delete()

    def add(doc_cd, ruta, nombre, x, y, z):
        o = doc_cd.Occurrences.Add(str(ruta), mmake(rel(x, y, z)))
        S(lambda: setattr(o, "Name", nombre))
        S(lambda: setattr(o, "Grounded", True))
        return o

    for i, (cx, cz) in enumerate(PILAS):
        for k in range(N_PAL):
            add(rcd, PALLET_IPT, f"Pila{i + 1}_pallet_{k + 1}", cx + off[0], k * ph + off[1], cz + off[2])
        dx, dz = PAL[0] / 2 + LUZ + GUIA / 2, PAL[1] / 2 + LUZ + GUIA / 2
        for j, (sx, sz) in enumerate(((-1, -1), (-1, 1), (1, -1), (1, 1))):
            add(rcd, placa, f"Placa_buffer_{i + 1}_{j + 1}", cx + sx * dx, 0.0, cz + sz * dz)
            add(rcd, guia, f"Guia_buffer_{i + 1}_{j + 1}", cx + sx * dx, 10.0, cz + sz * dz)
    for j, zp in enumerate(Z_PORT):
        for k, xp in enumerate(X_COL):
            add(rcd, col, f"Portico_buffer_{j + 1}_col_{'ab'[k]}", xp, 0.0, zp)
        add(rcd, trav, f"Portico_buffer_{j + 1}_travesano", (X_COL[0] + X_COL[1]) / 2, Y_RIEL_INF - COL, zp)
    rob.Update()
    rob.Save()
    log["alto_pila_mm"] = round(N_PAL * ph)
    log["pallet_alto"] = round(ph, 1)
    log["porticos_Z"] = [round(v) for v in Z_PORT]
    log["guias_caras_Z"] = [[round(cz + MEDIO_Z), round(cz - MEDIO_Z)] for _, cz in PILAS]
    log["libre_a_reja_norte_interna"] = round((Z2 - MEDIO_Z) - (Z_NORTE_INT + 90.0))
    log["libre_a_reja_cinta"] = round((Z_REJA - 90.0) - (Z1 + MEDIO_Z))
    if (Z2 - MEDIO_Z) - (Z_NORTE_INT + 90.0) < 100:
        log["avisos"].append("la pila 2 queda a menos de 100 mm de la reja norte interna de la celda")
    if N_PAL * ph > 1680 - ph:
        log["avisos"].append(f"pila de {N_PAL} = {N_PAL * ph:.0f} mm: más alta que el pallet en transporte (1528-1680): "
                             "el robot no puede pasar por encima de una pila llena")

    # ------------------------------------------------------------ puerta de paso en la pared (celda A)
    cel = abrir(CELDA)
    ccd = cel.ComponentDefinition
    for o in list(inv._items(ccd.Occurrences)):
        if o.Name.startswith("Puerta_paso"):
            o.Delete()
    xw = (X_PARED[0] + X_PARED[1]) / 2
    z_n = Z_PARED_PASILLO - 50.0                     # jamba norte a 50 de la esquina
    z_s = z_n - ANCHO_VANO
    add(ccd, jamba, "Puerta_paso_jamba_N", xw, 0.0, z_n - JAMBA / 2)
    add(ccd, jamba, "Puerta_paso_jamba_S", xw, 0.0, z_s + JAMBA / 2)
    add(ccd, dintel, "Puerta_paso_dintel", xw, ALTO_VANO - JAMBA, (z_n + z_s) / 2)
    add(ccd, hoja, "Puerta_paso_hoja", X_PARED[0] + 20.0, 5.0, (z_n + z_s) / 2)
    cel.Update()
    cel.Save()
    log["puerta"] = {"X_pared": X_PARED, "Z_vano": [round(z_s), round(z_n)], "paso_libre": ANCHO_VANO - 2 * JAMBA,
                     "libre_motor_T2b_a_pared": round(Z_PARED_PASILLO - (Z_T2 + 302.0))}
finally:
    S(lambda: setattr(app, "SilentOperation", False))
print(json.dumps(log, ensure_ascii=False, indent=1))
