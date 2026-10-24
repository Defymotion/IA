"""Corrige la columna Fademaq recortada (Celdas_IA\\Rejas_v2\\Ensamblaje Columna_..._H1400.iam, archivo propio): el caño
acortado quedó apoyado arriba (el eje de la pieza va al revés); se baja hasta la chapa base. Uso: python l3n_rejas_v2_fix_cano.py
"""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
import inventor_mcp as inv  # noqa: E402

S = inv._safe
COL = Path(r"C:\DEFYMOTION\L3N\Celdas_IA\Rejas_v2\Ensamblaje Columna_[CP1512]_ADECO_H1400.iam")
app = inv._inventor(start_if_needed=False)
tg = app.TransientGeometry
log = {}
app.SilentOperation = True
try:
    doc = next((d for d in inv._items(app.Documents) if S(lambda: Path(d.FullFileName).resolve() == COL.resolve(), False)), None)
    doc = doc or app.Documents.Open(str(COL), False)
    cd = doc.ComponentDefinition
    chapa = cano = None
    for o in inv._items(cd.Occurrences):
        b = o.RangeBox
        if (b.MaxPoint.Y - b.MinPoint.Y) * 10 > 500:
            cano = o
        else:
            chapa = o
    ytop_chapa = chapa.RangeBox.MaxPoint.Y * 10
    y0 = cano.RangeBox.MinPoint.Y * 10
    dy = ytop_chapa - y0
    log["antes"] = [round(y0, 1), round(cano.RangeBox.MaxPoint.Y * 10, 1)]
    if abs(dy) > 0.2:
        for c in list(inv._items(cd.Constraints)):
            if S(lambda: c.OccurrenceOne.Name) == cano.Name or S(lambda: c.OccurrenceTwo.Name) == cano.Name:
                S(lambda: c.Delete())
        m = cano.Transformation
        t = tg.CreateMatrix()
        t.SetTranslation(tg.CreateVector(0, dy / 10, 0))
        m.TransformBy(t)
        S(lambda: setattr(cano, "Grounded", False))
        cano.Transformation = m
        S(lambda: setattr(cano, "Grounded", True))
        doc.Update()
        doc.Save()
    log["despues"] = [round(cano.RangeBox.MinPoint.Y * 10, 1), round(cano.RangeBox.MaxPoint.Y * 10, 1)]
    log["columna"] = [round(cd.RangeBox.MinPoint.Y * 10, 1), round(cd.RangeBox.MaxPoint.Y * 10, 1)]
finally:
    S(lambda: setattr(app, "SilentOperation", False))
print(json.dumps(log, ensure_ascii=False))
