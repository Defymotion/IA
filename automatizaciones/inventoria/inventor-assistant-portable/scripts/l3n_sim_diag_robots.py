"""Sólo lectura: en la escena L3N_SIM_Planta.iam lista todas las ocurrencias de eslabones KUKA (KR_140*) y del gripper
(en el primer nivel y dentro de Celda_A_L3N, a cualquier profundidad) con su visibilidad en contexto y su caja.
Uso: python l3n_sim_diag_robots.py
"""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
import inventor_mcp as inv  # noqa: E402

S = inv._safe
ESC = Path.home() / "Documents" / "InventorIA" / "Generados" / "L3N_SIM2" / "L3N_SIM_Planta.iam"
app = inv._inventor(start_if_needed=False)
doc = next((d for d in inv._items(app.Documents) if S(lambda: Path(d.FullFileName).resolve() == ESC.resolve(), False)), None)
doc = doc or app.Documents.Open(str(ESC), True)
out = []


def caja(o):
    b = S(lambda: o.RangeBox, None)
    return None if b is None else [round(v * 10) for v in (b.MinPoint.X, b.MinPoint.Y, b.MinPoint.Z, b.MaxPoint.X, b.MaxPoint.Y, b.MaxPoint.Z)]


def rec(occs, ruta, prof):
    for o in inv._items(occs):
        f = Path(S(lambda: o.Definition.Document.FullFileName, "") or "").name
        r = ruta + o.Name
        if f.upper().startswith(("KR_140", "KUKA", "GRIPPER")) or "Gripper" in f:
            out.append({"ruta": r, "f": f, "vis": S(lambda: o.Visible), "caja": caja(o)})
        if prof < 4 and S(lambda: o.SubOccurrences.Count, 0) and not f.upper().startswith("GRIPPER"):
            rec(o.SubOccurrences, r + "/", prof + 1)


app.SilentOperation = True
try:
    tops = [o for o in inv._items(doc.ComponentDefinition.Occurrences)]
    for o in tops:
        f = Path(S(lambda: o.Definition.Document.FullFileName, "") or "").name
        if o.Name.startswith("SIM_V") or o.Name == "SIM_Gripper":
            out.append({"ruta": o.Name, "f": f, "vis": S(lambda: o.Visible), "caja": caja(o)})
        if o.Name.startswith("Celda_A"):
            rec(o.SubOccurrences, o.Name + "/", 1)
finally:
    S(lambda: setattr(app, "SilentOperation", False))
print(json.dumps(out, ensure_ascii=False, indent=0))
