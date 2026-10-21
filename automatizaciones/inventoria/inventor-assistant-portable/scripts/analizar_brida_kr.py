"""Sólo lectura: busca el patrón de la brida de montaje (ISO 9409) en un modelo de robot (.ipt/.iam de STEP).
Agrupa los agujeros circulares coplanares y equidistantes de un centro (círculo de agujeros) y lista los
círculos concéntricos (centrado). No guarda nada en el modelo.
Uso: python analizar_brida_kr.py "<ruta al .ipt o .iam>" [--dmax 20]
Salida: Documents\\InventorIA\\Analisis\\brida_<archivo>.json
"""
import argparse
import json
import math
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
import inventor_mcp as inv  # noqa: E402

a = argparse.ArgumentParser()
a.add_argument("modelo")
a.add_argument("--dmax", type=float, default=20.0)
x = a.parse_args()
S = inv._safe
app = inv._inventor(start_if_needed=False)
app.SilentOperation = True
ya_abierto = any(S(lambda: Path(d.FullFileName).resolve() == Path(x.modelo).resolve(), False)
                 for d in inv._items(app.Documents))
doc = app.Documents.Open(x.modelo, False)


def cuerpos(d):
    if d.DocumentType == inv.K_ASSEMBLY_DOCUMENT:
        for o in inv._items(d.ComponentDefinition.Occurrences):
            for b in inv._items(S(lambda: o.SurfaceBodies, []) or []):
                yield o.Name, b
    else:
        for b in inv._items(d.ComponentDefinition.SurfaceBodies):
            yield S(lambda: b.Name, "cuerpo"), b


circ = []
nb = 0
for nombre, body in cuerpos(doc):
    nb += 1
    for e in inv._items(body.Edges):
        g = S(lambda: e.Geometry)
        if g is None or S(lambda: g.Radius) is None or S(lambda: g.StartAngle) is not None:
            continue
        c, n = g.Center, g.Normal
        nn = [n.X, n.Y, n.Z]
        k = max(range(3), key=lambda i: abs(nn[i]))
        if nn[k] < 0:
            nn = [-v for v in nn]
        circ.append({"cuerpo": nombre, "c": [c.X * 10, c.Y * 10, c.Z * 10], "n": nn, "d": g.Radius * 20})
S(lambda: setattr(app, "SilentOperation", False))
if not ya_abierto:
    S(lambda: doc.Close(True))


def dot(u, v):
    return sum(p * q for p, q in zip(u, v))


# agrupar por normal + plano + diámetro (agujeros chicos)
grupos = {}
for ci in circ:
    if ci["d"] > x.dmax:
        continue
    key = (tuple(round(v, 2) for v in ci["n"]), round(dot(ci["c"], ci["n"]), 0), round(ci["d"], 1))
    grupos.setdefault(key, []).append(ci)
cands = []
for (n, h, d), lst in grupos.items():
    pts = {tuple(round(v, 2) for v in q["c"]) for q in lst}
    pts = [list(p) for p in pts]
    if len(pts) < 3:
        continue
    cen = [sum(p[i] for p in pts) / len(pts) for i in range(3)]
    rr = [math.dist(p, cen) for p in pts]
    rm = sum(rr) / len(rr)
    # el centro promedio sólo vale si el patrón es simétrico: si no, probar con el círculo por 3 puntos
    if max(rr) - min(rr) > 0.5 or rm < 10:
        continue
    # ángulos en el plano
    ref = [p - c for p, c in zip(pts[0], cen)]
    ref = [v / (math.sqrt(dot(ref, ref)) or 1) for v in ref]
    w = [n[1] * ref[2] - n[2] * ref[1], n[2] * ref[0] - n[0] * ref[2], n[0] * ref[1] - n[1] * ref[0]]
    angs = sorted(round(math.degrees(math.atan2(dot([p - c for p, c in zip(q, cen)], w),
                                               dot([p - c for p, c in zip(q, cen)], ref))) % 360, 1) for q in pts)
    # círculos concéntricos (centrado, agujeros de pasador) en planos cercanos
    conc = sorted({(round(q["d"], 2), round(dot(q["c"], n) - h, 1)) for q in circ
                   if abs(abs(dot(q["n"], n)) - 1) < 1e-3 and math.dist(
                       [q["c"][i] - dot(q["c"], n) * n[i] for i in range(3)],
                       [cen[i] - dot(cen, n) * n[i] for i in range(3)]) < 0.5 and abs(dot(q["c"], n) - h) < 40})
    otros = sorted({(round(q["d"], 2), round(math.dist(q["c"], cen), 1)) for q in circ
                    if abs(abs(dot(q["n"], n)) - 1) < 1e-3 and abs(dot(q["c"], n) - h) < 15
                    and 1 < math.dist(q["c"], cen) < rm + 30 and abs(q["d"] - d) > 0.05})
    cands.append({"normal": n, "plano_mm": h, "d_agujero": d, "cantidad": len(pts), "pcd": round(2 * rm, 2),
                  "centro": [round(v, 2) for v in cen], "angulos": angs, "concentricos_d_dz": conc,
                  "otros_cerca_d_r": otros[:20]})
cands.sort(key=lambda q: (-q["cantidad"], q["pcd"]))
res = {"modelo": x.modelo, "cuerpos": nb, "circulos": len(circ), "candidatos": cands[:25]}
out = Path.home() / "Documents" / "InventorIA" / "Analisis" / f"brida_{Path(x.modelo).stem}.json"
out.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps(res, ensure_ascii=False, indent=1)[:50000])
