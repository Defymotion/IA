"""Estira o acorta una COPIA de una pieza (también sólidos importados, sin parámetros): los cuerpos enteros más allá de
un plano de corte se trasladan y en los que lo cruzan se mueven sólo las caras que quedan del todo más allá
(MoveFeature + MoveFace, el mismo método de l3n_camas_medida.py). delta < 0 acorta.
Uso como módulo: estirar(app, origen, destino, eje(0|1|2), corte_mm, delta_mm) -> dict con la caja nueva y avisos.
"""
import shutil
from pathlib import Path

import inventor_mcp as inv

S = inv._safe


def _its(x):
    if x is None or isinstance(x, list):
        return x or []
    try:
        return inv._items(x)
    except Exception:  # noqa: BLE001
        return []


def _coord(p, eje):
    return (p.X, p.Y, p.Z)[eje]


def estirar(app, origen, destino, eje, corte_mm, delta_mm, lado=1):
    """lado=1: se mueven las caras más allá del corte (+eje) un delta; lado=-1: las de antes del corte, -delta."""
    tg, to = app.TransientGeometry, app.TransientObjects
    destino = Path(destino)
    if str(origen) != str(destino):
        shutil.copyfile(origen, destino)
    doc = app.Documents.Open(str(destino), False)
    cd = doc.ComponentDefinition
    c = corte_mm / 10
    d = delta_mm / 10
    info = {"enteros": 0, "parciales": 0, "caras_movidas": 0, "avisos": []}
    enteros = to.CreateObjectCollection()
    parciales = []
    for body in _its(cd.SurfaceBodies):
        b = body.RangeBox
        lo, hi = _coord(b.MinPoint, eje), _coord(b.MaxPoint, eje)
        if (lo > c) if lado > 0 else (hi < c):
            enteros.Add(body)
        elif lo < c < hi:
            parciales.append(body)
    info["enteros"], info["parciales"] = enteros.Count, len(parciales)
    vec = [0.0, 0.0, 0.0]
    vec[eje] = d if lado > 0 else -d
    if enteros.Count:
        md = cd.Features.MoveFeatures.CreateMoveDefinition(enteros)
        md.AddFreeDrag(*vec)
        cd.Features.MoveFeatures.Add(md)
        doc.Update()
    for body in parciales:
        fc = to.CreateFaceCollection()
        for f in _its(body.Faces):
            vs = _its(S(lambda: f.Vertices, None))
            if vs:
                if all((_coord(v.Point, eje) - c) * lado > 0.001 for v in vs):
                    fc.Add(f)
            else:                                   # caras sin vértices (agujeros): por su caja
                fb = S(lambda: f.Evaluator.RangeBox, None)
                if fb is not None and ((_coord(fb.MinPoint, eje) > c + 0.001) if lado > 0 else (_coord(fb.MaxPoint, eje) < c - 0.001)):
                    fc.Add(f)
        if fc.Count == 0:
            continue
        hi0 = _coord(body.RangeBox.MaxPoint if lado > 0 else body.RangeBox.MinPoint, eje)
        hecho = False
        for intento in range(2):
            try:
                mf = cd.Features.MoveFaceFeatures
                df = mf.CreateDefinition(fc)
                mt = tg.CreateMatrix()
                mt.SetTranslation(tg.CreateVector(*vec))
                df.SetFreeMoveType(mt)
                feat = mf.Add(df)
                doc.Update()
                if abs(_coord(body.RangeBox.MaxPoint if lado > 0 else body.RangeBox.MinPoint, eje) - (hi0 + vec[eje])) < 0.05:
                    hecho = True
                    info["caras_movidas"] += fc.Count
                    break
                feat.Delete()
                doc.Update()
            except Exception as e:  # noqa: BLE001
                info["avisos"].append(f"MoveFace: {e!r}"[:160])
                break
        if not hecho:
            info["avisos"].append(f"no pude mover las caras de {S(lambda: body.Name)}")
    doc.Update()
    b = cd.RangeBox
    info["caja"] = [round(v * 10, 1) for v in (b.MinPoint.X, b.MinPoint.Y, b.MinPoint.Z, b.MaxPoint.X, b.MaxPoint.Y, b.MaxPoint.Z)]
    doc.Save()
    doc.Close(True)
    return info
