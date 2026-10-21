"""Extrae la posición y orientación (matriz 4×4) y la caja envolvente de cada componente del ensamble
ACTIVO y de sus subensambles (2 niveles). No modifica nada.
Salida: Documents\\InventorIA\\Analisis\\<ensamble>\\transformaciones.json
"""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
import inventor_mcp as inv  # noqa: E402

S = inv._safe
app = inv._inventor(start_if_needed=False)
target = Path(sys.argv[1]) if len(sys.argv) > 1 else \
    Path.home() / "Documents" / "InventorIA" / "12_ADECO2" / "Gripper" / "Gripper_ADECO2_V1.iam"
asm = None
for d in inv._items(app.Documents):
    if S(lambda: Path(d.FullFileName).resolve() == target.resolve(), False):
        asm = d
if asm is None:
    app.SilentOperation = True
    try:
        asm = app.Documents.Open(str(target), True)
    finally:
        app.SilentOperation = False


def matrix(occ):
    m = occ.Transformation
    rows = []
    for r in range(1, 5):
        row = []
        for c in range(1, 5):
            v = m.Cell(r, c)
            row.append(round(v * 10, 3) if c == 4 and r < 4 else round(v, 6))
        rows.append(row)
    return rows


def box(occ):
    b = S(lambda: occ.RangeBox)
    if b is None:
        return None
    return [[round(b.MinPoint.X * 10, 2), round(b.MinPoint.Y * 10, 2), round(b.MinPoint.Z * 10, 2)],
            [round(b.MaxPoint.X * 10, 2), round(b.MaxPoint.Y * 10, 2), round(b.MaxPoint.Z * 10, 2)]]


def walk(occs, depth):
    out = []
    for occ in inv._items(occs):
        if S(lambda: occ.Suppressed, False):
            continue
        d = {"nombre": occ.Name, "archivo": S(lambda: Path(occ.Definition.Document.FullFileName).name),
             "matriz_mm": matrix(occ), "caja_mm": box(occ), "fija": S(lambda: occ.Grounded, False)}
        if depth < 2 and S(lambda: occ.DefinitionDocumentType) == inv.K_ASSEMBLY_DOCUMENT:
            d["hijos"] = walk(occ.SubOccurrences, depth + 1)
        out.append(d)
    return out


res = {"ensamble": asm.FullFileName, "componentes": walk(asm.ComponentDefinition.Occurrences, 1)}
dest = Path.home() / "Documents" / "InventorIA" / "Analisis" / Path(asm.FullFileName).stem
dest.mkdir(parents=True, exist_ok=True)
(dest / "transformaciones.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
print("Componentes:", len(res["componentes"]), "->", dest / "transformaciones.json")
