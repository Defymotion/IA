"""Relevamiento geométrico de piezas de referencia (sólo lectura).

Para cada archivo pedido (busca por nombre dentro de la copia de ADECO2) guarda:
- caja envolvente, espesor si es chapa, desarrollo si tiene
- circunferencias (centro, radio, normal) y caras planas (normal, área, caja) en coordenadas de la pieza
- si es ensamble: componentes (todos los niveles) con matriz en coordenadas del ensamble, fijo/flexible,
  cantidad de restricciones
Uso: python geometria_ref.py "empuja pala" "part_empuje" ...
Salida: Documents\\InventorIA\\Analisis\\geometria_ref.json
"""
import json
import os
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
import inventor_mcp as inv  # noqa: E402

S = inv._safe
ROOT = Path.home() / "Documents" / "InventorIA" / "12_ADECO2"
app = inv._inventor(start_if_needed=False)
app.SilentOperation = True


def r3(p):
    return [round(p.X * 10, 3), round(p.Y * 10, 3), round(p.Z * 10, 3)]


def v3(v):
    return [round(v.X, 4), round(v.Y, 4), round(v.Z, 4)]


def box(b):
    return [r3(b.MinPoint), r3(b.MaxPoint)]


def mat(m):
    return [[round(m.Cell(r, c) * (10 if c == 4 and r < 4 else 1), 4) for c in range(1, 5)] for r in range(1, 4)]


def geom_part(doc, max_faces=400):
    cd = doc.ComponentDefinition
    out = {"caja": box(cd.RangeBox), "chapa": doc.SubType == inv.SHEET_METAL_SUBTYPE,
           "material": S(lambda: doc.ComponentDefinition.Material.Name),
           "masa_kg": S(lambda: round(cd.MassProperties.Mass, 4))}
    if out["chapa"]:
        out["espesor"] = S(lambda: round(cd.Thickness.Value * 10, 3))
        fp = S(lambda: cd.FlatPattern)
        if fp is not None:
            out["desarrollo"] = S(lambda: [round(fp.Length * 10, 3), round(fp.Width * 10, 3)])
    circ, planes, cyl = [], [], []
    for body in inv._items(cd.SurfaceBodies):
        for e in inv._items(body.Edges):
            if S(lambda: e.CurveType) in (5122, 5123):
                continue
            g = S(lambda: e.Geometry)
            if g is None or S(lambda: g.StartAngle) is not None:
                continue
            c, r = S(lambda: g.Center), S(lambda: g.Radius)
            if c is None or r is None:
                continue
            circ.append([*r3(c), round(r * 20, 3), *v3(g.Normal)])
        for f in inv._items(body.Faces):
            st = S(lambda: f.SurfaceType)
            if st == 5890:      # kPlaneSurface
                planes.append({"n": v3(f.Geometry.Normal), "p": r3(f.Geometry.RootPoint),
                               "area_mm2": round(f.Evaluator.Area * 100, 1), "caja": box(f.Evaluator.RangeBox)})
            elif st == 5891:    # kCylinderSurface
                g = f.Geometry
                cyl.append({"eje": v3(g.AxisVector), "base": r3(g.BasePoint), "d": round(g.Radius * 20, 3),
                            "caja": box(f.Evaluator.RangeBox)})
    planes.sort(key=lambda p: -p["area_mm2"])
    out["circulos"] = sorted({tuple(c) for c in circ})
    out["planos"] = planes[:max_faces]
    out["cilindros"] = cyl[:max_faces]
    return out


def geom_asm(doc):
    cd = doc.ComponentDefinition
    occs = []

    def walk(col, depth):
        for o in inv._items(col):
            occs.append({"nombre": o.Name, "nivel": depth,
                         "archivo": S(lambda: Path(o.Definition.Document.FullFileName).name),
                         "matriz": mat(o.Transformation), "caja": S(lambda: box(o.RangeBox)),
                         "fija": S(lambda: o.Grounded), "flexible": S(lambda: o.Flexible),
                         "suprimida": S(lambda: o.Suppressed),
                         "restricciones": S(lambda: o.Constraints.Count)})
            if S(lambda: o.DefinitionDocumentType) == inv.K_ASSEMBLY_DOCUMENT and depth < 4:
                walk(o.SubOccurrences, depth + 1)
    walk(cd.Occurrences, 1)
    cons = []
    for c in inv._items(cd.Constraints):
        cons.append({"nombre": c.Name, "tipo": S(lambda: c.Type),
                     "o1": S(lambda: c.OccurrenceOne.Name), "o2": S(lambda: c.OccurrenceTwo.Name),
                     "offset_mm": S(lambda: round(c.Offset.Value * 10, 3)),
                     "suprimida": S(lambda: c.Suppressed)})
    return {"caja": box(cd.RangeBox), "componentes": occs, "restricciones": cons}


SALIDA = next((a.split("=", 1)[1] for a in sys.argv[1:] if a.startswith("--salida=")), "geometria_ref.json")
ARGS = [a for a in sys.argv[1:] if not a.startswith("--salida=")]
wanted = [a.lower() for a in ARGS if not Path(a).is_file()]
files = {a: Path(a) for a in ARGS if Path(a).is_file()}      # rutas completas (sólo lectura)
for p in ROOT.rglob("*"):
    if p.suffix.lower() in (".ipt", ".iam") and "oldversions" not in str(p).lower():
        for w in wanted:
            if p.stem.lower() == w or (w.endswith("*") and p.stem.lower().startswith(w[:-1])):
                files.setdefault(str(p), p)
res = {}
for path, p in files.items():
    opened_here = False
    doc = next((d for d in inv._items(app.Documents)
                if S(lambda: Path(d.FullFileName).resolve() == p.resolve(), False)), None)
    try:
        if doc is None:
            doc = app.Documents.Open(path, False)
            opened_here = True
        if doc.DocumentType == inv.K_ASSEMBLY_DOCUMENT:
            r = geom_asm(doc)
            # geometría de las piezas hoja del ensamble comercial
            r["piezas"] = {}
            for d in inv._items(doc.AllReferencedDocuments):
                if d.DocumentType == inv.K_PART_DOCUMENT:
                    r["piezas"][Path(d.FullFileName).name] = geom_part(d, 60)
        else:
            r = geom_part(doc)
        res[p.name] = {"archivo": path, **r}
        print("OK", p.name, flush=True)
    except Exception as exc:  # noqa: BLE001
        res[p.name] = {"archivo": path, "error": repr(exc)}
        print("ERROR", p.name, exc, flush=True)
    finally:
        if opened_here:
            S(lambda: doc.Close(True))
app.SilentOperation = False
dest = Path.home() / "Documents" / "InventorIA" / "Analisis" / SALIDA
dest.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
print("Faltan:", [w for w in wanted if not any(Path(k).stem.lower() == w for k in files)])
print("->", dest)
