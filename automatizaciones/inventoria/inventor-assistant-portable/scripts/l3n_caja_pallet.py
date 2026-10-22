"""L3N celda A: caja real TBA 250 Edge Helicap 3x8 (386 x 156 x 149, 6,1 kg) y pallet completo según el PDF
2PADOK 7703-UK-4: 17 cajas/capa (2 filas de 7 con el lado de 156 a lo largo + 1 fila de 3 a lo largo), 8 capas,
capas impares giradas 180° para trabar. Archivos nuevos en C:\\DEFYMOTION\\L3N\\Celdas_IA\\Producto\\.
Después reemplaza en Celda_A_L3N.iam el `Pallet_Completo:2` (demo de ADECO) por el pallet nuevo, en el mismo lugar,
y pone una caja sobre la cinta interna en el extremo del robot. Uso: python l3n_caja_pallet.py [--rehacer]
"""
import atexit
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
import inventor_mcp as inv  # noqa: E402

S = inv._safe
CELDA = Path(r"C:\DEFYMOTION\L3N\Celdas_IA\Celda_A_L3N.iam")
OUT = Path(r"C:\DEFYMOTION\L3N\Celdas_IA\Producto")
CAJA = OUT / "Caja_TBA250_3x8.ipt"
PALLET = OUT / "Pallet_TBA250_17x8.iam"
PALLET_IPT = Path(r"C:\DEFYMOTION\L3N\ADECO 12-12-25\European Pallet_3BC37FCD47819CDEC205D0C1A80F9DF2.ipt")
L, W, H, M = 386.0, 156.0, 149.0, 6.1      # caja (mm, kg)
PL, PW, PH = 1200.0, 1000.0, 150.0          # pallet
CAPAS = 8
BANDA_Y = 800.0

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


def mread(m):
    return [[m.Cell(r, c) * (10 if c == 4 else 1) for c in range(1, 5)] for r in range(1, 4)]


def caja_mm(b):
    return [b.MinPoint.X * 10, b.MinPoint.Y * 10, b.MinPoint.Z * 10, b.MaxPoint.X * 10, b.MaxPoint.Y * 10, b.MaxPoint.Z * 10]


def trasl(x, y, z, rot180=False):
    c = -1.0 if rot180 else 1.0
    return [[c, 0, 0, x], [0, 1, 0, y], [0, 0, c, z]]


# ------------------------------------------------------------------ 0. preparación
OUT.mkdir(parents=True, exist_ok=True)
if "--rehacer" in sys.argv:
    for d in list(inv._items(app.Documents)):
        f = str(S(lambda: d.FullFileName, "")).lower()
        if f.startswith(str(OUT).lower() + "\\"):
            S(lambda: d.Close(True))
    for p in (PALLET, CAJA):
        if p.exists():
            p.unlink()
for p in (PALLET, CAJA):
    if p.exists():
        sys.exit(f"Ya existe {p}: usá --rehacer.")

# ------------------------------------------------------------------ 1. caja (origen: centro de la base)
doc = app.Documents.Add(inv.K_PART_DOCUMENT, app.FileManager.GetTemplateFile(inv.K_PART_DOCUMENT), False)
cd = doc.ComponentDefinition
sk = cd.Sketches.Add(cd.WorkPlanes.Item(2))          # plano XZ
p1 = sk.ModelToSketchSpace(tg.CreatePoint(-L / 20, 0, -W / 20))
p2 = sk.ModelToSketchSpace(tg.CreatePoint(L / 20, 0, W / 20))
sk.SketchLines.AddAsTwoPointRectangle(p1, p2)
for direc in (20993, 20994):
    f = cd.Features.ExtrudeFeatures.AddByDistanceExtent(sk.Profiles.AddForSolid(), H / 10, direc, 20481)
    doc.Update()
    if cd.RangeBox.MaxPoint.Y * 10 > H - 0.1:
        break
    f.Delete()
eds = app.TransientObjects.CreateEdgeCollection()
for e in inv._items(cd.SurfaceBodies.Item(1).Edges):
    eds.Add(e)
S(lambda: cd.Features.FilletFeatures.AddSimple(eds, 0.4))
ap = None
for lib in inv._items(app.AssetLibraries):
    for asset in inv._items(S(lambda: lib.AppearanceAssets, []) or []):
        nm = (S(lambda: asset.DisplayName, "") or "").lower()
        if any(k in nm for k in ("cartón", "carton", "cardboard", "corrugated")):
            ap = asset
            break
    if ap:
        break
if ap is not None:
    S(lambda: setattr(doc, "ActiveAppearance", ap.CopyTo(doc)))
inv._iprop(doc, "Design Tracking Properties", "Part Number", "Caja TBA 250 Edge Helicap 3x8 WASF")
inv._iprop(doc, "Design Tracking Properties", "Description", f"{L:.0f} x {W:.0f} x {H:.0f} mm, {M} kg, 24 x 250 ml")
S(lambda: setattr(cd.MassProperties, "Mass", M))   # masa forzada (kg) si la API lo permite
doc.SaveAs(str(CAJA), False)
log["caja"] = {"archivo": str(CAJA), "caja_mm": [round(v, 1) for v in caja_mm(cd.RangeBox)],
               "masa_kg": S(lambda: round(cd.MassProperties.Mass, 2)), "apariencia": S(lambda: ap.DisplayName) if ap else None}
