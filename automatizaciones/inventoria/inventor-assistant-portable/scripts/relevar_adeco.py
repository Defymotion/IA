"""Sólo lectura: componentes de nivel superior del ensamble general ADECO2 (archivo, matriz, caja) +
cajas envolventes de piezas sueltas útiles (caja, pallet) + PDFs que parezcan patrones de paletizado.
Salida: Documents\\InventorIA\\Analisis\\adeco_general.json"""
import json
import os
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
import inventor_mcp as inv  # noqa: E402

S = inv._safe
ROOT = Path.home() / "Documents" / "InventorIA" / "12_ADECO2"
T0 = time.time()
res = {"pdfs": []}
for dp, dn, fn in os.walk(ROOT):
    if "OldVersions" in dp:
        continue
    for f in fn:
        fl = f.lower()
        if fl.endswith(".pdf") and any(k in fl for k in ("palet", "patron", "patrón", "mosaico", "pallet", "layer", "piso")):
            res["pdfs"].append(str(Path(dp) / f))
        if fl.endswith((".ipt", ".iam")) and any(k in fl for k in ("caja", "box", "pallet", "palet", "rolo", "cinta")):
            res.setdefault("archivos_utiles", []).append(str(Path(dp) / f))
app = inv._inventor(start_if_needed=False)
app.SilentOperation = True


def r3(p):
    return [round(p.X * 10, 1), round(p.Y * 10, 1), round(p.Z * 10, 1)]


def mat(m):
    return [[round(m.Cell(r, c) * (10 if c == 4 and r < 4 else 1), 3) for c in range(1, 5)] for r in range(1, 4)]


gd = app.Documents.Open(str(ROOT / "ADECOAGRO_Chivilcoy.iam"), True)
cd = gd.ComponentDefinition
res["caja_total"] = [r3(cd.RangeBox.MinPoint), r3(cd.RangeBox.MaxPoint)]
comp = []
for o in inv._items(cd.Occurrences):
    fn = S(lambda: o.Definition.Document.FullFileName, "") or ""
    comp.append({"nombre": o.Name, "archivo": fn.replace(str(ROOT), "~"), "sup": S(lambda: o.Suppressed),
                 "visible": S(lambda: o.Visible), "matriz": mat(o.Transformation),
                 "caja": [r3(o.RangeBox.MinPoint), r3(o.RangeBox.MaxPoint)] if not S(lambda: o.Suppressed) else None,
                 "n_sub": S(lambda: o.SubOccurrences.Count, 0)})
res["componentes"] = comp
res["representaciones"] = {
    "vista": [v.Name for v in inv._items(S(lambda: cd.RepresentationsManager.DesignViewRepresentations, []) or [])],
    "posicion": [v.Name for v in inv._items(S(lambda: cd.RepresentationsManager.PositionalRepresentations, []) or [])]}
try:
    gd.Activate() if S(lambda: gd.Views.Count, 0) else gd.Views.Add()
    cam = app.ActiveView.Camera
    for nombre, cod in (("adeco_iso.png", 10759), ("adeco_planta.png", 10754)):
        cam.ViewOrientationType = cod
        cam.Fit()
        cam.Apply()
        app.ActiveView.SaveAsBitmap(str(ROOT.parent / "Analisis" / nombre), 1800, 1200)
except Exception as exc:  # noqa: BLE001
    res["imagen"] = str(exc)
res["tiempo_s"] = round(time.time() - T0, 1)
app.SilentOperation = False
(ROOT.parent / "Analisis" / "adeco_general.json").write_text(json.dumps(res, ensure_ascii=False, indent=1),
                                                            encoding="utf-8")
print(json.dumps({"componentes": len(comp), "pdfs": res["pdfs"], "tiempo_s": res["tiempo_s"]}, ensure_ascii=False))
