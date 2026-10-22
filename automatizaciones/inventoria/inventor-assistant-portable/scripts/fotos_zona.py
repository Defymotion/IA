"""Fotos de una zona de un ensamble abierto (sin tocar geometría): oculta bocetos, cotas 3D y elementos de trabajo,
y saca planta + isométrica encuadrando la caja indicada (mm, coordenadas del ensamble). Restituye la cámara.
Uso: python fotos_zona.py <iam> <carpeta> <prefijo> xmin zmin xmax zmax [--guardar-visibilidad] [--dir dx,dz] [--alto mm]
"""
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
import inventor_mcp as inv  # noqa: E402

S = inv._safe
ruta, out, pref = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
x0, z0, x1, z1 = (float(v) / 10 for v in sys.argv[4:8])
dirx, dirz = (float(v) for v in sys.argv[sys.argv.index("--dir") + 1].split(",")) if "--dir" in sys.argv else (1.0, 1.0)
alto_cam = float(sys.argv[sys.argv.index("--alto") + 1]) / 10 if "--alto" in sys.argv else 2500.0
out.mkdir(parents=True, exist_ok=True)
app = inv._inventor(start_if_needed=False)
app.SilentOperation = True
try:
    doc = next((d for d in inv._items(app.Documents)
                if S(lambda: Path(d.FullFileName).resolve() == ruta.resolve(), False)), None)
    if doc is None or not S(lambda: doc.Views.Count, 0):
        doc = app.Documents.Open(str(ruta), True)
    doc.Activate()
    ov = doc.ObjectVisibility
    for p in ("Sketches", "Sketches3D", "SketchDimensions", "Annotations3D", "AllWorkFeatures", "ConstructionSurfaces",
              "UCSTriads", "UCSPlanes", "UCSAxes", "UCSPoints", "WeldmentSymbols", "SketchDOF"):
        S(lambda: setattr(ov, p, False))
    time.sleep(1)
    v = app.ActiveView
    cam = v.Camera
    tg = app.TransientGeometry
    cx, cz = (x0 + x1) / 2, (z0 + z1) / 2
    w, h = abs(x1 - x0) * 1.08, abs(z1 - z0) * 1.08
    hechos = []
    for nombre, eye, up in (("planta", (cx, 3000, cz), (0, 0, -1)),
                            ("iso", (cx + 2000 * dirx, alto_cam, cz + 2000 * dirz), (0, 1, 0))):
        cam.Target = tg.CreatePoint(cx, 100, cz)
        cam.Eye = tg.CreatePoint(*eye)
        cam.UpVector = tg.CreateUnitVector(*up)
        cam.Perspective = False
        r = 1600 / 1000
        if w / h > r:
            cam.SetExtents(w, w / r)
        else:
            cam.SetExtents(h * r, h)
        cam.Apply()
        p = out / f"{pref}_{nombre}.png"
        v.SaveAsBitmap(str(p), 1600, 1000)
        hechos.append(str(p))
    if "--guardar-visibilidad" in sys.argv:
        doc.Save()
    print("\n".join(hechos))
finally:
    S(lambda: setattr(app, "SilentOperation", False))
