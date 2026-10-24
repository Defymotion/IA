"""L3N: correcciones del layout que mostró la simulación de planta (archivos propios de Celdas_IA; antes se guardan copias
de respaldo *_antes_ajustes_sim.iam):
A) Robot_Aereo_Pallets: pórtico 1 (Z -36759) a Z -37500 — su columna 1b caía sobre la cinta interna, donde el pateador
   deja las cajas; columna 1b en X -11700 (libre del tablero y del gabinete KR C4) y travesaño nuevo de 2233.
B) Robot_Aereo_Pallets: travesaño del pórtico de buffer 2 (Z -33039, Y 1830-1980) reemplazado por dos ménsulas: estaba en
   el recorrido de la sujeción del pallet (Y 1680-1880).
C) Robot_Aereo_Pallets: buffers (pilas, placas y guías) +53 mm en X, centrados con los rieles (X -10582): con 53 mm de
   desfasaje la sujeción (1300) pasaba por dentro de una guía.
D) Celda_A_L3N: reja norte interna (columnas y paneles) y el receptor de la barrera IFM con sus brazos +150 mm en Z: la
   fila de 3 del lado norte necesita ~312 mm más allá de la carga para la pala y las cajas que cuelgan.
E) Celda_A_L3N: brazos y sensores de muting de Y 700 a Y 560 (a la altura del pallet): a 700 el gripper los tocaba al dejar
   la primera capa.
F) Celda_A_L3N: tramo de la reja norte bajo el recorrido del robot aéreo (columna 2 y paneles altos 1 y 2) bajado a
   1400 mm: el pallet colgado (cara inferior 1528) cruzaba la reja de 1955. (Altura a validar con seguridad.)
Uso: python l3n_ajustes_sim.py
"""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
import inventor_mcp as inv  # noqa: E402

S = inv._safe
BASE = Path(r"C:\DEFYMOTION\L3N\Celdas_IA")
ROBOT = BASE / "Robot_Aereo" / "Robot_Aereo_Pallets.iam"
CELDA = BASE / "Celda_A_L3N.iam"
PZ = BASE / "Ajustes_sim"
ORG_R = (-6503.2, 0.0, -35622.3)
ORG_C = (-6503.1706, 0.0, -35622.3429)
COL = 150.0
app = inv._inventor(start_if_needed=False)
tg = app.TransientGeometry
log = {"avisos": [], "hecho": []}
PZ.mkdir(parents=True, exist_ok=True)


def abrir(p):
    d = next((d for d in inv._items(app.Documents) if S(lambda: Path(d.FullFileName).resolve() == p.resolve(), False)), None)
    return d or app.Documents.Open(str(p), False)


def mover(o, dx=0.0, dy=0.0, dz=0.0):
    m = o.Transformation
    t = tg.CreateMatrix()
    t.SetTranslation(tg.CreateVector(dx / 10, dy / 10, dz / 10))
    m.TransformBy(t)
    g0 = S(lambda: o.Grounded, False)
    S(lambda: setattr(o, "Grounded", False))
    o.Transformation = m
    if g0:
        S(lambda: setattr(o, "Grounded", True))


def poner(cd, ruta, org, x, y, z, nombre):
    m = tg.CreateMatrix()
    m.SetTranslation(tg.CreateVector((x - org[0]) / 10, (y - org[1]) / 10, (z - org[2]) / 10))
    o = cd.Occurrences.Add(str(ruta), m)
    S(lambda: setattr(o, "Name", nombre))
    S(lambda: setattr(o, "Grounded", True))
    return o


def caja(o, org):
    b = o.RangeBox
    return [round(v * 10 + d, 1) for v, d in zip((b.MinPoint.X, b.MinPoint.Y, b.MinPoint.Z, b.MaxPoint.X, b.MaxPoint.Y,
                                                   b.MaxPoint.Z), (org[0], 0, org[2], org[0], 0, org[2]))]


def prisma(nombre, sx, sy, sz, doc_apariencia):
    """Prisma sx x sy x sz con origen en el centro de la base; apariencia copiada de otra pieza."""
    ruta = PZ / f"{nombre}.ipt"
    if ruta.exists():
        return ruta
    doc = app.Documents.Add(inv.K_PART_DOCUMENT, app.FileManager.GetTemplateFile(inv.K_PART_DOCUMENT), False)
    cd = doc.ComponentDefinition
    sk = cd.Sketches.Add(cd.WorkPlanes.Item(2))
    sk.SketchLines.AddAsTwoPointRectangle(sk.ModelToSketchSpace(tg.CreatePoint(-sx / 20, 0, -sz / 20)),
                                          sk.ModelToSketchSpace(tg.CreatePoint(sx / 20, 0, sz / 20)))
    for direc in (20993, 20994):
        f = cd.Features.ExtrudeFeatures.AddByDistanceExtent(sk.Profiles.AddForSolid(), sy / 10, direc, 20481)
        doc.Update()
        if cd.RangeBox.MaxPoint.Y * 10 > sy - 0.1:
            break
        f.Delete()
    ap = S(lambda: doc_apariencia.ActiveAppearance, None) if doc_apariencia is not None else None
    if ap is not None:
        S(lambda: setattr(doc, "ActiveAppearance", ap.CopyTo(doc)))
    inv._iprop(doc, "Design Tracking Properties", "Part Number", nombre)
    inv._iprop(doc, "Design Tracking Properties", "Description", f"{sx:.0f} x {sy:.0f} x {sz:.0f} mm (ajuste simulación)")
    doc.SaveAs(str(ruta), False)
    doc.Close(True)
    return ruta


