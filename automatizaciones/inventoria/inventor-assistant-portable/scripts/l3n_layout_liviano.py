"""L3N: layout LIVIANO para presentar la disposición final de transportes (el layout del usuario no se toca).
1. Por cada tipo de módulo del proveedor (S-11253, S-11255, cruces...) arma UNA pieza simplificada (shrinkwrap:
   cuerpos múltiples, sin piezas chicas -tornillería, sensores-, sin agujeros, vínculo roto) en
   Celdas_IA\\<carpeta_livianos>\\<PN>_liviano.ipt. Todas las instancias comparten esa pieza (en el original cada
   instancia era una copia distinta de ~800 piezas).
2. Arma Celdas_IA\\<salida>: paredes, celdas, línea de camas y robot aéreo del layout del usuario (mismas posiciones,
   leídas con Apprentice), los módulos livianos en la disposición final y la extensión del riel + buffer de cartones.
Uso: python l3n_layout_liviano.py <plan.json> [--rehacer-tipos] [--rehacer-ext] [--forzar] [--prueba PN] (sólo esa pieza)
"""
import glob
import json
import sys
import time
from pathlib import Path

import pythoncom
import win32com.client

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
import inventor_mcp as inv  # noqa: E402

S = inv._safe
plan = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
CELDAS = Path(r"C:\DEFYMOTION\L3N\Celdas_IA")
LAY = CELDAS / "LayoutL3N_Celdas.iam"
SAL = CELDAS / plan["salida"]
LIV = CELDAS / plan["carpeta_livianos"]
RDIR = CELDAS / "Robot_Aereo"
EXT = RDIR / plan.get("ext_archivo", "Extension_riel_buffer_cartones.iam")
PROV = Path(r"C:\DEFYMOTION\L3N\Relevamiento_planta\2026-10-28\30-07-26-E_01294_A_1_Adecoagro___Anteproyecto_de_Paletizado"
            r"\30-07-26-E_01294_A_1_Adecoagro___Anteproyecto_de_Paletizado")
log = {"avisos": [], "tipos": {}, "instancias": {}, "otros": {}}
T0 = time.time()


def enums(nombres):
    tlbs = glob.glob(r"C:\Program Files\Autodesk\Inventor 2025\Bin\RxInventor.tlb") or \
        glob.glob(r"C:\Program Files\Autodesk\Inventor 2025\Bin\*.tlb")
    out = {}
    for t in tlbs:
        tlb = pythoncom.LoadTypeLib(t)
        for i in range(tlb.GetTypeInfoCount()):
            if tlb.GetTypeInfoType(i) != pythoncom.TKIND_ENUM:
                continue
            ti = tlb.GetTypeInfo(i)
            for j in range(ti.GetTypeAttr().cVars):
                vd = ti.GetVarDesc(j)
                nm = ti.GetNames(vd.memid)[0]
                if nm in nombres:
                    out[nm] = vd.value
        if len(out) == len(nombres):
            break
    return out


K = enums({"kDeriveAsMultipleBodies", "kDeriveAsSingleBodyWithSeams", "kShrinkwrapRemoveAll", "kShrinkwrapRemoveNone"})
log["enums"] = K

# ------------------------------------------------------------ posiciones del layout del usuario (Apprentice, sin Inventor)
ap = None
for prog in ("Inventor.ApprenticeServer", "Inventor.ApprenticeServerComponent.1"):
    try:
        ap = win32com.client.Dispatch(prog)
        break
    except Exception:  # noqa: BLE001
        pass
otros = {}
ad = ap.Open(str(LAY))
aoccs = ad.ComponentDefinition.Occurrences
for i in range(1, aoccs.Count + 1):
    o = aoccs.Item(i)
    if o.Name in plan["otros"]:
        t = o.Transformation
        otros[o.Name] = {"archivo": o.ReferencedDocumentDescriptor.FullDocumentName,
                         "M": [t.Cell(r + 1, c + 1) * (10.0 if c == 3 else 1.0) for r in range(3) for c in range(4)]}
ad.Close()
log["otros"] = otros

app = inv._inventor(start_if_needed=False)
tg = app.TransientGeometry


def abierto(ruta):
    return next((d for d in inv._items(app.Documents) if S(lambda d=d: Path(d.FullFileName).resolve() == Path(ruta).resolve(), False)), None)


if abierto(LAY) is not None and "--forzar" not in sys.argv:
    sys.exit("El layout pesado (LayoutL3N_Celdas.iam) está abierto en Inventor: cerralo (guardando) y volvé a pedirlo. "
             "Con los dos abiertos se queda sin RAM.")


def matriz(m):
    M = tg.CreateMatrix()
    for i in range(3):
        for j in range(4):
            M.SetCell(i + 1, j + 1, m[i * 4 + j] / (10.0 if j == 3 else 1.0))
    return M


def lista(M):
    return [round(M.Cell(i + 1, j + 1) * (10.0 if j == 3 else 1.0), 3) for i in range(3) for j in range(4)]


def desplazada(M, dx, dy, dz):
    m = lista(M)
    m[3] += dx
    m[7] += dy
    m[11] += dz
    return m


