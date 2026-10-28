"""Sólo lectura: prueba qué devuelven por COM las llamadas con parámetros de salida (GetStrokes, FindUsingRay,
CalculateFacets) y lista las caras de una pieza. Uso: python sonda_brep.py <carpeta> <prefijo>"""
import json
import sys
import traceback
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
import inventor_mcp as inv  # noqa: E402

S = inv._safe
app = inv._inventor(start_if_needed=False)
tg = app.TransientGeometry
app.SilentOperation = True
f = sorted(Path(sys.argv[1]).glob(sys.argv[2] + "*.ipt"))[0]
d = app.Documents.Open(str(f), False)
out = {}
try:
    b = d.ComponentDefinition.SurfaceBodies.Item(1)
    caras = []
    for f in inv._items(b.Faces):
        g = f.Geometry
        e = {"tipo": S(lambda: f.SurfaceType), "area": S(lambda: round(f.Evaluator.Area, 3))}
        n = S(lambda: g.Normal, None)
        if n is not None:
            e["n"] = [round(n.X, 4), round(n.Y, 4), round(n.Z, 4)]
            e["o"] = S(lambda: [round(g.RootPoint.X, 3), round(g.RootPoint.Y, 3), round(g.RootPoint.Z, 3)])
        a = S(lambda: g.AxisVector, None)
        if a is not None:
            e["eje"] = [round(a.X, 4), round(a.Y, 4), round(a.Z, 4)]
            e["r"] = S(lambda: round(g.Radius, 4))
        e["lazos"] = S(lambda: f.EdgeLoops.Count)
        caras.append(e)
    out["caras"] = caras[:60]
    out["n_caras"] = len(caras)
    ed = b.Edges.Item(1)
    out["edge_tipo"] = S(lambda: ed.CurveType)
    ev = ed.Evaluator
    for nombre, fn in [
        ("GetParamExtents", lambda: ev.GetParamExtents(0.0, 0.0)),
        ("GetStrokes", lambda: ev.GetStrokes(0.0, 1.0, 0.01, 0, [])),
        ("GetEndPoints", lambda: ev.GetEndPoints([], [])),
        ("PointOnFace", lambda: [b.Faces.Item(1).PointOnFace.X, b.Faces.Item(1).PointOnFace.Y]),
        ("CalculateFacets", lambda: b.CalculateFacets(0.05, 0, 0, [], [], [])),
        ("FindUsingRay", lambda: b.FindUsingRay(tg.CreatePoint(0, 0, -100), tg.CreateUnitVector(0, 0, 1), 0.001,
                                                 None, None, True)),
    ]:
        try:
            r = fn()
            s = repr(r)
            out[nombre] = s[:400]
        except Exception as ex:  # noqa: BLE001
            out[nombre] = "ERR " + repr(ex)[:300]
except Exception:  # noqa: BLE001
    out["traceback"] = traceback.format_exc()[-1500:]
finally:
    S(lambda: d.Close(True))
    app.SilentOperation = False
print(json.dumps(out, ensure_ascii=False, indent=0)[:15000])
