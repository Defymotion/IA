"""Sólo lectura: lista TODAS las ocurrencias de primer nivel del principal y, para las indicadas, sus subocurrencias
de primer nivel con archivo, visibilidad (en el principal), supresión, caja y matriz en contexto del principal (mm).
Uso: python relevar_hijos.py <iam_abierto> <salida.json> "Occ1;Occ2"
"""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
import inventor_mcp as inv  # noqa: E402

S = inv._safe
ruta, salida = Path(sys.argv[1]), Path(sys.argv[2])
padres = [s for s in sys.argv[3].split(";") if s]
app = inv._inventor(start_if_needed=False)
doc = next(d for d in inv._items(app.Documents) if S(lambda: Path(d.FullFileName).resolve() == ruta.resolve(), False))


def mat(m):
    return [[round(m.Cell(i, j) * (10 if j == 4 else 1), 3) for j in range(1, 5)] for i in range(1, 4)]


def caja(o):
    b = o.RangeBox
    return [round(v * 10, 1) for v in (b.MinPoint.X, b.MinPoint.Y, b.MinPoint.Z, b.MaxPoint.X, b.MaxPoint.Y, b.MaxPoint.Z)]


def fila(o):
    return {"n": o.Name, "archivo": S(lambda: o.ReferencedDocumentDescriptor.FullDocumentName),
            "visible": bool(S(lambda: o.Visible, True)), "sup": bool(S(lambda: o.Suppressed, False)),
            "caja": S(lambda: caja(o)), "M": S(lambda: mat(o.Transformation))}


res = {"principal": [fila(o) for o in inv._items(doc.ComponentDefinition.Occurrences)], "hijos": {}}
for o in inv._items(doc.ComponentDefinition.Occurrences):
    if o.Name in padres:
        res["hijos"][o.Name] = [fila(s) for s in inv._items(o.SubOccurrences)]
salida.parent.mkdir(parents=True, exist_ok=True)
salida.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
print({k: len(v) for k, v in res["hijos"].items()}, len(res["principal"]))
