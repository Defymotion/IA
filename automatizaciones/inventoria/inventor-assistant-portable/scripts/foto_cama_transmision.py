"""Foto de la transmisión de una cama de rolos paramétrica: abre la cama (sólo para la foto), oculta lateral motriz, tapa
de cadena y cubrecadena (sin guardar) y saca una vista desde el lado de la transmisión y una iso de cerca.
Uso: python foto_cama_transmision.py <cama.iam> <carpeta_salida>
"""
import json
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
import inventor_mcp as inv  # noqa: E402

S = inv._safe
CAMA, OUT = Path(sys.argv[1]), Path(sys.argv[2])
OUT.mkdir(parents=True, exist_ok=True)
app = inv._inventor(start_if_needed=False)
tg = app.TransientGeometry
log = {"fotos": []}
app.SilentOperation = True
doc = None
try:
    doc = app.Documents.Open(str(CAMA), True)
    doc.Activate()
    for o in inv._items(doc.ComponentDefinition.Occurrences):
        n = o.Name
        if any(k in n for k in ("Lateral_motriz", "Tapa_cadena", "Cubrecadena", "Motoreductor")):
            S(lambda o=o: setattr(o, "Visible", False))
    time.sleep(1)
    v = app.ActiveView
    for nom, ojo, foco, ancho in (("frente_transmision", (-15, 5, 300), (-15, 5, 189), 90),      # cm
                                  ("iso_transmision", (25, 45, 260), (-15, 5, 189), 60)):
        cam = v.Camera
        cam.Perspective = False
        cam.Eye = tg.CreatePoint(*ojo)
        cam.Target = tg.CreatePoint(*foco)
        cam.UpVector = tg.CreateUnitVector(0, 1, 0)
        cam.SetExtents(ancho, ancho * 0.625)
        cam.Apply()
        time.sleep(0.5)
        f = OUT / f"{nom}.png"
        v.SaveAsBitmap(str(f), 1600, 1000)
        log["fotos"].append(str(f))
except Exception as exc:  # noqa: BLE001
    log["error"] = repr(exc)
finally:
    if doc is not None:
        S(lambda: doc.Close(True))
    S(lambda: setattr(app, "SilentOperation", False))
print(json.dumps(log, ensure_ascii=False))
