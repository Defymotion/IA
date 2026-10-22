"""L3N: robot aéreo de pallets vacíos (modelo de volumen, estimado) en C:\\DEFYMOTION\\L3N\\Celdas_IA\\Robot_Aereo\\.
Geometría en planta tomada del DWG ("TRANSPORTE AÉREO PALLETS VACÍOS"): dos rieles de 22,2 m (X -9797 y -11367),
tres pórticos (patas a 0,72 m) y pilas de pallets al inicio del riel. Alturas: el robot empieza en 2080 mm (perfil
blanco del layout) y va hacia arriba; rieles y pórticos hasta 3600 (recinto de 4000). Piezas como prismas simples.
Inserta `Robot_Aereo_Pallets.iam` en `LayoutL3N_Celdas.iam` (origen = giratoria A, con cotas), saca las pilas de
pallets de `Celda_A_L3N.iam` y la guía vieja de `Linea_Pallets.iam`. Uso: python l3n_robot_aereo.py [--rehacer]
"""
import atexit
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
import inventor_mcp as inv  # noqa: E402

S = inv._safe
BASE = Path(r"C:\DEFYMOTION\L3N\Celdas_IA")
OUT = BASE / "Robot_Aereo"
ROBOT = OUT / "Robot_Aereo_Pallets.iam"
LAYOUT = BASE / "LayoutL3N_Celdas.iam"
CELDA_A = BASE / "Celda_A_L3N.iam"
LINEA = BASE / "Linea_Pallets.iam"
PALLET_IPT = Path(r"C:\DEFYMOTION\L3N\ADECO 12-12-25\European Pallet_3BC37FCD47819CDEC205D0C1A80F9DF2.ipt")
ORG_A = (-6503.2, 0.0, -35622.3)      # origen del ensamble = giratoria A (coordenadas del layout)
DWG_A = (3843.973, 1293.966)
# --- parámetros (mm), estimados salvo los de planta
Y_ROBOT = 2080.0        # el robot empieza acá y va hacia arriba (perfil blanco del layout)
Y_TOP = 3600.0          # cara superior de pórticos y rieles
RIEL = (100.0, 200.0)   # ancho x alto
COL = 150.0             # columna cuadrada
X_RIELES = (-9797.0, -11367.0)
Z_RIEL = (-31350.0, -53550.0)
X_PATAS = (-9617.0, -11617.0)
PORTICOS_DWG = ((3844.75, 3845.47), (3849.70, 3850.40), (3860.83, 3861.56))
CARRO = (1900.0, 450.0, 1200.0)       # X, Y, Z
MASTIL = 220.0
HORQ = (1100.0, 60.0, 120.0)          # largo (Z), alto, ancho; dos horquillas a 600 entre ejes
Z_CARRO = -36100.0                    # posición actual del carro (sobre la celda A)
PILAS = ((-10635.0, -31753.0), (-10635.0, -32953.0))   # centros (X, Z) de las pilas de pallets, 10 c/u


def dwg_z(x):
    return ORG_A[2] - (x - DWG_A[0]) * 1000.0


app = inv._inventor(start_if_needed=False)
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


def trasl(x, y, z):
    return [[1, 0, 0, x], [0, 1, 0, y], [0, 0, 1, z]]


def caja_mm(b):
    return [b.MinPoint.X * 10, b.MinPoint.Y * 10, b.MinPoint.Z * 10, b.MaxPoint.X * 10, b.MaxPoint.Y * 10, b.MaxPoint.Z * 10]


_apar = {}


def apariencia(nombre_parcial):
    if nombre_parcial in _apar:
        return _apar[nombre_parcial]
    ap = None
    for lib in inv._items(app.AssetLibraries):
        for asset in inv._items(S(lambda: lib.AppearanceAssets, []) or []):
            nm = (S(lambda: asset.DisplayName, "") or "").lower()
            if nm.startswith(nombre_parcial):
                ap = asset
                break
        if ap:
            break
    _apar[nombre_parcial] = ap
    return ap


