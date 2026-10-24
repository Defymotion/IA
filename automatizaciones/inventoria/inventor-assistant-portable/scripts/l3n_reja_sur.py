"""L3N (Celda_A_L3N.iam, archivo propio; respaldo *_antes_reja_sur.iam): la reja sur estaba casi pegada a la base del
robot y hacen falta >= 600 mm detrás por la caída de los cables de alimentación. Corre hacia -Z (DZ, por defecto 700):
- la reja sur (columnas y paneles Reja_Sur_*),
- los tableros (Kr c4 Technologieschrank:1 y 11-06:1): así la columna 1b del pórtico ya no les tapa la puerta,
y alarga la reja este hasta la esquina nueva con un poste nuevo (copia de Reja_Este_col_1) y dos paneles a medida.
Uso: python l3n_reja_sur.py [DZ]
"""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
import inventor_mcp as inv  # noqa: E402

S = inv._safe
DZ = float(sys.argv[1]) if len(sys.argv) > 1 else 700.0
CELDA = Path(r"C:\DEFYMOTION\L3N\Celdas_IA\Celda_A_L3N.iam")
PZ = Path(r"C:\DEFYMOTION\L3N\Celdas_IA\Ajustes_sim")
ORG_C = (-6503.1706, 0.0, -35622.3429)
app = inv._inventor(start_if_needed=False)
tg = app.TransientGeometry
log = {"avisos": [], "hecho": []}


def mover(o, dz):
    m = o.Transformation
    t = tg.CreateMatrix()
    t.SetTranslation(tg.CreateVector(0, 0, dz / 10))
    m.TransformBy(t)
    g0 = S(lambda: o.Grounded, False)
    S(lambda: setattr(o, "Grounded", False))
    o.Transformation = m
    if g0:
        S(lambda: setattr(o, "Grounded", True))


def caja(o):
    b = o.RangeBox
    return [round(v * 10 + d, 1) for v, d in zip((b.MinPoint.X, b.MinPoint.Y, b.MinPoint.Z, b.MaxPoint.X, b.MaxPoint.Y,
                                                   b.MaxPoint.Z), (ORG_C[0], 0, ORG_C[2], ORG_C[0], 0, ORG_C[2]))]


def prisma(nombre, sx, sy, sz, doc_apariencia):
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
    PZ.mkdir(parents=True, exist_ok=True)
    cel = next((d for d in inv._items(app.Documents) if S(lambda: Path(d.FullFileName).resolve() == CELDA.resolve(), False)), None)
    cel = cel or app.Documents.Open(str(CELDA), False)
    resp = CELDA.with_name("Celda_A_L3N_antes_reja_sur.iam")
    if not resp.exists():
        cel.SaveAs(str(resp), True)
    cd = cel.ComponentDefinition
    occ = {o.Name: o for o in inv._items(cd.Occurrences)}
    if "Reja_Este_col_0" in occ:
        log["avisos"].append("ya estaba hecho (existe Reja_Este_col_0)")
    else:
        log["antes"] = {n: caja(occ[n]) for n in ("Reja_Sur_col_1", "Kr c4 Technologieschrank:1", "11-06:1", "Reja_Este_col_1",
                                                 "Reja_Este_panel_bajo_1", "base_principal_circular:2")}
        n = 0
        for nm, o in occ.items():
            if nm.startswith("Reja_Sur") or nm in ("Kr c4 Technologieschrank:1", "11-06:1"):
                mover(o, -DZ)
                n += 1
        log["hecho"].append(f"reja sur y tableros {-DZ:+.0f} en Z ({n} ocurrencias)")
        # reja este: poste nuevo en la esquina nueva + paneles a medida entre él y Reja_Este_col_1
        c1 = occ["Reja_Este_col_1"]
        m = c1.Transformation
        t = tg.CreateMatrix()
        t.SetTranslation(tg.CreateVector(0, 0, -DZ / 10))
        m.TransformBy(t)
        o = cd.Occurrences.Add(c1.Definition.Document.FullFileName, m)
        S(lambda: setattr(o, "Name", "Reja_Este_col_0"))
        S(lambda: setattr(o, "Grounded", True))
        cc1 = caja(c1)
        pb = caja(occ["Reja_Este_panel_bajo_1"])
        pa = caja(occ["Reja_Este_panel_alto_1"])
        largo = DZ + 97.0                                     # mismo solape que los paneles de 1240 cada 1143
        doc_pan = occ["Reja_Este_panel_bajo_1"].Definition.Document
        zc = (cc1[2] + cc1[5]) / 2 - DZ / 2
        for nombre, p in (("Reja_Este_panel_bajo_0", pb), ("Reja_Este_panel_alto_0", pa)):
            ruta = prisma(f"Panel_reja_{int(largo)}x{int(p[4] - p[1])}", p[3] - p[0], p[4] - p[1], largo, doc_pan)
            mm_ = tg.CreateMatrix()
            mm_.SetTranslation(tg.CreateVector(((p[0] + p[3]) / 2 - ORG_C[0]) / 10, p[1] / 10, (zc - ORG_C[2]) / 10))
            o = cd.Occurrences.Add(str(ruta), mm_)
            S(lambda: setattr(o, "Name", nombre))
            S(lambda: setattr(o, "Grounded", True))
        log["hecho"].append(f"reja este alargada {DZ:.0f} (poste Reja_Este_col_0 y paneles de {largo:.0f})")
        cel.Update()
        cel.Save()
        occ = {o.Name: o for o in inv._items(cd.Occurrences)}
        log["despues"] = {n: caja(occ[n]) for n in ("Reja_Sur_col_1", "Reja_Sur_panel_bajo_1", "Kr c4 Technologieschrank:1",
                                                   "11-06:1", "Reja_Este_col_0", "Reja_Este_panel_bajo_0", "Reja_Este_panel_alto_0",
                                                   "Reja_Sur_col_5")}
        b = log["antes"]["base_principal_circular:2"]
        log["luz_base_robot_reja"] = round(b[2] - log["despues"]["Reja_Sur_panel_bajo_1"][5], 1)
finally:
    S(lambda: setattr(app, "SilentOperation", False))
print(json.dumps(log, ensure_ascii=False, indent=1))
