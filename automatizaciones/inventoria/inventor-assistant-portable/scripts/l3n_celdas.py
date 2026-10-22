"""L3N Paletizado: reorganiza la copia de estudio en ensambles por celda (archivos NUEVOS, no toca nada existente).

Lee las posiciones de `Estudio_IA\\LayoutL3N_Estudio_DWG.iam` (abierto) y arma en C:\\DEFYMOTION\\L3N\\Celdas_IA\\:
  Cinta_Llegada_A.iam   bandas modulares BM2000 desde la CBP34 (biblioteca Documents\\InventorIA\\Cintas Transportadoras;
                        las familias BM comparten piezas entre carpetas: no copiar una sola carpeta)
  Celda_A_L3N.iam       celda nueva (alcance Defy): robot, base, gripper, tablero, cerco, freno, mesas, pallets,
                        giratoria A y la cinta de llegada
  Celda_B_existente.iam como está en planta (gráfica)
  Celda_C_existente.iam representación prolija (sin cintas Tetra, pateador ni empujador)
  En las tres celdas se quitan las paredes blancas (factory assets) y el "freno de cajas" (sólo estructura) se
  reemplaza por módulos BM2000 alineados al extremo del robot.
  Linea_Pallets.iam     camas entre celdas, línea hasta la envolvedora, envolvedora, giratoria final, guía y pasarela
  LayoutL3N_Celdas.iam  paredes + las cinco piezas anteriores, cada una con 3 restricciones de nivelación (planos de
                        origen) con la posición del plano DWG como valor.
Origen de cada celda: centro de su mesa giratoria, a nivel de piso, ejes del layout.
Uso: python l3n_celdas.py [--rehacer]
"""
import atexit
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
import inventor_mcp as inv  # noqa: E402

S = inv._safe
SRC = Path(r"C:\DEFYMOTION\L3N\Estudio_IA\LayoutL3N_Estudio_DWG.iam")
OUT = Path(r"C:\DEFYMOTION\L3N\Celdas_IA")
BM2000 = Path.home() / "Documents" / "InventorIA" / "Cintas Transportadoras" / "Banda Modular 2000" / "Ensamblaje BM2000.iam"
F = {k: OUT / f"{k}.iam" for k in ("Cinta_Llegada_A", "Celda_A_L3N", "Celda_B_existente", "Celda_C_existente",
                                    "Linea_Pallets", "LayoutL3N_Celdas")}
PASO, XMIN, BANDA_Y, BANDA_Z, BANDA_OBJ = 2225.7, -1024.2, 372.0, -75.0, 800.0
DWG_A, INV_A = (3843.973, 1293.966), (-6503.2, -35622.3)

app = inv._inventor(start_if_needed=False)
atexit.register(lambda: S(lambda: setattr(app, "SilentOperation", False)))
app.SilentOperation = True
tg = app.TransientGeometry
log = {"avisos": []}


def dwg2inv(x, y):
    return INV_A[0] + (DWG_A[1] - y) * 1000.0, INV_A[1] - (x - DWG_A[0]) * 1000.0


def mread(m):
    return [[m.Cell(r, c) * (10 if c == 4 else 1) for c in range(1, 5)] for r in range(1, 4)]


def mmake(M):
    m = tg.CreateMatrix()
    m.SetCoordinateSystem(tg.CreatePoint(M[0][3] / 10, M[1][3] / 10, M[2][3] / 10),
                          tg.CreateVector(M[0][0], M[1][0], M[2][0]), tg.CreateVector(M[0][1], M[1][1], M[2][1]),
                          tg.CreateVector(M[0][2], M[1][2], M[2][2]))
    return m


def rel(M, o):
    R = [r[:] for r in M]
    for i in range(3):
        R[i][3] -= o[i]
    return R


def centro(occ):
    b = occ.RangeBox
    return ((b.MinPoint.X + b.MaxPoint.X) * 5, 0.0, (b.MinPoint.Z + b.MaxPoint.Z) * 5)


