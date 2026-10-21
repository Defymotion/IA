"""Relevamiento SOLO LECTURA de piezas/ensambles comerciales (cilindros, guías, robots): caja de cada pieza,
agujeros (círculos de aristas) con centro, normal y diámetro, caras cilíndricas grandes (ejes) y masa.
Uso: python relevar_comercial.py "<iam/ipt>" ["<iam/ipt>" ...] [--nombre X] [--dmax 20]
Salida: Documents\\InventorIA\\Analisis\\<nombre>\\comerciales.json"""
import argparse
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
import inventor_mcp as inv  # noqa: E402

a = argparse.ArgumentParser()
a.add_argument("modelos", nargs="+")
a.add_argument("--nombre", default="COMERCIALES")
a.add_argument("--dmax", type=float, default=20.0)
x = a.parse_args()
S = inv._safe
app = inv._inventor(start_if_needed=False)
app.SilentOperation = True
OUT = Path.home() / "Documents" / "InventorIA" / "Analisis" / x.nombre
OUT.mkdir(parents=True, exist_ok=True)


def r(v):
    return round(v * 10, 2)


def box(b):
    return [[r(b.MinPoint.X), r(b.MinPoint.Y), r(b.MinPoint.Z)], [r(b.MaxPoint.X), r(b.MaxPoint.Y), r(b.MaxPoint.Z)]]


def geo(body):
    circ, cil = [], []
    for e in inv._items(body.Edges):
        g = S(lambda: e.Geometry)
        if g is None or S(lambda: g.Radius) is None or S(lambda: g.StartAngle) is not None:
            continue
        if g.Radius * 20 > x.dmax:
            continue
        c, n = g.Center, g.Normal
        circ.append([round(g.Radius * 20, 2), [r(c.X), r(c.Y), r(c.Z)], [round(n.X, 3), round(n.Y, 3), round(n.Z, 3)]])
    for f in inv._items(body.Faces):
        g = S(lambda: f.Geometry)
        rad = S(lambda: g.Radius)
        ax = S(lambda: g.AxisVector)
        if rad is None or ax is None:
            continue
        bp = S(lambda: g.BasePoint)
        cil.append([round(rad * 20, 2), [r(bp.X), r(bp.Y), r(bp.Z)], [round(ax.X, 3), round(ax.Y, 3), round(ax.Z, 3)],
                    S(lambda: box(f.Evaluator.RangeBox))])
    # sin repetidos
    vistos, c2 = set(), []
    for q in circ:
        k = (q[0], tuple(round(v, 1) for v in q[1]))
        if k not in vistos:
            vistos.add(k)
            c2.append(q)
    return c2, sorted(cil, key=lambda q: -q[0])[:30]


res = {}
for m in x.modelos:
    p = Path(m)
    ya = next((d for d in inv._items(app.Documents) if S(lambda: Path(d.FullFileName).resolve() == p.resolve(), False)), None)
    doc = ya or app.Documents.Open(str(p), False)
    cd = doc.ComponentDefinition
    item = {"archivo": str(p), "caja": S(lambda: box(cd.RangeBox)), "masa_kg": S(lambda: round(cd.MassProperties.Mass, 4)),
            "piezas": []}
    if doc.DocumentType == inv.K_ASSEMBLY_DOCUMENT:
        def rec(col, pref=""):
            for o in inv._items(col):
                if S(lambda: o.DefinitionDocumentType) == inv.K_ASSEMBLY_DOCUMENT:
                    rec(o.SubOccurrences, pref + o.Name + "/")
                    continue
                bodies = list(inv._items(S(lambda: o.SurfaceBodies, []) or []))
                circ, cil = [], []
                for b in bodies:
                    c1, c2 = geo(b)
                    circ += c1
                    cil += c2
                item["piezas"].append({"ruta": pref + o.Name, "archivo": Path(S(lambda: o.Definition.Document.FullFileName, "")).name,
                                       "caja": S(lambda: box(o.RangeBox)), "masa_kg": S(lambda: round(o.MassProperties.Mass, 4)),
                                       "agujeros": circ, "cilindros": cil})
        rec(cd.Occurrences)
        item["restricciones"] = [[c.Name, S(lambda: c.OccurrenceOne.Name), S(lambda: c.OccurrenceTwo.Name),
                                  S(lambda: c.Suppressed), S(lambda: c.Offset.Expression)] for c in inv._items(cd.Constraints)]
        item["parametros"] = [[q.Name, S(lambda: q.Expression)] for q in inv._items(S(lambda: cd.Parameters.UserParameters, []) or [])]
    else:
        circ, cil = [], []
        for b in inv._items(cd.SurfaceBodies):
            c1, c2 = geo(b)
            circ += c1
            cil += c2
        item["piezas"].append({"ruta": p.name, "caja": item["caja"], "agujeros": circ, "cilindros": cil})
    res[p.stem] = item
    if ya is None:
        S(lambda: doc.Close(True))
S(lambda: setattr(app, "SilentOperation", False))
(OUT / "comerciales.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
for k, v in res.items():
    print(k, v["caja"], v["masa_kg"], len(v["piezas"]))
    for q in v["piezas"]:
        print("   ", q["ruta"], q["caja"], q.get("masa_kg"), "agujeros:", len(q["agujeros"]))
