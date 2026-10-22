"""Busca en ensambles propios (y todo su árbol) referencias a archivos cuya ruta contiene un texto (p. ej. una carpeta
borrada) y las re-apunta a la misma ruta relativa bajo otra carpeta base. Con --solo-listar no cambia nada.
Uso: python reapuntar_refs.py "<base_vieja>" "<base_nueva>" ens1.iam ens2.iam ... [--solo-listar] [--solo-raiz]
"""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
import inventor_mcp as inv  # noqa: E402

S = inv._safe
vieja, nueva = sys.argv[1].lower().rstrip("\\"), sys.argv[2].rstrip("\\")
solo = "--solo-listar" in sys.argv
solo_raiz = "--solo-raiz" in sys.argv   # re-apuntar sólo las referencias directas del ensamble dado
rutas = [Path(a) for a in sys.argv[3:] if not a.startswith("--")]
app = inv._inventor(start_if_needed=False)
app.SilentOperation = True
res = {"encontradas": [], "reapuntadas": [], "guardados": [], "errores": [], "en_memoria": []}
try:
    for d in inv._items(app.Documents):
        f = str(S(lambda: d.FullFileName, ""))
        if vieja in f.lower():
            res["en_memoria"].append(f)
    for raiz in rutas:
        doc = next((d for d in inv._items(app.Documents) if S(lambda: Path(d.FullFileName).resolve() == raiz.resolve(), False)), None)
        if doc is None:
            try:
                doc = app.Documents.Open(str(raiz), False)
            except Exception as e:  # noqa: BLE001
                res["errores"].append(f"{raiz}: {e!r}")
                continue
        cambiados = {}
        for d in [doc] + ([] if solo_raiz else list(inv._items(doc.AllReferencedDocuments))):
            for fd in inv._items(S(lambda: d.File.ReferencedFileDescriptors, []) or []):
                ff = str(fd.FullFileName)
                if vieja in ff.lower():
                    res["encontradas"].append(f"{Path(str(d.FullFileName)).name} -> {ff}")
                    if not solo:
                        destino = nueva + ff[len(vieja):]
                        if Path(destino).exists():
                            try:
                                fd.ReplaceReference(destino)
                                res["reapuntadas"].append(f"{Path(str(d.FullFileName)).name}: {Path(ff).name} -> {destino}")
                                cambiados[str(d.FullFileName)] = d
                            except Exception as e:  # noqa: BLE001
                                res["errores"].append(f"{ff}: {e!r}")
                        else:
                            res["errores"].append(f"No existe el destino {destino}")
        for f, d in cambiados.items():
            try:
                d.Update()
                d.Save()
                res["guardados"].append(f)
            except Exception as e:  # noqa: BLE001
                res["errores"].append(f"guardar {f}: {e!r}")
    if not solo:
        S(lambda: app.Documents.CloseAll(True))   # soltar lo que quedó en memoria sin referencias
        res["en_memoria_despues"] = [str(S(lambda: d.FullFileName, "")) for d in inv._items(app.Documents)
                                     if vieja in str(S(lambda: d.FullFileName, "")).lower()]
finally:
    S(lambda: setattr(app, "SilentOperation", False))
print(json.dumps(res, ensure_ascii=False, indent=1))
