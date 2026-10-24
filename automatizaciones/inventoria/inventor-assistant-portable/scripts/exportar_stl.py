"""Exporta piezas a STL binario (copia; no modifica las piezas). Sirve para chequear choques del robot con geometría
real en la nube. Escribe también <salida>\\stl_info.json con la caja de cada pieza (mm, coordenadas de la pieza) para
verificar las unidades del STL.
Uso: python exportar_stl.py <carpeta_salida> <pieza1.ipt> [<pieza2.ipt> ...]
"""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
import inventor_mcp as inv  # noqa: E402

S = inv._safe
OUT = Path(sys.argv[1])
PIEZAS = [Path(p) for p in sys.argv[2:]]
OUT.mkdir(parents=True, exist_ok=True)
app = inv._inventor(start_if_needed=False)
log = {"piezas": {}, "avisos": []}
STL_ID = "{533E9A98-FC3B-11D4-8E7E-0010B541CD80}"

app.SilentOperation = True
try:
    tr_ = next((a for a in inv._items(app.ApplicationAddIns) if S(lambda: a.ClassIdString.upper(), "") == STL_ID), None)
    for p in PIEZAS:
        doc = next((d for d in inv._items(app.Documents) if S(lambda: Path(d.FullFileName).resolve() == p.resolve(), False)), None)
        abierto = doc is not None
        doc = doc or app.Documents.Open(str(p), False)
        b = doc.ComponentDefinition.RangeBox
        dst = OUT / (p.stem + ".stl")
        ok = False
        if tr_ is not None:
            try:
                ctx = app.TransientObjects.CreateTranslationContext()
                ctx.Type = 13059                      # kFileBrowseIOMechanism
                opts = app.TransientObjects.CreateNameValueMap()
                if tr_.HasSaveCopyAsOptions(doc, ctx, opts):
                    for k, v in (("ExportUnits", 5), ("Resolution", 1), ("OutputFileType", 0)):
                        S(lambda: opts.SetValue(k, v))
                dm = app.TransientObjects.CreateDataMedium()
                dm.FileName = str(dst)
                tr_.SaveCopyAs(doc, ctx, opts, dm)
                ok = dst.exists()
            except Exception as exc:  # noqa: BLE001
                log["avisos"].append(f"{p.name}: traductor {exc}")
        if not ok:
            try:
                doc.SaveAs(str(dst), True)
                ok = dst.exists()
            except Exception as exc:  # noqa: BLE001
                log["avisos"].append(f"{p.name}: SaveAs {exc}")
        log["piezas"][p.name] = {"stl": str(dst) if ok else None, "bytes": dst.stat().st_size if ok else 0,
                                 "caja_mm": [round(v * 10, 2) for v in (b.MinPoint.X, b.MinPoint.Y, b.MinPoint.Z,
                                                                         b.MaxPoint.X, b.MaxPoint.Y, b.MaxPoint.Z)]}
        if not abierto:
            S(lambda: doc.Close(True))
finally:
    S(lambda: setattr(app, "SilentOperation", False))
(OUT / "stl_info.json").write_text(json.dumps(log, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps(log, ensure_ascii=False, indent=1))
