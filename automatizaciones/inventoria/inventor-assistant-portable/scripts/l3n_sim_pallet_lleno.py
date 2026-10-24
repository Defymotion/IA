"""L3N simulación: actualiza el pallet lleno de la escena (Generados\\L3N_SIM2\\Piezas\\Pallet_lleno_sim.iam, archivo
propio) con las posiciones de cajas del plan (p. ej. cuando cambia la luz entre cajas). Mueve las 136 ocurrencias de caja
que ya tiene (no rehace el ensamble, así la escena no pierde la referencia) y guarda.
Uso: python l3n_sim_pallet_lleno.py <plan.json>
"""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
import inventor_mcp as inv  # noqa: E402

S = inv._safe
PLAN = Path(sys.argv[1])
PLL = Path.home() / "Documents" / "InventorIA" / "Generados" / "L3N_SIM2" / "Piezas" / "Pallet_lleno_sim.iam"
plan = json.loads(PLAN.read_text(encoding="utf-8"))
app = inv._inventor(start_if_needed=False)
tg = app.TransientGeometry
log = {"avisos": []}


def orto(x_, y_):
    n = sum(v * v for v in x_) ** 0.5
    x_ = [v / n for v in x_]
    d = sum(a_ * b_ for a_, b_ in zip(x_, y_))
    y_ = [b_ - d * a_ for a_, b_ in zip(x_, y_)]
    n = sum(v * v for v in y_) ** 0.5
    return x_, [v / n for v in y_]


def mx(c):
    c = [c[0:4], c[4:8], c[8:12]]
    ex, ey = orto([c[0][0], c[1][0], c[2][0]], [c[0][1], c[1][1], c[2][1]])
    ez = [ex[1] * ey[2] - ex[2] * ey[1], ex[2] * ey[0] - ex[0] * ey[2], ex[0] * ey[1] - ex[1] * ey[0]]
    m = tg.CreateMatrix()
    m.SetCoordinateSystem(tg.CreatePoint(c[0][3] / 10, c[1][3] / 10, c[2][3] / 10),
                          tg.CreateVector(*ex), tg.CreateVector(*ey), tg.CreateVector(*ez))
    return m


def caja(o):
    b = o.RangeBox
    return [round(v * 10, 1) for v in (b.MinPoint.X, b.MinPoint.Y, b.MinPoint.Z, b.MaxPoint.X, b.MaxPoint.Y, b.MaxPoint.Z)]


app.SilentOperation = True
try:
    doc = next((d for d in inv._items(app.Documents) if S(lambda: Path(d.FullFileName).resolve() == PLL.resolve(), False)), None)
    log["estaba_abierto"] = doc is not None
    doc = doc or app.Documents.Open(str(PLL), False)
    cd = doc.ComponentDefinition
    caja_f = Path(plan["pallet_lleno"]["caja"]).name.lower()
    occs = [o for o in inv._items(cd.Occurrences)
            if Path(S(lambda: o.Definition.Document.FullFileName, "") or "").name.lower() == caja_f]
    rel = plan["pallet_lleno"]["cajas_rel"]
    log["cajas_ensamble"], log["cajas_plan"] = len(occs), len(rel)
    log["caja_antes"] = caja(cd)
    if len(occs) != len(rel):
        log["avisos"].append("distinta cantidad de cajas: no se toca")
    else:
        for o, c in zip(occs, rel):
            g0 = S(lambda: o.Grounded, False)
            S(lambda: setattr(o, "Grounded", False))
            o.Transformation = mx(c)
            if g0:
                S(lambda: setattr(o, "Grounded", True))
        doc.Update()
        doc.Save()
        log["caja_despues"] = caja(cd)
finally:
    S(lambda: setattr(app, "SilentOperation", False))
print(json.dumps(log, ensure_ascii=False, indent=1))
