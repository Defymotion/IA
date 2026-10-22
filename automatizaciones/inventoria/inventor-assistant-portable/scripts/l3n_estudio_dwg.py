"""L3N Paletizado (Adecoagro Chivilcoy): arma una COPIA de estudio del layout ajustada al plano DWG de planta.

No toca originales: guarda copias (primero el subensamble, después el principal) en C:\\DEFYMOTION\\L3N\\Estudio_IA\\.
Cambios sobre la copia:
  - suprime las restricciones del principal y deja fijas las ocurrencias (posiciones absolutas);
  - celda B (ADECOAGRO_Chivilcoy:1) a 8,36 m de A; celda C a 6,59 m de B y a nivel de piso;
  - en la copia del subensamble de B se suprimen la mesa giratoria de C y sus camas (se ponen nuevas en el principal);
  - línea de pallets: envolvedora a 16,27 m y mesa giratoria final a 21,09 m de A (sin la giratoria intermedia);
  - cinta de llegada de la celda A (alcance Defy) con bandas modulares de la biblioteca "Cintas Transportadoras",
    siguiendo el recorrido del DWG desde la embandejadora CBP34;
  - freno de cajas (cinta de llegada) de la celda C en la misma posición relativa que en la celda A.
Uso: python l3n_estudio_dwg.py [--rehacer]
"""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
import inventor_mcp as inv  # noqa: E402

S = inv._safe
ORIG = Path(r"C:\DEFYMOTION\L3N\LayoutL3N_Principal.iam")
OUT = Path(r"C:\DEFYMOTION\L3N\Estudio_IA")
TOP = OUT / "LayoutL3N_Estudio_DWG.iam"
SUB = OUT / "ADECOAGRO_Chivilcoy_Estudio_DWG.iam"
BM = Path.home() / "Documents" / "InventorIA" / "Cintas Transportadoras"
MOD = {  # paso (largo total del módulo, mm) y xmin local, medidos con medir_ensambles.py (p009)
    "BM2400": (BM / "Banda Modular 2400" / "Ensamblaje BM2400.iam", 2620.7, -1224.0),
    "BM2260": (BM / "Banda Modular 2260" / "Ensamblaje BM2260.iam", 2481.6, -1154.2),
    "BM2000": (BM / "Banda Modular 2000" / "Ensamblaje BM2000.iam", 2225.7, -1024.2),
    "BM1800": (BM / "Banda Modular 1800" / "Ensamblaje BM1800.iam", 2021.6, -924.0),
}
BANDA_Y_LOCAL = 372.0      # cara superior de la banda en coordenadas del módulo
BANDA_Z_LOCAL = -75.0      # eje de la banda (entre laterales)
BANDA_Y_OBJ = 800.0        # altura de transporte buscada (curvas/freno de las celdas ~ 800-850)

# --- plano DWG (m) -> Inventor (mm). Ancla: centro de la giratoria A
DWG_A = (3843.973, 1293.966)
INV_A = (-6503.2, -35622.3)


def dwg2inv(x, y):
    return INV_A[0] + (DWG_A[1] - y) * 1000.0, INV_A[1] - (x - DWG_A[0]) * 1000.0  # (X, Z)


app = inv._inventor(start_if_needed=False)
import atexit  # noqa: E402
atexit.register(lambda: S(lambda: setattr(app, "SilentOperation", False)))
app.SilentOperation = True
tg = app.TransientGeometry
log = {"avisos": []}


def mmake(M):
    m = tg.CreateMatrix()
    m.SetCoordinateSystem(tg.CreatePoint(M[0][3] / 10, M[1][3] / 10, M[2][3] / 10),
                          tg.CreateVector(M[0][0], M[1][0], M[2][0]), tg.CreateVector(M[0][1], M[1][1], M[2][1]),
                          tg.CreateVector(M[0][2], M[1][2], M[2][2]))
    return m


def mread(m):
    return [[m.Cell(r, c) * (10 if c == 4 else 1) for c in range(1, 5)] for r in range(1, 4)]


def mover(o, dx=0.0, dy=0.0, dz=0.0, y_abs=None):
    M = mread(o.Transformation)
    M[0][3] += dx
    M[1][3] = y_abs if y_abs is not None else M[1][3] + dy
    M[2][3] += dz
    S(lambda: setattr(o, "Grounded", False))
    o.Transformation = mmake(M)
    o.Grounded = True


def agregar(cd, archivo, M, nombre):
    o = cd.Occurrences.Add(str(archivo), mmake(M))
    S(lambda: setattr(o, "Name", nombre))
    o.Grounded = True
    return o


FAMILIA = None  # una sola familia BM: las carpetas comparten nombres de archivo y Inventor no abre dos iguales


