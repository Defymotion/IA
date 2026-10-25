"""Mide cuánto tarda mover ocurrencias en la escena v5 (L3N_SIM5_Planta.iam) con distintos métodos; restituye todo y
no guarda. Uso: python bench_transform5.py [n]
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
ESC = Path.home() / "Documents" / "InventorIA" / "Generados" / "L3N_SIM5" / "L3N_SIM5_Planta.iam"
app = inv._inventor(start_if_needed=False)
tg = app.TransientGeometry
doc = next((d for d in inv._items(app.Documents) if S(lambda: Path(d.FullFileName).resolve() == ESC.resolve(), False)), None)
doc = doc or app.Documents.Open(str(ESC), True)
cd = doc.ComponentDefinition
todos = list(inv._items(cd.Occurrences))
grupos = {"cajas_visibles": [o for o in todos if o.Name.startswith("SIM_B_Caja_") and o.Visible][:N],
          "palas_B": [o for o in todos if o.Name.startswith("SIM_B_PM_")][:N],
          "robot": [o for o in todos if o.Name.startswith(("SIM_A_V0", "SIM_B_V0"))]}
if len(grupos["cajas_visibles"]) < 5:
    grupos["cajas_visibles"] = [o for o in todos if o.Name.startswith("SIM_A_Caja_")][:N]
res = {"n": {k: len(v) for k, v in grupos.items()}}


def desplazadas(M0, d):
    out = []
    for m in M0:
        m2 = tg.CreateMatrix()
        m2.TransformBy(m)
        t = tg.CreateMatrix()
        t.SetTranslation(tg.CreateVector(d / 10, 0, 0))
        m2.TransformBy(t)
        out.append(m2)
    return out


def medir(nombre, occs, fn):
    t0 = time.time()
    try:
        fn()
        t1 = time.time()
        doc.Update()
        res[nombre] = [round((t1 - t0) / len(occs), 4), round((time.time() - t1), 3)]
    except Exception as exc:  # noqa: BLE001
        res[nombre] = repr(exc)[:200]
    print(nombre, res[nombre], flush=True)


app.SilentOperation = True
M0s = {k: [o.Transformation for o in v] for k, v in grupos.items()}
try:
    for k, occs in grupos.items():
        if not occs:
            continue
        M0 = M0s[k]
        ms = desplazadas(M0, 10)
        medir(k + ":Transformation", occs, lambda: [setattr(o, "Transformation", m) for o, m in zip(occs, ms)])
        ms = desplazadas(M0, 20)
        medir(k + ":SetTransformWithoutConstraints", occs, lambda: [o.SetTransformWithoutConstraints(m) for o, m in zip(occs, ms)])

        def lote(d):
            oc = app.TransientObjects.CreateObjectCollection()
            mc = app.TransientObjects.CreateObjectCollection()
            for o, m in zip(occs, desplazadas(M0, d)):
                oc.Add(o)
                mc.Add(m)
            cd.TransformOccurrences(oc, mc)
        medir(k + ":TransformOccurrences", occs, lambda: lote(30))
        ao = app.AssemblyOptions
        du0 = S(lambda: ao.DeferUpdate, None)
        res["DeferUpdate_inicial"] = du0
        if S(lambda: setattr(ao, "DeferUpdate", True) or True, False):
            ms = desplazadas(M0, 40)
            medir(k + ":Transformation+DeferUpdate", occs, lambda: [setattr(o, "Transformation", m) for o, m in zip(occs, ms)])
            medir(k + ":TransformOccurrences+DeferUpdate", occs, lambda: lote(50))
            S(lambda: setattr(ao, "DeferUpdate", du0))
        S(lambda: setattr(app, "ScreenUpdating", False))
        ms = desplazadas(M0, 60)
        medir(k + ":Transformation+ScreenOff", occs, lambda: [setattr(o, "Transformation", m) for o, m in zip(occs, ms)])
        medir(k + ":TransformOccurrences+ScreenOff", occs, lambda: lote(70))
        S(lambda: setattr(app, "ScreenUpdating", True))
finally:
    for k, occs in grupos.items():
        if not occs:
            continue
        oc = app.TransientObjects.CreateObjectCollection()
        mc = app.TransientObjects.CreateObjectCollection()
        for o, m in zip(occs, M0s[k]):
            oc.Add(o)
            mc.Add(m)
        if S(lambda: cd.TransformOccurrences(oc, mc) or True, False) is False:
            for o, m in zip(occs, M0s[k]):
                S(lambda: setattr(o, "Transformation", m))
    S(lambda: setattr(app, "ScreenUpdating", True))
    S(lambda: doc.Update())
    S(lambda: setattr(app, "SilentOperation", False))
print(json.dumps(res, ensure_ascii=False, indent=1))
