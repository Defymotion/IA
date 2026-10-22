"""Mide ensambles (sólo lectura): caja envolvente, parámetros de usuario y componentes de primer nivel.
Abre invisible y cierra sin guardar los que no estaban abiertos. Uso: python medir_ensambles.py salida.json a.iam b.iam ...
"""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
import inventor_mcp as inv  # noqa: E402

S = inv._safe
app = inv._inventor(start_if_needed=False)
app.SilentOperation = True
salida = Path(sys.argv[1])
res = {}


def caja(b):
    return [round(b.MinPoint.X * 10, 1), round(b.MinPoint.Y * 10, 1), round(b.MinPoint.Z * 10, 1),
            round(b.MaxPoint.X * 10, 1), round(b.MaxPoint.Y * 10, 1), round(b.MaxPoint.Z * 10, 1)]


for r in sys.argv[2:]:
    ruta = Path(r)
    info = {}
    ya = next((d for d in inv._items(app.Documents)
               if S(lambda: Path(d.FullFileName).resolve() == ruta.resolve(), False)), None)
    try:
        doc = ya or app.Documents.Open(str(ruta), False)
        cd = doc.ComponentDefinition
        info["caja_mm"] = caja(cd.RangeBox)
        info["params"] = {p.Name: S(lambda: round(p.ModelValue * 10, 2) if p.Units in ("cm", "mm") else p.Expression)
                          for p in inv._items(cd.Parameters.UserParameters)}
        info["params_modelo"] = {p.Name: p.Expression for p in inv._items(cd.Parameters.ModelParameters)
                                 if not p.Name.startswith("d")}
        occs = []
        if doc.DocumentType == 12291:
            for o in inv._items(cd.Occurrences):
                occs.append({"n": o.Name, "f": Path(S(lambda: o.ReferencedDocumentDescriptor.FullDocumentName, "")).name,
                             "sup": bool(o.Suppressed),
                             "caja": S(lambda: caja(o.RangeBox)),
                             "pos": S(lambda: [round(o.Transformation.Translation.X * 10, 1),
                                               round(o.Transformation.Translation.Y * 10, 1),
                                               round(o.Transformation.Translation.Z * 10, 1)])})
        info["n_occ"] = len(occs)
        info["occs"] = occs[:80]
        if ya is None:
            doc.Close(True)
    except Exception as e:  # noqa: BLE001
        info["error"] = str(e)
    res[ruta.name + " | " + ruta.parent.name] = info
salida.parent.mkdir(parents=True, exist_ok=True)
salida.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps({k: {"caja_mm": v.get("caja_mm"), "n_occ": v.get("n_occ"), "params": v.get("params"),
                      "error": v.get("error")} for k, v in res.items()}, ensure_ascii=False, indent=1))
