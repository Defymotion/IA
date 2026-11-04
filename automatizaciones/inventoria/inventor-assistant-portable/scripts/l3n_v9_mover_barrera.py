"""L3N v9: corre en Z piezas de la celda A sin tocar la celda (oculta los proxies en el v9 y agrega copias en el primer
nivel con el corrimiento). Por defecto, el emisor de la barrera de salida 60 mm al sur (-Z) para que pase el pallet con
1200 de frente.
Uso: python l3n_v9_mover_barrera.py <resultado.json> [--dz -60] [--prefijos "Barrera_IFM_emisor,Barrera_brazo_emisor,Barrera_sensor_emisor"]
"""
import json
import sys
import traceback
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
import inventor_mcp as inv  # noqa: E402

S = inv._safe
A = sys.argv
OUT = Path(A[1])
DZ = float(A[A.index("--dz") + 1]) if "--dz" in A else -60.0
PREF = tuple((A[A.index("--prefijos") + 1] if "--prefijos" in A else "Barrera_IFM_emisor,Barrera_brazo_emisor,Barrera_sensor_emisor").split(","))
V9 = Path(r"C:\DEFYMOTION\L3N\Celdas_IA\LayoutL3N_liviano_v9.iam")
app = inv._inventor(start_if_needed=False)
tg = app.TransientGeometry
log = {"movidos": [], "avisos": []}


def cb(o):
    b = o.RangeBox
    return [round(v * 10, 1) for v in (b.MinPoint.X, b.MinPoint.Y, b.MinPoint.Z, b.MaxPoint.X, b.MaxPoint.Y, b.MaxPoint.Z)]


app.SilentOperation = True
try:
    doc = next((d for d in inv._items(app.Documents) if S(lambda d=d: Path(d.FullFileName).resolve() == V9.resolve(), False)), None)
    doc = doc or app.Documents.Open(str(V9), True)
    cd = doc.ComponentDefinition
    for o in list(inv._items(cd.Occurrences)):
        if o.Name.startswith("IA_movido_"):
            o.Delete()
    ca = next(o for o in inv._items(cd.Occurrences) if o.Name.startswith("Celda_A"))
    for h in list(inv._items(ca.SubOccurrences)):
        if not h.Name.startswith(PREF):
            continue
        S(lambda h=h: setattr(h, "Visible", True))
        M = tg.CreateMatrix()
        M.TransformBy(h.Transformation)
        T = tg.CreateMatrix()
        T.SetTranslation(tg.CreateVector(0, 0, DZ / 10))
        M.TransformBy(T)
        n = cd.Occurrences.Add(h.ReferencedDocumentDescriptor.FullDocumentName, M)
        S(lambda: setattr(n, "Name", "IA_movido_" + h.Name))
        S(lambda: setattr(n, "Grounded", True))
        antes = cb(h)
        S(lambda h=h: setattr(h, "Visible", False))
        log["movidos"].append({"n": h.Name, "antes": antes, "despues": cb(n)})
    doc.Update()
    doc.Save()
except Exception as exc:  # noqa: BLE001
    log["error"] = repr(exc)
    log["traza"] = traceback.format_exc()[-2000:]
finally:
    S(lambda: setattr(app, "SilentOperation", False))
OUT.write_text(json.dumps(log, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps(log, ensure_ascii=False, indent=1))