def nuevo():
    return app.Documents.Add(inv.K_ASSEMBLY_DOCUMENT, app.FileManager.GetTemplateFile(inv.K_ASSEMBLY_DOCUMENT), False)


def poner(doc, items, origen):
    """items: lista de (archivo, M_mundo, nombre)."""
    cd = doc.ComponentDefinition
    hechos = 0
    for archivo, M, nombre in items:
        try:
            o = cd.Occurrences.Add(str(archivo), mmake(rel(M, origen)))
            S(lambda: setattr(o, "Name", nombre))
            o.Grounded = True
            hechos += 1
        except Exception as exc:  # noqa: BLE001
            log["avisos"].append(f"No se pudo insertar {nombre}: {exc!r}")
    return hechos


def guardar(doc, ruta, titulo):
    S(lambda: setattr(doc.PropertySets.Item("Inventor Summary Information").Item("Title"), "Value", titulo))
    S(lambda: setattr(doc.PropertySets.Item("Design Tracking Properties").Item("Project"), "Value", "L3N Paletizado L3 2027"))
    doc.SaveAs(str(ruta), False)


def hijos(occ):
    return [s for s in inv._items(occ.SubOccurrences) if not S(lambda: s.Suppressed, False)]


def item(o):
    return (o.ReferencedDocumentDescriptor.FullDocumentName, mread(o.Transformation), o.Name)


def es(nombre, *claves):
    n = nombre.lower()
    return any(n.startswith(k.lower()) for k in claves)


# ------------------------------------------------------------------ 0. preparación
OUT.mkdir(parents=True, exist_ok=True)
if "--rehacer" in sys.argv:
    for d in list(inv._items(app.Documents)):
        if str(S(lambda: d.FullFileName, "")).lower().startswith(str(OUT).lower() + "\\"):
            S(lambda: d.Close(True))
    for p in F.values():
        if p.exists():
            p.unlink()
for p in F.values():
    if p.exists():
        sys.exit(f"Ya existe {p}: usá --rehacer.")
if not BM2000.exists():
    sys.exit(f"Falta la biblioteca de bandas: {BM2000}")
src = next((d for d in inv._items(app.Documents)
            if S(lambda: Path(d.FullFileName).resolve() == SRC.resolve(), False)), None) or app.Documents.Open(str(SRC), False)
top = {o.Name: o for o in inv._items(src.ComponentDefinition.Occurrences)}
oA = top["ADECOAGRO_Chivilcoy - L3N_Linea3:2"]
oB = next(o for n, o in top.items() if n.startswith("ADECOAGRO_Chivilcoy_Estudio_DWG"))
oC = top["ADECOAGRO_Chivilcoy - L3N_Linea3:3"]
CINTAS = ("Correa transportadora recta", "Cinta transportadora con correas")
ORG = {"A": centro(top["roller conveyor - rotating:1"]),
       "B": centro(next(s for s in hijos(oB) if s.Name == "roller conveyor - rotating:1")),
       "C": centro(top["IA_Giratoria_C"])}
log["origenes_mm"] = {k: [round(v) for v in o] for k, o in ORG.items()}

# ------------------------------------------------------------------ 1. cinta de llegada A
X1 = dwg2inv(0, 1283.10)[0]
Z2 = dwg2inv(3838.88, 0)[1]
X3 = dwg2inv(0, 1299.48)[0]
Z0 = dwg2inv(3829.273, 0)[1]
freno_A = next(s for s in hijos(oA) if s.Name.startswith("Ensamble freno de cajas"))
Zf = freno_A.RangeBox.MaxPoint.Z * 10
tramos = {"T1": ((X1, Z0), (X1, Z2 + 150.0)), "T2": ((X1 - 150.0, Z2), (X3 + 150.0, Z2)), "T3": ((X3, Z2 - 150.0), (X3, Zf))}


