"""Imágenes de un ensamble con cámara libre (sin modificar el ensamble).
Uso: python vistas_ensamble.py "<ensamble.iam>" --arriba 0 0 -1 --dirs="1,-1,-0.8;-1,1,-0.8" [--ancho 1600 --alto 1000]
  --arriba: vector 'arriba' del mundo real en coordenadas del ensamble (en los grippers z va hacia abajo).
  --dirs: direcciones desde el objetivo hacia el ojo (una imagen por dirección).
Salida: <carpeta del ensamble>\\<nombre>_vista<i>.png
"""
import argparse
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
import inventor_mcp as inv  # noqa: E402

a = argparse.ArgumentParser()
a.add_argument("ensamble")
a.add_argument("--arriba", nargs=3, type=float, default=[0, 0, 1])
a.add_argument("--dirs", default="1,-1,0.8", help='"x,y,z;x,y,z" (usar --dirs=...)')
a.add_argument("--ancho", type=int, default=1600)
a.add_argument("--alto", type=int, default=1000)
x = a.parse_args()
S = inv._safe
app = inv._inventor(start_if_needed=False)
app.SilentOperation = True
tg = app.TransientGeometry
doc = app.Documents.Open(x.ensamble, True)
doc.Activate()
v = app.ActiveView
for wp in inv._items(S(lambda: doc.ComponentDefinition.WorkPlanes, []) or []):
    S(lambda: setattr(wp, "Visible", False))
b = doc.ComponentDefinition.RangeBox
c = [(b.MinPoint.X + b.MaxPoint.X) / 2, (b.MinPoint.Y + b.MaxPoint.Y) / 2, (b.MinPoint.Z + b.MaxPoint.Z) / 2]
out = []
for i, dtxt in enumerate(x.dirs.split(";"), 1):
    d = [float(q) for q in dtxt.split(",")]
    cam = v.Camera
    cam.Target = tg.CreatePoint(*c)
    cam.Eye = tg.CreatePoint(c[0] + d[0] * 300, c[1] + d[1] * 300, c[2] + d[2] * 300)
    cam.UpVector = tg.CreateUnitVector(*x.arriba)
    cam.Apply()
    cam.Fit()
    cam.Apply()
    img = Path(x.ensamble).with_name(f"{Path(x.ensamble).stem}_vista{i}.png")
    v.SaveAsBitmap(str(img), x.ancho, x.alto)
    out.append(str(img))
S(lambda: setattr(app, "SilentOperation", False))
print(json.dumps({"imagenes": out}, ensure_ascii=False))
