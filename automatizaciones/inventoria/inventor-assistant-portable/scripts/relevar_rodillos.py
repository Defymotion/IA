"""Sólo lectura: de una pieza (ipt, típicamente un STEP importado de una cama de rodillos) informa cuerpos, caja local,
y las caras cilíndricas agrupadas por radio con la posición de su eje a lo largo del lado más largo (para hallar el
paso de rodillos y dónde cortar sin partir piezas).
Uso: python relevar_rodillos.py <ipt> <salida.json>
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
import inventor_mcp as inv  # noqa: E402

S = inv._safe
ruta, salida = Path(sys.argv[1]), Path(sys.argv[2])
app = inv._inventor(start_if_needed=False)
app.SilentOperation = True
res = {}
try:
    doc = next((d for d in inv._items(app.Documents) if S(lambda: Path(d.FullFileName).resolve() == ruta.resolve(), False)), None)
    doc = doc or app.Documents.Open(str(ruta), False)
    cd = doc.ComponentDefinition
    b = cd.RangeBox
    bb = [round(v * 10, 1) for v in (b.MinPoint.X, b.MinPoint.Y, b.MinPoint.Z, b.MaxPoint.X, b.MaxPoint.Y, b.MaxPoint.Z)]
    res["caja"] = bb
    largos = [bb[3] - bb[0], bb[4] - bb[1], bb[5] - bb[2]]
    eje = largos.index(max(largos))
    res["eje_largo"] = "XYZ"[eje]
    res["cuerpos"] = []
    cil = defaultdict(list)
    for body in inv._items(cd.SurfaceBodies):
        bx = body.RangeBox
        res["cuerpos"].append({"nombre": S(lambda: body.Name), "caras": S(lambda: body.Faces.Count),
                               "caja": [round(v * 10, 1) for v in (bx.MinPoint.X, bx.MinPoint.Y, bx.MinPoint.Z,
                                                                    bx.MaxPoint.X, bx.MaxPoint.Y, bx.MaxPoint.Z)],
                               "lumps": S(lambda: body.Lumps.Count)})
        for f in inv._items(body.Faces):
            if S(lambda: f.SurfaceType, 0) != 5891:          # kCylinderSurface
                continue
            g = f.Geometry
            r = round(g.Radius * 10, 1)
            ax = g.AxisVector
            axv = [round(ax.X, 3), round(ax.Y, 3), round(ax.Z, 3)]
            p = g.BasePoint
            pos = round((p.X, p.Y, p.Z)[eje] * 10, 1)
            if abs((ax.X, ax.Y, ax.Z)[eje]) < 0.01:          # eje perpendicular al largo (rodillos, ejes)
                cil[r].append(pos)
    res["cilindros_perpendiculares"] = {str(r): sorted(set(v)) for r, v in sorted(cil.items(), key=lambda kv: -len(kv[1]))[:8]}
    for r, v in list(res["cilindros_perpendiculares"].items())[:3]:
        if len(v) > 2:
            dif = [round(v[i + 1] - v[i], 1) for i in range(len(v) - 1)]
            res.setdefault("pasos", {})[r] = dif
finally:
    S(lambda: setattr(app, "SilentOperation", False))
salida.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps(res, ensure_ascii=False)[:4000])
