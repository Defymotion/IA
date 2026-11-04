"""Sólo lectura (v9): hijos del plato de la giratoria de la celda A (rolos: caja en el layout y en su propia pieza) y las
piezas de la barrera de salida de la celda A (caja y matriz en el layout).
Uso: python l3n_v9_relevar_gir_barrera.py <salida.json>
"""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
import inventor_mcp as inv  # noqa: E402

S = inv._safe
V9 = Path(r"C:\DEFYMOTION\L3N\Celdas_IA\LayoutL3N_liviano_v9.iam")
app = inv._inventor(start_if_needed=False)
res = {"plato": [], "barrera": []}


def cb(b):
    return [round(v * 10, 1) for v in (b.MinPoint.X, b.MinPoint.Y, b.MinPoint.Z, b.MaxPoint.X, b.MaxPoint.Y, b.MaxPoint.Z)]


def mr(m):
    return [[round(m.Cell(r, c) * (10 if c == 4 else 1), 4) for c in range(1, 5)] for r in range(1, 4)]


def rec(o, ruta, out, prof):
    for h in inv._items(o.SubOccurrences):
        d = S(lambda h=h: h.Definition)
        out.append({"n": ruta + h.Name, "c": S(lambda h=h: cb(h.RangeBox)), "c_def": S(lambda d=d: cb(d.RangeBox)),
                    "nh": S(lambda h=h: h.SubOccurrences.Count, 0)})
        if prof < 2 and out[-1]["nh"]:
            rec(h, ruta + h.Name + "/", out, prof + 1)


app.SilentOperation = True
try:
    doc = next((d for d in inv._items(app.Documents) if S(lambda d=d: Path(d.FullFileName).resolve() == V9.resolve(), False)), None)
    doc = doc or app.Documents.Open(str(V9), False)
    occ = {o.Name: o for o in inv._items(doc.ComponentDefinition.Occurrences)}
    g = occ["Giratoria_A_ingreso"]
    plato = next(h for h in inv._items(g.SubOccurrences) if h.Name.startswith("01-001"))
    rec(plato, "", res["plato"], 1)
    ca = next(o for n, o in occ.items() if n.startswith("Celda_A"))
    for h in inv._items(ca.SubOccurrences):
        if h.Name.startswith(("Barrera_", "Reja_Norte_interna", "Reja_Este")):
            res["barrera"].append({"n": h.Name, "c": S(lambda h=h: cb(h.RangeBox)), "M": S(lambda h=h: mr(h.Transformation)),
                                   "f": S(lambda h=h: h.ReferencedDocumentDescriptor.FullDocumentName), "vis": S(lambda h=h: bool(h.Visible))})
finally:
    S(lambda: setattr(app, "SilentOperation", False))
Path(sys.argv[1]).write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
print(len(res["plato"]), len(res["barrera"]))
