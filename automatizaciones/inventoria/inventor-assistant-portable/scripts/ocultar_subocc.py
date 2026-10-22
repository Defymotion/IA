"""Oculta (Visible=False en el ensamble principal, sin tocar el subensamble) las subocurrencias de primer nivel de
una ocurrencia cuyo nombre contenga alguna palabra clave, no contenga ninguna excluida y cuya caja caiga en la zona
(mm, X/Z del principal). Guarda el principal sólo con --guardar.
Uso: python ocultar_subocc.py <iam> <ocurrencia> "clave1;clave2" "excl1;excl2" xmin zmin xmax zmax [--guardar]
"""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
import inventor_mcp as inv  # noqa: E402

S = inv._safe
ruta, nom = Path(sys.argv[1]), sys.argv[2]
claves = [s.lower() for s in sys.argv[3].split(";") if s]
excl = [s.lower() for s in sys.argv[4].split(";") if s]
x0, z0, x1, z1 = (float(v) for v in sys.argv[5:9])
app = inv._inventor(start_if_needed=False)
app.SilentOperation = True
try:
    doc = next(d for d in inv._items(app.Documents) if S(lambda: Path(d.FullFileName).resolve() == ruta.resolve(), False))
    o = next(x for x in inv._items(doc.ComponentDefinition.Occurrences) if x.Name == nom)
    res = {"ocultas": [], "en_zona_no_ocultas": []}
    for s in inv._items(o.SubOccurrences):
        b = S(lambda: s.RangeBox)
        if b is None:
            continue
        bx = [b.MinPoint.X * 10, b.MinPoint.Z * 10, b.MaxPoint.X * 10, b.MaxPoint.Z * 10]
        if not (bx[0] >= x0 and bx[2] <= x1 and bx[1] >= z0 and bx[3] <= z1):
            continue
        n = s.Name.lower()
        fila = {"n": s.Name, "caja_xz": [round(v) for v in bx]}
        if any(k in n for k in claves) and not any(e in n for e in excl):
            s.Visible = False
            res["ocultas"].append(fila)
        else:
            res["en_zona_no_ocultas"].append(fila)
    if "--guardar" in sys.argv:
        doc.Save()
    print(json.dumps(res, ensure_ascii=False, indent=1))
finally:
    S(lambda: setattr(app, "SilentOperation", False))