def modulos(nombre, p0, p1, alinear_fin=False):
    """Módulos BM2000 en línea recta p0 -> p1 (X, Z en mm, eje de banda). Devuelve (items, resumen)."""
    dx, dz = p1[0] - p0[0], p1[1] - p0[1]
    L = (dx * dx + dz * dz) ** 0.5
    d = (dx / L, dz / L)
    nrm = (-d[1], d[0])      # d x Y en el plano XZ
    n = int(L // PASO)
    s0 = L - n * PASO if alinear_fin else 0.0
    items = []
    for i in range(n):
        s = s0 + i * PASO
        org = (p0[0] + d[0] * s - d[0] * XMIN - nrm[0] * BANDA_Z, BANDA_OBJ - BANDA_Y,
               p0[1] + d[1] * s - d[1] * XMIN - nrm[1] * BANDA_Z)
        M = [[d[0], 0.0, nrm[0], org[0]], [0.0, 1.0, 0.0, org[1]], [d[1], 0.0, nrm[1], org[2]]]
        items.append((BM2000, M, f"BM2000_{nombre}_{i + 1}"))
    return items, {"tramo": nombre, "largo_mm": round(L), "modulos": n, "sobrante_mm": round(L - n * PASO)}


mods, resumen = [], []
for t, (p0, p1) in tramos.items():
    it, r = modulos(t, p0, p1)
    mods += it
    resumen.append(r)


def cinta_celda(nombre, caja):
    """Cinta interna de la celda (reemplaza al freno de cajas, que es sólo estructura): a lo largo de X, con los
    módulos alineados al extremo del robot (este, X máx)."""
    zc = (caja[2] + caja[5]) / 2
    return modulos(nombre, (caja[0], zc), (caja[3], zc), alinear_fin=True)


caja_freno_A = [v * 10 for v in (freno_A.RangeBox.MinPoint.X, freno_A.RangeBox.MinPoint.Y, freno_A.RangeBox.MinPoint.Z,
                                 freno_A.RangeBox.MaxPoint.X, freno_A.RangeBox.MaxPoint.Y, freno_A.RangeBox.MaxPoint.Z)]
freno_B = next(s for s in hijos(oB) if s.Name.startswith("Ensamble freno de cajas"))
caja_freno_B = [v * 10 for v in (freno_B.RangeBox.MinPoint.X, freno_B.RangeBox.MinPoint.Y, freno_B.RangeBox.MinPoint.Z,
                                 freno_B.RangeBox.MaxPoint.X, freno_B.RangeBox.MaxPoint.Y, freno_B.RangeBox.MaxPoint.Z)]
dC = [ORG["C"][i] - ORG["A"][i] for i in range(3)]
caja_freno_C = [caja_freno_A[i] + dC[i % 3] for i in range(6)]
cintas_int = {}
for k, caja in (("A", caja_freno_A), ("B", caja_freno_B), ("C", caja_freno_C)):
    cintas_int[k] = cinta_celda(f"Celda{k}", caja)

# ------------------------------------------------------------------ 2. celdas
QUITAR = CINTAS + ("Pared", "Ensamble freno de cajas")   # paredes blancas (factory assets) y freno (sólo estructura)
itA = [item(s) for s in hijos(oA) if not es(s.Name, *QUITAR)] + cintas_int["A"][0]
itA += [item(top["roller conveyor - rotating:1"])]   # las pilas de pallets van en Robot_Aereo_Pallets
itA.append((F["Cinta_Llegada_A"], [[1, 0, 0, ORG["A"][0]], [0, 1, 0, 0], [0, 0, 1, ORG["A"][2]]], "Cinta_Llegada_A"))
LINEA_B = ("Roller_Conveyor_Straight", "Pasarela")   # la guía del robot aéreo se reemplaza por Robot_Aereo_Pallets
itB = [item(s) for s in hijos(oB) if not es(s.Name, *LINEA_B, "guia_robot_dispensador", "Pared", "Ensamble freno de cajas")] + cintas_int["B"][0]
itC = [item(s) for s in hijos(oC) if not es(s.Name, *QUITAR, "Ensamble pateador", "Empujador")] + cintas_int["C"][0]
itC.append(item(top["IA_Giratoria_C"]))
itL = [item(s) for s in hijos(oB) if es(s.Name, *LINEA_B)]
itL += [item(o) for n, o in top.items() if es(n, "Roller_Conveyor_Straight", "IA_Cama", "MP402", "roller conveyor - rotating:2")]
PAREDES = (top["Paredes:1"].ReferencedDocumentDescriptor.FullDocumentName, mread(top["Paredes:1"].Transformation))
# cerrar la copia de estudio (propia) antes de insertar: referencia la biblioteca BM de Documents y Inventor no
# admite dos archivos con el mismo nombre abiertos desde carpetas distintas
src.Close(True)
S(lambda: app.Documents.CloseAll(True))   # True = sólo documentos no referenciados (sin ventana)
cinta = nuevo()
poner(cinta, mods, ORG["A"])
guardar(cinta, F["Cinta_Llegada_A"], "Cinta de llegada celda A (CBP34 -> freno)")
log["cinta_A"] = {"tramos": resumen, "total_m": round(sum(r["largo_mm"] for r in resumen) / 1000, 2), "modulos": len(mods)}
log["cintas_internas"] = {k: v[1] for k, v in cintas_int.items()}

piezas = {}
for clave, items, org, titulo in (("Celda_A_L3N", itA, ORG["A"], "Celda A - L3N nueva (KUKA KR 180 R3200-2 PA)"),
                                  ("Celda_B_existente", itB, ORG["B"], "Celda B - existente (gráfica)"),
                                  ("Celda_C_existente", itC, ORG["C"], "Celda C - existente (representación)"),
                                  ("Linea_Pallets", itL, ORG["A"], "Línea de pallets, envolvedora y giratoria final")):
    d = nuevo()
    piezas[clave] = {"insertados": poner(d, items, org), "de": len(items)}
    guardar(d, F[clave], titulo)
    d.Close(True)
S(lambda: app.Documents.ItemByName(str(F["Cinta_Llegada_A"])).Close(True))
log["piezas"] = piezas

# ------------------------------------------------------------------ 3. layout con restricciones
lay = app.Documents.Add(inv.K_ASSEMBLY_DOCUMENT, app.FileManager.GetTemplateFile(inv.K_ASSEMBLY_DOCUMENT), True)
lcd = lay.ComponentDefinition
par = lcd.Occurrences.Add(PAREDES[0], mmake(PAREDES[1]))
par.Grounded = True
pos = {"Celda_A_L3N": ORG["A"], "Celda_B_existente": ORG["B"], "Celda_C_existente": ORG["C"], "Linea_Pallets": ORG["A"]}
restr = {}
for clave, p in pos.items():
    o = lcd.Occurrences.Add(str(F[clave]), mmake([[1, 0, 0, p[0]], [0, 1, 0, p[1]], [0, 0, 1, p[2]]]))
    cs = []
    for i, eje in enumerate("XYZ"):
        c = lcd.Constraints.AddFlushConstraint(o.CreateGeometryProxy(o.Definition.WorkPlanes.Item(i + 1)),
                                               lcd.WorkPlanes.Item(i + 1), p[i] / 10)
        S(lambda: setattr(c, "Name", f"{clave}_{eje}"))
        cs.append(c)
    lay.Update()
    t = mread(o.Transformation)
    for i, c in enumerate(cs):
        if abs(t[i][3] - p[i]) > 1.0:
            c.Offset.Value = -c.Offset.Value
    lay.Update()
    t = mread(o.Transformation)
    restr[clave] = {"objetivo": [round(v) for v in p], "resultado": [round(t[i][3]) for i in range(3)]}
log["layout"] = restr
ov = lay.ObjectVisibility
for prop in ("Sketches", "Sketches3D", "SketchDimensions", "Annotations3D", "AllWorkFeatures", "ConstructionSurfaces"):
    S(lambda: setattr(ov, prop, False))
guardar(lay, F["LayoutL3N_Celdas"], "Layout L3N por celdas")
S(lambda: lay.Views.Item(1).Fit())
app.SilentOperation = False
print(json.dumps(log, ensure_ascii=False, indent=1))
