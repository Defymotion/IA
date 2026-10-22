"""Sólo lectura: cajas en coordenadas locales de un ensamble (total y de las ocurrencias cuyo nombre empieza con los
prefijos dados). Uso: python diag_cajas_locales.py <ens.iam> "brida;frame;pala fija"
"""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
import inventor_mcp as inv  # noqa: E402

S = inv._safe
ruta = Path(sys.argv[1])
prefs = [p.lower() for p in sys.argv[2].split(";") if p]
app = inv._inventor(start_if_needed=False)
app.SilentOperation = True
try:
    doc = next((d for d in inv._items(app.Documents) if S(lambda: Path(d.FullFileName).resolve() == ruta.resolve(), False)), None)
    doc = doc or app.Documents.Open(str(ruta), False)
    cd = doc.ComponentDefinition

    def caja(b):
        return [round(v * 10, 1) for v in (b.MinPoint.X, b.MinPoint.Y, b.MinPoint.Z, b.MaxPoint.X, b.MaxPoint.Y, b.MaxPoint.Z)]

    res = {"total": caja(cd.RangeBox), "occ": {}}

    def walk(col, prof):
        for o in inv._items(col):
            if any(o.Name.lower().startswith(p) for p in prefs):
                res["occ"][o.Name] = caja(o.RangeBox)
            if prof < 2 and S(lambda: o.SubOccurrences.Count, 0):
                walk(o.SubOccurrences, prof + 1)
    walk(cd.Occurrences, 0)
finally:
    S(lambda: setattr(app, "SilentOperation", False))
print(json.dumps(res, ensure_ascii=False, indent=1))