def caja(b):
    return [round(b.MinPoint.X * 10, 1), round(b.MinPoint.Y * 10, 1), round(b.MinPoint.Z * 10, 1),
            round(b.MaxPoint.X * 10, 1), round(b.MaxPoint.Y * 10, 1), round(b.MaxPoint.Z * 10, 1)]


def apariencia(nombre_parcial):
    for lib in inv._items(app.AssetLibraries):
        for asset in inv._items(S(lambda: lib.AppearanceAssets, []) or []):
            if (S(lambda: asset.DisplayName, "") or "").lower().startswith(nombre_parcial):
                return asset
    return None


def prisma(nombre, sx, sy, sz, colores=()):
    ruta = RDIR / f"{nombre}.ipt"
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
    for c in colores:
        a = apariencia(c)
        if a is not None:
            S(lambda: setattr(doc, "ActiveAppearance", a.CopyTo(doc)))
            break
    inv._iprop(doc, "Design Tracking Properties", "Part Number", nombre)
    inv._iprop(doc, "Design Tracking Properties", "Description", f"{sx:.0f} x {sy:.0f} x {sz:.0f} mm (volumen estimado)")
    doc.SaveAs(str(ruta), False)
    doc.Close(True)
    return ruta


def archivo_modulo(pn):
    c = sorted(PROV.glob(f"{pn}_A;*.iam"), key=lambda p: len(p.name))
    return c[0] if c else None


