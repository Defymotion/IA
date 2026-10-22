"""Sólo lectura: estado de modelo / representación de nivel de detalle de ocurrencias de primer nivel y matrices
(contexto del ensamble principal) de subocurrencias cuyo nombre contenga los filtros.
Uso: python relevar_estados.py <iam_abierto> <salida.json> "filtro1;filtro2"
"""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
import inventor_mcp as inv  # noqa: E402

S = inv._safe
ruta, salida = Path(sys.argv[1]), Path(sys.argv[2])
filtros = [s.lower() for s in sys.argv[3].split(";") if s]
app = inv._inventor(start_if_needed=False)
doc = next(d for d in inv._items(app.Documents) if S(lambda: Path(d.FullFileName).resolve() == ruta.resolve(), False))


def mat(m):
    return [[round(m.Cell(i, j) * (10 if j == 4 else 1), 3) for j in range(1, 5)] for i in range(1, 4)]


res = {"top": {}, "sub": []}
for o in inv._items(doc.ComponentDefinition.Occurrences):
    if o.DefinitionDocumentType != 12291:
        continue
    res["top"][o.Name] = {"model_state": S(lambda: o.ActiveModelState), "lod": S(lambda: o.ActiveLevelOfDetailRepresentation),
                          "vista": S(lambda: o.ActiveDesignViewRepresentation),
                          "estados_disponibles": S(lambda: [m.Name for m in inv._items(o.Definition.ModelStates)]),
                          "suprimidos": [s.Name for s in inv._items(o.SubOccurrences) if S(lambda: s.Suppressed, False)]}
    for s in inv._items(o.SubOccurrences):
        if any(f in s.Name.lower() for f in filtros):
            res["sub"].append({"padre": o.Name, "n": s.Name, "sup": bool(S(lambda: s.Suppressed, False)),
                               "archivo": S(lambda: s.ReferencedDocumentDescriptor.FullDocumentName),
                               "M": S(lambda: mat(s.Transformation)),
                               "caja": S(lambda: [round(v * 10, 1) for v in (s.RangeBox.MinPoint.X, s.RangeBox.MinPoint.Y, s.RangeBox.MinPoint.Z, s.RangeBox.MaxPoint.X, s.RangeBox.MaxPoint.Y, s.RangeBox.MaxPoint.Z)])})
salida.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps(res, ensure_ascii=False, indent=1)[:15000])