doc.Close(True)

# ------------------------------------------------------------------ 2. pallet completo (origen: centro de la base del pallet)
pal = app.Documents.Add(inv.K_ASSEMBLY_DOCUMENT, app.FileManager.GetTemplateFile(inv.K_ASSEMBLY_DOCUMENT), False)
pcd = pal.ComponentDefinition
op = pcd.Occurrences.Add(str(PALLET_IPT), mmake(trasl(0, 0, 0)))
pal.Update()
b = caja_mm(op.RangeBox)
dx, dy, dz = -(b[0] + b[3]) / 2, -b[1], -(b[2] + b[5]) / 2
op.Transformation = mmake(trasl(dx, dy, dz))
op.Grounded = True
pal.Update()
b = caja_mm(op.RangeBox)
ph = b[4] - b[1]
log["pallet_ipt"] = {"medidas_mm": [round(b[3] - b[0]), round(ph), round(b[5] - b[2])]}
# patrón de capa (centrado en la carga 1158 x 928): filas 1-2: 7 cajas con el lado 156 a lo largo de X (giradas 90°);
# fila 3: 3 cajas con el lado 386 a lo largo de X. Carga: X = 1158, Z = 2*386 + 156 = 928.
LX, LZ = 3 * L, 2 * L + W
capa = []
for fila in range(2):
    z = -LZ / 2 + fila * L + L / 2
    for i in range(7):
        x = -7 * W / 2 + W / 2 + i * W
        capa.append((x, z, True))      # True = girada 90° (156 a lo largo de X)
z3 = LZ / 2 - W / 2
for i in range(3):
    capa.append((-LX / 2 + L / 2 + i * L, z3, False))
n = 0
for k in range(CAPAS):
    y = ph + k * H
    giro = k % 2 == 1
    for (x, z, rot90) in capa:
        if giro:
            x, z = -x, -z
        if rot90:
            Mx = [[0, 0, 1, x], [0, 1, 0, y], [-1, 0, 0, z]]
        else:
            Mx = [[1, 0, 0, x], [0, 1, 0, y], [0, 0, 1, z]]
        o = pcd.Occurrences.Add(str(CAJA), mmake(Mx))
        o.Grounded = True
        n += 1
pal.Update()
inv._iprop(pal, "Design Tracking Properties", "Part Number", "Pallet TBA 250 3x8 - 17 x 8 capas")
pal.SaveAs(str(PALLET), False)
bt = caja_mm(pcd.RangeBox)
log["pallet"] = {"archivo": str(PALLET), "cajas": n, "capas": CAPAS,
                 "envolvente_mm": [round(bt[3] - bt[0]), round(bt[4] - bt[1]), round(bt[5] - bt[2])],
                 "masa_kg": S(lambda: round(pcd.MassProperties.Mass, 1)),
                 "pdf": {"carga": [1158, 1192, 928], "total_alto": 1342, "cajas": 136, "masa": 854.6}}
pal.Close(True)

# ------------------------------------------------------------------ 3. reemplazo en la celda A
cel = next((d for d in inv._items(app.Documents) if S(lambda: Path(d.FullFileName).resolve() == CELDA.resolve(), False)), None)
cel = cel or app.Documents.Open(str(CELDA), False)
ccd = cel.ComponentDefinition
occ = {o.Name: o for o in inv._items(ccd.Occurrences)}
viejo = next((o for nme, o in occ.items() if nme.startswith("Pallet_Completo")), None)
if viejo is not None:
    bv = caja_mm(viejo.RangeBox)
    pos = ((bv[0] + bv[3]) / 2, bv[1], (bv[2] + bv[5]) / 2)
    viejo.Delete()
    log["reemplazo"] = {"quitado": "Pallet_Completo", "pos_mm": [round(v) for v in pos]}
else:
    pos = (-1718.0, 507.0, 5.0)   # posición del demo en la celda A (relativa a la giratoria), si ya no está
    log["avisos"].append("No había Pallet_Completo en la celda: pallet nuevo en la posición del demo")
viejo_p = next((o for nme, o in occ.items() if nme.startswith("IA_Pallet_TBA250")), None)
if viejo_p is not None:
    viejo_p.Delete()
npal = ccd.Occurrences.Add(str(PALLET), mmake(trasl(pos[0], pos[1], pos[2])))
S(lambda: setattr(npal, "Name", "IA_Pallet_TBA250"))
npal.Grounded = True
# caja sobre la cinta interna, en el extremo del robot (módulo BM2000_CeldaA_2)
cinta = next((o for nme, o in occ.items() if nme.startswith("BM2000_CeldaA_2")), None)
if cinta is not None:
    bc = caja_mm(cinta.RangeBox)
    for nme, o in list(occ.items()):
        if nme.startswith("IA_Caja_en_cinta"):
            o.Delete()
    oc = ccd.Occurrences.Add(str(CAJA), mmake(trasl(bc[3] - 450.0, BANDA_Y, (bc[2] + bc[5]) / 2 + 20.0)))
    S(lambda: setattr(oc, "Name", "IA_Caja_en_cinta"))
    oc.Grounded = True
cel.Update()
cel.Save()
log["celda"] = {"pallet_env_mm": [round(v) for v in caja_mm(npal.RangeBox)]}
print(json.dumps(log, ensure_ascii=False, indent=1))
