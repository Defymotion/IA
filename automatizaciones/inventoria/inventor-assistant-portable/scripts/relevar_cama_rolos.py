"""Sólo lectura: releva un ensamble de cama de rolos (p. ej. la CdR1512 de Fademaq) para hacerla paramétrica.
Para cada ocurrencia (todas las profundidades): nombre, archivo, caja (mm, coordenadas del ensamble), matriz, nivel;
para cada pieza distinta: caja local, cuerpos, operaciones (tipos), parámetros de usuario/modelo, material, apariencia,
masa. Restricciones y uniones del ensamble de primer nivel. Cierra lo que abrió.
Uso: python relevar_cama_rolos.py <ensamble.iam> <salida.json>
"""
import json
import sys
import time
import traceback
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
import inventor_mcp as inv  # noqa: E402

S = inv._safe
T0 = time.time()
IAM, OUT = Path(sys.argv[1]), Path(sys.argv[2])
app = inv._inventor(start_if_needed=False)
res = {"archivo": str(IAM), "avisos": [], "occ": [], "piezas": {}}


def caja_b(b):
    return [round(v * 10, 2) for v in (b.MinPoint.X, b.MinPoint.Y, b.MinPoint.Z, b.MaxPoint.X, b.MaxPoint.Y, b.MaxPoint.Z)]


def mread(m):
    return [[round(m.Cell(r, c) * (10 if c == 4 else 1), 4) for c in range(1, 5)] for r in range(1, 4)]


def pieza(d):
    f = d.FullFileName
    if f in res["piezas"]:
        return
    cd = d.ComponentDefinition
    e = {"caja": S(lambda: caja_b(cd.RangeBox)), "cuerpos": S(lambda: cd.SurfaceBodies.Count),
         "material": S(lambda: d.ActiveMaterial.DisplayName), "apariencia": S(lambda: d.ActiveAppearance.DisplayName),
         "masa_kg": S(lambda: round(cd.MassProperties.Mass, 3)),
         "operaciones": [S(lambda f_=f_: f"{f_.Name}|{type(f_).__name__}|{S(lambda: f_.Type)}") for f_ in inv._items(cd.Features)][:40],
         "n_operaciones": S(lambda: cd.Features.Count),
         "param_usuario": {p.Name: S(lambda p=p: p.Expression) for p in inv._items(S(lambda: cd.Parameters.UserParameters) or [])},
         "param_modelo": {p.Name: S(lambda p=p: p.Expression) for p in list(inv._items(S(lambda: cd.Parameters.ModelParameters) or []))[:40]},
         "descripcion": S(lambda: d.PropertySets.Item("Design Tracking Properties").Item("Description").Value),
         "n_caras": S(lambda: sum(b.Faces.Count for b in inv._items(cd.SurfaceBodies)))}
    res["piezas"][f] = e


def recorrer(occs, nivel, ruta):
    for o in inv._items(occs):
        d = S(lambda: o.Definition.Document)
        e = {"n": ruta + o.Name, "nivel": nivel, "f": S(lambda: d.FullFileName), "c": S(lambda: caja_b(o.RangeBox)),
             "M": S(lambda: mread(o.Transformation)), "vis": S(lambda: bool(o.Visible)), "sup": S(lambda: bool(o.Suppressed)),
             "flex": S(lambda: bool(o.Flexible)), "fija": S(lambda: bool(o.Grounded)), "nh": S(lambda: o.SubOccurrences.Count, 0)}
        res["occ"].append(e)
        if d is not None and S(lambda: d.DocumentType) == inv.K_PART_DOCUMENT:
            pieza(d)
        if e["nh"]:
            recorrer(o.SubOccurrences, nivel + 1, ruta + o.Name + "/")


abierto_antes = any(S(lambda d=d: Path(d.FullFileName).resolve() == IAM.resolve(), False) for d in inv._items(app.Documents))
app.SilentOperation = True
doc = None
try:
    doc = next((d for d in inv._items(app.Documents) if S(lambda d=d: Path(d.FullFileName).resolve() == IAM.resolve(), False)), None)
    doc = doc or app.Documents.Open(str(IAM), False)
    cd = doc.ComponentDefinition
    res["caja"] = caja_b(cd.RangeBox)
    res["param_usuario"] = {p.Name: S(lambda p=p: p.Expression) for p in inv._items(S(lambda: cd.Parameters.UserParameters) or [])}
    res["restricciones"] = [S(lambda c=c: f"{c.Name}|{c.Type}") for c in inv._items(cd.Constraints)][:200]
    res["n_restricciones"] = S(lambda: cd.Constraints.Count)
    res["uniones"] = [S(lambda j=j: j.Name) for j in inv._items(S(lambda: cd.Joints) or [])][:100]
    recorrer(cd.Occurrences, 1, "")
except Exception as exc:  # noqa: BLE001
    res["error"] = repr(exc)
    res["traza"] = traceback.format_exc()[-2000:]
finally:
    if doc is not None and not abierto_antes:
        S(lambda: doc.Close(True))
    S(lambda: setattr(app, "SilentOperation", False))
res["s"] = round(time.time() - T0, 1)
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps({"occ": len(res["occ"]), "piezas": len(res["piezas"]), "caja": res.get("caja"), "error": res.get("error"),
                  "s": res["s"]}, ensure_ascii=False))
