"""Mide cuánto tarda mover ocurrencias en la escena L3N_SIM_Planta.iam con distintos métodos (no guarda nada).
Uso: python bench_transform.py [n]
"""
import json
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
import inventor_mcp as inv  # noqa: E402

S = inv._safe
N = int(sys.argv[1]) if len(sys.argv) > 1 else 20
ESC = Path.home() / "Documents" / "InventorIA" / "Generados" / "L3N_SIM2" / "L3N_SIM_Planta.iam"
app = inv._inventor(start_if_needed=False)
tg = app.TransientGeometry
doc = next(d for d in inv._items(app.Documents) if S(lambda: Path(d.FullFileName).resolve() == ESC.resolve(), False))
cd = doc.ComponentDefinition
occs = [o for o in inv._items(cd.Occurrences) if o.Name.startswith("SIM_Caja_")][:N]
M0 = [o.Transformation for o in occs]
res = {}


def desplazadas(d):
    out = []
    for m in M0:
        m2 = tg.CreateMatrix()
        m2.TransformBy(m)
        v = tg.CreateVector(d / 10, 0, 0)
        t = tg.CreateMatrix()
        t.SetTranslation(v)
        m2.TransformBy(t)
        out.append(m2)
    return out


def medir(nombre, fn):
    t0 = time.time()
    try:
        fn()
        doc.Update()
        res[nombre] = round((time.time() - t0) / N, 4)
    except Exception as exc:  # noqa: BLE001
        res[nombre] = repr(exc)[:200]
    print(nombre, res[nombre], flush=True)


app.SilentOperation = True
try:
    ms = desplazadas(10)
    medir("Transformation", lambda: [setattr(o, "Transformation", m) for o, m in zip(occs, ms)])
    ms = desplazadas(20)
    medir("SetTransformWithoutConstraints", lambda: [o.SetTransformWithoutConstraints(m) for o, m in zip(occs, ms)])

    def lote(d):
        oc = app.TransientObjects.CreateObjectCollection()
        mc = app.TransientObjects.CreateObjectCollection()
        for o, m in zip(occs, desplazadas(d)):
            oc.Add(o)
            mc.Add(m)
        cd.TransformOccurrences(oc, mc)
    medir("TransformOccurrences", lambda: lote(30))
    ao = app.AssemblyOptions
    du0 = S(lambda: ao.DeferUpdate, None)
    res["DeferUpdate_inicial"] = du0
    if S(lambda: setattr(ao, "DeferUpdate", True) or True, False):
        ms = desplazadas(40)
        medir("Transformation+DeferUpdate", lambda: [setattr(o, "Transformation", m) for o, m in zip(occs, ms)])
        medir("TransformOccurrences+DeferUpdate", lambda: lote(50))
        S(lambda: setattr(ao, "DeferUpdate", du0))
    S(lambda: setattr(app, "ScreenUpdating", False))
    ms = desplazadas(60)
    medir("Transformation+ScreenUpdatingOff", lambda: [setattr(o, "Transformation", m) for o, m in zip(occs, ms)])
    medir("TransformOccurrences+ScreenUpdatingOff", lambda: lote(70))
    S(lambda: setattr(app, "ScreenUpdating", True))
    # visibilidad
    t0 = time.time()
    for o in occs:
        o.Visible = not o.Visible
    for o in occs:
        o.Visible = not o.Visible
    res["Visible_toggle"] = round((time.time() - t0) / (2 * N), 4)
finally:
    oc = app.TransientObjects.CreateObjectCollection()
    mc = app.TransientObjects.CreateObjectCollection()
    for o, m in zip(occs, M0):
        oc.Add(o)
        mc.Add(m)
    S(lambda: cd.TransformOccurrences(oc, mc))
    for o, m in zip(occs, M0):
        S(lambda: setattr(o, "Transformation", m))
    S(lambda: setattr(app, "ScreenUpdating", True))
    S(lambda: setattr(app, "SilentOperation", False))
print(json.dumps(res, ensure_ascii=False, indent=1))
