"""Cierra Inventor (sólo si no hay documentos sin guardar; con --forzar cierra igual SIN guardar) y lo vuelve a abrir
visible, activando el proyecto indicado y abriendo un documento. Sirve para limpiar documentos cargados en memoria
con nombres repetidos. Uso: python reiniciar_inventor.py <proyecto.ipj> <documento> [--forzar]
"""
import json
import subprocess
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
import inventor_mcp as inv  # noqa: E402

S = inv._safe
ipj, ruta = Path(sys.argv[1]), Path(sys.argv[2])
res = {"sin_guardar": [], "cerrado": False}
app = S(lambda: inv._inventor(start_if_needed=False))
if app is not None:
    for d in inv._items(app.Documents):
        if S(lambda: d.Dirty, False):
            res["sin_guardar"].append(str(S(lambda: d.DisplayName, "")))
    if res["sin_guardar"] and "--forzar" not in sys.argv:
        print(json.dumps(res, ensure_ascii=False, indent=1))
        sys.exit("Hay documentos sin guardar: no cierro Inventor (usá --forzar para cerrar sin guardar)")
    S(lambda: setattr(app, "SilentOperation", True))
    S(lambda: app.Documents.CloseAll())
    S(lambda: app.Quit())
    res["cerrado"] = True
    app = None
    for _ in range(60):
        time.sleep(2)
        if inv._get_running() is None:
            break
    else:
        subprocess.run(["taskkill", "/IM", "Inventor.exe", "/F"], capture_output=True)
        time.sleep(5)
    res["cerrado_s"] = True
exe = inv._inventor_exe()
subprocess.Popen([str(exe)], close_fds=True)       # sin /Automation: visible y normal para el usuario
app = None
for _ in range(120):
    time.sleep(3)
    app = inv._get_running()
    if app is not None and S(lambda: app.Ready, False):
        break
if app is None:
    sys.exit("Inventor no volvió a aparecer")
S(lambda: setattr(app, "Visible", True))
dpm = app.DesignProjectManager
if Path(str(S(lambda: dpm.ActiveDesignProject.FullFileName, ""))).resolve() != ipj.resolve():
    proj = next((p for p in inv._items(dpm.DesignProjects) if S(lambda: Path(p.FullFileName).resolve() == ipj.resolve(), False)), None)
    proj = proj or dpm.DesignProjects.AddExisting(str(ipj))
    proj.Activate(True)
doc = app.Documents.Open(str(ruta), True)
doc.Activate()
res.update({"proyecto": S(lambda: dpm.ActiveDesignProject.FullFileName), "abierto": str(doc.FullFileName),
            "documentos": app.Documents.Count})
print(json.dumps(res, ensure_ascii=False, indent=1))
