"""Copia las apariencias (colores) de un ensamble de referencia a las piezas de un gripper generado, por rol:
frame <- "plegado estructura", brida <- "brida", pala fija/móvil <- "pala", empuja pala, soporte, placa de empuje.
Sólo lectura sobre la referencia; guarda las piezas del gripper (carpeta propia).
Uso: python pintar_como.py <referencia.iam> <carpeta_chapas_gripper> [ensamble_gripper.iam]
"""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
import inventor_mcp as inv  # noqa: E402

S = inv._safe
ref, carpeta = Path(sys.argv[1]), Path(sys.argv[2])
ens = Path(sys.argv[3]) if len(sys.argv) > 3 else None
ROLES = {  # pieza generada (prefijo, minúsculas) -> prefijos del archivo de referencia (en orden de preferencia)
    "goma pala fija": ["goma pala fija"], "goma pala movil": ["goma pala movil"],
    "frame": ["frame_principal", "plegado estructura"], "brida": ["brida nueva", "brida"],
    "pala fija": ["pala fija"], "pala movil": ["pala movil"], "empuja pala": ["empuja pala"],
    "soporte": ["soporte piston"], "placa empuje": ["part_empuje"],
}
app = inv._inventor(start_if_needed=False)
app.SilentOperation = True
res = {"referencia": {}, "pintadas": {}, "sin_match": []}
try:
    rdoc = next((d for d in inv._items(app.Documents) if S(lambda: Path(d.FullFileName).resolve() == ref.resolve(), False)), None)
    rdoc = rdoc or app.Documents.Open(str(ref), False)
    aps = {}
    for d in inv._items(rdoc.AllReferencedDocuments):
        if d.DocumentType != inv.K_PART_DOCUMENT:
            continue
        nm = Path(str(d.FullFileName)).name.lower()
        ap = S(lambda: d.ActiveAppearance)
        if ap is not None:
            aps[nm] = ap
            res["referencia"][nm] = S(lambda: ap.DisplayName)
    for ipt in sorted(carpeta.glob("*.ipt")):
        low = ipt.name.lower()
        rol = next((r for r in ROLES if low.startswith(r)), None)
        if rol is None:
            res["sin_match"].append(ipt.name)
            continue
        src = next((aps[n] for k in ROLES[rol] for n in aps if n.startswith(k)), None)
        if src is None:
            res["sin_match"].append(ipt.name)
            continue
        d = next((d for d in inv._items(app.Documents) if S(lambda: Path(d.FullFileName).resolve() == ipt.resolve(), False)), None)
        d = d or app.Documents.Open(str(ipt), False)
        nombre = S(lambda: src.DisplayName, "")
        destino = next((a for a in inv._items(S(lambda: d.AppearanceAssets, []) or []) if S(lambda: a.DisplayName) == nombre), None)
        if destino is None:
            destino = S(lambda: src.CopyTo(d))
        if destino is None:   # buscar la misma apariencia en las bibliotecas
            for lib in inv._items(app.AssetLibraries):
                a = next((a for a in inv._items(S(lambda: lib.AppearanceAssets, []) or []) if S(lambda: a.DisplayName) == nombre), None)
                if a is not None:
                    destino = S(lambda: a.CopyTo(d))
                    break
        if destino is None:
            res["sin_match"].append(f"{ipt.name}: no pude copiar '{nombre}'")
            continue
        d.ActiveAppearance = destino
        d.Save()
        res["pintadas"][ipt.name] = S(lambda: src.DisplayName)
    if ens is not None:
        e = next((d for d in inv._items(app.Documents) if S(lambda: Path(d.FullFileName).resolve() == ens.resolve(), False)), None)
        e = e or app.Documents.Open(str(ens), True)
        e.Update()
        e.Save()
        e.Activate()
        v = app.ActiveView
        cam = v.Camera
        cam.ViewOrientationType = 10759
        cam.Fit()
        cam.Apply()
        p = ens.with_name(ens.stem + "_iso_pintado.png")
        v.SaveAsBitmap(str(p), 1600, 1000)
        res["imagen"] = str(p)
finally:
    S(lambda: setattr(app, "SilentOperation", False))
print(json.dumps(res, ensure_ascii=False, indent=1))
