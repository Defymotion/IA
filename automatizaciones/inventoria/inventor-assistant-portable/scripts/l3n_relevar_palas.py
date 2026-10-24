"""Sólo lectura: cajas (coordenadas locales del gripper, mm) de todas las piezas del gripper de simulación y de las piezas
de cada módulo de pala móvil, para saber el espesor real de la pala fija y dónde está la pala móvil.
Uso: python l3n_relevar_palas.py
"""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
import inventor_mcp as inv  # noqa: E402

S = inv._safe
GR = Path.home() / "Documents" / "InventorIA" / "Generados" / "L3N_SIM2" / "Gripper_SIM" / "Gripper_SIM.iam"
app = inv._inventor(start_if_needed=False)
out = {"piezas": []}


def caja(o):
    b = S(lambda: o.RangeBox, None)
    return None if b is None else [round(v * 10, 1) for v in (b.MinPoint.X, b.MinPoint.Y, b.MinPoint.Z, b.MaxPoint.X, b.MaxPoint.Y, b.MaxPoint.Z)]


app.SilentOperation = True
try:
    doc = next((d for d in inv._items(app.Documents) if S(lambda: Path(d.FullFileName).resolve() == GR.resolve(), False)), None)
    doc = doc or app.Documents.Open(str(GR), False)
    for o in inv._items(doc.ComponentDefinition.Occurrences):
        out["piezas"].append({"n": o.Name, "caja": caja(o)})
        if o.Name.startswith("Modulo pala movil:1"):
            for h in inv._items(o.SubOccurrences):
                out["piezas"].append({"n": o.Name + "/" + h.Name, "caja": caja(h)})
                for h2 in inv._items(S(lambda: h.SubOccurrences, []) or []):
                    out["piezas"].append({"n": o.Name + "/" + h.Name + "/" + h2.Name, "caja": caja(h2)})
finally:
    S(lambda: setattr(app, "SilentOperation", False))
print(json.dumps(out, ensure_ascii=False, indent=0))
