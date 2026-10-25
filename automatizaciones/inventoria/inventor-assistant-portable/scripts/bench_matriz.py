"""Mide el costo de armar la Matrix de Inventor para un 3x4 en mm: SetCoordinateSystem (como el renderizador) contra
PutMatrixData sobre una Matrix reutilizada; verifica que den lo mismo y que asignar la misma Matrix a dos ocurrencias
no las enlace. No guarda nada. Uso: python bench_matriz.py
"""
import json
import math
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
import inventor_mcp as inv  # noqa: E402

S = inv._safe
ESC = Path.home() / "Documents" / "InventorIA" / "Generados" / "L3N_SIM5" / "L3N_SIM5_Planta.iam"
app = inv._inventor(start_if_needed=False)
tg = app.TransientGeometry
res = {}
c = [math.cos(0.3), 0.0, math.sin(0.3), -8000.0, 0.0, 1.0, 0.0, 800.0, -math.sin(0.3), 0.0, math.cos(0.3), -42000.0]


def mx_actual(c):
    ex = [c[0], c[4], c[8]]
    ey = [c[1], c[5], c[9]]
    ez = [ex[1] * ey[2] - ex[2] * ey[1], ex[2] * ey[0] - ex[0] * ey[2], ex[0] * ey[1] - ex[1] * ey[0]]
    m = tg.CreateMatrix()
    m.SetCoordinateSystem(tg.CreatePoint(c[3] / 10, c[7] / 10, c[11] / 10), tg.CreateVector(*ex),
                          tg.CreateVector(*ey), tg.CreateVector(*ez))
    return m


M1 = tg.CreateMatrix()


def mx_put(c):
    ex = [c[0], c[4], c[8]]
    ey = [c[1], c[5], c[9]]
    ez = [ex[1] * ey[2] - ex[2] * ey[1], ex[2] * ey[0] - ex[0] * ey[2], ex[0] * ey[1] - ex[1] * ey[0]]
    d = [ex[0], ey[0], ez[0], c[3] / 10, ex[1], ey[1], ez[1], c[7] / 10, ex[2], ey[2], ez[2], c[11] / 10, 0.0, 0.0, 0.0, 1.0]
    M1.PutMatrixData(d)
    return M1


def celdas(m):
    return [round(m.Cell(r, k), 5) for r in (1, 2, 3, 4) for k in (1, 2, 3, 4)]


N = 40
t0 = time.time()
for _ in range(N):
    a = mx_actual(c)
res["mx_actual_s"] = round((time.time() - t0) / N, 4)
try:
    t0 = time.time()
    for _ in range(N):
        b = mx_put(c)
    res["mx_put_s"] = round((time.time() - t0) / N, 4)
    res["iguales"] = celdas(a) == celdas(b)
    res["a"], res["b"] = celdas(a)[:8], celdas(b)[:8]
except Exception as e:  # noqa: BLE001
    res["mx_put_error"] = repr(e)[:300]
# asignación a dos ocurrencias con la misma Matrix reutilizada
doc = next((d for d in inv._items(app.Documents) if S(lambda: Path(d.FullFileName).resolve() == ESC.resolve(), False)), None)
if doc is not None and "mx_put_error" not in res:
    cd = doc.ComponentDefinition
    oc = [o for o in inv._items(cd.Occurrences) if o.Name in ("SIM_B_Caja_000", "SIM_B_Caja_001")]
    if len(oc) == 2:
        m0 = [o.Transformation for o in oc]
        app.SilentOperation = True
        try:
            o1, o2 = oc
            o1.Transformation = mx_put(c)
            c2 = list(c)
            c2[3] += 500.0
            o2.Transformation = mx_put(c2)
            res["o1_x"] = round(o1.Transformation.Cell(1, 4) * 10, 1)
            res["o2_x"] = round(o2.Transformation.Cell(1, 4) * 10, 1)
            t0 = time.time()
            for k in range(N):
                c2[3] = -8000.0 + k
                o1.Transformation = mx_put(c2)
            res["asignar_put_s"] = round((time.time() - t0) / N, 4)
            t0 = time.time()
            for k in range(N):
                c2[3] = -8000.0 + k
                o1.Transformation = mx_actual(c2)
            res["asignar_actual_s"] = round((time.time() - t0) / N, 4)
        finally:
            for o, m in zip(oc, m0):
                S(lambda: setattr(o, "Transformation", m))
            S(lambda: setattr(app, "SilentOperation", False))
print(json.dumps(res, ensure_ascii=False, indent=1))
