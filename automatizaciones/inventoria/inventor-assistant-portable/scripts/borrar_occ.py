"""Borra ocurrencias de primer nivel por nombre exacto en un ensamble PROPIO y guarda; informa tipo antes de borrar.
Uso: python borrar_occ.py <iam> "<nombre1;nombre2>"
"""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
import inventor_mcp as inv  # noqa: E402

S = inv._safe
ruta = Path(sys.argv[1])
nombres = [n for n in sys.argv[2].split(";") if n]
app = inv._inventor(start_if_needed=False)
app.SilentOperation = True
res = {"borradas": [], "fallas": []}
try:
    doc = next((d for d in inv._items(app.Documents) if S(lambda: Path(d.FullFileName).resolve() == ruta.resolve(), False)), None)
    doc = doc or app.Documents.Open(str(ruta), False)
    for o in list(inv._items(doc.ComponentDefinition.Occurrences)):
        if o.Name in nombres:
            info = {"nombre": o.Name, "definicion": S(lambda: o.Definition.Type), "suprimida": S(lambda: o.Suppressed),
                    "archivo": S(lambda: o.ReferencedDocumentDescriptor.FullDocumentName)}
            try:
                o.Delete()
                res["borradas"].append(info)
            except Exception as e:  # noqa: BLE001
                info["error"] = repr(e)
                res["fallas"].append(info)
    doc.Update()
    doc.Save()
finally:
    S(lambda: setattr(app, "SilentOperation", False))
print(json.dumps(res, ensure_ascii=False, indent=1))
