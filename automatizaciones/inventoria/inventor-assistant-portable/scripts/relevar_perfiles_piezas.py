"""Sólo lectura: perfiles de piezas importadas (sin parámetros) para reconstruirlas paramétricas.
Para cada pieza: caja; caras planas cuya normal es paralela al eje pedido y que están en el extremo mínimo de ese eje
(perfil de la sección), con sus lazos como polilíneas (mm, coordenadas de la pieza; arcos muestreados); caras
cilíndricas (eje, radio, punto) y planas (normal, punto, área) resumidas.
Uso: python relevar_perfiles_piezas.py <salida.json> <pieza.ipt>:<eje x|y|z> [...]
"""
import json
import math
import sys
import time
import traceback
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
import inventor_mcp as inv  # noqa: E402

S = inv._safe
T0 = time.time()
OUT = Path(sys.argv[1])
app = inv._inventor(start_if_needed=False)
res = {"piezas": {}, "avisos": []}
K_PLANE, K_CYL = 5890, 5891          # kPlaneSurface, kCylinderSurface


def p3(p):
    return [round(p.X * 10, 3), round(p.Y * 10, 3), round(p.Z * 10, 3)]


def muestrear(e, n=12):
    ev = e.Evaluator
    r = ev.GetParamExtents(0.0, 0.0)
    a, b = [v for v in (r if isinstance(r, (tuple, list)) else [r]) if isinstance(v, float)][-2:]
    pts = []
    tipo = S(lambda: e.GeometryType, 0)
    k = 1 if tipo == 5122 else n          # kLineSegmentCurve: sólo extremos
    for i in range(k + 1):
        t = a + (b - a) * i / k
        r = ev.GetPointAtParam([t], [0.0, 0.0, 0.0])
        seq = r[-1] if isinstance(r, tuple) and isinstance(r[-1], (tuple, list)) else r
        pts.append([round(v * 10, 3) for v in list(seq)[:3]])
    return pts


for arg in sys.argv[2:]:
    ruta, eje = arg.rsplit(":", 1)
    ax = "xyz".index(eje)
    e = {"eje": eje, "lazos_extremo": [], "cilindros": [], "planos": []}
    res["piezas"][ruta] = e
    d = None
    abierto = False
    try:
        d = next((x for x in inv._items(app.Documents) if S(lambda x=x: Path(x.FullFileName).resolve() == Path(ruta).resolve(), False)), None)
        abierto = d is not None
        d = d or app.Documents.Open(ruta, False)
        cd = d.ComponentDefinition
        b = cd.RangeBox
        e["caja"] = [round(v * 10, 3) for v in (b.MinPoint.X, b.MinPoint.Y, b.MinPoint.Z, b.MaxPoint.X, b.MaxPoint.Y, b.MaxPoint.Z)]
        lo = e["caja"][ax]
        for body in inv._items(cd.SurfaceBodies):
            for f in inv._items(body.Faces):
                st = S(lambda f=f: f.SurfaceType, 0)
                g = S(lambda f=f: f.Geometry)
                if st == K_PLANE and g is not None:
                    n = [g.Normal.X, g.Normal.Y, g.Normal.Z]
                    pt = p3(g.RootPoint)
                    area = S(lambda f=f: round(f.Evaluator.Area * 100, 1), None)
                    e["planos"].append({"n": [round(v, 4) for v in n], "p": pt, "area": area})
                    if abs(abs(n[ax]) - 1) < 1e-4 and abs(pt[ax] - lo) < 0.5:
                        for lazo in inv._items(f.EdgeLoops):
                            pl = []
                            for ed in inv._items(lazo.Edges):
                                pl.append(S(lambda ed=ed: muestrear(ed)))
                            e["lazos_extremo"].append({"exterior": S(lambda lazo=lazo: bool(lazo.IsOuterEdgeLoop)), "aristas": pl})
                elif st == K_CYL and g is not None:
                    e["cilindros"].append({"eje": [round(g.AxisVector.X, 4), round(g.AxisVector.Y, 4), round(g.AxisVector.Z, 4)],
                                           "r": round(g.Radius * 10, 3), "p": p3(g.BasePoint)})
    except Exception as exc:  # noqa: BLE001
        e["error"] = repr(exc)
        e["traza"] = traceback.format_exc()[-1500:]
    finally:
        if d is not None and not abierto:
            S(lambda: d.Close(True))
res["s"] = round(time.time() - T0, 1)
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps({k: {"caja": v.get("caja"), "lazos": len(v["lazos_extremo"]), "cil": len(v["cilindros"]), "pl": len(v["planos"]),
                      "error": v.get("error")} for k, v in res["piezas"].items()}, ensure_ascii=False, indent=1))
