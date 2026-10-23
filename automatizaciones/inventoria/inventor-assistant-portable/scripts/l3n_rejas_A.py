"""L3N: arma el cerco de la celda A (o C) con las rejas Fademaq de la celda B (CP1512: columnas 180x180 de 1955 y
paneles 03 de 1240 x 900 en dos alturas), RESPETANDO el área de cercamiento planteada en el layout original
(las líneas de las "Puerta estándar" genéricas de 2262 de alto, que chocaban con el riel del robot aéreo).
Líneas (relativas a la giratoria de la celda, mm): sur z -2905 (x -5127..-859), este x -935 (z -2981..-695),
norte interna z +866 (x -5127..-859), norte lejana z +4518 (x -5215..+1796). Lado oeste abierto (entra la cinta).
En A (23/10) la norte lejana se reemplaza por la reja que protege la cinta T2 hasta la Curva_1 (ver LINEAS).
Edita Celda_A_L3N.iam / Celda_C_existente.iam (archivos propios). Uso: python l3n_rejas_A.py [A|C] [--zt2 Z]
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
BASE = Path(r"C:\DEFYMOTION\L3N\Celdas_IA")
CUAL = (sys.argv[1] if len(sys.argv) > 1 else "A").upper()
CELDA = BASE / ("Celda_A_L3N.iam" if CUAL == "A" else "Celda_C_existente.iam")
CELDA_B = BASE / "Celda_B_existente.iam"
PASO_MAX = 1320.0            # paso entre columnas en la celda B
LINEAS = [  # (nombre, p0, p1) en (x, z) relativos a la giratoria
    ("Sur", (-5127.0, -2905.0), (-859.0, -2905.0)),
    ("Este", (-935.0, -2981.0), (-935.0, -695.0)),
    ("Norte_interna", (-5127.0, 866.0), (-859.0, 866.0)),
    ("Norte_lejana", (-5215.0, 4518.0), (1796.0, 4518.0)),
]
if CUAL == "A":
    # 23/10: la reja norte lejana pasa a proteger la cinta de llegada T2: a 100 mm del bastidor (eje de columnas a
    # 350 del eje de T2), desde la pared (cara este X -11664) hasta la Curva_1, y la rodea por afuera junto a T1.
    ORG = (-6503.2, -35622.3)
    Z_T2 = float(sys.argv[sys.argv.index("--zt2") + 1]) if "--zt2" in sys.argv else -30894.0
    zf = Z_T2 - 350.0 - ORG[1]
    x_ini = -11664.0 + 90.0 - ORG[0]                 # columna apoyada contra la pared
    x_esq = 4363.0 + 302.0 + 100.0 + 90.0 - ORG[0]   # afuera del motor de T1 (+X)
    z_fin = Z_T2 + 475.0 + 1000.0 - ORG[1]           # pasando la curva y el motor de T1
    LINEAS[3] = ("Cinta_T2", (x_ini, zf), (x_esq, zf))
    LINEAS.append(("Cinta_C1", (x_esq, zf), (x_esq, z_fin)))
app = inv._inventor(start_if_needed=False)
atexit.register(lambda: S(lambda: setattr(app, "SilentOperation", False)))
app.SilentOperation = True
tg = app.TransientGeometry
log = {"avisos": []}


def abrir(p):
    d = next((d for d in inv._items(app.Documents) if S(lambda: Path(d.FullFileName).resolve() == p.resolve(), False)), None)
    return d or app.Documents.Open(str(p), False)


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


# ---- 1. plantillas desde el cerco de B: columna, panel bajo/alto a lo largo de X y a lo largo de Z
B = abrir(CELDA_B)
lay = next(o for o in inv._items(B.ComponentDefinition.Occurrences) if o.Name.startswith("ADECOAGRO2_Layout"))
cerco = next(o for o in inv._items(lay.SubOccurrences) if o.Name.startswith("Cerco Perimetral"))
T = {}
for s in inv._items(cerco.SubOccurrences):
    if S(lambda: s.Suppressed, False):
        continue
    c = caja(s)
    n = s.Name
    cen = ((c[0] + c[3]) / 2, c[1], (c[2] + c[5]) / 2)   # centro en X/Z, base en Y
    plantilla = {"archivo": s.ReferencedDocumentDescriptor.FullDocumentName, "M": mread(s.Transformation), "cen": cen,
                 "dx": c[3] - c[0], "dz": c[5] - c[2], "y0": c[1], "y1": c[4]}
    if n.startswith("Ensamblaje Columna_") and "col" not in T:
        T["col"] = plantilla
    elif n.startswith("Panel 03"):
        a_lo_largo = "X" if plantilla["dx"] > plantilla["dz"] else "Z"
        nivel = "bajo" if c[1] < 600 else "alto"
        T.setdefault(f"panel_{a_lo_largo}_{nivel}", plantilla)
faltan = [k for k in ("col", "panel_X_bajo", "panel_X_alto", "panel_Z_bajo", "panel_Z_alto") if k not in T]
if faltan:
    sys.exit(f"Faltan plantillas en el cerco de B: {faltan}")
log["plantillas"] = {k: {"archivo": Path(v["archivo"]).name, "ancho": round(max(v["dx"], v["dz"])), "alto": round(v["y1"] - v["y0"])}
                     for k, v in T.items()}

# ---- 2. celda: quitar genéricas / rejas previas y construir las líneas
A = abrir(CELDA)
acd = A.ComponentDefinition
quitados = 0
for o in list(inv._items(acd.Occurrences)):
    if o.Name.startswith(("Puerta estándar", "Reja_")):
        o.Delete()
        quitados += 1
n_puestos = 0


def poner(clave, cx, cz, nombre):
    """Copia la plantilla con su centro (X/Z) en (cx, cz) y la base en el piso; misma orientación."""
    global n_puestos
    t = T[clave]
    M = [r[:] for r in t["M"]]
    M[0][3] += cx - t["cen"][0]
    M[1][3] += 0.0 - T["col"]["y0"]          # la columna apoya en el piso; los paneles conservan su altura
    M[2][3] += cz - t["cen"][2]
    o = acd.Occurrences.Add(t["archivo"], mmake(M))
    S(lambda: setattr(o, "Name", nombre))
    o.Grounded = True
    n_puestos += 1


detalle = []
cols_puestas = []
for nombre, p0, p1 in LINEAS:
    dx, dz = p1[0] - p0[0], p1[1] - p0[1]
    L = math.hypot(dx, dz)
    eje = "X" if abs(dx) >= abs(dz) else "Z"
    nb = max(1, math.ceil(L / PASO_MAX))
    paso = L / nb
    ux, uz = dx / L, dz / L
    for i in range(nb + 1):
        cx, cz = p0[0] + ux * paso * i, p0[1] + uz * paso * i
        if any(abs(cx - a) < 1 and abs(cz - b) < 1 for a, b in cols_puestas):
            continue                               # esquina compartida con la línea anterior
        cols_puestas.append((cx, cz))
        poner("col", cx, cz, f"Reja_{nombre}_col_{i + 1}")
    for i in range(nb):
        sm = paso * (i + 0.5)
        cx, cz = p0[0] + ux * sm, p0[1] + uz * sm
        poner(f"panel_{eje}_bajo", cx, cz, f"Reja_{nombre}_panel_bajo_{i + 1}")
        poner(f"panel_{eje}_alto", cx, cz, f"Reja_{nombre}_panel_alto_{i + 1}")
    detalle.append({"linea": nombre, "largo": round(L), "bahias": nb, "paso": round(paso)})
A.Update()
A.Save()
rejas = [caja(o) for o in inv._items(acd.Occurrences) if o.Name.startswith("Reja_")]
log["celda"] = {"archivo": str(CELDA), "quitados": quitados, "puestos": n_puestos, "lineas": detalle,
                "alto_max": round(max(c[4] for c in rejas))}
print(json.dumps(log, ensure_ascii=False, indent=1))
