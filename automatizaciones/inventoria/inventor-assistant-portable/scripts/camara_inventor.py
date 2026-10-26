"""Sólo lectura: aplica en la vista activa la cámara del renderizador (ojo, objetivo, ancho; perspectiva 0,52) y lee lo
que Inventor usa realmente (ojo, objetivo, ángulo, extensión), para copiar el encuadre en otro programa.
Uso: python camara_inventor.py "ex,ey,ez,tx,ty,tz,w" [...]
"""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
import inventor_mcp as inv  # noqa: E402

S = inv._safe
app = inv._inventor(start_if_needed=False)
tg = app.TransientGeometry
vw = app.ActiveView
cam = vw.Camera
R = 1920 / 1080
res = []
for arg in sys.argv[1:]:
    ex, ey, ez, tx, ty, tz, w = [float(v) for v in arg.split(",")]
    cam.Target = tg.CreatePoint(tx / 10, ty / 10, tz / 10)
    cam.Eye = tg.CreatePoint(ex / 10, ey / 10, ez / 10)
    cam.UpVector = tg.CreateUnitVector(0, 1, 0)
    cam.Perspective = True
    S(lambda: setattr(cam, "PerspectiveAngle", 0.52))
    cam.SetExtents(w / 10, w / 10 / R)
    cam.Apply()
    c2 = vw.Camera
    e, t = c2.Eye, c2.Target
    ext = S(lambda: c2.GetExtents(), None)
    res.append({"pedido": arg, "ojo_mm": [round(e.X * 10, 1), round(e.Y * 10, 1), round(e.Z * 10, 1)],
                "objetivo_mm": [round(t.X * 10, 1), round(t.Y * 10, 1), round(t.Z * 10, 1)],
                "angulo": S(lambda: c2.PerspectiveAngle), "extension_cm": ext, "vista_px": [vw.Width, vw.Height]})
print(json.dumps(res, ensure_ascii=False, indent=1))
