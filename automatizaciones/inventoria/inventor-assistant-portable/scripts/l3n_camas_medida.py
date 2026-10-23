"""L3N: camas de rolos de la línea de pallets a la medida justa, editando una COPIA del mismo CAD
(Roller_Conveyor_Straight_400V_FlatBelt: sólido multicuerpo importado RM8x10...step.ipt + 4 patas Conv_Ayak).
Para cada hueco alarga la cama vecina en DELTA:
  - copia el .ipt a Celdas_IA\\Camas_medida\\RM8x10_cama_L<L>.ipt (el original no se toca);
  - "estira": los cuerpos enteros más allá del plano de corte se trasladan DELTA (MoveFeature) y en los que cruzan
    el plano (largueros, guías) se mueven sólo las caras del extremo (MoveFace);
  - agrega los rodillos que faltan (Ø89, mismo largo y paso 150) con la apariencia de los existentes;
  - arma Cama_rolos_400V_L<L>.iam con la pieza estirada y las 4 patas originales (las de atrás corridas DELTA);
  - en Linea_Pallets.iam reemplaza la cama vecina por la nueva y la corre para que cubra el hueco; borra los bloques
    gráficos IA_Cama_amedida_*.
Uso: python l3n_camas_medida.py
"""
import json
import shutil
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
import inventor_mcp as inv  # noqa: E402

S = inv._safe
BASE = Path(r"C:\DEFYMOTION\L3N\Celdas_IA")
LINEA = BASE / "Linea_Pallets.iam"
DEST = BASE / "Camas_medida"
SRC_DIR = Path(r"C:\DEFYMOTION\L3N\ADECO 12-12-25\CAD\eur-pallet-transform-line-1.snapshot.2\Eur Pallet Transform Line"
               r"\Eur Pallet Transform Line")
SRC_IAM = SRC_DIR / "Roller_Conveyor_Straight_400V_FlatBelt.iam"
SRC_IPT = SRC_DIR / "RM8x10_800020-5500-429-19-0_B_IAD_000.step.ipt"
L0 = 2038.0
VER = sys.argv[sys.argv.index("--ver") + 1] if "--ver" in sys.argv else ""
Z_CORTE = -1214.0                 # entre los rodillos de -1139 y -1289 (coordenadas de la pieza, mm)
PASO, R_ROD, Y_ROD, X_ROD = 150.0, 44.5, 43.8, (-785.0, 510.0)
# (ocurrencia vecina en Linea_Pallets, eje del layout, lado del hueco, delta)
CAMAS = [("Roller_Conveyor_Straight_400V_FlatBelt:5", 2, "min", 610.0),
         ("Roller_Conveyor_Straight_400V_FlatBelt:3", 2, "min", 882.0),
         ("IA_Cama_linea_3", 0, "max", 1282.0)]

app = inv._inventor(start_if_needed=False)
tg = app.TransientGeometry
to = app.TransientObjects
log = {"avisos": [], "camas": []}


def abrir(p, visible=False):
    d = next((d for d in inv._items(app.Documents) if S(lambda: Path(d.FullFileName).resolve() == p.resolve(), False)), None)
    return d or app.Documents.Open(str(p), visible)


def caja(o):
    b = o.RangeBox
    return [round(v * 10, 1) for v in (b.MinPoint.X, b.MinPoint.Y, b.MinPoint.Z, b.MaxPoint.X, b.MaxPoint.Y, b.MaxPoint.Z)]


