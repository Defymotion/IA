"""Sólo lectura: releva las piezas (.ipt) de una carpeta importada desde JT/STEP: tipo de cuerpo (sólido B-rep,
superficie o malla), caras, caja (mm), volumen, área, material e iProperties. Sin duplicados (_1, _2...).
Abre cada pieza invisible y la cierra (sólo las que abrió). No guarda nada.
Uso: python relevar_jt_piezas.py <carpeta> <salida.json> [--max N]
"""
import json
import re
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
import inventor_mcp as inv  # noqa: E402

S = inv._safe
carpeta, salida = Path(sys.argv[1]), Path(sys.argv[2])
MAX = int(sys.argv[sys.argv.index("--max") + 1]) if "--max" in sys.argv else 10 ** 6
app = inv._inventor(start_if_needed=False)
abiertos = {S(lambda d=d: str(Path(d.FullFileName).resolve()).lower(), "") for d in inv._items(app.Documents)}
base = {}
for f in sorted(carpeta.glob("*.ipt")):
    k = re.sub(r"_\d+$", "", f.stem)
    base.setdefault(k, []).append(f)
res = {"carpeta": str(carpeta), "unicas": len(base), "piezas": []}
app.SilentOperation = True
T0 = time.time()
try:
    for i, (k, fs) in enumerate(sorted(base.items())):
        if i >= MAX:
            break
        f = fs[0]
        e = {"nombre": k, "archivo": f.name, "copias": len(fs), "kb": round(f.stat().st_size / 1024)}
        ya = str(f.resolve()).lower() in abiertos
        d = None
        try:
            d = app.Documents.Open(str(f), False)
            cd = d.ComponentDefinition
            cuerpos = []
            for b in inv._items(cd.SurfaceBodies):
                cuerpos.append({"solido": bool(S(lambda: b.IsSolid, False)),
                                "caras": S(lambda: b.Faces.Count, 0)})
            e["cuerpos"] = cuerpos
            e["mallas"] = S(lambda: sum(ms.Count for ms in inv._items(cd.MeshFeatureSets)), None)
            e["features"] = S(lambda: cd.Features.Count, None)
            e["chapa"] = S(lambda: d.SubType == "{9C464203-9BAE-11D3-8BAD-0060B0CE6BB4}", False)
            b = cd.RangeBox
            e["caja"] = [round((b.MaxPoint.X - b.MinPoint.X) * 10, 1), round((b.MaxPoint.Y - b.MinPoint.Y) * 10, 1),
                         round((b.MaxPoint.Z - b.MinPoint.Z) * 10, 1)]
            mp = S(lambda: cd.MassProperties, None)
            if mp is not None:
                e["vol_cm3"] = S(lambda: round(mp.Volume, 2), None)
                e["area_cm2"] = S(lambda: round(mp.Area, 1), None)
            e["material"] = S(lambda: cd.Material.Name, None)
            ps = d.PropertySets
            e["pn"] = S(lambda: ps.Item("Design Tracking Properties").Item("Part Number").Value, None)
            e["desc"] = S(lambda: ps.Item("Design Tracking Properties").Item("Description").Value, None)
        except Exception as ex:  # noqa: BLE001
            e["error"] = repr(ex)[:200]
        finally:
            if d is not None and not ya:
                S(lambda: d.Close(True))
        res["piezas"].append(e)
        if i % 20 == 0:
            print(f"[{time.time() - T0:6.0f} s] {i} {k}", flush=True)
finally:
    app.SilentOperation = False
res["segundos"] = round(time.time() - T0, 1)
salida.parent.mkdir(parents=True, exist_ok=True)
salida.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps({k: v for k, v in res.items() if k != "piezas"}, ensure_ascii=False))
print(json.dumps(res["piezas"][:8], ensure_ascii=False))
