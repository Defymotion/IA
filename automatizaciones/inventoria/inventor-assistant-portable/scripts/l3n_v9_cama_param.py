"""L3N v9: reemplaza el tramo corto genérico (Cama_corta_A_L368) por la cama de rolos paramétrica de 368 (copia de la
CdR1512 hecha con cama_rolos_param.py), con la misma orientación que las mesas de la celda A (girada 180° sobre Y,
transmisión al sur), tocando la mesa del puesto. Guarda el v9 y deja las cajas en el resultado.
Uso: python l3n_v9_cama_param.py <resultado.json> [--cama <ensamble.iam>] [--tx X] [--occ nombre] [--ocultar-mesa1]
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
A = sys.argv
OUT = Path(A[1])
V9 = Path(r"C:\DEFYMOTION\L3N\Celdas_IA\LayoutL3N_liviano_v9.iam")
CAMA = Path(A[A.index("--cama") + 1]) if "--cama" in A else (
    Path.home() / "Documents" / "InventorIA" / "Generados" / "CAMA_ROLOS_PARAMETRICA" / "Cama_rolos_368x1499_celdaA"
    / "Cama_rolos_368x1499_celdaA.iam")
TX = float(A[A.index("--tx") + 1]) if "--tx" in A else -10393.7   # (-10393,7: tramo corto; -8831,916: lugar de la mesa 1)
TY, TZ = 365.7826, -34362.0234
OCC = A[A.index("--occ") + 1] if "--occ" in A else "Cama_rolos_A_368_parametrica"
OCULTAR_MESA1 = "--ocultar-mesa1" in A
MESA1 = "00.Ensamblaje Mesa de Rolos Completa_[CdR-STD]_[CdR1512]:1"
app = inv._inventor(start_if_needed=False)
tg = app.TransientGeometry
log = {"avisos": []}
app.SilentOperation = True
try:
    doc = next((d for d in inv._items(app.Documents) if S(lambda d=d: Path(d.FullFileName).resolve() == V9.resolve(), False)), None)
    doc = doc or app.Documents.Open(str(V9), True)
    cd = doc.ComponentDefinition
    for o in list(inv._items(cd.Occurrences)):
        if o.Name.startswith(("Cama_corta_A_", "Cama_rolos_A_")):
            log.setdefault("borrados", []).append(o.Name)
            o.Delete()
    if OCULTAR_MESA1:
        ca = next(o for o in inv._items(cd.Occurrences) if o.Name.startswith("Celda_A"))
        h = next((h for h in inv._items(ca.SubOccurrences) if h.Name == MESA1), None)
        if h is not None:
            S(lambda: setattr(h, "Visible", False))
            log["oculta"] = MESA1
    m = tg.CreateMatrix()
    m.SetCoordinateSystem(tg.CreatePoint(TX / 10, TY / 10, TZ / 10), tg.CreateVector(-1, 0, 0), tg.CreateVector(0, 1, 0),
                          tg.CreateVector(0, 0, -1))
    o = cd.Occurrences.Add(str(CAMA), m)
    S(lambda: setattr(o, "Name", OCC))
    S(lambda: setattr(o, "Grounded", True))
    doc.Update()
    b = o.RangeBox
    log["caja"] = [round(v * 10, 1) for v in (b.MinPoint.X, b.MinPoint.Y, b.MinPoint.Z, b.MaxPoint.X, b.MaxPoint.Y, b.MaxPoint.Z)]
    log["hijos"] = {}
    for h in inv._items(o.SubOccurrences):
        bb = S(lambda h=h: h.RangeBox)
        if bb is not None:
            log["hijos"][h.Name] = [round(v * 10, 1) for v in (bb.MinPoint.X, bb.MinPoint.Y, bb.MinPoint.Z, bb.MaxPoint.X, bb.MaxPoint.Y, bb.MaxPoint.Z)]
    doc.Save()
    log["v9"] = str(V9)
except Exception as exc:  # noqa: BLE001
    log["error"] = repr(exc)
    log["traza"] = traceback.format_exc()[-2000:]
finally:
    S(lambda: setattr(app, "SilentOperation", False))
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(log, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps({k: v for k, v in log.items() if k != "hijos"}, ensure_ascii=False, indent=1))
