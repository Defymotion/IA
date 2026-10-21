"""Prueba de calidad de imagen sobre la escena de simulación ADECO (no guarda nada).
Lista las opciones de visualización disponibles en la API y renderiza el mismo cuadro con distintas
configuraciones: actual, alta resolución, estilo realista con sombras / oclusión ambiental / perspectiva.
Salida: Generados\\ADECO_SIM\\Calidad\\*.png + calidad.json"""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
import inventor_mcp as inv  # noqa: E402

S = inv._safe
DOCS = Path.home() / "Documents" / "InventorIA"
ESC = DOCS / "Generados" / "ADECO_SIM" / "ADECO_simulacion.iam"
OUT = DOCS / "Generados" / "ADECO_SIM" / "Calidad"
OUT.mkdir(exist_ok=True)
app = inv._inventor(start_if_needed=False)
res = {}


def miembros(obj):
    try:
        ti = obj._oleobj_.GetTypeInfo()
        ta = ti.GetTypeAttr()
        return sorted({ti.GetNames(ti.GetFuncDesc(i).memid)[0] for i in range(ta.cFuncs)})
    except Exception as exc:  # noqa: BLE001
        return str(exc)


doc = next((d for d in inv._items(app.Documents)
            if S(lambda: Path(d.FullFileName).resolve() == ESC.resolve(), False)), None) or app.Documents.Open(str(ESC), True)
doc.Activate()
v = app.ActiveView
res["View"] = miembros(v)
for nombre, obj in (("Camera", S(lambda: v.Camera)), ("DisplayOptions", S(lambda: app.DisplayOptions)),
                    ("DocDisplaySettings", S(lambda: doc.DisplaySettings)),
                    ("LightingStyle", S(lambda: doc.ActiveLightingStyle))):
    if obj is not None:
        res[nombre] = miembros(obj)
res["estilos_visuales"] = [S(lambda: s.Name) for s in inv._items(S(lambda: doc.VisualStyles) or
                                                              app.TransientObjects.CreateObjectCollection())]
res["estilos_iluminacion"] = [S(lambda: s.Name) for s in inv._items(S(lambda: doc.LightingStyles) or
                                                                 app.TransientObjects.CreateObjectCollection())]
res["actual"] = {k: str(S(lambda: getattr(v, k))) for k in ("DisplayMode", "VisualStyle", "ShowShadows")}


def foto(nombre, w, h):
    v.Update()
    v.SaveAsBitmap(str(OUT / nombre), w, h)


foto("A_actual_1280.png", 1280, 720)
foto("B_alta_2560.png", 2560, 1440)
cambios = {}
ds = S(lambda: doc.DisplaySettings)
do = S(lambda: app.DisplayOptions)
for obj, props in ((v, {"DisplayMode": [8710, 8711, 8712]}),
                   (ds, {"GroundShadows": [True], "ObjectShadows": [True], "AmbientShadows": [True],
                         "GroundReflections": [False], "ShowGroundPlane": [False], "Perspective": [True]}),
                   (do, {"AmbientShadows": [True], "ObjectShadows": [True], "GroundShadows": [True],
                         "AntiAliasing": [True], "AntiAliasingMode": [2, 1]})):
    if obj is None:
        continue
    for k, vals in props.items():
        for val in vals:
            try:
                setattr(obj, k, val)
                cambios[k] = str(val)
                break
            except Exception as exc:  # noqa: BLE001
                cambios[k] = f"no: {exc}"[:80]
cam = v.Camera
S(lambda: setattr(cam, "Perspective", True))
S(lambda: cam.Apply())
res["cambios"] = cambios
foto("C_realista_2560.png", 2560, 1440)
res["despues"] = {k: str(S(lambda: getattr(v, k))) for k in ("DisplayMode", "VisualStyle")}
(OUT / "calidad.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps({"cambios": cambios, "despues": res["despues"], "estilos": res["estilos_visuales"][:20]},
                 ensure_ascii=False))
