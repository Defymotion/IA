"""Radiografía de piezas del ensamble ACTIVO: bocetos con sus cotas (nombre, expresión, valor),
parámetros, operaciones y patrones. No modifica nada.

Uso: .\\.venv\\Scripts\\python.exe .\\scripts\\radiografia_piezas.py [texto1 texto2 ...]
     (filtra piezas cuyo nombre contenga alguno de los textos; sin filtro, todas las de chapa propias)
Salida: Documents\\InventorIA\\Analisis\\<ensamble>\\radiografia.json y impresión resumida.
"""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
import inventor_mcp as inv  # noqa: E402

S = inv._safe
filters = [a.lower() for a in sys.argv[1:]]
app = inv._inventor(start_if_needed=False)
asm = app.ActiveDocument
if asm.DocumentType != inv.K_ASSEMBLY_DOCUMENT:
    sys.exit("El documento activo no es un ensamble")
counts = inv._leaf_counts(asm)


def param_info(p):
    return {"nombre": p.Name, "expresion": S(lambda: p.Expression),
            "valor_mm": S(lambda: round(p.Value * 10, 3)), "unidades": S(lambda: p.Units)}


def part_report(doc):
    cd = doc.ComponentDefinition
    rep = {"archivo": doc.FullFileName, "cantidad": counts.get(doc.FullFileName, 0),
           "chapa": doc.SubType == inv.SHEET_METAL_SUBTYPE,
           "envolvente_mm": S(lambda: inv._extent_mm(cd)),
           "espesor_mm": S(lambda: round(cd.Thickness.Value * 10, 3)),
           "parametros_usuario": [param_info(p) for p in inv._items(cd.Parameters.UserParameters)],
           "bocetos": [], "operaciones": []}
    for sk in inv._items(cd.Sketches):
        dims = []
        for dc in inv._items(sk.DimensionConstraints):
            p = S(lambda: dc.Parameter)
            if p is not None:
                dims.append({**param_info(p), "conducida": S(lambda: bool(dc.Driven), False)})
        rep["bocetos"].append({
            "nombre": sk.Name,
            "plano": S(lambda: sk.PlanarEntity.Name) or S(lambda: str(sk.PlanarEntity.Type)),
            "estado": S(lambda: inv.CONSTRAINT_STATUS_GUESS.get(int(sk.ConstraintStatus))),
            "lineas": S(lambda: sk.SketchLines.Count, 0), "circulos": S(lambda: sk.SketchCircles.Count, 0),
            "arcos": S(lambda: sk.SketchArcs.Count, 0), "cotas": dims})
    for f in inv._items(cd.Features):
        info = {"nombre": f.Name, "tipo": S(lambda: f.Type), "suprimida": S(lambda: f.Suppressed, False)}
        params = []
        for p in S(lambda: inv._items(f.Parameters), []) or []:
            params.append(param_info(p))
        if params:
            info["parametros"] = params
        rep["operaciones"].append(info)
    rep["parametros_modelo"] = [param_info(p) for p in inv._items(cd.Parameters.ModelParameters)]
    return rep


out = {}
for d in inv._items(asm.AllReferencedDocuments):
    if d.DocumentType != inv.K_PART_DOCUMENT:
        continue
    name = Path(d.FullFileName).stem
    if "content center files" in d.FullFileName.lower():
        continue
    if filters:
        if not any(f in name.lower() for f in filters):
            continue
    elif d.SubType != inv.SHEET_METAL_SUBTYPE:
        continue
    try:
        out[name] = part_report(d)
    except Exception as exc:  # noqa: BLE001
        out[name] = {"error": str(exc)}

dest = Path.home() / "Documents" / "InventorIA" / "Analisis" / Path(asm.FullFileName).stem
dest.mkdir(parents=True, exist_ok=True)
(dest / "radiografia.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
for name, rep in out.items():
    if "error" in rep:
        print(f"## {name}: ERROR {rep['error']}")
        continue
    print(f"## {name}  (x{rep['cantidad']})  env={rep['envolvente_mm']}  e={rep['espesor_mm']}")
    for sk in rep["bocetos"]:
        cot = ", ".join(f"{c['nombre']}={c['expresion']}" for c in sk["cotas"])
        print(f"  [{sk['nombre']}] {sk['estado']} L{sk['lineas']} C{sk['circulos']} A{sk['arcos']}: {cot}")
    print("  ops:", ", ".join(o["nombre"] for o in rep["operaciones"]))
print("\nGuardado en", dest / "radiografia.json")
