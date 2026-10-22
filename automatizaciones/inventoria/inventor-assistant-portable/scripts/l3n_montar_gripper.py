"""Celda A: reemplaza el gripper de ADECO2 por el gripper generado, alineando el centro de la cara superior de la
brida (cara de montaje al robot) y conservando la orientación del gripper viejo. Verifica que la brida nueva quede
concéntrica con la brida del robot (eslabón V05) y mide la distancia. Edita Celda_A_L3N.iam (archivo propio).
Uso: python l3n_montar_gripper.py <gripper_nuevo.iam> [--giro-grados 0] [--en-brida]
"""
import atexit
import json
import math
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
import inventor_mcp as inv  # noqa: E402

S = inv._safe
CELDA = Path(r"C:\DEFYMOTION\L3N\Celdas_IA\Celda_A_L3N.iam")
NUEVO = Path(sys.argv[1])
GIRO = float(sys.argv[sys.argv.index("--giro-grados") + 1]) if "--giro-grados" in sys.argv else 0.0
app = inv._inventor(start_if_needed=False)
atexit.register(lambda: S(lambda: setattr(app, "SilentOperation", False)))
app.SilentOperation = True
tg = app.TransientGeometry
log = {"avisos": []}


def abrir(p, vis=False):
    d = next((d for d in inv._items(app.Documents) if S(lambda: Path(d.FullFileName).resolve() == p.resolve(), False)), None)
    return d or app.Documents.Open(str(p), vis)


def caja(o):
    b = o.RangeBox
    return [b.MinPoint.X * 10, b.MinPoint.Y * 10, b.MinPoint.Z * 10, b.MaxPoint.X * 10, b.MaxPoint.Y * 10, b.MaxPoint.Z * 10]


def mread(m):
    return [[m.Cell(r, c) * (10 if c == 4 else 1) for c in range(1, 5)] for r in range(1, 4)]


def mmake(M):
    m = tg.CreateMatrix()
    m.SetCoordinateSystem(tg.CreatePoint(M[0][3] / 10, M[1][3] / 10, M[2][3] / 10),
                          tg.CreateVector(M[0][0], M[1][0], M[2][0]), tg.CreateVector(M[0][1], M[1][1], M[2][1]),
                          tg.CreateVector(M[0][2], M[1][2], M[2][2]))
    return m


def mul(A, B):
    A4 = A + [[0, 0, 0, 1]]
    B4 = B + [[0, 0, 0, 1]]
    return [[sum(A4[i][k] * B4[k][j] for k in range(4)) for j in range(4)] for i in range(3)]


def buscar(occ, pref, prof=0):
    for s in inv._items(occ.SubOccurrences):
        if s.Name.lower().startswith(pref):
            return s
        if prof < 2 and S(lambda: s.SubOccurrences.Count, 0):
            r = buscar(s, pref, prof + 1)
            if r is not None:
                return r
    return None


def centro_sup(c):
    return [(c[0] + c[3]) / 2, c[4], (c[2] + c[5]) / 2]


cel = abrir(CELDA)
cd = cel.ComponentDefinition
occ = {o.Name: o for o in inv._items(cd.Occurrences)}
viejo = next((o for n, o in occ.items() if n.startswith("Gripper_ADECO2")), None)
if viejo is None:
    sys.exit("No encontré el gripper viejo en la celda A")
M_old = mread(viejo.Transformation)
brida_vieja = buscar(viejo, "brida")
c_old = centro_sup(caja(brida_vieja)) if brida_vieja is not None else centro_sup(caja(viejo))
log["viejo"] = {"n": viejo.Name, "brida": S(lambda: brida_vieja.Name), "centro_sup_brida": [round(v) for v in c_old],
                "caja": [round(v) for v in caja(viejo)]}
# brida del robot: eslabón V05 (último) del KUKA
robot = next(o for n, o in occ.items() if n.startswith("KUKA"))
v05 = buscar(robot, "kr_140_r3200-2_pa_v05") or buscar(robot, "kr_140_r3200-2_pa_v05".replace("_", " "))
log["robot_v05"] = S(lambda: [round(v) for v in caja(v05)])
if "--en-brida" in sys.argv and v05 is not None:
    # montar en la brida del robot: centro del círculo de agujeros del eslabón V05 relevado con
    # analizar_brida_kr.py (local del .ipt: (1850, 0, 1745), normal +Z), llevado al ensamble de la celda.
    # La cara superior de la brida del gripper (+Y en el sistema de ADECO2) mira contra la brida del robot (-n).
    Mv = mread(v05.Transformation)
    PL, NL = (1850.0, 0.0, 1745.0), (0.0, 0.0, -1.0)   # la brida mira hacia -Z local (verificado con foto)
    P = [sum(Mv[i][k] * PL[k] for k in range(3)) + Mv[i][3] for i in range(3)]
    n = [sum(Mv[i][k] * NL[k] for k in range(3)) for i in range(3)]
    up = [-v for v in n]                                  # +Y del gripper (ADECO2) = hacia el robot
    # largo del gripper: lo más cercano a X del mundo, perpendicular a 'up'
    xw = [1.0, 0.0, 0.0]
    d = sum(xw[i] * up[i] for i in range(3))
    lx = [xw[i] - d * up[i] for i in range(3)]
    nl = math.sqrt(sum(v * v for v in lx)) or 1.0
    lx = [v / nl for v in lx]
    zz = [lx[1] * up[2] - lx[2] * up[1], lx[2] * up[0] - lx[0] * up[2], lx[0] * up[1] - lx[1] * up[0]]   # X × Y
    M_old = [[lx[i], up[i], zz[i], 0.0] for i in range(3)]
    c_old = P
    log["montaje"] = {"en": "brida V05 (círculo de agujeros)", "centro": [round(v) for v in P], "normal": [round(v, 3) for v in n]}

