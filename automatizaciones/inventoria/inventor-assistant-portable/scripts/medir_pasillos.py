"""Sólo lectura: mide espacios libres en un ensamble tirando rayos (FindUsingRay del ensamble) desde puntos dados.
Para cada rayo devuelve la distancia al primer objeto VISIBLE que toca (ignora ocultos) y qué es.
rayos.json: [{"id": "...", "p": [x, y, z] (mm), "d": [dx, dy, dz]}, ...]
Uso: python medir_pasillos.py <iam> <rayos.json> <salida.json>
"""
import json
import math
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
import inventor_mcp as inv  # noqa: E402

S = inv._safe
ruta, rayos, salida = Path(sys.argv[1]), json.loads(Path(sys.argv[2]).read_text(encoding="utf-8")), Path(sys.argv[3])
app = inv._inventor(start_if_needed=False)
tg = app.TransientGeometry
T0 = time.time()
res = {"rayos": []}
vis_cache = {}


def visible(occ):
    """Visible si la ocurrencia y todos sus padres lo son."""
    try:
        path = occ.OccurrencePath
        n = path.Count
    except Exception:  # noqa: BLE001
        return True
    for i in range(1, n + 1):
        o = path.Item(i)
        v = S(lambda o=o: bool(o.Visible), True)
        if not v:
            return False
    return True


def nombre(occ):
    try:
        path = occ.OccurrencePath
        return "/".join(path.Item(i).Name for i in range(1, path.Count + 1))
    except Exception:  # noqa: BLE001
        return S(lambda: occ.Name, "?")


app.SilentOperation = True
try:
    doc = next((d for d in inv._items(app.Documents) if S(lambda d=d: Path(d.FullFileName).resolve() == ruta.resolve(), False)), None)
    if doc is None:
        doc = app.Documents.Open(str(ruta), True)
    cd = doc.ComponentDefinition
    for r in rayos:
        p = tg.CreatePoint(r["p"][0] / 10, r["p"][1] / 10, r["p"][2] / 10)
        d = tg.CreateUnitVector(*r["d"])
        e = {"id": r["id"], "dist_mm": None, "toca": None}
        try:
            out = cd.FindUsingRay(p, d, 0.05, None, None, False)
            ents, pts = out[0], out[1]
            best = None
            for i in range(len(pts) if pts else 0):
                q = pts[i]
                dist = math.dist((q.X * 10, q.Y * 10, q.Z * 10), r["p"])
                ent = ents[i]
                occ = S(lambda ent=ent: ent.ContainingOccurrence, None)
                if occ is not None and not visible(occ):
                    continue
                if best is None or dist < best[0]:
                    best = (dist, nombre(occ) if occ is not None else "?")
            if best:
                e["dist_mm"], e["toca"] = round(best[0]), best[1]
        except Exception as ex:  # noqa: BLE001
            e["error"] = repr(ex)[:160]
        res["rayos"].append(e)
finally:
    app.SilentOperation = False
res["s"] = round(time.time() - T0, 1)
salida.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps(res, ensure_ascii=False)[:12000])
