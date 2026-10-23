"""Foto (iso y frente) de un ensamble cualquiera, abriéndolo con ventana. Uso: python foto_ensamble.py <iam> <png_base>"""
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
import inventor_mcp as inv  # noqa: E402

S = inv._safe
ruta, base = Path(sys.argv[1]), sys.argv[2]
app = inv._inventor(start_if_needed=False)
app.SilentOperation = True
try:
    doc = next((d for d in inv._items(app.Documents) if S(lambda: Path(d.FullFileName).resolve() == ruta.resolve(), False)), None)
    if doc is None or not S(lambda: doc.Views.Count, 0):
        doc = app.Documents.Open(str(ruta), True)
    doc.Activate()
    time.sleep(1)
    v = app.ActiveView
    cam = v.Camera
    for nombre, orient in (("iso", 10759), ("frente", 10764), ("superior", 10754)):
        cam.ViewOrientationType = orient
        cam.Fit()
        cam.Apply()
        v.SaveAsBitmap(f"{base}_{nombre}.png", 1600, 900)
        print(f"{base}_{nombre}.png")
finally:
    S(lambda: setattr(app, "SilentOperation", False))
