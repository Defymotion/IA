"""L3N layout v9: mesa giratoria en el ingreso de la celda A (gira el pallet vacío 90° antes de paletizar).
Trabaja sobre una COPIA del layout liviano v7 (el v7 y la celda A no se tocan):
1) SaveAs copia LayoutL3N_liviano_v7.iam -> LayoutL3N_liviano_v9.iam.
2) Oculta en el v9 las dos camas de rolos iniciales de la celda A (CdR1512 :2 y :3).
3) Agrega la giratoria (el mismo CAD que las de B y C) centrada bajo el punto de dejada del robot aéreo, con el motor
   hacia la reja norte (girada 180° respecto de la de B).
4) Agrega un tramo corto de rolos (IA, ~368 mm) entre la giratoria y la mesa del puesto de paletizado.
5) Fotos (planta, iso y detalle) en Analisis\\L3N\\giratoria_A\\fotos y cajas de lo nuevo en el resultado.
Uso: python l3n_layout_v8_giratoria.py <resultado.json> [--xc -10582] [--zc -35622.3] [--giro 90|180] [--sin-fotos] [--solo-fotos]\n(las fotos se sacan sin el robot aéreo ni las paredes, que se vuelven a mostrar)
"""
import json
import sys
import time
import traceback
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import inventor_mcp as inv  # noqa: E402
from cinta_modular import Gen  # noqa: E402

S = inv._safe
T0 = time.time()
A = sys.argv
OUT = Path(A[1])
XC = float(A[A.index("--xc") + 1]) if "--xc" in A else -10582.0
ZC = float(A[A.index("--zc") + 1]) if "--zc" in A else -35622.3429
GIRO = int(A[A.index("--giro") + 1]) if "--giro" in A else 90
BASE = Path(r"C:\DEFYMOTION\L3N\Celdas_IA")
V7 = BASE / "LayoutL3N_liviano_v7.iam"
V8 = BASE / "LayoutL3N_liviano_v9.iam"      # (el v8 es el de la esquina corrida, descartado: no se toca)
DIR = BASE / "Giratoria_A"
GIR = Path(r"C:\DEFYMOTION\L3N\ADECO 12-12-25\CAD\roller conveyor - rotating\roller conveyor - rotating"
           r"\roller conveyor - rotating\roller conveyor - rotating.iam")
FOTOS = Path.home() / "Documents" / "InventorIA" / "Analisis" / "L3N" / "giratoria_A" / "fotos"
OCULTAR = ["00.Ensamblaje Mesa de Rolos Completa_[CdR-STD]_[CdR1512]:2", "00.Ensamblaje Mesa de Rolos Completa_[CdR-STD]_[CdR1512]:3"]
# tramo corto: de la punta de los rolos de la giratoria (868 mm del centro, como en la celda B) a la mesa del puesto
X_MESA1 = -9346.0
L_CAMA = round(X_MESA1 - (XC + 868.0), 1)
Z_MESA = (-36439.0 + -34940.0) / 2
ANCHO_MESA = 1420.0          # más angosta que la mesa (1499) para no tocar las patas de la cinta interna
Y_TOP = 543.0
app = inv._inventor(start_if_needed=False)
tg = app.TransientGeometry
log = {"avisos": [], "xc": XC, "zc": ZC, "giro": GIRO, "L_cama": L_CAMA}


def mx(R, t):
    m = tg.CreateMatrix()
    m.SetCoordinateSystem(tg.CreatePoint(t[0] / 10, t[1] / 10, t[2] / 10), tg.CreateVector(R[0][0], R[1][0], R[2][0]),
                          tg.CreateVector(R[0][1], R[1][1], R[2][1]), tg.CreateVector(R[0][2], R[1][2], R[2][2]))
    return m


def caja(o):
    b = o.RangeBox
    return [round(v * 10, 1) for v in (b.MinPoint.X, b.MinPoint.Y, b.MinPoint.Z, b.MaxPoint.X, b.MaxPoint.Y, b.MaxPoint.Z)]


def abierto(p):
    return next((d for d in inv._items(app.Documents) if S(lambda d=d: Path(d.FullFileName).resolve() == Path(p).resolve(), False)), None)


