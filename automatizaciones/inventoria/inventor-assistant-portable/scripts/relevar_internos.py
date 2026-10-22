"""Sólo lectura: dentro de las ocurrencias de primer nivel indicadas, lista subcomponentes (hasta 3 niveles)
cuyo nombre contiene alguno de los filtros, con su caja en coordenadas del ensamble principal (mm).
Uso: python relevar_internos.py <iam_abierto> <salida.json> "Occ1;Occ2" "filtro1;filtro2"
"""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
import inventor_mcp as inv  # noqa: E402

S = inv._safe
ruta, salida = Path(sys.argv[1]), Path(sys.argv[2])
occs_q = [s for s in sys.argv[3].split(";") if s]
filtros = [s.lower() for s in sys.argv[4].split(";") if s]
app = inv._inventor(start_if_needed=False)
doc = next((d for d in inv._items(app.Documents)
            if S(lambda: Path(d.FullFileName).resolve() == ruta.resolve(), False)), None)
if doc is None:
    sys.exit(f"No está abierto: {ruta}")


def caja(b):
    return [round(b.MinPoint.X * 10, 1), round(b.MinPoint.Y * 10, 1), round(b.MinPoint.Z * 10, 1),
            round(b.MaxPoint.X * 10, 1), round(b.MaxPoint.Y * 10, 1), round(b.MaxPoint.Z * 10, 1)]


res = {}


def walk(o, path, depth, out):
    for s in inv._items(S(lambda: o.SubOccurrences, None) or []):
        n = str(s.Name)
        if any(f in n.lower() for f in filtros):
            out.append({"ruta": path + "/" + n, "sup": bool(S(lambda: s.Suppressed, False)),
                        "caja": S(lambda: caja(s.RangeBox))})
        if depth < 3 and not S(lambda: s.Suppressed, False):
            walk(s, path + "/" + n, depth + 1, out)


for o in inv._items(doc.ComponentDefinition.Occurrences):
    if o.Name in occs_q:
        out = []
        walk(o, o.Name, 1, out)
        res[o.Name] = out
salida.parent.mkdir(parents=True, exist_ok=True)
salida.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps(res, ensure_ascii=False, indent=1)[:12000])
