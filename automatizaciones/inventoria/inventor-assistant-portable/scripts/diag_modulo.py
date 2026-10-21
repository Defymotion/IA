"""Sólo lectura: cajas de las ocurrencias de un módulo y círculos verticales de bloques / empuja pala / pala."""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
import inventor_mcp as inv  # noqa: E402

S = inv._safe
app = inv._inventor(start_if_needed=False)
app.SilentOperation = True
res = {}
for ruta in sys.argv[1:]:
    doc = app.Documents.Open(ruta, False)
    occs = []
    for o in inv._items(doc.ComponentDefinition.Occurrences):
        rb = o.RangeBox
        it = {"n": o.Name, "caja": [[round(rb.MinPoint.X * 10, 2), round(rb.MinPoint.Y * 10, 2), round(rb.MinPoint.Z * 10, 2)],
                                    [round(rb.MaxPoint.X * 10, 2), round(rb.MaxPoint.Y * 10, 2), round(rb.MaxPoint.Z * 10, 2)]]}
        nm = o.Name.lower()
        if "0485" in nm or "empuja" in nm or "pala" in nm:
            cs = set()
            for body in inv._items(S(lambda: o.SurfaceBodies, []) or []):
                for e in inv._items(body.Edges):
                    g = S(lambda: e.Geometry)
                    if g is None or S(lambda: g.Radius) is None or S(lambda: g.StartAngle) is not None:
                        continue
                    if g.Radius * 20 > 8:
                        continue
                    cs.add((round(g.Center.X * 10, 1), round(g.Center.Y * 10, 1), round(g.Radius * 20, 2),
                            round(g.Normal.X, 2), round(g.Normal.Y, 2), round(g.Normal.Z, 2)))
            it["circ"] = sorted(cs)[:40]
        occs.append(it)
    res[Path(ruta).parent.parent.name] = occs
S(lambda: setattr(app, "SilentOperation", False))
print(json.dumps(res, ensure_ascii=False))
