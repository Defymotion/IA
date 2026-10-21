"""Animación de apertura/cierre de un gripper YA GENERADO (no crea ni guarda piezas).

Mueve la restricción "Apertura" del módulo de pala móvil (todas las cajas usan el mismo módulo, así que se mueven
juntas), captura un cuadro por paso desde la vista elegida y deja todo como estaba (no guarda).
El sentido de cierre se toma de la goma (está del lado de la caja respecto de la pala).

Uso: python animar_gripper.py --ensamble <Gripper.iam> [--carrera 80] [--pasos 16] [--vista iso|frente|arriba]
Salida: <carpeta del ensamble>\\Animacion\\cuadro_###.png + animacion.json
"""
import argparse
import json
import math
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
import inventor_mcp as inv  # noqa: E402

a = argparse.ArgumentParser()
a.add_argument("--ensamble", required=True)
a.add_argument("--carrera", type=float, default=80.0)
a.add_argument("--pasos", type=int, default=16)
a.add_argument("--vista", default="iso")
a.add_argument("--ancho", type=int, default=1280)
a.add_argument("--alto", type=int, default=800)
x = a.parse_args()

S = inv._safe
T0 = time.time()
app = inv._inventor(start_if_needed=False)
path = Path(x.ensamble)
doc = next((d for d in inv._items(app.Documents)
            if S(lambda: Path(d.FullFileName).resolve() == path.resolve(), False)), None)
if doc is None:
    app.SilentOperation = True
    doc = app.Documents.Open(str(path), True)
    app.SilentOperation = False
doc.Activate()
mod = next(d for d in inv._items(doc.AllReferencedDocuments)
           if any(S(lambda: c.Name, "") == "Apertura" for c in inv._items(S(lambda: d.ComponentDefinition.Constraints, []) or [])))
mcd = mod.ComponentDefinition
ap = next(c for c in inv._items(mcd.Constraints) if c.Name == "Apertura")
v0 = ap.Offset.Value                       # cm


def centro(o):
    b = o.RangeBox
    return [(b.MinPoint.X + b.MaxPoint.X) / 2, (b.MinPoint.Y + b.MaxPoint.Y) / 2, (b.MinPoint.Z + b.MaxPoint.Z) / 2]


occs = {o.Name.lower(): o for o in inv._items(mcd.Occurrences)}
pala = next((o for n, o in occs.items() if "pala" in n and "goma" not in n and "empuja" not in n), None) \
    or max(occs.values(), key=lambda o: S(lambda: o.MassProperties.Mass, 0) or 0)
goma = next((o for n, o in occs.items() if "goma" in n), None)


def mover(v):
    ap.Offset.Value = v
    mod.Update()
    doc.Update()


# sentido de cierre: +1 si aumentar Apertura acerca la pala a la goma-lado-caja
c0 = centro(pala)
g0 = centro(goma) if goma else None
mover(v0 + 0.5)
c1 = centro(pala)
mover(v0)
d = [c1[i] - c0[i] for i in range(3)]
if g0:
    hacia_caja = [g0[i] - c0[i] for i in range(3)]
    signo_cierre = 1 if sum(d[i] * hacia_caja[i] for i in range(3)) > 0 else -1
else:
    signo_cierre = -1
v_abierto = v0 - signo_cierre * x.carrera / 10           # el modelo está cerrado sobre la caja

cam = app.ActiveView.Camera
cam.ViewOrientationType = {"iso": 10759, "frente": 10764, "arriba": 10754}.get(x.vista, 10759)
cam.Apply()
mover(v_abierto)
app.ActiveView.Fit()
cam = app.ActiveView.Camera
cam.Fit()
cam.Apply()

OUT = path.parent / "Animacion"
OUT.mkdir(exist_ok=True)
for f in OUT.glob("cuadro_*.png"):
    f.unlink()
n = 0


def cuadro():
    global n
    app.ActiveView.Update()
    app.ActiveView.SaveAsBitmap(str(OUT / f"cuadro_{n:03d}.png"), x.ancho, x.alto)
    n += 1


# abierto -> cierra -> pausa -> abre (suavizado coseno)
seq = []
for i in range(x.pasos + 1):
    t = (1 - math.cos(math.pi * i / x.pasos)) / 2
    seq.append(v_abierto + (v0 - v_abierto) * t)
for v in seq:
    mover(v)
    cuadro()
mover(v0)
log = {"apertura_cerrado_mm": round(v0 * 10, 2), "apertura_abierto_mm": round(v_abierto * 10, 2),
       "signo_cierre": signo_cierre, "cuadros": n, "carpeta": str(OUT), "modulo": mod.FullFileName}
mover(v0)                                 # queda como estaba; no se guarda nada
log["tiempo_s"] = round(time.time() - T0, 1)
(OUT / "animacion.json").write_text(json.dumps(log, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps(log, ensure_ascii=False, indent=1))
