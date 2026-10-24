"""Celda A (archivo propio): con el pateador corrido 120 mm, su chapa de cubierta "chapa nueva 2" toca el lateral de T3
(27,5 mm). El ensamble del pateador es de ADECO (no se toca): en Celda_A_L3N se oculta esa chapa y se pone una copia
recortada 32 mm del lado de T3 en el mismo lugar (Celdas_IA\\Ajustes_sim). Uso: python l3n_pateador_A_cubierta.py
"""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import inventor_mcp as inv  # noqa: E402
from estirar_pieza import estirar  # noqa: E402

S = inv._safe
CEL = Path(r"C:\DEFYMOTION\L3N\Celdas_IA\Celda_A_L3N.iam")
PZ = Path(r"C:\DEFYMOTION\L3N\Celdas_IA\Ajustes_sim")
RECORTE = 32.0
app = inv._inventor(start_if_needed=False)
tg = app.TransientGeometry
log = {"avisos": []}
app.SilentOperation = True
try:
    cel = next((d for d in inv._items(app.Documents) if S(lambda: Path(d.FullFileName).resolve() == CEL.resolve(), False)), None)
    cel = cel or app.Documents.Open(str(CEL), False)
    cd = cel.ComponentDefinition
    occ = {o.Name: o for o in inv._items(cd.Occurrences)}
    if "IA_Pateador_A_chapa_nueva_2_recortada" in occ:
        log["avisos"].append("ya estaba hecho")
    else:
        pat = occ["Ensamble pateador adeco:1"]
        ch = next(h for h in inv._items(pat.SubOccurrences) if h.Name.startswith("chapa nueva 2"))
        f = Path(ch.Definition.Document.FullFileName)
        M = ch.Transformation                         # en coordenadas de Celda_A
        b = ch.Definition.RangeBox                    # caja local de la pieza
        # eje local que en la celda va a lo largo de X, y de qué lado queda +X
        mejor = None
        for eje in range(3):
            v = [0.0, 0.0, 0.0]
            v[eje] = 1.0
            vv = tg.CreateVector(*v)
            vv.TransformBy(M)
            if mejor is None or abs(vv.X) > abs(mejor[1]):
                mejor = (eje, vv.X)
        eje, sx = mejor
        lo = (b.MinPoint.X, b.MinPoint.Y, b.MinPoint.Z)[eje] * 10
        hi = (b.MaxPoint.X, b.MaxPoint.Y, b.MaxPoint.Z)[eje] * 10
        dst = PZ / f"{f.stem}_recortada_{int(RECORTE)}.ipt"
        if not dst.exists():
            pass
        if sx > 0:                                    # el lado de T3 (+X de la celda) es el +eje de la pieza
            info = estirar(app, str(f), dst, eje, hi - 60.0, -RECORTE, lado=1)
        else:
            info = estirar(app, str(f), dst, eje, lo + 60.0, -RECORTE, lado=-1)
        log["estirar"] = info
        S(lambda: setattr(ch, "Visible", False))
        ex = [M.Cell(1, 1), M.Cell(2, 1), M.Cell(3, 1)]
        ey = [M.Cell(1, 2), M.Cell(2, 2), M.Cell(3, 2)]
        n_ = sum(v * v for v in ex) ** 0.5
        ex = [v / n_ for v in ex]
        d_ = sum(a * b for a, b in zip(ex, ey))
        ey = [b - d_ * a for a, b in zip(ex, ey)]
        n_ = sum(v * v for v in ey) ** 0.5
        ey = [v / n_ for v in ey]
        ez = [ex[1] * ey[2] - ex[2] * ey[1], ex[2] * ey[0] - ex[0] * ey[2], ex[0] * ey[1] - ex[1] * ey[0]]
        m2 = tg.CreateMatrix()
        m2.SetCoordinateSystem(tg.CreatePoint(M.Cell(1, 4), M.Cell(2, 4), M.Cell(3, 4)), tg.CreateVector(*ex),
                               tg.CreateVector(*ey), tg.CreateVector(*ez))
        log["ortonormal"] = [round(v, 6) for v in ex + ey + ez]
        try:
            o = cd.Occurrences.Add(str(dst), m2)
        except Exception as e:  # noqa: BLE001
            log["avisos"].append(f"Add con matriz: {e!r}"[:200])
            o = cd.Occurrences.Add(str(dst), tg.CreateMatrix())
            o.Transformation = m2
        S(lambda: setattr(o, "Name", "IA_Pateador_A_chapa_nueva_2_recortada"))
        S(lambda: setattr(o, "Grounded", True))
        cel.Update()
        cel.Save()
        c0, c1 = ch.RangeBox, o.RangeBox
        log["x_max_antes_despues"] = [round(c0.MaxPoint.X * 10, 1), round(c1.MaxPoint.X * 10, 1)]
        log["eje_local"] = eje
finally:
    S(lambda: setattr(app, "SilentOperation", False))
print(json.dumps(log, ensure_ascii=False, indent=1))
