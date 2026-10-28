"""Sólo lectura: compara una pieza original (sólido importado) con su reconstrucción paramétrica.
Calcula original−nueva (falta material) y nueva−original (sobra material) con TransientBRep y lista cada trozo
con su volumen y su caja (mm). Uso: python comparar_reconstruccion.py <original.ipt> <nueva.ipt> [<salida.json>]"""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
import inventor_mcp as inv  # noqa: E402

S = inv._safe
app = inv._inventor(start_if_needed=False)
tb = app.TransientBRep
app.SilentOperation = True
res = {}
docs = []
try:
    a = app.Documents.Open(sys.argv[1], False)
    docs.append(a)
    b = app.Documents.Open(sys.argv[2], False)
    docs.append(b)
    A = a.ComponentDefinition.SurfaceBodies.Item(1)
    B = b.ComponentDefinition.SurfaceBodies.Item(1)
    for nombre, x, y in (("falta", A, B), ("sobra", B, A)):
        for tipo in (27395, 27393, 27394):
            try:
                X = tb.Copy(x)
                Y = tb.Copy(y)
                tb.DoBoolean(X, Y, tipo)
                break
            except Exception as ex:  # noqa: BLE001
                res.setdefault("probados", []).append([tipo, repr(ex)[-160:]])
                X = None
        if X is None:
            continue
        res[nombre + "_tipo"] = tipo
        trozos = []
        for L in inv._items(S(lambda: X.Lumps, []) or []):
            bx = S(lambda: L.RangeBox, None)
            vol = S(lambda: L.Volume(0.001), None)
            trozos.append({"vol_cm3": round(vol, 4) if vol is not None else None,
                           "caja_mm": [round(bx.MinPoint.X * 10, 1), round(bx.MinPoint.Y * 10, 1), round(bx.MinPoint.Z * 10, 1),
                                       round(bx.MaxPoint.X * 10, 1), round(bx.MaxPoint.Y * 10, 1), round(bx.MaxPoint.Z * 10, 1)]
                           if bx is not None else None})
        trozos.sort(key=lambda t: -(t["vol_cm3"] or 0))
        res[nombre] = {"vol_total": round(S(lambda: X.Volume(0.001), 0) or 0, 4), "n": len(trozos), "trozos": trozos[:40]}
    bx = A.RangeBox
    res["caja_orig_mm"] = [round(bx.MinPoint.X * 10, 1), round(bx.MinPoint.Y * 10, 1), round(bx.MinPoint.Z * 10, 1),
                           round(bx.MaxPoint.X * 10, 1), round(bx.MaxPoint.Y * 10, 1), round(bx.MaxPoint.Z * 10, 1)]
finally:
    for d in docs:
        S(lambda d=d: d.Close(True))
    app.SilentOperation = False
txt = json.dumps(res, ensure_ascii=False, indent=1)
if len(sys.argv) > 3:
    Path(sys.argv[3]).write_text(txt, encoding="utf-8")
print(txt[:12000])
