"""Sondeo de la API de presentaciones (.ipn) de Inventor: qué objetos y métodos expone esta versión.
Crea una presentación temporal de la escena de paletizado (no la guarda) y lista los miembros de cada objeto
por introspección de la typelib. Salida: Documents\\InventorIA\\Analisis\\api_presentacion.json"""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
import inventor_mcp as inv  # noqa: E402

S = inv._safe
app = inv._inventor(start_if_needed=False)
ESC = Path.home() / "Documents" / "InventorIA" / "Generados" / "CELDA_KR140" / "Celda_KR140_paletizado.iam"
res = {"version": S(lambda: app.SoftwareVersion.DisplayVersion)}


def miembros(obj):
    try:
        ti = obj._oleobj_.GetTypeInfo()
        ta = ti.GetTypeAttr()
        nombres = set()
        for i in range(ta.cFuncs):
            fd = ti.GetFuncDesc(i)
            nombres.add(ti.GetNames(fd.memid)[0])
        return {"tipo": ti.GetDocumentation(-1)[0], "miembros": sorted(nombres)}
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc)}


tpl = S(lambda: app.FileManager.GetTemplateFile(12293))
res["plantilla"] = tpl
pd = app.Documents.Add(12293, tpl, True)
res["PresentationDocument"] = miembros(pd)
for nombre in ("Scenes", "ComponentDefinition"):
    o = S(lambda: getattr(pd, nombre))
    if o is not None:
        res[nombre] = miembros(o)
scenes = S(lambda: pd.Scenes)
if scenes is not None:
    sc = None
    for intento in ("ruta", "doc"):
        try:
            sc = scenes.Add(str(ESC)) if intento == "ruta" else scenes.Add(app.Documents.Open(str(ESC), False))
            res["scene_add"] = intento
            break
        except Exception as exc:  # noqa: BLE001
            res[f"scene_add_{intento}"] = str(exc)
    if sc is not None:
        res["Scene"] = miembros(sc)
        for nombre in ("Storyboards", "SnapshotViews", "Tweaks", "SceneComponents", "Camera"):
            o = S(lambda: getattr(sc, nombre))
            if o is not None:
                res[nombre] = miembros(o)
        sb = S(lambda: sc.Storyboards.Item(1))
        if sb is not None:
            res["Storyboard"] = miembros(sb)
            for nombre in ("StoryboardActions", "Actions", "Tracks"):
                o = S(lambda: getattr(sb, nombre))
                if o is not None:
                    res[nombre] = miembros(o)
        tw = S(lambda: sc.Tweaks)
        if tw is not None:
            res["n_tweaks"] = S(lambda: tw.Count)
S(lambda: pd.Close(True))
out = Path.home() / "Documents" / "InventorIA" / "Analisis" / "api_presentacion.json"
out.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps({k: (v if not isinstance(v, dict) else v.get("tipo", v.get("error"))) for k, v in res.items()},
                 ensure_ascii=False, indent=1))
