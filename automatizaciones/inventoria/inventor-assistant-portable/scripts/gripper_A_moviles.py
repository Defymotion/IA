"""Sólo lectura (restituye todo): qué piezas del módulo de pala móvil del gripper A (Gripper_A_SIM) se mueven cuando
cambia la restricción "Apertura" y cuánto (mm en coordenadas del gripper por cada cm de offset). Para animar el gripper A
fuera de Inventor. Uso: python gripper_A_moviles.py
"""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
import inventor_mcp as inv  # noqa: E402

S = inv._safe
G = Path.home() / "Documents" / "InventorIA" / "Generados" / "L3N_SIM5" / "Gripper_SIM" / "Gripper_A_SIM.iam"
OUT = Path.home() / "Documents" / "InventorIA" / "Generados" / "L3N_SIM5" / "Blender" / "gripper_A_moviles.json"
app = inv._inventor(start_if_needed=False)
res = {}
app.SilentOperation = True
gd = next((d for d in inv._items(app.Documents) if S(lambda: Path(d.FullFileName).resolve() == G.resolve(), False)), None)
gd = gd or app.Documents.Open(str(G), False)
try:
    occ = {o.Name: o for o in inv._items(gd.ComponentDefinition.Occurrences)}
    m1 = occ["Modulo pala movil:1"]
    md = m1.Definition.Document
    ap = next(c for c in inv._items(md.ComponentDefinition.Constraints) if "apertura" in c.Name.lower())
    v0 = ap.Offset.Value

    def leer():
        out = {}
        for h in inv._items(m1.SubOccurrences):
            m = h.Transformation
            out[h.Name] = [m.Cell(1, 4) * 10, m.Cell(2, 4) * 10, m.Cell(3, 4) * 10]
        return out

    a = leer()
    ap.Offset.Value = v0 + 1.0
    md.Update()
    gd.Update()
    b = leer()
    ap.Offset.Value = v0
    md.Update()
    gd.Update()
    c = leer()
    mov = {}
    for n in a:
        d = [b[n][k] - a[n][k] for k in range(3)]
        if max(abs(v) for v in d) > 0.01:
            mov[n] = [round(v, 4) for v in d]
    res = {"v0_cm": v0, "moviles": mov, "restituido": max(abs(c[n][k] - a[n][k]) for n in a for k in range(3)) < 0.01,
           "piezas_modulo": list(a)}
finally:
    S(lambda: setattr(app, "SilentOperation", False))
OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps(res, ensure_ascii=False, indent=1))