def estirar_pieza(L, delta):
    ruta = DEST / f"RM8x10_cama_L{round(L)}{VER}.ipt"
    shutil.copyfile(SRC_IPT, ruta)
    doc = app.Documents.Open(str(ruta), False)
    cd = doc.ComponentDefinition
    zc = Z_CORTE / 10
    enteros = to.CreateObjectCollection()
    parciales = []
    ap_rod = None
    for body in inv._items(cd.SurfaceBodies):
        b = body.RangeBox
        if b.MaxPoint.Z < zc:
            enteros.Add(body)
        elif b.MinPoint.Z < zc < b.MaxPoint.Z:
            parciales.append(body)
        if ap_rod is None and S(lambda: body.Faces.Count) == 3 and abs((b.MaxPoint.Y - b.MinPoint.Y) * 10 - 2 * R_ROD) < 1:
            ap_rod = S(lambda: body.Appearance)
    info = {"enteros": enteros.Count, "parciales": len(parciales), "caras_movidas": 0, "rodillos_nuevos": 0}
    dz = -delta / 10                                   # el extremo lejano está hacia -Z de la pieza
    # 1) trasladar los cuerpos enteros
    if enteros.Count:
        md = cd.Features.MoveFeatures.CreateMoveDefinition(enteros)
        md.AddFreeDrag(0, 0, dz)
        cd.Features.MoveFeatures.Add(md)
    # 2) estirar los que cruzan el plano: caras con todos sus vértices más allá del corte
    for body in parciales:
        fc = to.CreateFaceCollection()
        for f in inv._items(body.Faces):
            vs = list(inv._items(S(lambda: f.Vertices, []) or []))
            if vs and all(v.Point.Z < zc - 0.001 for v in vs):
                fc.Add(f)
        if fc.Count == 0:
            continue
        mf = cd.Features.MoveFaceFeatures
        zmin0 = body.RangeBox.MinPoint.Z
        hecho = False
        for modo in ("libre", "rev", "dir"):
            try:
                d = mf.CreateDefinition(fc)
                if modo == "libre":
                    mt = tg.CreateMatrix()
                    mt.SetTranslation(tg.CreateVector(0, 0, dz))
                    d.SetFreeMoveType(mt)
                else:
                    d.SetDirectionAndDistanceMoveType(abs(dz), cd.WorkAxes.Item(3), modo == "rev")
                feat = mf.Add(d)
                doc.Update()
                if abs(body.RangeBox.MinPoint.Z - (zmin0 + dz)) < 0.05:
                    hecho = True
                    info["caras_movidas"] += fc.Count
                    break
                feat.Delete()
                doc.Update()
            except Exception as e:  # noqa: BLE001
                info.setdefault("errores_modo", []).append(f"{modo}: {e!r}"[:160])
        if not hecho:
            log["avisos"].append(f"L{round(L)}: no pude estirar {S(lambda: body.Name)}")
    doc.Update()
    # 3) rodillos nuevos en el tramo vacío
    primero_movido = -1289.0 - delta
    pos, z = [], -1289.0
    while z > primero_movido + 100.0:
        pos.append(z)
        z -= PASO
    if pos:
        pl = cd.WorkPlanes.AddByPlaneAndOffset(cd.WorkPlanes.Item(1), X_ROD[0] / 10)
        S(lambda: setattr(pl, "Visible", False))
        sk = cd.Sketches.Add(pl)
        for zz in pos:
            sk.SketchCircles.AddByCenterRadius(sk.ModelToSketchSpace(tg.CreatePoint(X_ROD[0] / 10, Y_ROD / 10, zz / 10)), R_ROD / 10)
        prof = sk.Profiles.AddForSolid()
        largo = (X_ROD[1] - X_ROD[0]) / 10
        antes = cd.SurfaceBodies.Count
        f = None
        for direc in (20993, 20994):
            ed = cd.Features.ExtrudeFeatures.CreateExtrudeDefinition(prof, 20485)     # nuevo cuerpo
            ed.SetDistanceExtent(largo, direc)
            f = cd.Features.ExtrudeFeatures.Add(ed)
            doc.Update()
            if f.SurfaceBodies.Count and f.SurfaceBodies.Item(1).RangeBox.MaxPoint.X > X_ROD[1] / 10 - 0.05:
                break
            f.Delete()
            f = None
        if f is None:
            log["avisos"].append(f"L{round(L)}: no pude extruir los rodillos nuevos")
        else:
            for k in range(cd.SurfaceBodies.Count - antes):
                bd = cd.SurfaceBodies.Item(antes + k + 1)
                if ap_rod is not None:
                    S(lambda: setattr(bd, "Appearance", ap_rod))
            info["rodillos_nuevos"] = len(pos)
    doc.Update()
    b = cd.RangeBox
    info["caja"] = [round(v * 10, 1) for v in (b.MinPoint.X, b.MinPoint.Y, b.MinPoint.Z, b.MaxPoint.X, b.MaxPoint.Y, b.MaxPoint.Z)]
    inv._iprop(doc, "Design Tracking Properties", "Description", f"CAMA DE ROLOS 400V A MEDIDA L={round(L)} (COPIA ESTIRADA)")
    doc.Save()
    doc.Close(True)
    return ruta, info


