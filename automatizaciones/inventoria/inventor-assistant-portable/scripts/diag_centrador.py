"""Diagnóstico (sin guardar) del centrador de la escena NewPack2: cajas en el MUNDO de las piezas de los pistones
con la chapa en su lugar y corrida, y de los hijos de los cilindros (para mover vástagos)."""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import inventor_mcp as inv  # noqa: E402
import celda_kin as K  # noqa: E402

S = inv._safe
OUT = Path.home() / "Documents" / "InventorIA" / "Generados" / "NEWPACK2_SIM"
esc = json.loads((OUT / "escena.json").read_text(encoding="utf-8"))
app = inv._inventor(start_if_needed=False)
app.SilentOperation = True
tg = app.TransientGeometry
doc = next((d for d in inv._items(app.Documents) if Path(d.FullFileName).name == "NewPack2_simulacion.iam"), None) \
    or app.Documents.Open(str(OUT / "NewPack2_simulacion.iam"), True)
by = {o.Name: o for o in inv._items(doc.ComponentDefinition.Occurrences)}
cen = by[esc["centrador"]["occ"]]


def bx(o):
    b = o.RangeBox
    return [[round(b.MinPoint.X * 10, 1), round(b.MinPoint.Y * 10, 1), round(b.MinPoint.Z * 10, 1)],
            [round(b.MaxPoint.X * 10, 1), round(b.MaxPoint.Y * 10, 1), round(b.MaxPoint.Z * 10, 1)]]


def hojas(o, out, p=""):
    for h in inv._items(S(lambda: o.SubOccurrences, []) or []):
        q = f"{p}/{h.Name}"
        out[q] = bx(h)
        hojas(h, out, q)
    return out


res = {"centrador_mundo": hojas(cen, {})}
tp = next(o for o in inv._items(cen.SubOccurrences) if o.Name == esc["centrador"]["pistones_occ"])
pdoc = tp.Definition.Document
pocc = {o.Name: o for o in inv._items(pdoc.ComponentDefinition.Occurrences)}
ch = pocc["Chapa tope piston:1"]
M0 = esc["centrador"]["chapas"]["Chapa tope piston:1"]
res["chapa_mundo_modelo"] = bx(next(o for o in inv._items(tp.SubOccurrences) if o.Name == "Chapa tope piston:1"))
for dz in (60.0, -60.0):
    ch.Transformation = inv_m = None or tg.CreateMatrix()
    m = tg.CreateMatrix()
    M = K.mmul(K.tr(0, 0, dz), M0)
    m.SetCoordinateSystem(tg.CreatePoint(M[0][3] / 10, M[1][3] / 10, M[2][3] / 10),
                          tg.CreateVector(M[0][0], M[1][0], M[2][0]), tg.CreateVector(M[0][1], M[1][1], M[2][1]),
                          tg.CreateVector(M[0][2], M[1][2], M[2][2]))
    ch.Transformation = m
    pdoc.Update()
    doc.Update()
    res[f"chapa_mundo_dz{int(dz):+d}"] = bx(next(o for o in inv._items(tp.SubOccurrences)
                                                if o.Name == "Chapa tope piston:1"))
m = tg.CreateMatrix()
M = M0
m.SetCoordinateSystem(tg.CreatePoint(M[0][3] / 10, M[1][3] / 10, M[2][3] / 10),
                      tg.CreateVector(M[0][0], M[1][0], M[2][0]), tg.CreateVector(M[0][1], M[1][1], M[2][1]),
                      tg.CreateVector(M[0][2], M[1][2], M[2][2]))
ch.Transformation = m
pdoc.Update()
doc.Update()
# hijos de los cilindros (Ensamblaje1) en coord. de los pistones + sus restricciones
res["ensamblaje1"] = {}
for nm, o in pocc.items():
    if nm.startswith("Ensamblaje1"):
        d = o.Definition.Document
        res["ensamblaje1"][nm] = {"hijos": {h.Name: [Path(S(lambda: h.Definition.Document.FullFileName, "")).name, bx(h)]
                                            for h in inv._items(d.ComponentDefinition.Occurrences)},
                                  "restricciones": [[c.Name, S(lambda: c.OccurrenceOne.Name), S(lambda: c.OccurrenceTwo.Name),
                                                     S(lambda: c.Offset.Expression)]
                                                    for c in inv._items(d.ComponentDefinition.Constraints)],
                                  "archivo": d.FullFileName}
res["pistones_restricciones"] = [[c.Name, S(lambda: c.OccurrenceOne.Name), S(lambda: c.OccurrenceTwo.Name),
                                  S(lambda: c.Suppressed), S(lambda: c.Offset.Expression)]
                                 for c in inv._items(pdoc.ComponentDefinition.Constraints)]
S(lambda: setattr(app, "SilentOperation", False))
print(json.dumps(res, ensure_ascii=False, indent=1))
