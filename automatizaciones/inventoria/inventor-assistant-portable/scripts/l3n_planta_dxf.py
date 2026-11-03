"""L3N etapa 1: geometría en planta (vista superior, líneas visibles) de los equipos nuevos del layout v7, para pasarla
al DWG de planta. Arma ensambles temporales por grupo (no toca el layout), un dibujo con una hoja por grupo (vista
superior 1:ESC, sin borde ni cajetín) y lo exporta a DXF (una hoja = un archivo). Guarda la transformación
modelo -> hoja de cada vista para llevar la geometría a coordenadas de planta en la nube.
Uso: python l3n_planta_dxf.py <carpeta_salida> [--escala 100]
"""
import json
import sys
import time
import traceback
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
import inventor_mcp as inv  # noqa: E402

S = inv._safe
T0 = time.time()
SAL = Path(sys.argv[1])
TMP = SAL / "_ensambles_temporales"
TMP.mkdir(parents=True, exist_ok=True)
ESC = float(sys.argv[sys.argv.index("--escala") + 1]) if "--escala" in sys.argv else 100.0
LAY = Path(r"C:\DEFYMOTION\L3N\Celdas_IA\LayoutL3N_liviano_v7.iam")
DXF_ADDIN = "{C24E3AC4-122E-11D5-8E91-0010B541CD80}"
GRUPOS = {
    "TRANSPORTES": ("Cruz_", "T1_", "T2_", "T3_", "Salida_"),
    "ENVOLVEDORA": ("Envolvedora_MP402",),
    "ROBOT_AEREO_EXT": ("Extension_",),
    "RESERVA_ETAPA2": ("Etapa2_",),
    "CELDA_A": ("Celda_A_L3N",),
}
log = {"avisos": [], "grupos": {}}
app = inv._inventor(start_if_needed=False)
tg = app.TransientGeometry
app.SilentOperation = True
abiertos = []
ddoc = None
try:
    lay = next((d for d in inv._items(app.Documents) if S(lambda d=d: Path(d.FullFileName).resolve() == LAY.resolve(), False)), None)
    lay = lay or app.Documents.Open(str(LAY), False)
    tops = list(inv._items(lay.ComponentDefinition.Occurrences))
    plantilla = app.FileManager.GetTemplateFile(inv.K_DRAWING_DOCUMENT)
    ddoc = app.Documents.Add(inv.K_DRAWING_DOCUMENT, plantilla, False)
    hojas = []
    for gi, (g, prefs) in enumerate(GRUPOS.items()):
        occs = [o for o in tops if o.Name.startswith(prefs)]
        if not occs:
            log["avisos"].append(f"{g}: sin ocurrencias")
            continue
        asm = app.Documents.Add(inv.K_ASSEMBLY_DOCUMENT, app.FileManager.GetTemplateFile(inv.K_ASSEMBLY_DOCUMENT), False)
        for o in occs:
            f = o.ReferencedDocumentDescriptor.FullDocumentName
            n = asm.ComponentDefinition.Occurrences.Add(f, o.Transformation)
            S(lambda: setattr(n, "Grounded", True))
            for s in inv._items(o.SubOccurrences):            # visibilidad de los hijos como en el layout
                if not S(lambda s=s: s.Visible, True):
                    h = next((h for h in inv._items(n.SubOccurrences) if h.Name == s.Name), None)
                    if h is not None:
                        S(lambda h=h: setattr(h, "Visible", False))
        ruta = TMP / f"Planta_{g}.iam"
        if ruta.exists():
            ruta.unlink()
        asm.SaveAs(str(ruta), False)
        abiertos.append(asm)
        sh = ddoc.ActiveSheet if gi == 0 else ddoc.Sheets.Add(9999, 10242)   # A0 apaisada
        S(lambda: setattr(sh, "Size", 9999))
        S(lambda: setattr(sh, "Orientation", 10242))
        S(lambda: sh.TitleBlock.Delete())
        S(lambda: sh.Border.Delete())
        S(lambda: setattr(sh, "Name", g))
        W, H = sh.Width, sh.Height
        t1 = time.time()
        v = sh.DrawingViews.AddBaseView(asm, tg.CreatePoint2d(W / 2, H / 2), 1.0 / ESC, inv.K_VIEW_TOP, inv.K_STYLE_HLR)
        S(lambda: setattr(v, "ShowLabel", False))
        # transformación modelo (cm) -> hoja (cm) con 3 puntos
        pts = {}
        for k, (x, z) in (("o", (0.0, 0.0)), ("x", (1000.0, 0.0)), ("z", (0.0, 1000.0))):
            p = v.ModelToSheetSpace(tg.CreatePoint(x, 0.0, z))
            pts[k] = [p.X, p.Y]
        log["grupos"][g] = {"hoja": len(hojas) + 1, "n_occ": len(occs), "vista_s": round(time.time() - t1, 1),
                            "hoja_cm": [W, H], "m2s_cm": pts, "vista_cm": [v.Left, v.Top, v.Width, v.Height]}
        hojas.append(g)
        print(f"[{time.time() - T0:6.0f} s] {g}: {len(occs)} ocurrencias, vista {log['grupos'][g]['vista_s']} s", flush=True)
    ext = ".dwg" if str(plantilla).lower().endswith(".dwg") else ".idw"
    idw = SAL / f"L3N_planta_nuevos_inventor{ext}"
    if idw.exists():
        idw.unlink()
    ddoc.SaveAs(str(idw), False)
    tr = app.ApplicationAddIns.ItemById(DXF_ADDIN)
    ctx = app.TransientObjects.CreateTranslationContext()
    ctx.Type = inv.K_FILE_BROWSE_IO
    opts = app.TransientObjects.CreateNameValueMap()
    S(lambda: tr.HasSaveCopyAsOptions(ddoc, ctx, opts))
    S(lambda: opts.Add("Sheet_Range", 14082))          # todas las hojas
    data = app.TransientObjects.CreateDataMedium()
    data.FileName = str(SAL / "L3N_planta_nuevos.dxf")
    tr.SaveCopyAs(ddoc, ctx, opts, data)
    log["dxf"] = sorted(str(p) for p in SAL.glob("L3N_planta_nuevos*.dxf"))
except Exception as exc:  # noqa: BLE001
    log["error"] = repr(exc)
    log["traza"] = traceback.format_exc()[-2000:]
finally:
    if ddoc is not None:
        S(lambda: ddoc.Close(True))
    for a in abiertos:
        S(lambda a=a: a.Close(True))
    S(lambda: setattr(app, "SilentOperation", False))
log["s"] = round(time.time() - T0, 1)
(SAL / "L3N_planta_nuevos_resultado.json").write_text(json.dumps(log, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps(log, ensure_ascii=False, indent=1))
