"""L3N etapa 1: plano de planta (vista superior) del layout liviano v7 con la línea nueva, rótulos de los equipos,
y exportación a DWG (AutoCAD) y PDF. No modifica el layout (lo abre y no lo guarda).
Uso: python l3n_plano_linea.py <carpeta_salida> [--escala 150] [--hoja A3] [--sin-rotulos]
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
SAL.mkdir(parents=True, exist_ok=True)
ARG = sys.argv
ESC = float(ARG[ARG.index("--escala") + 1]) if "--escala" in ARG else 150.0
HOJA = ARG[ARG.index("--hoja") + 1] if "--hoja" in ARG else "A3"
LAY = Path(r"C:\DEFYMOTION\L3N\Celdas_IA\LayoutL3N_liviano_v7.iam")
NOMBRE = "L3N_Etapa1_Layout_linea_v7"
DWG_ADDIN = "{C24E3AC2-122E-11D5-8E91-0010B541CD80}"
TAM = {"A4": 9995, "A3": 9996, "A2": 9997, "A1": 9998, "A0": 9999}
# rótulos: (texto, x, z) en mm del layout
ROT = [("CELDA A (nueva)", -10200, -37400), ("CELDA B (existente)", -10200, -42600), ("CELDA C (existente)", -10200, -49200),
       ("Cruz A S-11211", -6585, -34300), ("T3 - acumulación en cadenas", 2000, -34200), ("Cruz S-11256", 10800, -37100),
       ("T2 S-11261", 12300, -34284), ("T2 S-11259 + envolvedora MP402 (girada 90°)", 12600, -32880),
       ("Salida S-11219 / S-11226 (retiro con autoelevador)", 12300, -30300),
       ("Reserva etapa 2: pallet cautivo 3,5 x 5 m", 10640, -27900),
       ("Camas de rodillos B/C -> cruz A", -5000, -44000), ("Robot aéreo: buffers de pallets 1 y 2", -13600, -33000),
       ("Buffer de cartones (extensión del riel +2 m)", -13600, -54800)]
log = {"avisos": []}
app = inv._inventor(start_if_needed=False)
tg = app.TransientGeometry
app.SilentOperation = True
ddoc = None
try:
    lay = next((d for d in inv._items(app.Documents) if S(lambda d=d: Path(d.FullFileName).resolve() == LAY.resolve(), False)), None)
    lay = lay or app.Documents.Open(str(LAY), False)
    plantilla = app.FileManager.GetTemplateFile(inv.K_DRAWING_DOCUMENT)
    ddoc = app.Documents.Add(inv.K_DRAWING_DOCUMENT, plantilla, False)
    sh = ddoc.ActiveSheet
    S(lambda: setattr(sh, "Size", TAM.get(HOJA, 9996)))
    S(lambda: setattr(sh, "Orientation", 10242))          # apaisada
    W, H = sh.Width, sh.Height                            # cm
    log["hoja_cm"] = [round(W, 1), round(H, 1)]
    t1 = time.time()
    v = sh.DrawingViews.AddBaseView(lay, tg.CreatePoint2d(W * 0.40, H * 0.55), 1.0 / ESC, inv.K_VIEW_TOP, inv.K_STYLE_HLR)
    log["vista_s"] = round(time.time() - t1, 1)
    S(lambda: setattr(v, "ShowLabel", False))
    log["vista_cm"] = [round(v.Width, 1), round(v.Height, 1), round(v.Left, 1), round(v.Top, 1)]
    # encuadre: centrar la vista en el área libre (a la izquierda del cajetín)
    v.Position = tg.CreatePoint2d(max(v.Width / 2 + 1.0, (W - 1.0) / 2 - 2.0), max(v.Height / 2 + 1.0, H / 2 + 0.6))
    # rótulos
    if "--sin-rotulos" not in ARG:
        notas = sh.DrawingNotes.GeneralNotes
        n_ok = 0
        for txt, x, z in ROT:
            try:
                p = v.ModelToSheetSpace(tg.CreatePoint(x / 10.0, 300.0, z / 10.0))
                notas.AddFitted(p, txt)
                n_ok += 1
            except Exception as ex:  # noqa: BLE001
                log["avisos"].append(f"rótulo {txt}: {ex!r}"[:160])
        log["rotulos"] = n_ok
        try:
            notas.AddFitted(tg.CreatePoint2d(1.5, H - 1.2),
                            f"L3N ADECOAGRO CHIVILCOY - ETAPA 1: DISPOSICIÓN DE LA LÍNEA DE PALLETS (LAYOUT v7) - ESC. 1:{ESC:g}")
        except Exception as ex:  # noqa: BLE001
            log["avisos"].append(f"título: {ex!r}"[:160])
    inv._iprop(ddoc, "Inventor Summary Information", "Title", "L3N ETAPA 1 - LAYOUT LINEA")
    inv._iprop(ddoc, "Design Tracking Properties", "Part Number", NOMBRE[:30])
    inv._iprop(ddoc, "Design Tracking Properties", "Description", "Disposición final de la línea de pallets, etapa 1")
    idw = SAL / f"{NOMBRE}.idw"
    dwg = SAL / f"{NOMBRE}.dwg"
    pdf = SAL / f"{NOMBRE}.pdf"
    for f in (idw, dwg, pdf):
        if f.exists():
            f.rename(f.with_name(f.stem + time.strftime("_anterior_%Y%m%d_%H%M") + f.suffix))
    ddoc.SaveAs(str(idw), False)
    log["pdf"] = inv._export_pdf(app, ddoc, pdf)
    tr = app.ApplicationAddIns.ItemById(DWG_ADDIN)
    ctx = app.TransientObjects.CreateTranslationContext()
    ctx.Type = inv.K_FILE_BROWSE_IO
    opts = app.TransientObjects.CreateNameValueMap()
    S(lambda: tr.HasSaveCopyAsOptions(ddoc, ctx, opts))
    data = app.TransientObjects.CreateDataMedium()
    data.FileName = str(dwg)
    tr.SaveCopyAs(ddoc, ctx, opts, data)
    log["archivos"] = {k: (str(f), round(f.stat().st_size / 1024, 1) if f.exists() else None) for k, f in
                       (("idw", idw), ("dwg", dwg), ("pdf", pdf))}
except Exception as exc:  # noqa: BLE001
    log["error"] = repr(exc)
    log["traza"] = traceback.format_exc()[-2000:]
finally:
    if ddoc is not None:
        S(lambda: ddoc.Close(True))
    S(lambda: setattr(app, "SilentOperation", False))
log["s"] = round(time.time() - T0, 1)
(SAL / f"{NOMBRE}_resultado.json").write_text(json.dumps(log, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps(log, ensure_ascii=False, indent=1))
