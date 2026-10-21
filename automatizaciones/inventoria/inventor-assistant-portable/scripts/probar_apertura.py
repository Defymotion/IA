"""Prueba el mecanismo del módulo: cambia la restricción "Apertura" (carrera del cilindro) y mide cuánto se mueven
la pala, la goma, los bloques, la placa de empuje y el vástago. Deja todo como estaba (no guarda).
Uso: python probar_apertura.py <Modulo pala movil.iam> [carrera_mm=80]
"""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
import inventor_mcp as inv  # noqa: E402

S = inv._safe
path = Path(sys.argv[1])
carrera = float(sys.argv[2]) if len(sys.argv) > 2 else 80.0
app = inv._inventor(start_if_needed=False)
app.SilentOperation = True
doc = next((d for d in inv._items(app.Documents)
            if S(lambda: Path(d.FullFileName).resolve() == path.resolve(), False)), None) or \
    app.Documents.Open(str(path), True)
cd = doc.ComponentDefinition
ap = next(c for c in inv._items(cd.Constraints) if c.Name == "Apertura")
v0 = ap.Offset.Value


def pos():
    out = {}
    for o in inv._items(cd.Occurrences):
        m = o.Transformation
        out[o.Name] = [round(m.Cell(r, 4) * 10, 2) for r in range(1, 4)]
    return out


p0 = pos()
res = {"apertura_mm": round(v0 * 10, 3), "pruebas": {}}
for sg in (1, -1):
    ap.Offset.Value = v0 + sg * carrera / 10
    doc.Update()
    p1 = pos()
    mov = {k: [round(p1[k][i] - p0[k][i], 2) for i in range(3)] for k in p0
           if max(abs(p1[k][i] - p0[k][i]) for i in range(3)) > 0.01}
    res["pruebas"][f"{'+' if sg > 0 else '-'}{carrera}"] = {
        "movieron": mov, "salud": sorted({str(S(lambda: c.HealthStatus)) for c in inv._items(cd.Constraints)})}
    ap.Offset.Value = v0
    doc.Update()
res["vuelve_a_origen"] = pos() == p0
app.SilentOperation = False
print(json.dumps(res, ensure_ascii=False, indent=1))
