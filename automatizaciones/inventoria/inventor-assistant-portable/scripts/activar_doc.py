"""Activa un documento ya abierto en Inventor (por nombre de archivo) y cierra sólo documentos propios de una
carpeta de pruebas. No abre ni modifica originales.
Uso: python activar_doc.py --activar LayoutL3N_Principal.iam [--cerrar-carpeta C:\\...\\Generados\\PRUEBA]
"""
import argparse
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
import inventor_mcp as inv  # noqa: E402

a = argparse.ArgumentParser()
a.add_argument("--activar", required=True)
a.add_argument("--cerrar-carpeta", default="")
x = a.parse_args()
app = inv._inventor(start_if_needed=False, visible=True)
res = {"cerrados": [], "activado": None, "abiertos": []}
carpeta = x.cerrar_carpeta.lower().rstrip("\\")
objetivo = None
for i in range(app.Documents.Count, 0, -1):
    d = app.Documents.Item(i)
    ruta = str(d.FullFileName)
    res["abiertos"].append(ruta)
    if carpeta and ruta.lower().startswith(carpeta + "\\"):
        d.Close(True)  # sin guardar: es una pieza de prueba propia
        res["cerrados"].append(ruta)
        continue
    if Path(ruta).name.lower() == x.activar.lower():
        objetivo = d
if objetivo is None:
    print(json.dumps(res, ensure_ascii=False, indent=1))
    sys.exit(f"No está abierto: {x.activar}")
if objetivo.Views.Count > 0:
    objetivo.Views.Item(1).Activate()
res["activado"] = str(app.ActiveDocument.FullFileName)
print(json.dumps(res, ensure_ascii=False, indent=1))
