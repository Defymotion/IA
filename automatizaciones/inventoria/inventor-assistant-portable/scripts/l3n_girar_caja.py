"""Celda A: gira 90° (eje vertical) la caja de muestra sobre la cinta interna, para que quede como la deja el
pateador: lado de 386 cruzado a la cinta (a lo largo de Z) y lado de 156 en el sentido de avance (X), igual que
las 7 garras del gripper (paso 156 a lo largo de X). Edita Celda_A_L3N.iam (archivo propio).
Uso: python l3n_girar_caja.py
"""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
import inventor_mcp as inv  # noqa: E402

S = inv._safe
CELDA = Path(r"C:\DEFYMOTION\L3N\Celdas_IA\Celda_A_L3N.iam")
app = inv._inventor(start_if_needed=False)
app.SilentOperation = True
tg = app.TransientGeometry
res = {}
try:
    doc = next((d for d in inv._items(app.Documents) if S(lambda: Path(d.FullFileName).resolve() == CELDA.resolve(), False)), None)
    doc = doc or app.Documents.Open(str(CELDA), False)
    o = next(x for x in inv._items(doc.ComponentDefinition.Occurrences) if x.Name.startswith("IA_Caja_en_cinta"))

    def caja():
        b = o.RangeBox
        return [round(v * 10, 1) for v in (b.MinPoint.X, b.MinPoint.Y, b.MinPoint.Z, b.MaxPoint.X, b.MaxPoint.Y, b.MaxPoint.Z)]

    antes = caja()
    res["antes"] = antes
    if antes[3] - antes[0] > antes[5] - antes[2]:          # 386 a lo largo de X: girar
        c = tg.CreatePoint((antes[0] + antes[3]) / 20, 0, (antes[2] + antes[5]) / 20)
        rot = tg.CreateMatrix()
        rot.SetToRotation(1.5707963267948966, tg.CreateVector(0, 1, 0), c)
        m = o.Transformation
        m.TransformBy(rot)
        S(lambda: setattr(o, "Grounded", False))
        o.SetTransformWithoutConstraints(m)
        S(lambda: setattr(o, "Grounded", True))
        doc.Update()
        doc.Save()
        res["girada"] = True
    else:
        res["girada"] = False
    res["despues"] = caja()
finally:
    S(lambda: setattr(app, "SilentOperation", False))
print(json.dumps(res, ensure_ascii=False, indent=1))