app.SilentOperation = True
try:
    # ------------------------------------------------------------------ Robot aéreo
    rob = abrir(ROBOT)
    resp = ROBOT.with_name("Robot_Aereo_Pallets_antes_ajustes_sim.iam")
    if not resp.exists():
        rob.SaveAs(str(resp), True)
    rcd = rob.ComponentDefinition
    occ = {o.Name: o for o in inv._items(rcd.Occurrences)}
    if "Travesano_1_L2233" not in occ:
        # A) pórtico 1
        c1a, c1b = caja(occ["Columna_1a"], ORG_R), caja(occ["Columna_1b"], ORG_R)
        z0 = (c1a[2] + c1a[5]) / 2
        mover(occ["Columna_1a"], dz=-37500.0 - z0)
        mover(occ["Columna_1b"], dx=-11700.0 - (c1b[0] + c1b[3]) / 2, dz=-37500.0 - z0)
        ct = caja(occ["Travesano_1"], ORG_R)
        largo = abs(-9617.0 - -11700.0) + COL
        trav = prisma(f"Travesano_portico_L{int(largo)}", largo, COL, COL, occ["Travesano_1"].Definition.Document)
        occ["Travesano_1"].Delete()
        poner(rcd, trav, ORG_R, (-9617.0 + -11700.0) / 2, ct[1], -37500.0, "Travesano_1_L2233")
        log["hecho"].append("A pórtico 1 a Z -37500")
        # B) ménsulas en el pórtico de buffer 2
        tb = occ.get("Portico_buffer_2_travesano")
        if tb is not None:
            cb = caja(tb, ORG_R)
            mens = prisma("Mensula_riel_342", 342.0, COL, COL, tb.Definition.Document)
            tb.Delete()
            zc = (cb[2] + cb[5]) / 2
            poner(rcd, mens, ORG_R, cb[0] + 171.0, cb[1], zc, "Portico_buffer_2_mensula_a")
            poner(rcd, mens, ORG_R, cb[3] - 171.0, cb[1], zc, "Portico_buffer_2_mensula_b")
            log["hecho"].append("B ménsulas en el pórtico de buffer 2")
        # C) buffers centrados con los rieles
        n = 0
        for nm, o in occ.items():
            if nm.startswith(("Pila1_", "Pila2_", "Placa_buffer", "Guia_buffer")):
                mover(o, dx=53.0)
                n += 1
        log["hecho"].append(f"C buffers +53 en X ({n} piezas)")
        rob.Update()
        rob.Save()
    else:
        log["avisos"].append("Robot_Aereo_Pallets ya tenía los ajustes")
    # ------------------------------------------------------------------ Celda A
    cel = abrir(CELDA)
    resp = CELDA.with_name("Celda_A_L3N_antes_ajustes_sim.iam")
    if not resp.exists():
        cel.SaveAs(str(resp), True)
    ccd = cel.ComponentDefinition
    occ = {o.Name: o for o in inv._items(ccd.Occurrences)}
    if "Reja_Norte_aereo_col_2_H1400" not in occ:
        # D) reja norte interna + receptor de la barrera +150 en Z
        n = 0
        for nm, o in occ.items():
            if nm.startswith("Reja_Norte_interna") or (nm.startswith("Barrera") and "receptor" in nm):
                mover(o, dz=150.0)
                n += 1
        log["hecho"].append(f"D reja norte interna y receptor +150 en Z ({n} piezas)")
        # E) muting a la altura del pallet
        n = 0
        for nm, o in occ.items():
            if nm.startswith(("Barrera_brazo", "Barrera_sensor")):
                mover(o, dy=-140.0)
                n += 1
        log["hecho"].append(f"E brazos/sensores de muting a Y 560 ({n} piezas)")
        # F) tramo bajo el robot aéreo a 1400
        col2 = occ["Reja_Norte_interna_col_2"]
        cc = caja(col2, ORG_C)
        doc_pan = occ["Reja_Norte_interna_panel_alto_1"].Definition.Document
        doc_col = col2.Definition.Document
        poste = prisma("Poste_reja_180_H1400", 180.0, 1400.0, 180.0, None)
        panel = prisma("Panel_reja_1240x345", 1240.0, 345.0, 30.0, doc_pan)
        for nm in ("Reja_Norte_interna_col_2", "Reja_Norte_interna_panel_alto_1", "Reja_Norte_interna_panel_alto_2"):
            S(lambda: setattr(occ[nm], "Visible", False))
        poner(ccd, poste, ORG_C, (cc[0] + cc[3]) / 2, 0.0, (cc[2] + cc[5]) / 2, "Reja_Norte_aereo_col_2_H1400")
        for k in (1, 2):
            cp = caja(occ[f"Reja_Norte_interna_panel_bajo_{k}"], ORG_C)
            poner(ccd, panel, ORG_C, (cp[0] + cp[3]) / 2, cp[4] + 5.0, (cp[2] + cp[5]) / 2, f"Reja_Norte_aereo_panel_{k}_H1400")
        log["hecho"].append("F tramo de reja bajo el robot aéreo a 1400 (columna 2 y paneles altos 1-2 ocultos)")
        cel.Update()
        cel.Save()
    else:
        log["avisos"].append("Celda_A_L3N ya tenía los ajustes")
    occ = {o.Name: o for o in inv._items(ccd.Occurrences)}
    log["verificacion"] = {nm: caja(occ[nm], ORG_C) for nm in ("Reja_Norte_interna_col_4", "Barrera_IFM_receptor",
                                                              "Barrera_brazo_emisor", "Reja_Norte_aereo_col_2_H1400",
                                                              "Reja_Norte_aereo_panel_1_H1400") if nm in occ}
finally:
    S(lambda: setattr(app, "SilentOperation", False))
print(json.dumps(log, ensure_ascii=False, indent=1))