# gripper nuevo: insertar provisorio en el origen para medir su brida en coordenadas locales
tmp = next((o for n, o in occ.items() if n.startswith(NUEVO.stem)), None)   # resto de una corrida anterior
if tmp is not None:
    S(lambda: setattr(tmp, "Grounded", False))
    tmp.SetTransformWithoutConstraints(mmake([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0]]))
else:
    tmp = cd.Occurrences.Add(str(NUEVO), mmake([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0]]))
cel.Update()
brida_nueva = buscar(tmp, "brida")
cb = caja(brida_nueva)
# El gripper generado tiene el largo en +Y local, la cara de montaje de la brida en z mínimo (normal -Z) y las
# palas hacia +Z. El de ADECO2 tiene el largo en +X local, la brida arriba (+Y) y las palas hacia -Y.
c_new = [(cb[0] + cb[3]) / 2, (cb[1] + cb[4]) / 2, cb[2]]       # centro de la cara de montaje (local nuevo)
log["nuevo"] = {"centro_montaje_local": [round(v) for v in c_new], "caja_local": [round(v) for v in caja(tmp)]}
RN2O = [[0, 1, 0], [0, 0, -1], [-1, 0, 0]]                       # local nuevo -> local ADECO2 (X=largo, Y=arriba)
R_old = [row[:3] for row in M_old]
R = [[sum(R_old[i][k] * RN2O[k][j] for k in range(3)) for j in range(3)] for i in range(3)]
if GIRO:                                                          # giro alrededor del eje de la brida (Y de ADECO2)
    a = math.radians(GIRO)
    Rg = [[math.cos(a), 0, math.sin(a)], [0, 1, 0], [-math.sin(a), 0, math.cos(a)]]
    R = [[sum(R_old[i][k] * sum(Rg[k][m] * RN2O[m][j] for m in range(3)) for k in range(3)) for j in range(3)] for i in range(3)]
# traslación: R·c_new + t = c_old
t = [c_old[i] - sum(R[i][k] * c_new[k] for k in range(3)) for i in range(3)]
M_new = [R[i] + [t[i]] for i in range(3)]
try:
    viejo.Delete()
    log["viejo"]["accion"] = "borrado"
except Exception:  # noqa: BLE001  (Delete falla a veces con el layout abierto: se suprime)
    S(lambda: viejo.Suppress())
    S(lambda: setattr(viejo, "Name", "Gripper_ADECO2_V1_reemplazado"))
    log["viejo"]["accion"] = "suprimido"
nuevo = tmp                       # se reubica la misma ocurrencia (Delete de una recién agregada falla)
log["M_old"] = [[round(v, 4) for v in r] for r in M_old]
log["M_new"] = [[round(v, 4) for v in r] for r in M_new]
nuevo.SetTransformWithoutConstraints(mmake(M_new))   # (Transformation = ... falla con el layout abierto)
S(lambda: setattr(nuevo, "Name", "IA_Gripper_7xTBA250"))
if not S(lambda: setattr(nuevo, "Grounded", True), False):
    log["avisos"].append("No se pudo fijar (Grounded) el gripper nuevo")
cel.Update()
cel.Save()
bn = buscar(nuevo, "brida")
cbn = caja(bn)
cs = [(cbn[0] + cbn[3]) / 2, cbn[4], (cbn[2] + cbn[5]) / 2]   # en el mundo la cara de montaje queda arriba (y máx)
log["resultado"] = {"centro_sup_brida": [round(v) for v in cs], "desvio_mm": [round(cs[i] - c_old[i], 1) for i in range(3)],
                    "caja_gripper": [round(v) for v in caja(nuevo)], "giro_grados": GIRO}
if v05 is not None:
    cv = caja(v05)
    log["resultado"]["robot_v05_min_y"] = round(cv[1])
    log["resultado"]["brida_vs_v05_xz"] = [round(cs[0] - (cv[0] + cv[3]) / 2), round(cs[2] - (cv[2] + cv[5]) / 2)]
print(json.dumps(log, ensure_ascii=False, indent=1))
