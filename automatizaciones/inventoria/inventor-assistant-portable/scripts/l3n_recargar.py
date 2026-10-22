"""Cierra (sin guardar: ya están guardados) todos los documentos de Celdas_IA y Estudio_IA, suelta lo que quedó en
memoria de la copia borrada y vuelve a abrir el layout por celdas, que ahora resuelve a la biblioteca de Documents.
Uso: python l3n_recargar.py
"""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
import inventor_mcp as inv  # noqa: E402

S = inv._safe
PROPIAS = (r"c:\defymotion\l3n\celdas_ia", r"c:\defymotion\l3n\estudio_ia")
LAYOUT = Path(r"C:\DEFYMOTION\L3N\Celdas_IA\LayoutL3N_Celdas.iam")
VIEJA = "_descartar_copia_bm2000"
app = inv._inventor(start_if_needed=False)
app.SilentOperation = True
res = {"cerrados": [], "sin_guardar": []}
try:
    for d in list(inv._items(app.Documents)):
        f = str(S(lambda: d.FullFileName, ""))
        if f.lower().startswith(PROPIAS) and S(lambda: d.Views.Count, 0):
            if S(lambda: d.Dirty, False):
                res["sin_guardar"].append(f)
            S(lambda: d.Close(True))
            res["cerrados"].append(f)
    for _ in range(3):
        S(lambda: app.Documents.CloseAll(True))
    res["viejos_en_memoria"] = [str(S(lambda: d.FullFileName, "")) for d in inv._items(app.Documents) if VIEJA in str(S(lambda: d.FullFileName, "")).lower()]
    res["documentos_en_memoria"] = app.Documents.Count
    doc = app.Documents.Open(str(LAYOUT), True)
    doc.Activate()
    faltan = []
    for d in [doc] + list(inv._items(doc.AllReferencedDocuments)):
        for fd in inv._items(S(lambda: d.File.ReferencedFileDescriptors, []) or []):
            if S(lambda: fd.ReferenceMissing, False) or VIEJA in str(fd.FullFileName).lower():
                faltan.append(f"{Path(str(d.FullFileName)).name} -> {fd.FullFileName}")
    res["referencias_malas_tras_reabrir"] = faltan
    res["viejos_tras_reabrir"] = [str(S(lambda: d.FullFileName, "")) for d in inv._items(app.Documents) if VIEJA in str(S(lambda: d.FullFileName, "")).lower()]
    S(lambda: doc.Views.Item(1).Fit())
finally:
    S(lambda: setattr(app, "SilentOperation", False))
print(json.dumps(res, ensure_ascii=False, indent=1))
