"""L3N -> Blender: exporta a OBJ (con .mtl: colores por cara) las piezas listadas en Blender\\escena_blender.json
(las mismas mallas que l3n_blender_exportar.py, que sólo traían el color de la ocurrencia). Sólo lectura de las piezas.
Uso: python l3n_blender_mallas_obj.py [--resolucion N]
"""
import json
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
import inventor_mcp as inv  # noqa: E402

S = inv._safe
T0 = time.time()
BL = Path.home() / "Documents" / "InventorIA" / "Generados" / "L3N_SIM5" / "Blender"
DST = BL / "mallas_obj"
DST.mkdir(parents=True, exist_ok=True)
OBJ_ID = "{F539FB09-FC01-4260-A429-1818B14D6BAC}"
D = json.loads((BL / "escena_blender.json").read_text(encoding="utf-8"))
app = inv._inventor(start_if_needed=False)
log = {"avisos": [], "ok": 0}
app.SilentOperation = True
try:
    tr_ = next(a for a in inv._items(app.ApplicationAddIns) if S(lambda: a.ClassIdString.upper(), "") == OBJ_ID)
    abiertos = {S(lambda: d.FullFileName, ""): d for d in inv._items(app.Documents)}
    for k, (mid, m) in enumerate(sorted(D["mallas"].items())):
        dst = DST / f"{mid}.obj"
        if dst.exists() and dst.stat().st_size > 100:
            log["ok"] += 1
            continue
        f = m["f"]
        doc = abiertos.get(f)
        cerrar = doc is None
        try:
            doc = doc or app.Documents.Open(f, False)
            ctx = app.TransientObjects.CreateTranslationContext()
            ctx.Type = 13059
            opts = app.TransientObjects.CreateNameValueMap()
            tr_.HasSaveCopyAsOptions(doc, ctx, opts)
            dm = app.TransientObjects.CreateDataMedium()
            dm.FileName = str(dst)
            tr_.SaveCopyAs(doc, ctx, opts, dm)
            log["ok"] += dst.exists()
        except Exception as e:  # noqa: BLE001
            log["avisos"].append(f"{mid} {Path(f).name}: {e!r}"[:200])
        finally:
            if cerrar and doc is not None:
                S(lambda: doc.Close(True))
        if k % 100 == 0:
            print(f"[{time.time() - T0:6.1f} s] {k}/{len(D['mallas'])}", flush=True)
finally:
    S(lambda: setattr(app, "SilentOperation", False))
log["tiempo_s"] = round(time.time() - T0, 1)
log["total"] = len(D["mallas"])
print(json.dumps(log, ensure_ascii=False, indent=1))