def prisma(nombre, sx, sy, sz, color=None):
    """Pieza prismática sx x sy x sz (mm) con origen en el centro de la base. Devuelve la ruta."""
    ruta = OUT / f"{nombre}.ipt"
    if ruta.exists():
        return ruta
    doc = app.Documents.Add(inv.K_PART_DOCUMENT, app.FileManager.GetTemplateFile(inv.K_PART_DOCUMENT), False)
    cd = doc.ComponentDefinition
    sk = cd.Sketches.Add(cd.WorkPlanes.Item(2))      # XZ
    p1 = sk.ModelToSketchSpace(tg.CreatePoint(-sx / 20, 0, -sz / 20))
    p2 = sk.ModelToSketchSpace(tg.CreatePoint(sx / 20, 0, sz / 20))
    sk.SketchLines.AddAsTwoPointRectangle(p1, p2)
    for direc in (20993, 20994):
        f = cd.Features.ExtrudeFeatures.AddByDistanceExtent(sk.Profiles.AddForSolid(), sy / 10, direc, 20481)
        doc.Update()
        if cd.RangeBox.MaxPoint.Y * 10 > sy - 0.1:
            break
        f.Delete()
    ap = apariencia(color) if color else None
    if ap is not None:
        S(lambda: setattr(doc, "ActiveAppearance", ap.CopyTo(doc)))
    inv._iprop(doc, "Design Tracking Properties", "Part Number", nombre)
    inv._iprop(doc, "Design Tracking Properties", "Description", f"{sx:.0f} x {sy:.0f} x {sz:.0f} mm (volumen estimado)")
    doc.SaveAs(str(ruta), False)
    doc.Close(True)
    return ruta


# ------------------------------------------------------------------ 0. preparación
OUT.mkdir(parents=True, exist_ok=True)
if "--rehacer" in sys.argv:
    for d in list(inv._items(app.Documents)):
        f = str(S(lambda: d.FullFileName, "")).lower()
        if f.startswith(str(OUT).lower() + "\\"):
            S(lambda: d.Close(True))
    for p in OUT.glob("*.i??"):
        p.unlink()
if ROBOT.exists():
    sys.exit(f"Ya existe {ROBOT}: usá --rehacer.")

# ------------------------------------------------------------------ 1. piezas
L_RIEL = Z_RIEL[0] - Z_RIEL[1]
P = {
    "Riel_aereo": prisma("Riel_aereo", RIEL[0], RIEL[1], L_RIEL, "acero"),
    "Columna_portico": prisma("Columna_portico", COL, Y_TOP, COL, "acero"),
    "Travesano_portico": prisma("Travesano_portico", abs(X_PATAS[0] - X_PATAS[1]) + COL, COL, COL, "acero"),
    "Carro_robot": prisma("Carro_robot", CARRO[0], CARRO[1], CARRO[2], "naranja"),
    "Mastil_robot": prisma("Mastil_robot", MASTIL, Y_TOP - RIEL[1] - CARRO[1] - Y_ROBOT, MASTIL, "naranja"),
    "Horquilla_robot": prisma("Horquilla_robot", HORQ[2], HORQ[1], HORQ[0], "acero"),
}
log["piezas"] = {k: str(v) for k, v in P.items()}

# ------------------------------------------------------------------ 2. ensamble (coordenadas relativas a la giratoria A)
def rel(x, y, z):
    return trasl(x - ORG_A[0], y - ORG_A[1], z - ORG_A[2])


rob = app.Documents.Add(inv.K_ASSEMBLY_DOCUMENT, app.FileManager.GetTemplateFile(inv.K_ASSEMBLY_DOCUMENT), False)
rcd = rob.ComponentDefinition
n = 0


def add(nombre, ruta, x, y, z):
    global n
    o = rcd.Occurrences.Add(str(ruta), mmake(rel(x, y, z)))
    S(lambda: setattr(o, "Name", nombre))
    o.Grounded = True
    n += 1
    return o


y_riel = Y_TOP - COL - RIEL[1]          # rieles colgados bajo los travesaños
for i, x in enumerate(X_RIELES):
    add(f"Riel_{i + 1}", P["Riel_aereo"], x, y_riel, (Z_RIEL[0] + Z_RIEL[1]) / 2)
for j, (xa, xb) in enumerate(PORTICOS_DWG):
    z = (dwg_z(xa) + dwg_z(xb)) / 2
    for k, x in enumerate(X_PATAS):
        add(f"Columna_{j + 1}{'ab'[k]}", P["Columna_portico"], x, 0.0, z)
    add(f"Travesano_{j + 1}", P["Travesano_portico"], (X_PATAS[0] + X_PATAS[1]) / 2, Y_TOP - COL, z)
