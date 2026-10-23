"""Sólo lectura: lista las ocurrencias (de primer nivel y hojas) de un ensamble cuya caja toca un círculo en planta
(X, Z en mm del ensamble, radio R). Sirve para identificar piezas "volando" marcadas en una captura.
Uso: python relevar_puntos.py <iam> <salida.json> R x1,z1 x2,z2 ...
"""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
import inventor_mcp as inv  # noqa: E402

S = inv._safe
ruta, salida, R = Path(sys.argv[1]), Path(sys.argv[2]), float(sys.argv[3])
pts = [tuple(float(v) for v in a.split(",")) for a in sys.argv[4:]]
app = inv._inventor(start_if_needed=False)
app.SilentOperation = True
res = {"puntos": {}}
try:
    doc = next((d for d in inv._items(app.Documents) if S(lambda: Path(d.FullFileName).resolve() == ruta.resolve(), False)), None)
    doc = doc or app.Documents.Open(str(ruta), False)
    cd = doc.ComponentDefinition

    def caja(o):
        b = o.RangeBox
        return [round(v * 10, 1) for v in (b.MinPoint.X, b.MinPoint.Y, b.MinPoint.Z, b.MaxPoint.X, b.MaxPoint.Y, b.MaxPoint.Z)]

    def cerca(c, p):
        dx = max(c[0] - p[0], 0, p[0] - c[3])
        dz = max(c[2] - p[1], 0, p[1] - c[5])
        return (dx * dx + dz * dz) ** 0.5 <= R

    tops = [(o, caja(o)) for o in inv._items(cd.Occurrences) if S(lambda: o.Visible, True)]
    hojas = []
    for o in inv._items(cd.Occurrences.AllLeafOccurrences):
        if not S(lambda: o.Visible, True):
            continue
        c = S(lambda: caja(o))
        if c:
            hojas.append((o, c))
    res["n_top"], res["n_hojas"] = len(tops), len(hojas)
    for p in pts:
        k = f"{p[0]:g},{p[1]:g}"
        res["puntos"][k] = {
            "top": [{"nombre": o.Name, "caja": c, "archivo": Path(str(S(lambda: o.Definition.Document.FullFileName, ""))).name}
                    for o, c in tops if cerca(c, p) and (c[3] - c[0]) * (c[5] - c[2]) < 4e6],
            "hojas": [{"ruta": "/".join(S(lambda: [x.Name for x in o.OccurrencePath], [o.Name])), "caja": c,
                       "archivo": Path(str(S(lambda: o.Definition.Document.FullFileName, ""))).name}
                      for o, c in sorted(hojas, key=lambda h: (h[1][3] - h[1][0]) * (h[1][4] - h[1][1]) * (h[1][5] - h[1][2]))
                      if cerca(c, p) and "Mesa de Rolos" not in o.Name][:40],
        }
    res["top_todas"] = [{"nombre": o.Name, "caja": c} for o, c in tops]
finally:
    S(lambda: setattr(app, "SilentOperation", False))
salida.parent.mkdir(parents=True, exist_ok=True)
salida.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps({k: {"top": [t["nombre"] for t in v["top"]], "hojas": [h["ruta"] for h in v["hojas"]][:15]}
                  for k, v in res["puntos"].items()}, ensure_ascii=False, indent=1))
