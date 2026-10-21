"""Diagnóstico (sin guardar): por qué la chapa de los pistones no se mueve en la escena NewPack2."""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import inventor_mcp as inv  # noqa: E402

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
cdoc = cen.Definition.Document
tp = next(o for o in inv._items(cen.SubOccurrences) if o.Name == esc["centrador"]["pistones_occ"])
pdoc = tp.Definition.Document
pcd = pdoc.ComponentDefinition
ch = next(o for o in inv._items(pcd.Occurrences) if o.Name.startswith("Chapa tope piston"))
proxy = next(o for o in inv._items(tp.SubOccurrences) if o.Name == ch.Name)


def bx(o):
    b = o.RangeBox
    return [round(b.MinPoint.Y * 10, 1), round(b.MaxPoint.Y * 10, 1)]


def tz(o):
    m = o.Transformation
    return [round(m.Cell(i, 4) * 10, 1) for i in (1, 2, 3)]


res = {"pdoc": pdoc.FullFileName, "cdoc": cdoc.FullFileName, "tp_archivo": tp.Definition.Document.FullFileName,
       "chapa": {"nombre": ch.Name, "grounded": S(lambda: ch.Grounded), "adaptive": S(lambda: ch.Adaptive),
                 "flexible": S(lambda: tp.Flexible), "T": tz(ch), "y_proxy": bx(proxy), "y_local": bx(ch)},
       "restricciones_chapa": [[c.Name, S(lambda: c.Suppressed)] for c in inv._items(pcd.Constraints)
                               if ch.Name in (S(lambda: c.OccurrenceOne.Name, ""), S(lambda: c.OccurrenceTwo.Name, ""))],
       "joints": [[j.Name, S(lambda: j.OccurrenceOne.Name), S(lambda: j.OccurrenceTwo.Name), S(lambda: j.Suppressed)]
                  for j in inv._items(S(lambda: pcd.Joints, []) or [])],
       "cdoc_es_pdoc_padre": S(lambda: tp.ParentOccurrence is None),
       "docs_abiertos_pistones": [d.FullFileName for d in inv._items(app.Documents) if "pistones" in d.FullFileName.lower()],
       "pruebas": []}
m0 = ch.Transformation


def prueba(etq, fn):
    try:
        fn()
        pdoc.Update()
        cdoc.Update()
        doc.Update()
        res["pruebas"].append([etq, "T", tz(ch), "y_local", bx(ch), "y_proxy", bx(proxy)])
    except Exception as exc:  # noqa: BLE001
        res["pruebas"].append([etq, "error", repr(exc)])
    finally:
        ch.Transformation = m0
        pdoc.Update()
        cdoc.Update()
        doc.Update()




def mz(dz):
    m = ch.Transformation
    v = tg.CreateVector(0, 0, dz / 10.0)
    t = tg.CreateMatrix()
    t.SetTranslation(v)
    t.PostMultiplyBy(m)
    return t


def set_t(dz):
    ch.Transformation = mz(dz)


prueba("Transformation z+60 local", lambda: set_t(60.0))
gr = S(lambda: ch.Grounded)
if gr:
    def f2():
        ch.Grounded = False
        set_t(60.0)
    prueba("sin grounded z+60", f2)
    S(lambda: setattr(ch, "Grounded", gr))


def f3():
    ch.SetTransformWithoutConstraints(mz(60.0))
prueba("SetTransformWithoutConstraints z+60", f3)
S(lambda: setattr(app, "SilentOperation", False))
print(json.dumps(res, ensure_ascii=False, indent=1))
