"""L3N v5: ingreso de cajas real en las celdas A y B (archivos propios de Celdas_IA; respaldo *_antes_infeed_v5.iam).
A) Celda_A_L3N: el pateador (DSBC-32-300) se acerca 120 mm a T3: la chapa queda a 44 mm de la caja y con los 300 mm de
   carrera la caja termina 20 mm adentro de la cinta interna (antes quedaba sobre T3; la simulación usaba 450).
   Informa solapes (cajas) del pateador movido contra las piezas de la cinta de llegada.
B) Celda_B_existente (representación de la celda instalada):
   - pateador +150 mm hacia la cinta Tetra (la caja termina ~60 mm adentro de la cinta 1);
   - cinta 1 (BM2000_CeldaB_1) -339 mm en X: empieza junto a la cinta de llegada (antes había 350 mm de hueco);
   - entre la cinta 1 y la 2 (343 mm) va el freno con contador: módulo fijo (marco + mesa) y el tope del freno
     (pieza aparte, la anima la simulación) + sensor contador;
   - oculta "Empujador 01:1" (otro empujador del CAD de ADECO superpuesto con el pateador, como en A).
Uso: python l3n_infeed_v5.py
"""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
import inventor_mcp as inv  # noqa: E402

S = inv._safe
BASE = Path(r"C:\DEFYMOTION\L3N\Celdas_IA")
PZ = BASE / "Ajustes_sim"
CEL_A, CEL_B = BASE / "Celda_A_L3N.iam", BASE / "Celda_B_existente.iam"
ORG_A = (-6503.1706, 0.0, -35622.3429)
ORG_B = (-6495.6706, 0.0, -43982.2999)
DX_PAT_A, DX_PAT_B, DX_CINTA1_B = 120.0, 150.0, -339.0
app = inv._inventor(start_if_needed=False)
tg = app.TransientGeometry
log = {"avisos": [], "hecho": []}


def its(x):
    if x is None or isinstance(x, list):
        return x or []
    try:
        return inv._items(x)
    except Exception:  # noqa: BLE001
        return []


def abrir(p):
    d = next((d for d in its(app.Documents) if S(lambda: Path(d.FullFileName).resolve() == Path(p).resolve(), False)), None)
    return d or app.Documents.Open(str(p), False)


def caja(o, org):
    b = o.RangeBox
    return [round(b.MinPoint.X * 10 + org[0], 1), round(b.MinPoint.Y * 10, 1), round(b.MinPoint.Z * 10 + org[2], 1),
            round(b.MaxPoint.X * 10 + org[0], 1), round(b.MaxPoint.Y * 10, 1), round(b.MaxPoint.Z * 10 + org[2], 1)]


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


def prisma(nombre, sx, sy, sz, apariencia=None):
    """Pieza prisma con el origen en el centro de la base (X, Z centrados; Y de 0 a sy)."""
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
    if apariencia:
        for lib in its(app.AssetLibraries):
            a = next((x for x in its(S(lambda: lib.AppearanceAssets, None)) if S(lambda: x.DisplayName.lower(), "").startswith(apariencia)), None)
            if a is not None:
                S(lambda: setattr(doc, "ActiveAppearance", a.CopyTo(doc)))
                break
    inv._iprop(doc, "Design Tracking Properties", "Part Number", nombre)
    inv._iprop(doc, "Design Tracking Properties", "Description", f"{sx:.0f} x {sy:.0f} x {sz:.0f} mm (ingreso v5, representación)")
    doc.SaveAs(str(ruta), False)
    doc.Close(True)
    return ruta


def poner(cd, ruta, org, x, y, z, nombre):
    m = tg.CreateMatrix()
    m.SetTranslation(tg.CreateVector((x - org[0]) / 10, y / 10, (z - org[2]) / 10))
    o = cd.Occurrences.Add(str(ruta), m)
    S(lambda: setattr(o, "Name", nombre))
    S(lambda: setattr(o, "Grounded", True))
    return o


def solapes(a_list, b_list):
    out = []
    for na, ca in a_list:
        for nb, cb in b_list:
            ov = [min(ca[3 + i], cb[3 + i]) - max(ca[i], cb[i]) for i in range(3)]
            if min(ov) > 1.0:
                out.append((na, nb, [round(v) for v in ov]))
    return out


