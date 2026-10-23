"""Sólo lectura: ocurrencias (primer nivel y segundo nivel) de un ensamble cuya caja toca un rectángulo en planta
(X, Z en mm del ensamble). Para identificar qué hay en una zona (paredes, rejas, pallets, guías...).
Uso: python relevar_region.py <iam> <salida.json> xmin zmin xmax zmax [--prof 2]
"""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
import inventor_mcp as inv  # noqa: E402

S = inv._safe
ruta, salida = Path(sys.argv[1]), Path(sys.argv[2])
x0, z0, x1, z1 = (float(v) for v in sys.argv[3:7])
PROF = int(sys.argv[sys.argv.index("--prof") + 1]) if "--prof" in sys.argv else 2
app = inv._inventor(start_if_needed=False)
app.SilentOperation = True
res = {"region": [x0, z0, x1, z1], "occ": []}


def caja(o):
    b = o.RangeBox
    return [round(v * 10, 1) for v in (b.MinPoint.X, b.MinPoint.Y, b.MinPoint.Z, b.MaxPoint.X, b.MaxPoint.Y, b.MaxPoint.Z)]


def toca(c):
    return c[0] <= x1 and c[3] >= x0 and c[2] <= z1 and c[5] >= z0


try:
    doc = next((d for d in inv._items(app.Documents) if S(lambda: Path(d.FullFileName).resolve() == ruta.resolve(), False)), None)
    doc = doc or app.Documents.Open(str(ruta), False)

    def rec(occs, prof, padre):
        for o in inv._items(occs):
            if S(lambda: o.Suppressed, False):
                continue
            c = S(lambda: caja(o))
            if not c or not toca(c):
                continue
            vis = S(lambda: bool(o.Visible), True)
            res["occ"].append({"ruta": (padre + "/" if padre else "") + o.Name, "prof": prof, "caja": c, "visible": vis,
                               "archivo": Path(str(S(lambda: o.ReferencedDocumentDescriptor.FullDocumentName, ""))).name,
                               "n_hijos": S(lambda: o.SubOccurrences.Count, 0)})
            if prof < PROF and vis and S(lambda: o.SubOccurrences.Count, 0):
                rec(o.SubOccurrences, prof + 1, (padre + "/" if padre else "") + o.Name)

    rec(doc.ComponentDefinition.Occurrences, 1, "")
finally:
    S(lambda: setattr(app, "SilentOperation", False))
salida.parent.mkdir(parents=True, exist_ok=True)
salida.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
for r in res["occ"]:
    if r["prof"] <= 2 and r["visible"]:
        print(f'{"  " * (r["prof"] - 1)}{r["ruta"].split("/")[-1][:60]:60s} {r["caja"]} {r["archivo"][:40]}')
