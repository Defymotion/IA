"""Evita choques de nombres de archivo (Inventor no inserta un ensamble si otro archivo con el mismo nombre, de otra
carpeta, ya está cargado). Copia los archivos indicados con nombre nuevo y re-apunta las referencias dentro del árbol
de un ensamble. Pensado para COPIAS de bibliotecas (no originales). Cierra antes sólo documentos propios de las
carpetas indicadas y los no referenciados.
Uso: python renombrar_refs.py <ensamble.iam> "<viejo1>=><nuevo1>;<viejo2>=><nuevo2>" "<carpeta_propia1>;<carpeta_propia2>"
"""
import json
import shutil
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
import inventor_mcp as inv  # noqa: E402

S = inv._safe
raiz = Path(sys.argv[1])
mapa = {}
for par in sys.argv[2].split(";"):
    if "=>" in par:
        a, b = par.split("=>")
        mapa[str(Path(a)).lower()] = Path(b)
propias = [s.lower().rstrip("\\") for s in sys.argv[3].split(";") if s]
app = inv._inventor(start_if_needed=False)
app.SilentOperation = True
res = {"cerrados": [], "copiados": [], "reapuntados": [], "guardados": []}
try:
    for d in list(inv._items(app.Documents)):
        f = str(S(lambda: d.FullFileName, "")).lower()
        if any(f.startswith(c + "\\") for c in propias) and S(lambda: d.Views.Count, 0):
            S(lambda: d.Close(True))
            res["cerrados"].append(f)
    S(lambda: app.Documents.CloseAll(True))   # True = sólo los no referenciados (sin ventanas)
    nombres = {Path(b).name.lower() for b in mapa.values()} | {Path(a).name.lower() for a in mapa}
    res["siguen_cargados"] = [str(d.FullFileName) for d in inv._items(app.Documents)
                              if Path(str(d.FullFileName)).name.lower() in nombres]
    for a, b in mapa.items():
        if not b.exists():
            shutil.copy2(a, b)
            res["copiados"].append(str(b))
    doc = app.Documents.Open(str(raiz), False)
    cambiados = {}
    for d in [doc] + list(inv._items(doc.AllReferencedDocuments)):
        for fd in inv._items(d.File.ReferencedFileDescriptors):
            ff = str(fd.FullFileName).lower()
            if ff in mapa:
                fd.ReplaceReference(str(mapa[ff]))
                res["reapuntados"].append(f"{d.FullFileName}: {Path(ff).name} -> {mapa[ff].name}")
                cambiados[str(d.FullFileName)] = d
    for f, d in cambiados.items():
        try:
            d.Save()
            res["guardados"].append(f)
        except Exception as e:  # noqa: BLE001
            res.setdefault("errores_guardado", []).append(f"{f}: {e!r}")
    doc.Close(True)
finally:
    S(lambda: setattr(app, "SilentOperation", False))
print(json.dumps(res, ensure_ascii=False, indent=1))