def combinacion(largo):
    """Cantidad de módulos de la familia elegida que entran en el largo (sobrante >= 0)."""
    paso = MOD[FAMILIA][1]
    n = int(largo // paso)
    return largo - n * paso, [FAMILIA] * n


def tramo(cd, nombre, p0, p1):
    """Bandas modulares en línea recta de p0 a p1 (X, Z en mm, eje de banda), flujo p0 -> p1."""
    dx, dz = p1[0] - p0[0], p1[1] - p0[1]
    largo = (dx * dx + dz * dz) ** 0.5
    d = (dx / largo, 0.0, dz / largo)
    n = (d[1] * 0 - d[2] * 1, d[2] * 0 - d[0] * 0, d[0] * 1 - d[1] * 0)  # d x Y
    sobra, mods = combinacion(largo)
    s = 0.0
    puestos = []
    for i, k in enumerate(mods):
        f, paso, xmin = MOD[k]
        px, pz = p0[0] + d[0] * s, p0[1] + d[2] * s
        org = (px - d[0] * xmin - n[0] * BANDA_Z_LOCAL, BANDA_Y_OBJ - BANDA_Y_LOCAL, pz - d[2] * xmin - n[2] * BANDA_Z_LOCAL)
        M = [[d[0], 0.0, n[0], org[0]], [d[1], 1.0, n[1], org[1]], [d[2], 0.0, n[2], org[2]]]
        agregar(cd, f, M, f"IA_{nombre}_{i + 1}_{k}")
        puestos.append(k)
        s += paso
    return {"tramo": nombre, "largo_mm": round(largo), "modulos": puestos, "sobrante_mm": round(sobra)}


# ---------------------------------------------------------------- 1. copias (subensamble primero)
for d in inv._items(app.Documents):
    if S(lambda: Path(d.FullFileName).resolve() == ORIG.resolve(), False):
        if d.Dirty:
            sys.exit("El layout original está abierto con cambios sin guardar: no sigo.")
        d.Close(True)
OUT.mkdir(parents=True, exist_ok=True)
if "--rehacer" in sys.argv:   # sólo documentos y archivos propios de Estudio_IA
    for d in list(inv._items(app.Documents)):
        if str(S(lambda: d.FullFileName, "")).lower().startswith(str(OUT).lower() + "\\"):
            S(lambda: d.Close(True))
    for p in (TOP, SUB):
        if p.exists():
            p.unlink()
for p in (TOP, SUB):
    if p.exists():
        sys.exit(f"Ya existe {p}: no lo piso. Usá --rehacer.")
doc = app.Documents.Open(str(ORIG), True)
cd = doc.ComponentDefinition
occ = {o.Name: o for o in inv._items(cd.Occurrences)}
B = occ["ADECOAGRO_Chivilcoy:1"]
sub = B.Definition.Document
sub.SaveAs(str(SUB), False)   # desde acá el subensamble en memoria es la copia
doc.SaveAs(str(TOP), False)   # y el principal (copia) la referencia
log["copias"] = [str(SUB), str(TOP)]

# datos de la celda B antes de mover (contexto del principal)
subocc = {s.Name: s for s in inv._items(B.SubOccurrences)}
M_gir_C = mread(subocc["roller conveyor - rotating:2"].Transformation)
M_roll_BC = mread(subocc["Roller_Conveyor_Straight_400V_FlatBelt:8"].Transformation)
ROLL_FILE = subocc["Roller_Conveyor_Straight_400V_FlatBelt:8"].Definition.Document.FullFileName
GIR_FILE = subocc["roller conveyor - rotating:2"].Definition.Document.FullFileName
A = occ["ADECOAGRO_Chivilcoy - L3N_Linea3:2"]
freno_A = next(s for s in inv._items(A.SubOccurrences) if s.Name.startswith("Ensamble freno de cajas"))
M_freno_A = mread(freno_A.Transformation)
FRENO_FILE = freno_A.Definition.Document.FullFileName

# en la copia del subensamble: suprimir giratoria de C y sus camas
scd = sub.ComponentDefinition
for o in inv._items(scd.Occurrences):
    if o.Name in ("roller conveyor - rotating:2", "Roller_Conveyor_Straight_400V_FlatBelt:8",
                  "Roller_Conveyor_Straight_400V_FlatBelt:9"):
        o.Suppress()
sub.Save()

# ---------------------------------------------------------------- 2. restricciones fuera, todo fijo
n_sup = 0
for c in inv._items(cd.Constraints):
    if not S(lambda: c.Suppressed, True):
        S(lambda: setattr(c, "Suppressed", True))
        n_sup += 1
log["restricciones_suprimidas"] = n_sup
for o in inv._items(cd.Occurrences):
    S(lambda: setattr(o, "Grounded", True))

# ---------------------------------------------------------------- 3. celdas
Z_A = INV_A[1]
Z_B = Z_A - 8360.0
Z_C = Z_B - 6590.0
dz_B = Z_B - (-43314.343)
mover(B, dz=dz_B)
C = occ["ADECOAGRO_Chivilcoy - L3N_Linea3:3"]
dz_C = Z_C - M_gir_C[2][3]
y_A = mread(A.Transformation)[1][3]
mover(C, dz=dz_C, y_abs=y_A)
log["celdas"] = {"B_dz_mm": round(dz_B), "C_dz_mm": round(dz_C), "C_y_mm": round(y_A, 1)}

# giratoria C y cama B->C en el principal, a nivel de piso
M = [r[:] for r in M_gir_C]
M[1][3] = 230.5           # misma altura que las giratorias A y B
M[2][3] = Z_C
agregar(cd, GIR_FILE, M, "IA_Giratoria_C")
M = [r[:] for r in M_roll_BC]
M[2][3] = Z_C + 990.0 - 150.0          # origen = zmin; 150 mm de solape sobre la giratoria, como las demás
agregar(cd, ROLL_FILE, M, "IA_Cama_BC_1")
fin_B = -46144.343 + dz_B              # zmin de la cama de B hacia C (ya movida)
log["avisos"].append(f"Tramo B->C sin cama: {round(fin_B - (M[2][3] + 2038.0))} mm (cama a medida)")
log["avisos"].append(f"Tramo A->B sin cama: {round(-38478.343 - (-38420.343 + dz_B))} mm (cama a medida)")

# freno de cajas de la celda C (misma posición relativa que en A)
dCx = mread(C.Transformation)[0][3] - mread(A.Transformation)[0][3]
dCz = mread(C.Transformation)[2][3] - mread(A.Transformation)[2][3]
M = [r[:] for r in M_freno_A]
M[0][3] += dCx
M[2][3] += dCz
agregar(cd, FRENO_FILE, M, "IA_Freno_cajas_C")

# ---------------------------------------------------------------- 4. línea de pallets
X_GA = INV_A[0]
dx_env = (X_GA + 16270.0) - 3351.1
dx_fin = (X_GA + 21090.0) - 7296.8
mover(occ["MP402:1"], dx=dx_env)
mover(occ["roller conveyor - rotating:2"], dx=dx_fin)
mover(occ["Roller_Conveyor_Straight_400V_FlatBelt:10"], dx=dx_fin)
M9 = mread(occ["Roller_Conveyor_Straight_400V_FlatBelt:9"].Transformation)
x_fin_giro = 6271.84 + dx_fin
nuevas = []
k = 1
while True:
    x0 = M9[0][3] + 2000.0 * k
    if x0 + 2038.0 > x_fin_giro + 150.0:
        break
    M = [r[:] for r in M9]
    M[0][3] = x0
    agregar(cd, ROLL_FILE, M, f"IA_Cama_linea_{k}")
    nuevas.append(round(x0))
    k += 1
ult = (nuevas[-1] if nuevas else M9[0][3]) + 2038.0
log["linea"] = {"envolvedora_dx": round(dx_env), "giratoria_final_dx": round(dx_fin), "camas_nuevas_x0": nuevas}
log["avisos"].append(f"Línea de pallets: tramo sin cama de {round(x_fin_giro + 150 - ult)} mm antes de la giratoria final (cama a medida)")

# ---------------------------------------------------------------- 5. cinta de llegada celda A (DWG, CBP34)
X_A1 = dwg2inv(0, 1283.10)[0]          # eje tramo 1 (este, a y=1283,10)
Z_A2 = dwg2inv(3838.88, 0)[1]          # eje tramo 2 (norte, a x=3838,88)
X_A3 = dwg2inv(0, 1299.48)[0]          # eje tramo 3 (este, a y=1299,48)
Z_ini = dwg2inv(3829.273, 0)[1]
Z_fin = freno_A.RangeBox.MaxPoint.Z * 10  # termina sobre el freno de cajas de A
tramos = [((X_A1, Z_ini), (X_A1, Z_A2 + 150.0)), ((X_A1 - 150.0, Z_A2), (X_A3 + 150.0, Z_A2)),
          ((X_A3, Z_A2 - 150.0), (X_A3, Z_fin))]
largos = [abs(b[0] - a[0]) + abs(b[1] - a[1]) for a, b in tramos]
FAMILIA = min(MOD, key=lambda k: sum(L % MOD[k][1] for L in largos))
log["familia_BM"] = FAMILIA
log["cinta_A"] = [
    tramo(cd, "LlegadaA_T1", (X_A1, Z_ini), (X_A1, Z_A2 + 150.0)),
    tramo(cd, "LlegadaA_T2", (X_A1 - 150.0, Z_A2), (X_A3 + 150.0, Z_A2)),
    tramo(cd, "LlegadaA_T3", (X_A3, Z_A2 - 150.0), (X_A3, Z_fin)),
]
log["cinta_A_total_m"] = round(sum(t["largo_mm"] for t in log["cinta_A"]) / 1000, 2)

doc.Update()
doc.Save()
S(lambda: doc.Views.Item(1).Fit())
log["caja_total_mm"] = S(lambda: [round(v * 10) for v in (cd.RangeBox.MinPoint.X, cd.RangeBox.MinPoint.Y, cd.RangeBox.MinPoint.Z,
                                                          cd.RangeBox.MaxPoint.X, cd.RangeBox.MaxPoint.Y, cd.RangeBox.MaxPoint.Z)])
app.SilentOperation = False
print(json.dumps(log, ensure_ascii=False, indent=1))
