"""Sólo lectura: en la escena L3N_SIM6 releva, dentro de Celda_B_existente y Celda_C_existente, las ocurrencias de robot
(KUKA*) y gripper (Gripper*), con su matriz en el layout (mm) y la de sus hijos directos.
Uso: python relevar_robots_bc_sim6.py <salida.json>
"""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
import inventor_mcp as inv  # noqa: E402

S = inv._safe
ESC = Path.home() / "Documents" / "InventorIA" / "Generados" / "L3N_SIM6" / "L3N_SIM6_Planta.iam"
app = inv._inventor(start_if_needed=False)


def M(o):
    t = o.Transformation
    return [[t.Cell(r, c) * (10.0 if c == 4 else 1.0) for c in range(1, 5)] for r in range(1, 4)]


def caja(o):
    b = o.RangeBox
    return [round(v * 10, 1) for v in (b.MinPoint.X, b.MinPoint.Y, b.MinPoint.Z, b.MaxPoint.X, b.MaxPoint.Y, b.MaxPoint.Z)]


out = {}
app.SilentOperation = True
try:
    doc = next((d for d in inv._items(app.Documents) if S(lambda d=d: Path(d.FullFileName).resolve() == ESC.resolve(), False)), None)
    doc = doc or app.Documents.Open(str(ESC), False)
    for t in inv._items(doc.ComponentDefinition.Occurrences):
        if not t.Name.startswith(("Celda_B", "Celda_C")):
            continue
        lst = []
        for h in inv._items(t.SubOccurrences):
            if h.Name.upper().startswith(("KUKA", "GRIPPER")):
                e = {"n": h.Name, "f": S(lambda h=h: h.ReferencedDocumentDescriptor.FullDocumentName), "M": M(h),
                     "c": S(lambda h=h: caja(h)), "vis": S(lambda h=h: bool(h.Visible)), "hijos": []}
                for s in inv._items(h.SubOccurrences):
                    e["hijos"].append({"n": s.Name, "f": S(lambda s=s: s.ReferencedDocumentDescriptor.FullDocumentName),
                                       "M": M(s), "c": S(lambda s=s: caja(s)), "vis": S(lambda s=s: bool(s.Visible))})
                lst.append(e)
        out[t.Name] = {"M": M(t), "robots": lst}
finally:
    app.SilentOperation = False
Path(sys.argv[1]).write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps({k: [(r["n"], r["c"], [h["n"] for h in r["hijos"]]) for r in v["robots"]] for k, v in out.items()}, ensure_ascii=False, indent=1))