def cama_corta():
    """Subensamble IA_Cama_corta_L<L>.iam: origen en el centro, al piso; avance en X, rolos a lo largo de Z."""
    ruta = DIR / f"IA_Cama_corta_L{int(round(L_CAMA))}.iam"
    g = Gen(app, DIR / "Piezas")
    ap_acero = ["acero galvanizado", "galvanized", "acero", "steel"]
    larg = g.caja(f"Cama_corta_larguero_L{int(round(L_CAMA))}", L_CAMA, 110.0, 50.0, "Larguero de cama corta de rolos", ap_acero)
    pata = g.caja("Cama_corta_pata_60x433", 60.0, 433.0, 60.0, "Pata de cama corta de rolos", ap_acero)
    rod = g.cilindro("Cama_corta_rodillo_D89_L1300", 89.0, 1300.0, "z", "Rodillo de cama corta (pallet)",
                     ["cromo", "chrome", "acero inoxidable", "acero"])
    d = abierto(ruta)
    if d is not None:
        d.Close(True)
    ens = app.Documents.Add(inv.K_ASSEMBLY_DOCUMENT, app.FileManager.GetTemplateFile(inv.K_ASSEMBLY_DOCUMENT), False)
    I = [[1, 0, 0], [0, 1, 0], [0, 0, 1]]
    oc = ens.ComponentDefinition.Occurrences
    zl = ANCHO_MESA / 2 - 25.0
    for s in (-1, 1):
        oc.Add(str(larg), mx(I, (0.0, 433.0, s * zl)))
        for sx in (-1, 1):
            oc.Add(str(pata), mx(I, (sx * (L_CAMA / 2 - 30.0), 0.0, s * zl)))
    n = max(2, int(L_CAMA // 120))
    paso = L_CAMA / n
    for i in range(n):
        oc.Add(str(rod), mx(I, (-L_CAMA / 2 + paso * (i + 0.5), Y_TOP - 44.5, 0.0)))
    for o in inv._items(oc):
        S(lambda o=o: setattr(o, "Grounded", True))
    inv._iprop(ens, "Design Tracking Properties", "Description", f"CAMA CORTA DE ROLOS L{int(round(L_CAMA))} (IA, A DEFINIR)")
    if ruta.exists():
        ruta.unlink()
    ens.SaveAs(str(ruta), False)
    ens.Close(True)
    return ruta


def fotos(doc):
    out = []
    ocultar = [o for o in inv._items(doc.ComponentDefinition.Occurrences) if o.Name.startswith(("Robot_Aereo", "Paredes"))
               and S(lambda o=o: o.Visible, False)]
    for o in ocultar:                        # sólo para las fotos (no se guarda)
        S(lambda o=o: setattr(o, "Visible", False))
    doc.Activate()
    time.sleep(2)
    v = app.ActiveView
    cam = v.Camera
    c0 = (cam.Eye, cam.Target, cam.UpVector, S(lambda: cam.Perspective, False))
    FOTOS.mkdir(parents=True, exist_ok=True)
    tomas = [("v8_planta_celdaA", (XC + 1500, 15000, ZC - 1200), (XC + 1500, 0, ZC - 1200), (0, 0, -1), False, (7200, 5200)),
             ("v8_iso_celdaA", (XC + 7500, 7500, ZC + 7000), (XC + 1300, 500, ZC - 900), (0, 1, 0), True, (8000, 5000)),
             ("v8_detalle_giratoria", (XC - 3200, 2600, ZC - 3600), (XC, 350, ZC - 300), (0, 1, 0), True, (3800, 2400)),
             ("v8_detalle_reja_norte", (XC + 2200, 2200, ZC + 2900), (XC, 350, ZC + 500), (0, 1, 0), True, (3800, 2400))]
    try:
        for nombre, eye, tgt, up, persp, ext in tomas:
            cam.Target = tg.CreatePoint(*[v_ / 10 for v_ in tgt])
            cam.Eye = tg.CreatePoint(*[v_ / 10 for v_ in eye])
            cam.UpVector = tg.CreateUnitVector(*up)
            cam.Perspective = persp
            w, h = ext[0] / 10, ext[1] / 10
            cam.SetExtents(max(w, h * 1.6), max(w, h * 1.6) / 1.6)
            cam.Apply()
            ruta = FOTOS / f"{nombre}.png"
            for _ in range(2):
                v.Update()
                v.SaveAsBitmap(str(ruta), 1600, 1000)
            out.append(str(ruta))
    finally:
        for o in ocultar:
            S(lambda o=o: setattr(o, "Visible", True))
        S(lambda: setattr(cam, "Perspective", c0[3]))
        cam.Eye, cam.Target, cam.UpVector = c0[0], c0[1], c0[2]
        S(lambda: cam.Apply())
    return out


app.SilentOperation = True
try:
    if "--solo-fotos" in A:
        d8 = abierto(V8) or app.Documents.Open(str(V8), True)
        log["fotos"] = fotos(d8)
        raise SystemExit(0)
    DIR.mkdir(parents=True, exist_ok=True)
    # arreglo de nombres de la primera prueba (04/11), que guardó como v8 y apartó el v8 descartado del 03/11
    v8 = BASE / "LayoutL3N_liviano_v8.iam"
    v8_orig = BASE / "LayoutL3N_liviano_v8_anterior_20261104_095601.iam"
    if v8_orig.exists():
        pr = DIR / "_pruebas"
        pr.mkdir(exist_ok=True)
        dv = abierto(v8)
        if dv is not None:
            dv.Close(True)
        if v8.exists():
            v8.rename(pr / "LayoutL3N_giratoria_prueba2.iam")
        p1 = BASE / "LayoutL3N_liviano_v8_anterior_20261104_095839.iam"
        if p1.exists():
            p1.rename(pr / "LayoutL3N_giratoria_prueba1.iam")
        v8_orig.rename(v8)
        log["renombres"] = "v8 descartado restituido; pruebas en Giratoria_A\\_pruebas"
    d8 = abierto(V8)
    if d8 is not None:
        d8.Close(True)
    if V8.exists():
        V8.rename(V8.with_name(V8.stem + time.strftime("_anterior_%Y%m%d_%H%M%S") + ".iam"))
    lay = abierto(V7) or app.Documents.Open(str(V7), False)
    lay.SaveAs(str(V8), True)                 # copia: el v7 queda igual y abierto como estaba
    ruta_cama = cama_corta()
    log["cama"] = str(ruta_cama)
    doc = app.Documents.Open(str(V8), True)
    cd = doc.ComponentDefinition
    tops = {o.Name: o for o in inv._items(cd.Occurrences)}
    ca = next((o for n, o in tops.items() if n.startswith("Celda_A")), None)
    log["ocultos"] = []
    for nm in OCULTAR:
        h = next((h for h in inv._items(ca.SubOccurrences) if h.Name == nm), None)
        if h is None:
            log["avisos"].append(f"no encontré {nm}")
            continue
        S(lambda h=h: setattr(h, "Visible", False))
        log["ocultos"].append(nm)
    # giratoria: la de B tiene R = [[0,1,0],[0,0,1],[1,0,0]] y origen en Y 230.5. Acá girada +90° sobre Y: rolos del plato a
    # lo largo de Z (transfiere en X, hacia la cama corta) y motor bajo la cinta interna, entre sus patas.
    # (180°: motor al norte junto a la reja, pero el plato queda con los rolos a lo largo de X)
    R = {90: [[1, 0, 0], [0, 0, 1], [0, -1, 0]], 180: [[0, -1, 0], [0, 0, 1], [-1, 0, 0]]}[GIRO]
    g = cd.Occurrences.Add(str(GIR), mx(R, (XC, 230.5, ZC)))
    S(lambda: setattr(g, "Name", "Giratoria_A_ingreso"))
    S(lambda: setattr(g, "Grounded", True))
    c = cd.Occurrences.Add(str(ruta_cama), mx([[1, 0, 0], [0, 1, 0], [0, 0, 1]], (X_MESA1 - L_CAMA / 2, 0.0, Z_MESA)))
    S(lambda: setattr(c, "Name", f"Cama_corta_A_L{int(round(L_CAMA))}"))
    S(lambda: setattr(c, "Grounded", True))
    doc.Update()
    log["nuevos"] = {"giratoria": caja(g), "giratoria_hijos": {h.Name: S(lambda h=h: caja(h)) for h in inv._items(g.SubOccurrences)},
                     "cama_corta": caja(c)}
    doc.Save()
    log["v8"] = str(V8)
    if "--sin-fotos" not in A:
        log["fotos"] = fotos(doc)
except SystemExit:
    pass
except Exception as exc:  # noqa: BLE001
    log["error"] = repr(exc)
    log["traza"] = traceback.format_exc()[-2500:]
finally:
    S(lambda: setattr(app, "SilentOperation", False))
log["s"] = round(time.time() - T0, 1)
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(log, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps(log, ensure_ascii=False, indent=1)[:6000])
