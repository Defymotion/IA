"""Sólo lectura (v9): todo lo que hay en la franja de paso del pallet de la celda A (giratoria -> cama de rolos ->
barrera -> transporte de salida), con cajas hasta 3 niveles, y los cilindros (rolos, piñones, ejes) de las piezas que se
pidan para medir altura de paso real (no la caja).
Uso: python l3n_v9_relevar_pases.py <salida.json> [--x0 -12000 --x1 -4000 --z0 -37200 --z1 -34000] [--cil texto1;texto2] [--todos texto: todas las caras cilíndricas y planas horizontales]
"""
import json
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
import inventor_mcp as inv  # noqa: E402

S = inv._safe
A = sys.argv
OUT = Path(A[1])


def arg(n, d):
    return float(A[A.index(n) + 1]) if n in A else d


X0, X1, Z0, Z1 = arg("--x0", -12000), arg("--x1", -4000), arg("--z0", -37200), arg("--z1", -34000)
CIL = [p for p in (A[A.index("--cil") + 1].split(";") if "--cil" in A else []) if p]
TODOS = [p for p in (A[A.index("--todos") + 1].split(";") if "--todos" in A else []) if p]
V9 = Path(r"C:\DEFYMOTION\L3N\Celdas_IA\LayoutL3N_liviano_v9.iam")
app = inv._inventor(start_if_needed=False)
res = {"ventana": [X0, Z0, X1, Z1], "occ": [], "cil": {}}
T0 = time.time()


def cb(b):
    return [round(v * 10, 1) for v in (b.MinPoint.X, b.MinPoint.Y, b.MinPoint.Z, b.MaxPoint.X, b.MaxPoint.Y, b.MaxPoint.Z)]


def dentro(c):
    return c and c[0] < X1 and c[3] > X0 and c[2] < Z1 and c[5] > Z0 and c[1] < 1500


def cilindros(o, todos=False):
    out = []
    for b in inv._items(S(lambda: o.SurfaceBodies, None) or []):
        for f in inv._items(b.Faces):
            st = S(lambda f=f: f.SurfaceType, 0)
            if todos and st == 5890:          # plano: sólo los horizontales (caras de apoyo)
                g = S(lambda f=f: f.Geometry)
                if g is not None and abs(g.Normal.Y) > 0.99:
                    out.append({"plano_y": round(g.RootPoint.Y * 10, 1), "caja": S(lambda f=f: cb(f.Evaluator.RangeBox))})
                continue
            if st != 5891:
                continue
            g = S(lambda f=f: f.Geometry)
            if g is None:
                continue
            ax = [round(g.AxisVector.X, 3), round(g.AxisVector.Y, 3), round(g.AxisVector.Z, 3)]
            out.append({"r": round(g.Radius * 10, 2), "p": [round(g.BasePoint.X * 10, 1), round(g.BasePoint.Y * 10, 1),
                                                           round(g.BasePoint.Z * 10, 1)], "ax": ax,
                        "caja": S(lambda f=f: cb(f.Evaluator.RangeBox))})
    if todos:
        return out[:6000]
    out.sort(key=lambda e: -e["r"])
    return out[:6]


def rec(o, ruta, prof):
    c = S(lambda: cb(o.RangeBox))
    if not dentro(c):
        return
    vis = S(lambda: bool(o.Visible), True)
    nh = S(lambda: o.SubOccurrences.Count, 0)
    e = {"n": ruta + o.Name, "c": c, "vis": vis, "nh": nh, "prof": prof,
         "f": S(lambda: o.ReferencedDocumentDescriptor.FullDocumentName, "")}
    res["occ"].append(e)
    if CIL and nh == 0 and vis and any(p in e["n"] for p in CIL) and len(res["cil"]) < 400:
        res["cil"][e["n"]] = cilindros(o, todos=any(p in e["n"] for p in TODOS))
    if nh and prof < 4 and vis:
        for h in inv._items(o.SubOccurrences):
            rec(h, ruta + o.Name + "/", prof + 1)


app.SilentOperation = True
try:
    doc = next((d for d in inv._items(app.Documents) if S(lambda d=d: Path(d.FullFileName).resolve() == V9.resolve(), False)), None)
    doc = doc or app.Documents.Open(str(V9), False)
    for o in inv._items(doc.ComponentDefinition.Occurrences):
        if o.Name.startswith(("Paredes", "Robot_Aereo")):
            continue
        rec(o, "", 1)
except Exception as exc:  # noqa: BLE001
    res["error"] = repr(exc)
finally:
    S(lambda: setattr(app, "SilentOperation", False))
res["s"] = round(time.time() - T0, 1)
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(res, ensure_ascii=False, indent=0), encoding="utf-8")
print(len(res["occ"]), len(res["cil"]), res["s"], res.get("error"))