app.SilentOperation = True
try:
    # ------------------------------------------------------------ 1. piezas livianas por tipo
    LIV.mkdir(parents=True, exist_ok=True)
    PRUEBA = sys.argv[sys.argv.index("--prueba") + 1] if "--prueba" in sys.argv else None
    for pn in ([PRUEBA] if PRUEBA else plan["tipos"]):
        dest = LIV / f"{pn}_liviano.ipt"
        e = {"archivo": str(dest)}
        if dest.exists() and "--rehacer-tipos" not in sys.argv:
            e["ya_existia"] = True
            log["tipos"][pn] = e
            continue
        src = archivo_modulo(pn)
        if src is None:
            log["avisos"].append(f"no encontré el ensamble de {pn}")
            continue
        e["origen"] = str(src)
        t1 = time.time()
        ya = abierto(src) is not None
        pd = app.Documents.Add(inv.K_PART_DOCUMENT, app.FileManager.GetTemplateFile(inv.K_PART_DOCUMENT), False)
        try:
            sws = pd.ComponentDefinition.ReferenceComponents.ShrinkwrapComponents
            d = sws.CreateDefinition(str(src))
            for prop, val in (("DeriveStyle", K.get("kDeriveAsMultipleBodies")), ("RemoveInternalParts", False),
                              ("RemoveAllInternalVoids", True), ("RemoveHolesStyle", K.get("kShrinkwrapRemoveAll")),
                              ("RemovePartsBySize", True), ("RemovePartsSize", plan["tam_pieza_chica_mm"] / 10.0)):
                if val is not None:
                    r = S(lambda prop=prop, val=val: (setattr(d, prop, val), True)[1], False)
                    if not r:
                        log["avisos"].append(f"{pn}: no pude fijar {prop}")
            sw = sws.Add(d)
            e["vinculo_roto"] = bool(S(lambda: (sw.BreakLinkToFile(), True)[1], False))
            pd.Update()
            cdp = pd.ComponentDefinition
            e["cuerpos"] = S(lambda: cdp.SurfaceBodies.Count, None)
            e["caras"] = S(lambda: sum(b.Faces.Count for b in inv._items(cdp.SurfaceBodies)), None)
            inv._iprop(pd, "Design Tracking Properties", "Part Number", f"{pn}_liviano")
            inv._iprop(pd, "Design Tracking Properties", "Description", f"Simplificado (shrinkwrap) de {src.name}")
            pd.SaveAs(str(dest), False)
        except Exception as ex:  # noqa: BLE001
            e["error"] = repr(ex)[:300]
        finally:
            S(lambda: pd.Close(True))
            if not ya:
                x = abierto(src)
                if x is not None:
                    S(lambda: x.Close(True))
        e["s"] = round(time.time() - t1, 1)
        e["mb"] = round(dest.stat().st_size / 2**20, 2) if dest.exists() else None
        log["tipos"][pn] = e
        print(f"[{time.time() - T0:6.0f} s] {pn}: {e}", flush=True)
    # ------------------------------------------------------------ 2. layout liviano
    if PRUEBA:
        raise SystemExit(0)
    viejo = abierto(SAL)
    if viejo is not None:
        S(lambda: viejo.Close(True))
    lay = app.Documents.Add(inv.K_ASSEMBLY_DOCUMENT, app.FileManager.GetTemplateFile(inv.K_ASSEMBLY_DOCUMENT), True)
    occs = lay.ComponentDefinition.Occurrences
    for n in plan["otros"]:
        if n not in otros:
            log["avisos"].append(f"no está {n} en el layout del usuario")
            continue
        o = occs.Add(plan.get("reemplazos", {}).get(n, otros[n]["archivo"]), matriz(otros[n]["M"]))
        o.Grounded = True
        S(lambda: setattr(o, "Name", n.split(":")[0]))
        for s in inv._items(o.SubOccurrences) if n in plan.get("ocultar_sub", {}) else []:
            if s.Name in plan["ocultar_sub"][n]:
                S(lambda s=s: setattr(s, "Visible", False))
    for it in plan["instancias"]:
        ruta = LIV / f"{it['pn']}_liviano.ipt"
        if not ruta.exists():
            log["avisos"].append(f"falta la pieza liviana de {it['pn']}")
            continue
        o = occs.Add(str(ruta), matriz(it["M"]))
        o.Grounded = True
        S(lambda: setattr(o, "Name", it["nombre"]))
        log["instancias"][it["nombre"]] = caja(o.RangeBox)
    for it in plan.get("archivos", []):          # equipos sueltos (p. ej. la envolvedora)
        o = occs.Add(it["archivo"], matriz(it["M"]))
        o.Grounded = True
        S(lambda: setattr(o, "Name", it["nombre"]))
        log["instancias"][it["nombre"]] = caja(o.RangeBox)
    for pz in plan.get("prismas", []):           # volúmenes de reserva (p. ej. espacio para el pallet cautivo)
        ruta = prisma(pz["nombre"], pz["sx"], pz["sy"], pz["sz"], tuple(pz.get("colores", ())))
        c = pz["centro_base"]
        o = occs.Add(str(ruta), matriz([1, 0, 0, c[0], 0, 1, 0, c[1], 0, 0, 1, c[2]]))
        o.Grounded = True
        S(lambda: setattr(o, "Name", pz["nombre"]))
        log["instancias"][pz["nombre"]] = caja(o.RangeBox)
    # ------------------------------------------------------------ 3. extensión del riel + buffer de cartones
    rob = next((o for o in inv._items(occs) if o.Name.startswith("Robot_Aereo_Pallets")), None)
    rs = {x.Name: x for x in inv._items(rob.SubOccurrences)}
    if "--rehacer-ext" in sys.argv and EXT.exists():
        x = abierto(EXT)
        if x is not None:
            S(lambda: x.Close(True))
        EXT.unlink()
    ex = plan["extension"]
    if not EXT.exists():
        ed = app.Documents.Add(inv.K_ASSEMBLY_DOCUMENT, app.FileManager.GetTemplateFile(inv.K_ASSEMBLY_DOCUMENT), False)
        eo = ed.ComponentDefinition.Occurrences

        def poner(nombre, ruta, m):
            x = eo.Add(str(ruta), matriz(m))
            x.Grounded = True
            S(lambda: setattr(x, "Name", nombre))

        riel = prisma(f"Riel_extension_L{ex['largo_riel']:.0f}", 100, 100, ex["largo_riel"], ("acero", "steel"))
        pila = prisma("Pila_cartones_1200x1000x900", 1200, 900, 1000, ("cart", "card", "madera", "wood", "naranja"))
        for i, x in enumerate(ex["x_rieles"]):
            poner(f"Riel_ext_{i + 1}", riel, [1, 0, 0, x, 0, 1, 0, ex["y_riel"], 0, 0, 1, ex["z_riel_centro"]])
        for nuevo, base in (("Columna_ext_a", "Columna_3a"), ("Columna_ext_b", "Columna_3b"), ("Travesano_ext", "Travesano_3")):
            r = rs[base]
            poner(nuevo, r.Definition.Document.FullFileName, desplazada(r.Transformation, ex.get("dx_portico", 0.0), 0, ex["dz_portico"]))
        r = rs["Pila1_pallet_1"]
        poner("Buffer_cartones_pallet", r.Definition.Document.FullFileName, desplazada(r.Transformation, 0, 0, ex["dz_buffer"]))
        for k in range(1, 5):
            for t in ("Guia", "Placa"):
                r = rs[f"{t}_buffer_1_{k}"]
                poner(f"Buffer_cartones_{t.lower()}_{k}", r.Definition.Document.FullFileName,
                      desplazada(r.Transformation, 0, 0, ex["dz_buffer"]))
        poner("Pila_cartones", pila, [1, 0, 0, ex["pila_centro"][0], 0, 1, 0, ex["pila_centro"][1], 0, 0, 1, ex["pila_centro"][2]])
        ed.Update()
        ed.SaveAs(str(EXT), False)
        ed.Close(True)
    o = occs.Add(str(EXT), tg.CreateMatrix())
    o.Grounded = True
    S(lambda: setattr(o, "Name", "Extension_riel_buffer_cartones"))
    log["ext_caja"] = caja(o.RangeBox)
    lay.Update()
    lay.SaveAs(str(SAL), False)
    log["salida"] = str(SAL)
    log["mb_salida"] = round(SAL.stat().st_size / 2**20, 2)
finally:
    app.SilentOperation = False
log["s"] = round(time.time() - T0, 1)
out = Path(r"C:\Users\nm\Documents\InventorIA\Analisis\L3N\transportes_nuevos\layout_liviano.json")
out.write_text(json.dumps(log, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps(log, ensure_ascii=False, indent=1)[:20000])
