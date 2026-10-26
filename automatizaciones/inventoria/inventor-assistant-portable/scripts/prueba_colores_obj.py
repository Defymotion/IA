"""Sólo lectura: traductores disponibles, apariencias por cuerpo/cara de algunas piezas y prueba de exportar a OBJ
(¿trae los colores por cara en el .mtl?). Uso: python prueba_colores_obj.py <carpeta_salida> <pieza1.ipt> [...]
"""
import json
import sys
from collections import Counter
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
import inventor_mcp as inv  # noqa: E402

S = inv._safe
OUT = Path(sys.argv[1])
OUT.mkdir(parents=True, exist_ok=True)
app = inv._inventor(start_if_needed=False)
res = {"traductores": [], "piezas": {}}
for a in inv._items(app.ApplicationAddIns):
    n = S(lambda: a.DisplayName, "")
    if any(k in n.upper() for k in ("OBJ", "STL", "FBX", "USD", "GLTF", "3MF", "JT")):
        res["traductores"].append([n, S(lambda: a.ClassIdString, "")])
obj_tr = next((a for a in inv._items(app.ApplicationAddIns) if "OBJ" in S(lambda: a.DisplayName, "").upper()
               and "IMPORT" not in S(lambda: a.DisplayName, "").upper()), None)
app.SilentOperation = True
try:
    for p in sys.argv[2:]:
        p = Path(p)
        doc = next((d for d in inv._items(app.Documents) if S(lambda: Path(d.FullFileName).resolve() == p.resolve(), False)), None)
        doc = doc or app.Documents.Open(str(p), False)
        cd = doc.ComponentDefinition
        info = {"doc_apariencia": S(lambda: doc.ActiveAppearance.DisplayName), "cuerpos": []}
        for b in inv._items(cd.SurfaceBodies):
            caras = Counter()
            for f in inv._items(b.Faces):
                caras[S(lambda: f.Appearance.DisplayName, "?")] += 1
            info["cuerpos"].append({"apariencia": S(lambda: b.Appearance.DisplayName), "fuente": S(lambda: b.AppearanceSourceType),
                                    "caras": dict(caras.most_common(6)), "n_caras": sum(caras.values())})
        if obj_tr is not None:
            try:
                ctx = app.TransientObjects.CreateTranslationContext()
                ctx.Type = 13059
                opts = app.TransientObjects.CreateNameValueMap()
                tiene = obj_tr.HasSaveCopyAsOptions(doc, ctx, opts)
                info["opciones_obj"] = {S(lambda: opts.Name(i + 1)): str(S(lambda: opts.Value(opts.Name(i + 1)))) for i in range(S(lambda: opts.Count, 0))} if tiene else None
                dm = app.TransientObjects.CreateDataMedium()
                dst = OUT / (p.stem + ".obj")
                dm.FileName = str(dst)
                obj_tr.SaveCopyAs(doc, ctx, opts, dm)
                info["obj"] = [str(x.name) + f" {x.stat().st_size}" for x in OUT.glob(p.stem + "*")]
                mtl = next(OUT.glob(p.stem + "*.mtl"), None)
                if mtl:
                    info["mtl"] = mtl.read_text(encoding="utf-8", errors="replace")[:1500]
            except Exception as e:  # noqa: BLE001
                info["obj_error"] = repr(e)[:300]
        res["piezas"][p.name] = info
finally:
    S(lambda: setattr(app, "SilentOperation", False))
print(json.dumps(res, ensure_ascii=False, indent=1))
