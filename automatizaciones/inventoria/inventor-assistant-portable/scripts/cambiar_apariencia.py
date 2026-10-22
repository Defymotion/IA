"""Cambia la apariencia activa de piezas (.ipt): elige la primera cuyo nombre EMPIEZA con el texto dado (ej. "naranja").
Uso: python cambiar_apariencia.py "<texto>" pieza1.ipt pieza2.ipt ...
"""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
import inventor_mcp as inv  # noqa: E402

S = inv._safe
app = inv._inventor(start_if_needed=False)
app.SilentOperation = True
txt = sys.argv[1].lower()
res = {"candidatas": [], "cambiadas": []}
try:
    ap = None
    for lib in inv._items(app.AssetLibraries):
        for a in inv._items(S(lambda: lib.AppearanceAssets, []) or []):
            nm = (S(lambda: a.DisplayName, "") or "")
            if nm.lower().startswith(txt):
                res["candidatas"].append(nm)
                ap = ap or a
    for r in sys.argv[2:]:
        p = Path(r)
        d = next((d for d in inv._items(app.Documents) if S(lambda: Path(d.FullFileName).resolve() == p.resolve(), False)), None)
        d = d or app.Documents.Open(str(p), False)
        if ap is not None:
            d.ActiveAppearance = ap.CopyTo(d)
            d.Save()
            res["cambiadas"].append(p.name)
finally:
    S(lambda: setattr(app, "SilentOperation", False))
print(json.dumps(res, ensure_ascii=False, indent=1))
