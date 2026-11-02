"""L3N: layout con la disposición final de los transportes nuevos + extensión del riel del robot aéreo y buffer de cartones.
Trabaja sobre una COPIA del layout del usuario (el original no se toca):
  1. Guarda una copia del layout abierto (o del archivo) como Celdas_IA\\<plan.copia> y la abre.
  2. Mueve ocurrencias de primer nivel (plan.mover: nombre -> matriz 3x4 en mm), oculta (plan.ocultar) e inserta
     módulos sueltos tomando el archivo de una subocurrencia de un grupo (plan.agregar).
  3. Arma Celdas_IA\\Robot_Aereo\\Extension_riel_buffer_cartones.iam (coordenadas del layout): riel +2 m, pórtico nuevo
     y buffer de cartones (pallet + pila 1200x1000 con 4 guías), reusando piezas del robot y lo inserta.
  4. Choques por caja de lo movido/agregado contra celdas, robot y el resto de los transportes.
Uso: python l3n_layout_final.py <plan.json> [--rehacer-ext]
"""
import json
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
import inventor_mcp as inv  # noqa: E402

S = inv._safe
plan = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
CELDAS = Path(r"C:\DEFYMOTION\L3N\Celdas_IA")
LAY = CELDAS / "LayoutL3N_Celdas.iam"
COPIA = CELDAS / plan["copia"]
RDIR = CELDAS / "Robot_Aereo"
EXT = RDIR / "Extension_riel_buffer_cartones.iam"
app = inv._inventor(start_if_needed=False)
tg = app.TransientGeometry
log = {"avisos": [], "movidos": {}, "agregados": {}, "ext": {}, "choques_caja": []}
T0 = time.time()


def matriz(m):
    M = tg.CreateMatrix()
    for i in range(3):
        for j in range(4):
            M.SetCell(i + 1, j + 1, m[i * 4 + j] / (10.0 if j == 3 else 1.0))
    return M


def lista(M):
    return [round(M.Cell(i + 1, j + 1) * (10.0 if j == 3 else 1.0), 3) for i in range(3) for j in range(4)]


def caja(b):
    return [round(b.MinPoint.X * 10, 1), round(b.MinPoint.Y * 10, 1), round(b.MinPoint.Z * 10, 1),
            round(b.MaxPoint.X * 10, 1), round(b.MaxPoint.Y * 10, 1), round(b.MaxPoint.Z * 10, 1)]


def solapa(a, b, tol=2.0):
    return all(a[i] < b[i + 3] - tol and b[i] < a[i + 3] - tol for i in range(3))


def por_nombre(occs, nombre):
    return next((o for o in inv._items(occs) if o.Name == nombre), None)


def desplazada(M, dx, dy, dz):
    m = lista(M)
    m[3] += dx
    m[7] += dy
    m[11] += dz
    return m


def apariencia(nombre_parcial):
    for lib in inv._items(app.AssetLibraries):
        for asset in inv._items(S(lambda: lib.AppearanceAssets, []) or []):
            if (S(lambda: asset.DisplayName, "") or "").lower().startswith(nombre_parcial):
                return asset
    return None


def prisma(nombre, sx, sy, sz, colores=()):
    """Pieza prismática sx x sy x sz (mm), origen en el centro de la base (como las del robot aéreo)."""
    ruta = RDIR / f"{nombre}.ipt"
    if ruta.exists():
        return ruta
    doc = app.Documents.Add(inv.K_PART_DOCUMENT, app.FileManager.GetTemplateFile(inv.K_PART_DOCUMENT), False)
    cd = doc.ComponentDefinition
    sk = cd.Sketches.Add(cd.WorkPlanes.Item(2))      # XZ
    sk.SketchLines.AddAsTwoPointRectangle(sk.ModelToSketchSpace(tg.CreatePoint(-sx / 20, 0, -sz / 20)),
                                          sk.ModelToSketchSpace(tg.CreatePoint(sx / 20, 0, sz / 20)))
    for direc in (20993, 20994):
        f = cd.Features.ExtrudeFeatures.AddByDistanceExtent(sk.Profiles.AddForSolid(), sy / 10, direc, 20481)
        doc.Update()
        if cd.RangeBox.MaxPoint.Y * 10 > sy - 0.1:
            break
        f.Delete()
    for c in colores:
        ap = apariencia(c)
        if ap is not None:
            S(lambda: setattr(doc, "ActiveAppearance", ap.CopyTo(doc)))
            break
    inv._iprop(doc, "Design Tracking Properties", "Part Number", nombre)
    inv._iprop(doc, "Design Tracking Properties", "Description", f"{sx:.0f} x {sy:.0f} x {sz:.0f} mm (volumen estimado)")
    doc.SaveAs(str(ruta), False)
    doc.Close(True)
    return ruta


