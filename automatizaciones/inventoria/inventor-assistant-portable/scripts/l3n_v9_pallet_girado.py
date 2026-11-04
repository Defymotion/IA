"""L3N v9: el pallet lleno de la celda A pasa a "1200 de frente" (1000 en X, 1200 en Z), como B y C, porque la giratoria
lo gira vacío antes de paletizar. En el v9: oculta Celda_A/IA_Pallet_TBA250 (sin tocar la celda) y agrega en el primer
nivel el mismo archivo girado 90° sobre el eje vertical que pasa por el centro del pallet.
Uso: python l3n_v9_pallet_girado.py <resultado.json> [--giro 90]
"""
import json
import math
import sys
import traceback
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
import inventor_mcp as inv  # noqa: E402

S = inv._safe
A = sys.argv
OUT = Path(A[1])
GIRO = float(A[A.index("--giro") + 1]) if "--giro" in A else 90.0
V9 = Path(r"C:\DEFYMOTION\L3N\Celdas_IA\LayoutL3N_liviano_v9.iam")
app = inv._inventor(start_if_needed=False)
tg = app.TransientGeometry
log = {"avisos": []}


def caja(o):
    b = o.RangeBox
    return [round(v * 10, 1) for v in (b.MinPoint.X, b.MinPoint.Y, b.MinPoint.Z, b.MaxPoint.X, b.MaxPoint.Y, b.MaxPoint.Z)]


app.SilentOperation = True
try:
    doc = next((d for d in inv._items(app.Documents) if S(lambda d=d: Path(d.FullFileName).resolve() == V9.resolve(), False)), None)
    doc = doc or app.Documents.Open(str(V9), True)
    cd = doc.ComponentDefinition
    for o in list(inv._items(cd.Occurrences)):
        if o.Name.startswith("IA_Pallet_TBA250_girado"):
            o.Delete()
    ca = next(o for o in inv._items(cd.Occurrences) if o.Name.startswith("Celda_A"))
    p = next(h for h in inv._items(ca.SubOccurrences) if h.Name.startswith("IA_Pallet_TBA250"))
    if not S(lambda: p.Visible, True):
        S(lambda: setattr(p, "Visible", True))
    c0 = caja(p)
    log["antes"] = c0
    cx, cz = (c0[0] + c0[3]) / 2, (c0[2] + c0[5]) / 2
    M = p.Transformation                       # proxy: ya en coordenadas del v9
    R = tg.CreateMatrix()
    R.SetToRotation(math.radians(GIRO), tg.CreateVector(0, 1, 0), tg.CreatePoint(cx / 10, 0, cz / 10))
    M2 = tg.CreateMatrix()
    M2.TransformBy(M)
    M2.TransformBy(R)
    f = p.ReferencedDocumentDescriptor.FullDocumentName
    o = cd.Occurrences.Add(f, M2)
    S(lambda: setattr(o, "Name", "IA_Pallet_TBA250_girado"))
    S(lambda: setattr(o, "Grounded", True))
    S(lambda: setattr(p, "Visible", False))
    doc.Update()
    log["despues"] = caja(o)
    log["medidas_xz"] = [round(log["despues"][3] - log["despues"][0], 1), round(log["despues"][5] - log["despues"][2], 1)]
    doc.Save()
except Exception as exc:  # noqa: BLE001
    log["error"] = repr(exc)
    log["traza"] = traceback.format_exc()[-2000:]
finally:
    S(lambda: setattr(app, "SilentOperation", False))
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(log, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps(log, ensure_ascii=False, indent=1))
