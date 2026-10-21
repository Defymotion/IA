"""Fotos (sólo lectura) de un ensamble: ISO, frente, lateral, superior e ISO desde abajo. Restituye la cámara.
Uso: python fotos_ensamble.py "<iam>" <carpeta_salida> [prefijo]"""
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
import inventor_mcp as inv  # noqa: E402

S = inv._safe
ruta, out = Path(sys.argv[1]), Path(sys.argv[2])
pref = sys.argv[3] if len(sys.argv) > 3 else ruta.stem
out.mkdir(parents=True, exist_ok=True)
app = inv._inventor(start_if_needed=False)
app.SilentOperation = True
doc = next((d for d in inv._items(app.Documents)
            if S(lambda: Path(d.FullFileName).resolve() == ruta.resolve(), False)), None)
if doc is None or not S(lambda: doc.Views.Count, 0):
    doc = app.Documents.Open(str(ruta), True)
doc.Activate()
time.sleep(1)
v = app.ActiveView
cam = v.Camera
for prop in ("ShowAmbientShadows", "ShowObjectShadows"):
    S(lambda: setattr(v, prop, True))
hechos = []
for nombre, orient, invertir in (("iso", 10759, False), ("frente", 10764, False), ("derecha", 10755, False),
                                 ("superior", 10754, False), ("iso_abajo", 10759, True)):
    try:
        cam.ViewOrientationType = orient
        cam.Fit()
        cam.Apply()
        if invertir:
            t, e = cam.Target, cam.Eye
            cam.Eye = app.TransientGeometry.CreatePoint(e.X, 2 * t.Y - e.Y, e.Z)
            cam.Apply()
            cam.Fit()
            cam.Apply()
        p = out / f"{pref}_{nombre}.png"
        v.SaveAsBitmap(str(p), 1600, 1000)
        hechos.append(str(p))
    except Exception as exc:  # noqa: BLE001
        hechos.append(f"{nombre}: {exc!r}")
S(lambda: setattr(app, "SilentOperation", False))
print("\n".join(hechos))