app.SilentOperation = True
try:
    # ------------------------------------------------------------ 1. copia del layout
    lay = next((d for d in inv._items(app.Documents) if S(lambda d=d: Path(d.FullFileName).resolve() == LAY.resolve(), False)), None)
    cop = next((d for d in inv._items(app.Documents) if S(lambda d=d: Path(d.FullFileName).resolve() == COPIA.resolve(), False)), None)
    if cop is None:
        if COPIA.exists():
            log["avisos"].append(f"{COPIA.name} ya existía: se reabre y se ajusta (no se vuelve a copiar)")
        else:
            if lay is None:
                lay = app.Documents.Open(str(LAY), False)
                log["avisos"].append("el layout no estaba abierto: se abrió invisible para copiarlo")
            lay.SaveAs(str(COPIA), True)          # SaveCopyAs: el original queda igual y abierto
        cop = app.Documents.Open(str(COPIA), True)
    cd = cop.ComponentDefinition
    occs = cd.Occurrences
    # ------------------------------------------------------------ 2. transportes
    for nombre, m in plan["mover"].items():
        o = por_nombre(occs, nombre)
        if o is None:
            log["avisos"].append(f"no encontré {nombre}")
            continue
        antes = lista(o.Transformation)
        g = S(lambda: o.Grounded, False)
        S(lambda: setattr(o, "Grounded", False))
        o.Transformation = matriz(m)
        S(lambda: setattr(o, "Grounded", g))
        log["movidos"][nombre] = {"antes": antes, "despues": lista(o.Transformation)}
    for nombre in plan.get("ocultar", []):
        o = por_nombre(occs, nombre)
        if o is not None:
            o.Visible = False
            log["movidos"][nombre] = "oculto"
    for a in plan.get("agregar", []):
        viejo = por_nombre(occs, a["nombre"])
        if viejo is not None:
            viejo.Delete()
        grupo = por_nombre(occs, a["de"][0])
        s = next((x for x in inv._items(grupo.SubOccurrences) if x.Name.startswith(a["de"][1])), None)
        ruta = s.Definition.Document.FullFileName
        o = occs.Add(ruta, matriz(a["M"]))
        o.Grounded = True
        S(lambda: setattr(o, "Name", a["nombre"]))
        log["agregados"][a["nombre"]] = {"archivo": ruta, "caja": caja(o.RangeBox)}
    cop.Update()
    # ------------------------------------------------------------ 3. extensión del riel + buffer de cartones
    rob = next((o for o in inv._items(occs) if o.Name.startswith("Robot_Aereo_Pallets")), None)
    rs = {x.Name: x for x in inv._items(rob.SubOccurrences)}
    viejo = por_nombre(occs, "IA_Extension_riel_buffer_cartones")
    if viejo is not None:
        viejo.Delete()
    if "--rehacer-ext" in sys.argv and EXT.exists():
        for d in list(inv._items(app.Documents)):
            if S(lambda d=d: Path(d.FullFileName).resolve() == EXT.resolve(), False):
                S(lambda d=d: d.Close(True))
        EXT.unlink()
    e = plan["extension"]
    if not EXT.exists():
        ed = app.Documents.Add(inv.K_ASSEMBLY_DOCUMENT, app.FileManager.GetTemplateFile(inv.K_ASSEMBLY_DOCUMENT), False)
        eo = ed.ComponentDefinition.Occurrences

        def poner(nombre, ruta, m):
            x = eo.Add(str(ruta), matriz(m))
            x.Grounded = True
            S(lambda: setattr(x, "Name", nombre))
            return x

        riel = prisma(f"Riel_extension_L{e['largo_riel']:.0f}", 100, 100, e["largo_riel"], ("acero", "steel"))
        pila = prisma("Pila_cartones_1200x1000x900", 1200, 900, 1000, ("cart", "card", "madera", "wood", "naranja"))
        for i, x in enumerate(e["x_rieles"]):
            poner(f"Riel_ext_{i + 1}", riel, [1, 0, 0, x, 0, 1, 0, e["y_riel"], 0, 0, 1, e["z_riel_centro"]])
        for nuevo, base in (("Columna_ext_a", "Columna_3a"), ("Columna_ext_b", "Columna_3b"), ("Travesano_ext", "Travesano_3")):
            r = rs[base]
            poner(nuevo, r.Definition.Document.FullFileName, desplazada(r.Transformation, 0, 0, e["dz_portico"]))
        r = rs["Pila1_pallet_1"]
        poner("Buffer_cartones_pallet", r.Definition.Document.FullFileName, desplazada(r.Transformation, 0, 0, e["dz_buffer"]))
        for k in range(1, 5):
            for t in ("Guia", "Placa"):
                r = rs[f"{t}_buffer_1_{k}"]
                poner(f"Buffer_cartones_{t.lower()}_{k}", r.Definition.Document.FullFileName,
                      desplazada(r.Transformation, 0, 0, e["dz_buffer"]))
        poner("Pila_cartones", pila, [1, 0, 0, e["pila_centro"][0], 0, 1, 0, e["pila_centro"][1], 0, 0, 1, e["pila_centro"][2]])
        ed.Update()
        ed.SaveAs(str(EXT), False)
        log["ext"]["piezas"] = {x.Name: caja(x.RangeBox) for x in inv._items(eo)}
        ed.Close(True)
    o = occs.Add(str(EXT), tg.CreateMatrix())
    o.Grounded = True
    S(lambda: setattr(o, "Name", "IA_Extension_riel_buffer_cartones"))
    log["ext"]["caja"] = caja(o.RangeBox)
    cop.Update()
    # ------------------------------------------------------------ 4. choques por caja
    nuevos = list(plan["mover"]) + [a["nombre"] for a in plan.get("agregar", [])] + ["IA_Extension_riel_buffer_cartones"]
    piezas = {}
    for x in inv._items(occs):
        if not S(lambda x=x: x.Visible, True):
            continue
        subs = [s for s in inv._items(S(lambda x=x: x.SubOccurrences, []) or []) if S(lambda s=s: s.Visible, True)]
        lst = []
        for s in subs or [x]:
            c = S(lambda s=s: caja(s.RangeBox), None)
            if c and c[3] - c[0] > 0.5:
                lst.append((s.Name, c))
        piezas[x.Name] = lst
    for n in nuevos:
        for a_n, a_c in piezas.get(n, []):
            for m_n, lst in piezas.items():
                if m_n == n or m_n.startswith("Paredes"):
                    continue
                for b_n, b_c in lst:
                    if solapa(a_c, b_c):
                        log["choques_caja"].append([n, a_n, m_n, b_n, a_c, b_c])
    log["cajas_modulos"] = {n: caja(por_nombre(occs, n).RangeBox) for n in nuevos if por_nombre(occs, n) is not None}
    cop.Save()
    log["copia"] = str(COPIA)
finally:
    app.SilentOperation = False
log["s"] = round(time.time() - T0, 1)
out = Path(r"C:\Users\nm\Documents\InventorIA\Analisis\L3N\transportes_nuevos\layout_final.json")
out.write_text(json.dumps(log, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps(log, ensure_ascii=False, indent=1)[:20000])