def armar_cama(L, delta, ipt):
    src = abrir(SRC_IAM)
    piezas = []                                     # (ruta, matriz, es_pata, nombre)
    for o in inv._items(src.ComponentDefinition.Occurrences):
        if S(lambda: o.SubOccurrences.Count, 0):
            for so in inv._items(o.SubOccurrences):
                piezas.append((ipt, so.Transformation, False, "Cama"))
        else:
            piezas.append((o.Definition.Document.FullFileName, o.Transformation, True, o.Name.split(":")[0]))
    m_cama = next(p[1] for p in piezas if not p[2])
    inv_c = m_cama.Copy()
    inv_c.Invert()
    eje_z = tg.CreateVector(0, 0, -delta / 10)
    eje_z.TransformBy(m_cama)                       # -Z de la pieza expresado en el ensamble
    ens = app.Documents.Add(inv.K_ASSEMBLY_DOCUMENT, app.FileManager.GetTemplateFile(inv.K_ASSEMBLY_DOCUMENT), False)
    cd = ens.ComponentDefinition
    n_pata = 0
    for ruta, m, es_pata, nombre in piezas:
        mm = m.Copy()
        if es_pata:
            p = tg.CreatePoint(mm.Translation.X, mm.Translation.Y, mm.Translation.Z)
            p.TransformBy(inv_c)
            if p.Z < Z_CORTE / 10:
                mm.SetTranslation(tg.CreateVector(mm.Translation.X + eje_z.X, mm.Translation.Y + eje_z.Y, mm.Translation.Z + eje_z.Z))
            n_pata += 1
            nombre = f"Pata_{n_pata}"
        o = cd.Occurrences.Add(str(ruta), mm)
        S(lambda: setattr(o, "Name", nombre))
        S(lambda: setattr(o, "Grounded", True))
    ruta = DEST / f"Cama_rolos_400V_L{round(L)}{VER}.iam"
    inv._iprop(ens, "Design Tracking Properties", "Description", f"CAMA DE ROLOS 400V A MEDIDA L={round(L)}")
    ens.SaveAs(str(ruta), False)
    ens.Close(True)
    return ruta


app.SilentOperation = True
try:
    DEST.mkdir(parents=True, exist_ok=True)
    lin = abrir(LINEA)
    lcd = lin.ComponentDefinition
    for o in list(inv._items(lcd.Occurrences)):
        if o.Name.startswith("IA_Cama_amedida"):
            o.Delete()
    occs = {o.Name: o for o in inv._items(lcd.Occurrences)}
    for nombre, eje, lado, delta in CAMAS:
        L = L0 + delta
        ipt, info = estirar_pieza(L, delta)
        iam = armar_cama(L, delta, ipt)
        ya = f"IA_Cama_L{round(L)}_{nombre.split(':')[-1]}"
        rehecha = ya in occs
        o = occs.get(ya) or occs.get(nombre)
        if o is None:
            log["avisos"].append(f"no encontré {nombre}")
            continue
        c0 = caja(o)
        o.Replace(str(iam), False)
        lin.Update()
        c1 = caja(o)
        if rehecha:                                   # ya estaba alargada y corrida: conservar la posición
            objetivo = c0[eje] if lado == "min" else c0[eje + 3]
        else:
            objetivo = c0[eje] - delta if lado == "min" else c0[eje + 3] + delta
        actual = c1[eje] if lado == "min" else c1[eje + 3]
        mov = objetivo - actual
        if abs(mov) > 0.5:
            m = o.Transformation
            v = [0.0, 0.0, 0.0]
            v[eje] = mov / 10
            m.SetTranslation(tg.CreateVector(m.Translation.X + v[0], m.Translation.Y + v[1], m.Translation.Z + v[2]), False)
            S(lambda: setattr(o, "Grounded", False))
            o.SetTransformWithoutConstraints(m)
            S(lambda: setattr(o, "Grounded", True))
        S(lambda: setattr(o, "Name", f"IA_Cama_L{round(L)}_{nombre.split(':')[-1]}"))
        c2 = caja(o)
        log["camas"].append({"vecina": nombre, "largo": round(L), "pieza": info, "antes": c0, "despues": c2,
                             "corrida_mm": round(mov, 1)})
        if abs((c2[eje + 3] - c2[eje]) - (c0[eje + 3] - c0[eje] + (0 if rehecha else delta))) > 2:
            log["avisos"].append(f"{nombre}: el largo final no coincide con el esperado")
    lin.Update()
    lin.Save()
finally:
    S(lambda: setattr(app, "SilentOperation", False))
print(json.dumps(log, ensure_ascii=False, indent=1))
