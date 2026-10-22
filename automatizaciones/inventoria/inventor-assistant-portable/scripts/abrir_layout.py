"""Inicia Inventor si hace falta, activa el proyecto indicado (sólo si no hay documentos abiertos) y abre un
documento visible en modo lectura (no guarda nada). Uso: python abrir_layout.py <proyecto.ipj> <documento>
"""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
import inventor_mcp as inv  # noqa: E402

S = inv._safe
ipj, ruta = Path(sys.argv[1]), Path(sys.argv[2])
app = inv._inventor(start_if_needed=True, visible=True)
dpm = app.DesignProjectManager
res = {"proyecto_antes": S(lambda: dpm.ActiveDesignProject.FullFileName)}
if Path(str(res["proyecto_antes"])).resolve() != ipj.resolve():
    if app.Documents.Count:
        sys.exit("Hay documentos abiertos con otro proyecto activo; no cambio el proyecto.")
    proj = None
    for p in inv._items(dpm.DesignProjects):
        if S(lambda: Path(p.FullFileName).resolve() == ipj.resolve(), False):
            proj = p
    if proj is None:
        proj = dpm.DesignProjects.AddExisting(str(ipj))
    proj.Activate(True)
res["proyecto"] = S(lambda: dpm.ActiveDesignProject.FullFileName)
doc = next((d for d in inv._items(app.Documents)
            if S(lambda: Path(d.FullFileName).resolve() == ruta.resolve(), False)), None)
if doc is None:
    doc = app.Documents.Open(str(ruta), True)
doc.Activate()
res["activo"] = str(app.ActiveDocument.FullFileName)
print(json.dumps(res, ensure_ascii=False, indent=1))