app.SilentOperation = True
try:
    PZ.mkdir(parents=True, exist_ok=True)
    # ---------------------------------------------------------------- A
    ca = abrir(CEL_A)
    resp = CEL_A.with_name("Celda_A_L3N_antes_infeed_v5.iam")
    if not resp.exists():
        ca.SaveAs(str(resp), True)
    occ = {o.Name: o for o in its(ca.ComponentDefinition.Occurrences)}
    pat = occ["Ensamble pateador adeco:1"]
    antes = caja(pat, ORG_A)
    if antes[3] > -12370.2 + DX_PAT_A / 2:            # la chapa ya está corrida (corrida previa)
        log["avisos"].append(f"A ya estaba hecho (x máx del pateador {antes[3]})")
    else:
        mover(pat, dx=DX_PAT_A)
        ca.Update()
        log["hecho"].append(f"A: pateador +{DX_PAT_A:.0f} en X ({antes[3]} -> {caja(pat, ORG_A)[3]})")
        ca.Save()
    piezas_pat = [(h.Name, caja(h, ORG_A)) for h in its(pat.SubOccurrences)]
    cinta = occ.get("Cinta_Llegada_A")
    piezas_t3 = []
    if cinta is not None:
        for h in its(cinta.SubOccurrences):
            if h.Name.startswith(("Cinta_Llegada_T3", "Curva_2")):
                piezas_t3 += [(h.Name + "/" + h2.Name, caja(h2, ORG_A)) for h2 in its(h.SubOccurrences)] or [(h.Name, caja(h, ORG_A))]
    log["A_solapes_pateador_vs_T3"] = solapes(piezas_pat, piezas_t3)[:40]
    log["A_chapa_pateador"] = next((c for n, c in piezas_pat if n.startswith("chapa pateador")), None)
    # ---------------------------------------------------------------- B
    cb = abrir(CEL_B)
    resp = CEL_B.with_name("Celda_B_existente_antes_infeed_v5.iam")
    if not resp.exists():
        cb.SaveAs(str(resp), True)
    bcd = cb.ComponentDefinition
    occ = {o.Name: o for o in its(bcd.Occurrences)}
    if "IA_Freno_contador_B" in occ:
        log["avisos"].append("B ya estaba hecho")
    else:
        mover(occ["Ensamble pateador adeco:1"], dx=DX_PAT_B)
        mover(occ["BM2000_CeldaB_1"], dx=DX_CINTA1_B)
        S(lambda: setattr(occ["Empujador 01:1"], "Visible", False))
        bm1, bm2 = caja(occ["BM2000_CeldaB_1"], ORG_B), caja(occ["BM2000_CeldaB_2"], ORG_B)
        x0, x1 = bm1[3] + 2.0, bm2[0] - 2.0               # hueco entre cintas
        zc = (bm2[2] + bm2[5]) / 2.0 - 0.0
        lat = [caja(h, ORG_B) for h in its(occ["BM2000_CeldaB_2"].SubOccurrences) if h.Name.startswith("Lateral")]
        if len(lat) == 2:
            zc = (min(l[2] for l in lat) + max(l[5] for l in lat)) / 2.0
        L = x1 - x0
        marco = prisma(f"Freno_contador_marco_L{int(L)}", L, 200.0, 270.0, "acero inoxidable")
        poner(bcd, marco, ORG_B, (x0 + x1) / 2, 598.0, zc, "IA_Freno_contador_B")
        tope = prisma("Freno_contador_tope_12x160x240", 12.0, 160.0, 240.0, "aluminio")
        poner(bcd, tope, ORG_B, x1 - 8.0, 700.0, zc, "IA_Freno_contador_B_tope")       # abajo (abierto)
        sensor = prisma("Sensor_contador_40x60x30", 40.0, 60.0, 30.0, "plástico")
        poner(bcd, sensor, ORG_B, x0 - 120.0, 860.0, zc + 175.0, "IA_Freno_contador_B_sensor")
        cb.Update()
        cb.Save()
        log["hecho"].append(f"B: pateador +{DX_PAT_B:.0f}, cinta 1 {DX_CINTA1_B:+.0f}, freno con contador en X {x0:.1f}..{x1:.1f} "
                            f"(z {zc:.1f}), Empujador 01 oculto")
    occ = {o.Name: o for o in its(bcd.Occurrences)}
    log["B_cajas"] = {n: caja(occ[n], ORG_B) for n in ("Ensamble pateador adeco:1", "BM2000_CeldaB_1", "BM2000_CeldaB_2",
                                                     "IA_Freno_contador_B", "IA_Freno_contador_B_tope", "IA_Freno_contador_B_sensor",
                                                     "Correa transportadora recta:13", "Tope cinta tetra:1") if n in occ}
    pb = occ["Ensamble pateador adeco:1"]
    log["B_chapa_pateador"] = next((caja(h, ORG_B) for h in its(pb.SubOccurrences) if h.Name.startswith("chapa pateador")), None)
    log["B_solapes_pateador"] = solapes([(h.Name, caja(h, ORG_B)) for h in its(pb.SubOccurrences)],
                                        [(n, caja(o, ORG_B)) for n, o in occ.items() if n.startswith(("Correa", "Tope cinta", "BM2000", "Cinta"))])[:30]
finally:
    S(lambda: setattr(app, "SilentOperation", False))
print(json.dumps(log, ensure_ascii=False, indent=1))
