"""Diagnóstico (sin guardar): mover la chapa de los pistones a través del PROXY (Tope_pistones es flexible).
Primero cierra sin guardar la escena NewPack2 (quedó con 'flexible' apagado en memoria) y la vuelve a abrir."""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
import inventor_mcp as inv  # noqa: E402

S = inv._safe
OUT = Path.home() / "Documents" / "InventorIA" / "Generados" / "NEWPACK2_SIM"
esc = json.loads((OUT / "escena.json").read_text(encoding="utf-8"))
app = inv._inventor(start_if_needed=False)
app.SilentOperation = True
tg = app.TransientGeometry
res = {"cerrados": []}
for d in list(inv._items(app.Documents)):
    if S(lambda: Path(d.FullFileName).name == "NewPack2_simulacion.iam", False):
        res["cerrados"].append(d.FullFileName)
        d.Close(True)
S(lambda: app.Documents.CloseAll(True))            # sólo los que ya no están referenciados
res["abiertos_despues"] = [d.FullFileName for d in inv._items(app.Documents)]
doc = app.Documents.Open(str(OUT / "NewPack2_simulacion.iam"), True)
by = {o.Name: o for o in inv._items(doc.ComponentDefinition.Occurrences)}
cen = by[esc["centrador"]["occ"]]
cdoc = cen.Definition.Document
tp_c = next(o for o in inv._items(cdoc.ComponentDefinition.Occurrences) if o.Name == esc["centrador"]["pistones_occ"])
tp_w = next(o for o in inv._items(cen.SubOccurrences) if o.Name == tp_c.Name)
res["flexible"] = S(lambda: tp_c.Flexible)
res["centrador_flexible"] = S(lambda: cen.Flexible)


def bx(o):
    b = o.RangeBox
    return [[round(b.MinPoint.X * 10, 1), round(b.MinPoint.Y * 10, 1), round(b.MinPoint.Z * 10, 1)],
            [round(b.MaxPoint.X * 10, 1), round(b.MaxPoint.Y * 10, 1), round(b.MaxPoint.Z * 10, 1)]]


def chapa(occ):
    return next(o for o in inv._items(occ.SubOccurrences) if o.Name.startswith("Chapa tope piston"))


def otros():
    return {o.Name: bx(o) for o in inv._items(cen.SubOccurrences)}


res["inicio"] = {"chapa": bx(chapa(tp_w)), "centrador": otros()}


def trasl(m, v):
    t = tg.CreateMatrix()
    t.SetTranslation(tg.CreateVector(*[c / 10.0 for c in v]))
    r = m.Copy()
    r.TransformBy(t)
    return r


pruebas = []
for etq, occ, v in (("proxy en el centrador (z local +60)", tp_c, (0, 0, 60.0)),
                    ("proxy en la escena (y mundo -60)", tp_w, (0, -60.0, 0))):
    pr = chapa(occ)
    m0 = pr.Transformation
    try:
        pr.Transformation = trasl(m0, v)
        S(lambda: cdoc.Update())
        doc.Update()
        pruebas.append({"prueba": etq, "chapa": bx(chapa(tp_w)), "flexible": S(lambda: tp_c.Flexible)})
    except Exception as exc:  # noqa: BLE001
        pruebas.append({"prueba": etq, "error": repr(exc)})
    finally:
        S(lambda: setattr(pr, "Transformation", m0))
        S(lambda: cdoc.Update())
        doc.Update()
res["pruebas"] = pruebas
res["final"] = {"chapa": bx(chapa(tp_w)), "centrador": otros()}
S(lambda: setattr(app, "SilentOperation", False))
print(json.dumps(res, ensure_ascii=False, indent=1))
