"""Sólo lectura: distancia mínima desde puntos (mm, coordenadas del ensamble) a una ocurrencia de primer nivel
(p. ej. las paredes). Uso: python medir_distancia.py <iam> <prefijo_ocurrencia> x,y,z [x,y,z ...]
"""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
import inventor_mcp as inv  # noqa: E402

S = inv._safe
ruta, pref = Path(sys.argv[1]), sys.argv[2]
pts = [tuple(float(v) for v in a.split(",")) for a in sys.argv[3:]]
app = inv._inventor(start_if_needed=False)
app.SilentOperation = True
tg = app.TransientGeometry
res = {"distancias": []}
try:
    doc = next((d for d in inv._items(app.Documents) if S(lambda: Path(d.FullFileName).resolve() == ruta.resolve(), False)), None)
    doc = doc or app.Documents.Open(str(ruta), False)
    occ = next(o for o in inv._items(doc.ComponentDefinition.Occurrences) if o.Name.startswith(pref))
    res["occ"] = occ.Name
    for p in pts:
        try:
            d = app.MeasureTools.GetMinimumDistance(tg.CreatePoint(p[0] / 10, p[1] / 10, p[2] / 10), occ)
            if isinstance(d, tuple):
                d = d[0]
            res["distancias"].append({"p": p, "d": round(float(d) * 10, 1)})
        except Exception as e:  # noqa: BLE001
            res["distancias"].append({"p": p, "error": repr(e)[:200]})
finally:
    S(lambda: setattr(app, "SilentOperation", False))
print(json.dumps(res, ensure_ascii=False, indent=1))
