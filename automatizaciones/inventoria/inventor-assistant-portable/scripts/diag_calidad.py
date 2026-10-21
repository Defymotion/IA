"""Diagnóstico (sólo lectura): opciones de calidad de imagen de Inventor y si hay Pillow en el .venv
(--instalar: lo instala con pip)."""
import json
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
import inventor_mcp as inv  # noqa: E402

S = inv._safe
res = {}
try:
    import PIL  # noqa: F401
    res["pillow"] = PIL.__version__
except ImportError:
    res["pillow"] = None
    if "--instalar" in sys.argv:
        p = subprocess.run([sys.executable, "-m", "pip", "install", "pillow"], capture_output=True, text=True)
        res["pip"] = (p.stdout[-1500:], p.stderr[-1500:])
app = inv._inventor(start_if_needed=False)


def miembros(obj):
    try:
        ti = obj._oleobj_.GetTypeInfo()
        ta = ti.GetTypeAttr()
        return sorted({ti.GetNames(ti.GetFuncDesc(i).memid)[0] for i in range(ta.cFuncs)})
    except Exception as exc:  # noqa: BLE001
        return repr(exc)


def valores(obj, nombres):
    out = {}
    for n in nombres:
        v = S(lambda: getattr(obj, n), "?")
        if isinstance(v, (int, float, str, bool)) or v is None:
            out[n] = v
    return out


do = S(lambda: app.DisplayOptions)
m = miembros(do)
res["DisplayOptions"] = valores(do, m) if isinstance(m, list) else m
vw = S(lambda: app.ActiveView)
if vw is not None:
    mv = miembros(vw)
    res["View_miembros"] = mv
    res["View_valores"] = valores(vw, [n for n in mv if not n.startswith("Save")]) if isinstance(mv, list) else None
doc = S(lambda: app.ActiveDocument)
if doc is not None:
    md = miembros(doc)
    res["Doc_miembros_visual"] = [n for n in md if any(k in n.lower() for k in
                                                         ("light", "style", "visual", "display", "render", "scene"))]
    res["LightingStyles"] = [S(lambda i=i: doc.LightingStyles.Item(i).Name) for i in
                             range(1, S(lambda: doc.LightingStyles.Count, 0) + 1)]
    res["VisualStyles?"] = S(lambda: [doc.VisualStyles.Item(i).Name for i in range(1, doc.VisualStyles.Count + 1)])
print(json.dumps(res, ensure_ascii=False, indent=1, default=str))