xc = (X_RIELES[0] + X_RIELES[1]) / 2
y_carro = y_riel - CARRO[1]
add("Carro", P["Carro_robot"], xc, y_carro, Z_CARRO)
add("Mastil", P["Mastil_robot"], xc, Y_ROBOT, Z_CARRO)
for k, dx in enumerate((-300.0, 300.0)):
    add(f"Horquilla_{k + 1}", P["Horquilla_robot"], xc + dx, Y_ROBOT - HORQ[1], Z_CARRO)
# pallet en las horquillas y pilas de 10 al inicio del riel (origen del ipt: se corrige por caja)
tmp = rcd.Occurrences.Add(str(PALLET_IPT), mmake(trasl(0, 0, 0)))
rob.Update()
b = caja_mm(tmp.RangeBox)
off = (-(b[0] + b[3]) / 2, -b[1], -(b[2] + b[5]) / 2)
ph = b[4] - b[1]
tmp.Delete()


def pallet(nombre, x, y, z):
    o = rcd.Occurrences.Add(str(PALLET_IPT), mmake(rel(x + off[0], y + off[1], z + off[2])))
    S(lambda: setattr(o, "Name", nombre))
    o.Grounded = True


pallet("Pallet_en_horquillas", xc, Y_ROBOT - HORQ[1] - ph, Z_CARRO)
for i, (x, z) in enumerate(PILAS):
    for k in range(10):
        pallet(f"Pila{i + 1}_pallet_{k + 1}", x, k * ph, z)
rob.Update()
inv._iprop(rob, "Design Tracking Properties", "Part Number", "Robot aéreo de pallets vacíos (volumen estimado)")
rob.SaveAs(str(ROBOT), False)
bt = caja_mm(rcd.RangeBox)
log["robot"] = {"archivo": str(ROBOT), "ocurrencias": n + 21,
                "envolvente_layout_mm": [round(bt[i] + ORG_A[i % 3]) for i in range(6)],
                "porticos_Z": [round((dwg_z(a) + dwg_z(b)) / 2) for a, b in PORTICOS_DWG]}
rob.Close(True)


# ------------------------------------------------------------------ 3. limpiar celda A y línea, insertar en el layout
def abrir(p):
    d = next((d for d in inv._items(app.Documents) if S(lambda: Path(d.FullFileName).resolve() == p.resolve(), False)), None)
    return d or app.Documents.Open(str(p), False)


def borrar(doc, prefijos):
    out = []
    for o in list(inv._items(doc.ComponentDefinition.Occurrences)):
        if any(o.Name.startswith(p) for p in prefijos):
            out.append(o.Name)
            o.Delete()
    if out:
        doc.Update()
        doc.Save()
    return out


log["quitado_celda_A"] = borrar(abrir(CELDA_A), ("European Pallet",))
log["quitado_linea"] = borrar(abrir(LINEA), ("guia_robot_dispensador",))
lay = abrir(LAYOUT)
lcd = lay.ComponentDefinition
for o in list(inv._items(lcd.Occurrences)):
    if o.Name.startswith("Robot_Aereo_Pallets"):
        o.Delete()
o = lcd.Occurrences.Add(str(ROBOT), mmake(trasl(*ORG_A)))
for i, eje in enumerate("XYZ"):
    c = lcd.Constraints.AddFlushConstraint(o.CreateGeometryProxy(o.Definition.WorkPlanes.Item(i + 1)),
                                           lcd.WorkPlanes.Item(i + 1), ORG_A[i] / 10)
    S(lambda: setattr(c, "Name", f"Robot_Aereo_{eje}"))
    lay.Update()
    t = o.Transformation.Translation
    if abs([t.X, t.Y, t.Z][i] * 10 - ORG_A[i]) > 1.0:
        c.Offset.Value = -c.Offset.Value
        lay.Update()
lay.Update()
lay.Save()
t = o.Transformation.Translation
log["layout"] = {"robot_pos": [round(t.X * 10), round(t.Y * 10), round(t.Z * 10)]}
print(json.dumps(log, ensure_ascii=False, indent=1))
