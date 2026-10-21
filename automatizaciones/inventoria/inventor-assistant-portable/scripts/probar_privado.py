"""Prueba del Inventor privado: a qué Inventor se conecta, si está oculto y si puede sacar imágenes sin ventana
(vista activa y cámara transitoria). Sólo lectura: no guarda nada.
Uso: python probar_privado.py "<ensamble.iam>"
"""
import json
import os
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
import inventor_mcp as inv  # noqa: E402

S = inv._safe
res = {"INVENTORIA_INSTANCIA": os.environ.get("INVENTORIA_INSTANCIA")}
app = inv._inventor(start_if_needed=False)
res["privado"] = inv.es_privado(app)
res["visible"] = S(lambda: app.Visible)
res["hwnd"] = S(lambda: int(app.MainFrameHWND))
res["documentos_abiertos"] = S(lambda: app.Documents.Count)
usuario = S(lambda: inv.Dispatch(inv.pythoncom.GetActiveObject(inv.PROGID).QueryInterface(
    inv.pythoncom.IID_IDispatch)))
res["hwnd_usuario"] = S(lambda: int(usuario.MainFrameHWND)) if usuario else None
app.SilentOperation = True
ruta = sys.argv[1]
out = Path(ruta).with_name("prueba_privado")
t0 = time.time()
doc = app.Documents.Open(ruta, True)
res["abrir_s"] = round(time.time() - t0, 1)
# 1) vista activa
try:
    doc.Activate()
    v = app.ActiveView
    v.Camera.ViewOrientationType = 10759
    v.Camera.Fit()
    v.Camera.Apply()
    t0 = time.time()
    v.SaveAsBitmap(str(out) + "_vista.png", 1600, 1000)
    res["vista_png"] = {"ok": Path(str(out) + "_vista.png").exists(), "s": round(time.time() - t0, 1)}
except Exception as exc:  # noqa: BLE001
    res["vista_png"] = {"ok": False, "error": repr(exc)}
# 2) cámara transitoria (no necesita ventana)
try:
    cam = app.TransientObjects.CreateCamera()
    cam.SceneObject = doc.ComponentDefinition
    cam.ViewOrientationType = 10759
    cam.Fit()
    cam.ApplyWithoutTransition()
    t0 = time.time()
    cam.SaveAsBitmap(str(out) + "_camara.png", 1600, 1000)
    res["camara_png"] = {"ok": Path(str(out) + "_camara.png").exists(), "s": round(time.time() - t0, 1)}
except Exception as exc:  # noqa: BLE001
    res["camara_png"] = {"ok": False, "error": repr(exc)}
res["visible_al_final"] = S(lambda: app.Visible)
print(json.dumps(res, ensure_ascii=False, indent=1))
