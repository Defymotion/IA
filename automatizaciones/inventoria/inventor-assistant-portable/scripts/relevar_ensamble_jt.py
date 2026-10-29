"""Sólo lectura: abre un ensamble (p. ej. el importado del JT) y lista las ocurrencias hasta N niveles con su caja
(mm, coordenadas del ensamble) y su matriz. Cierra el ensamble al terminar si lo abrió.
Uso: python relevar_ensamble_jt.py <ensamble.iam> <salida.json> [--niveles 2]"""
import json
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
import inventor_mcp as inv  # noqa: E402

S = inv._safe
ruta, salida = Path(sys.argv[1]), Path(sys.argv[2])
NIV = int(sys.argv[sys.argv.index("--niveles") + 1]) if "--niveles" in sys.argv else 2
app = inv._inventor(start_if_needed=False)
T0 = time.time()
ya = next((d for d in inv._items(app.Documents) if S(lambda d=d: Path(d.FullFileName).resolve() == ruta.resolve(), False)), None)
app.SilentOperation = True
doc = ya or app.Documents.Open(str(ruta), False)
t_open = round(time.time() - T0, 1)


def caja(b):
    return [round(b.MinPoint.X * 10, 1), round(b.MinPoint.Y * 10, 1), round(b.MinPoint.Z * 10, 1),
            round(b.MaxPoint.X * 10, 1), round(b.MaxPoint.Y * 10, 1), round(b.MaxPoint.Z * 10, 1)]


def walk(occs, nivel):
    out = []
    for o in inv._items(occs):
        e = {"n": str(o.Name), "doc": S(lambda: Path(o.Definition.Document.FullFileName).name),
             "caja": S(lambda: caja(o.RangeBox)), "vis": S(lambda: o.Visible),
             "M": S(lambda: [round(o.Transformation.Cell(i, j) * (10 if j == 4 else 1), 3) for i in (1, 2, 3) for j in (1, 2, 3, 4)])}
        if nivel < NIV:
            subs = S(lambda: o.SubOccurrences, None)
            if subs is not None and subs.Count:
                e["subs"] = walk(subs, nivel + 1)
        out.append(e)
    return out


try:
    res = {"ensamble": str(ruta), "t_abrir_s": t_open, "caja": caja(doc.ComponentDefinition.RangeBox),
           "occ": walk(doc.ComponentDefinition.Occurrences, 1)}
finally:
    if ya is None:
        S(lambda: doc.Close(True))
    app.SilentOperation = False
res["t_s"] = round(time.time() - T0, 1)
salida.parent.mkdir(parents=True, exist_ok=True)
salida.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps({k: v for k, v in res.items() if k != "occ"}, ensure_ascii=False), len(res["occ"]))
for e in res["occ"][:80]:
    print(e["n"], e["caja"], len(e.get("subs", [])))
