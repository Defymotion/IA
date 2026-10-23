"""Sólo lectura: relevamiento de un ensamble para editarlo por parámetros: ocurrencias (todos los niveles) con archivo,
caja y transformación, y por cada pieza/ensamble distinto: parámetros de modelo y de usuario (nombre, expresión,
valor), features con su tipo y, en patrones, cantidad y distancia. También restricciones del ensamble.
Uso: python relevar_cad_param.py <iam> <salida.json>
"""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
import inventor_mcp as inv  # noqa: E402

S = inv._safe
ruta, salida = Path(sys.argv[1]), Path(sys.argv[2])
app = inv._inventor(start_if_needed=False)
app.SilentOperation = True
res = {"occ": [], "docs": {}}


def caja(o):
    b = S(lambda: o.RangeBox, None)
    if b is None:
        return None
    return [round(v * 10, 1) for v in (b.MinPoint.X, b.MinPoint.Y, b.MinPoint.Z, b.MaxPoint.X, b.MaxPoint.Y, b.MaxPoint.Z)]


def relevar_doc(d):
    fn = S(lambda: d.FullFileName, "?")
    if fn in res["docs"]:
        return
    info = {"tipo": S(lambda: d.DocumentType, None), "params": [], "user": [], "features": [], "restricciones": []}
    res["docs"][fn] = info
    cd = d.ComponentDefinition
    pars = S(lambda: cd.Parameters, None)
    if pars is not None:
        for p in inv._items(S(lambda: pars.ModelParameters, []) or []):
            info["params"].append([S(lambda: p.Name), S(lambda: p.Expression), S(lambda: round(p.ModelValue, 5))])
        for p in inv._items(S(lambda: pars.UserParameters, []) or []):
            info["user"].append([S(lambda: p.Name), S(lambda: p.Expression), S(lambda: round(p.ModelValue, 5))])
    feats = S(lambda: cd.Features, None)
    if feats is not None:
        for f in inv._items(feats):
            e = {"nombre": S(lambda: f.Name), "tipo": S(lambda: f.Type), "supr": S(lambda: f.Suppressed)}
            for attr in ("Count", "Spacing", "XCount", "XSpacing", "YCount", "YSpacing"):
                v = S(lambda: getattr(f.Definition, attr) if hasattr(f, "Definition") else getattr(f, attr), None)
                if v is None:
                    v = S(lambda: getattr(f, attr), None)
                if v is not None:
                    e[attr] = S(lambda: v.Expression, None) or S(lambda: v.Value, None) or str(v)
            info["features"].append(e)
        info["n_features"] = len(info["features"])
    if info["tipo"] == inv.K_ASSEMBLY_DOCUMENT:
        for c in inv._items(S(lambda: cd.Constraints, []) or []):
            info["restricciones"].append([S(lambda: c.Name), S(lambda: c.Type), S(lambda: c.Suppressed),
                                          S(lambda: c.OccurrenceOne.Name), S(lambda: c.OccurrenceTwo.Name),
                                          S(lambda: c.Offset.Expression, None) or S(lambda: c.Distance.Expression, None)])
        for pat in inv._items(S(lambda: cd.OccurrencePatterns, []) or []):
            info["features"].append({"patron_ocurrencias": S(lambda: pat.Name), "tipo": S(lambda: pat.Type),
                                     "ColumnCount": S(lambda: pat.ColumnCount.Expression), "ColumnOffset": S(lambda: pat.ColumnOffset.Expression),
                                     "RowCount": S(lambda: pat.RowCount.Expression), "RowOffset": S(lambda: pat.RowOffset.Expression),
                                     "Count": S(lambda: pat.Count.Expression), "Angle": S(lambda: pat.Angle.Expression)})


def recorrer(occs, ruta_, prof):
    for o in inv._items(occs):
        d = S(lambda: o.Definition.Document, None)
        t = S(lambda: o.Transformation.Translation, None)
        res["occ"].append({"ruta": ruta_ + o.Name, "prof": prof, "archivo": S(lambda: Path(d.FullFileName).name), "caja": caja(o),
                           "tr": [round(t.X * 10, 1), round(t.Y * 10, 1), round(t.Z * 10, 1)] if t else None,
                           "patron": S(lambda: o.IsPatternElement, None), "supr": S(lambda: o.Suppressed, None)})
        if d is not None:
            relevar_doc(d)
            if prof < 4 and S(lambda: o.SubOccurrences.Count, 0):
                recorrer(o.SubOccurrences, ruta_ + o.Name + "/", prof + 1)


try:
    doc = next((d for d in inv._items(app.Documents) if S(lambda: Path(d.FullFileName).resolve() == ruta.resolve(), False)), None)
    doc = doc or app.Documents.Open(str(ruta), False)
    res["raiz"] = doc.FullFileName
    relevar_doc(doc)
    recorrer(doc.ComponentDefinition.Occurrences, "", 1)
finally:
    S(lambda: setattr(app, "SilentOperation", False))
salida.parent.mkdir(parents=True, exist_ok=True)
salida.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps({"occ": len(res["occ"]), "docs": len(res["docs"])}, ensure_ascii=False))
