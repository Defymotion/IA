"""Vigilante: ejecuta pedidos que Claude deja en Documents\\InventorIA\\_pedidos.

Arrancarlo una vez (doble clic en scripts\\vigilante.bat) y dejar la ventana abierta.
Cada pedido es un archivo <id>.json con {"script": "planos_gripper.py", "args": [...]}.
Solo se ejecutan archivos .py de la carpeta scripts\\ de este complemento.
El resultado queda en <id>.resultado.json (salida, errores y código de salida).
Para detenerlo: cerrar la ventana o Ctrl+C.

INVENTOR PRIVADO (para que el usuario pueda seguir usando su PC y su Inventor):
- Al arrancar, el vigilante abre SU PROPIO Inventor, oculto y con prioridad baja, y lo registra en la ROT como
  '!InventorIA.Privado'. inventor_mcp._inventor() usa ese Inventor; el del usuario no se toca.
- Si no puede (licencia, error), sigue como antes con el Inventor del usuario y lo avisa en _pedidos\\instancia.txt.
- Un pedido puede pedir el Inventor del usuario con "instancia": "usuario" en el .json.
- Después de cada pedido cierra los documentos del Inventor privado (sin guardar: los scripts guardan lo suyo).
- Si un pedido se pasa de tiempo, se reinicia el Inventor privado (puede haber quedado un diálogo oculto).
- Los trabajos corren con prioridad "debajo de lo normal".
Por defecto usa el Inventor del usuario (modo compartido). vigilante.py --privado -> prueba el Inventor privado.
"""
import atexit
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
JOBS = Path.home() / "Documents" / "InventorIA" / "_pedidos"
PY = ROOT / ".venv" / "Scripts" / "python.exe"
JOBS.mkdir(parents=True, exist_ok=True)
ESTADO = JOBS / "instancia.txt"            # .txt: los .json de esta carpeta se toman como pedidos
PIDF = JOBS / "inventor_privado.pid"
BELOW_NORMAL = 0x00004000
PRIVADO = "InventorIA.Privado"
COMPARTIDO = "--privado" not in sys.argv     # por ahora el Inventor privado es opcional (en prueba)

priv = {"app": None, "pid": None, "cookie": None, "rot": None, "fallo": False}


def estado(txt: str) -> None:
    print(f"[{datetime.now():%H:%M:%S}] {txt}", flush=True)
    ESTADO.write_text(f"{datetime.now().isoformat()}\n{txt}\n", encoding="utf-8")


def _pid_de(app):
    import win32process
    return win32process.GetWindowThreadProcessId(int(app.MainFrameHWND))[1]


def _matar(pid):
    if not pid:
        return
    try:
        import win32api
        import win32con
        h = win32api.OpenProcess(win32con.PROCESS_TERMINATE | win32con.PROCESS_QUERY_INFORMATION, False, int(pid))
        import win32process
        nombre = win32process.GetModuleFileNameEx(h, 0)
        if nombre.lower().endswith("inventor.exe"):
            win32api.TerminateProcess(h, 1)
    except Exception:  # noqa: BLE001
        pass


def cerrar_privado(forzar=False):
    app, pid = priv["app"], priv["pid"]
    if priv["rot"] is not None and priv["cookie"] is not None:
        try:
            priv["rot"].Revoke(priv["cookie"])
        except Exception:  # noqa: BLE001
            pass
    priv.update(app=None, cookie=None, rot=None)
    if app is not None and not forzar:
        try:
            app.SilentOperation = True
            app.Documents.CloseAll()
            app.Quit()
            time.sleep(3)
        except Exception:  # noqa: BLE001
            pass
    _matar(pid)
    priv["pid"] = None
    PIDF.unlink(missing_ok=True)


def abrir_privado() -> bool:
    """Abre un Inventor NUEVO (CreateObject crea otro proceso), oculto, prioridad baja, registrado en la ROT."""
    import pythoncom
    import win32api
    import win32con
    import win32process
    from win32com.client.dynamic import Dispatch
    pythoncom.CoInitialize()
    if PIDF.exists():                                   # Inventor privado huérfano de una sesión anterior
        _matar(PIDF.read_text().strip() or 0)
        PIDF.unlink(missing_ok=True)
    try:
        usuario_hwnd = None
        try:
            u = Dispatch(pythoncom.GetActiveObject("Inventor.Application").QueryInterface(pythoncom.IID_IDispatch))
            usuario_hwnd = int(u.MainFrameHWND)
            del u
        except pythoncom.com_error:
            pass
        estado("Abriendo el Inventor privado (oculto)... puede tardar 1-2 minutos")
        # CreateObject: Inventor crea un proceso nuevo por cada cliente (si devolviera el del usuario, se detecta abajo)
        app = Dispatch(pythoncom.CoCreateInstance(pythoncom.MakeIID(_clsid()), None,
                                                  pythoncom.CLSCTX_LOCAL_SERVER, pythoncom.IID_IDispatch))
        if app is None:
            estado("El segundo Inventor no apareció (¿licencia?): sigo en modo compartido")
            priv["fallo"] = True
            return False
        t0 = time.time()
        while time.time() - t0 < 240:
            try:
                if app.Ready:
                    break
            except pythoncom.com_error:
                pass
            time.sleep(2)
        if usuario_hwnd is not None and int(app.MainFrameHWND) == usuario_hwnd:
            estado("Obtuve el Inventor del usuario en lugar de uno nuevo: sigo en modo compartido")
            priv["fallo"] = True
            return False
        app.Visible = False
        app.SilentOperation = True
        pid = _pid_de(app)
        h = win32api.OpenProcess(win32con.PROCESS_SET_INFORMATION | win32con.PROCESS_QUERY_INFORMATION, False, pid)
        win32process.SetPriorityClass(h, BELOW_NORMAL)
        rot = pythoncom.GetRunningObjectTable()
        mk = pythoncom.CreateItemMoniker("!", PRIVADO)
        cookie = rot.Register(1, app._oleobj_, mk)       # 1 = ROTFLAGS_REGISTRATIONKEEPSALIVE
        priv.update(app=app, pid=pid, cookie=cookie, rot=rot)
        PIDF.write_text(str(pid), encoding="utf-8")
        estado(f"Inventor privado listo (pid {pid}, oculto, prioridad baja). Tu Inventor queda libre.")
        return True
    except Exception as exc:  # noqa: BLE001
        estado(f"No pude abrir el Inventor privado ({exc!r}): sigo en modo compartido")
        cerrar_privado(forzar=True)
        priv["fallo"] = True
        return False


def limpiar_huerfanos() -> list:
    """Cierra los Inventor OCULTOS lanzados por automatización (/Automation o -Embedding) que no tienen ninguna
    ventana visible y no son el Inventor del usuario. Devuelve los pid cerrados."""
    import pythoncom
    import win32gui
    import win32process
    from win32com.client.dynamic import Dispatch
    usuario_pid = None
    try:
        u = Dispatch(pythoncom.GetActiveObject("Inventor.Application").QueryInterface(pythoncom.IID_IDispatch))
        usuario_pid = win32process.GetWindowThreadProcessId(int(u.MainFrameHWND))[1]
        del u
    except Exception:  # noqa: BLE001
        pass
    visibles = set()

    def _cb(hwnd, _):
        if win32gui.IsWindowVisible(hwnd) and win32gui.GetWindowText(hwnd):
            visibles.add(win32process.GetWindowThreadProcessId(hwnd)[1])
        return True
    win32gui.EnumWindows(_cb, None)
    try:
        out = subprocess.run(["powershell", "-NoProfile", "-Command",
                              "Get-CimInstance Win32_Process -Filter \"Name='Inventor.exe'\" | "
                              "ForEach-Object { \"$($_.ProcessId)|$($_.CommandLine)\" }"],
                             capture_output=True, text=True, timeout=60).stdout
    except Exception:  # noqa: BLE001
        return []
    cerrados = []
    for ln in out.splitlines():
        if "|" not in ln:
            continue
        pid_s, cmd = ln.split("|", 1)
        pid = int(pid_s)
        auto = "/automation" in cmd.lower() or "-embedding" in cmd.lower()
        if auto and pid != usuario_pid and pid not in visibles:
            _matar(pid)
            cerrados.append(pid)
    return cerrados


def _otro_inventor(usuario_hwnd):
    """Recorre la ROT y devuelve una aplicación Inventor cuya ventana no sea la del usuario."""
    import pythoncom
    from win32com.client.dynamic import Dispatch
    rot = pythoncom.GetRunningObjectTable()
    for mk in rot.EnumRunning():
        try:
            d = Dispatch(rot.GetObject(mk).QueryInterface(pythoncom.IID_IDispatch))
            hwnd = int(d.MainFrameHWND)
            if hwnd and hwnd != usuario_hwnd and "Inventor" in str(d.SoftwareVersion.ProductName):
                return d
        except Exception:  # noqa: BLE001
            continue
    return None


def _exe() -> str:
    import winreg
    with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, rf"CLSID\{_clsid()}\LocalServer32") as key:
        raw = winreg.QueryValue(key, None).strip()
    return raw[1:].split('"', 1)[0] if raw.startswith('"') else raw.split(" /", 1)[0]


def _clsid() -> str:
    import winreg
    with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, r"Inventor.Application\CLSID") as key:
        return winreg.QueryValue(key, None)


def privado_vivo() -> bool:
    if priv["app"] is None:
        return False
    try:
        return bool(priv["app"].Ready)
    except Exception:  # noqa: BLE001
        return False


def run(job_file: Path) -> None:
    rid = job_file.stem
    res_file = JOBS / f"{rid}.resultado.json"
    timeout = False
    try:
        job = json.loads(job_file.read_text(encoding="utf-8"))
        target = (SCRIPTS / Path(job["script"]).name).resolve()
        if target.parent != SCRIPTS.resolve() or target.suffix != ".py" or not target.is_file():
            raise ValueError(f"Script no permitido: {job.get('script')}")
        args = [str(a) for a in job.get("args", [])]
        env = dict(os.environ)
        usuario = str(job.get("instancia", "")).lower() == "usuario"
        if not COMPARTIDO and not usuario and not priv["fallo"] and not privado_vivo():
            cerrar_privado(forzar=True)
            abrir_privado()
        env["INVENTORIA_INSTANCIA"] = "usuario" if (usuario or not privado_vivo()) else "privado"
        print(f"[{datetime.now():%H:%M:%S}] {rid}: {target.name} {' '.join(args)}  "
              f"(Inventor {env['INVENTORIA_INSTANCIA']})", flush=True)
        t0 = time.time()
        try:
            proc = subprocess.run([str(PY if PY.is_file() else sys.executable), str(target), *args],
                                  cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8",
                                  errors="replace", timeout=int(job.get("timeout_s", 1800)), env=env,
                                  creationflags=BELOW_NORMAL)
            result = {"codigo_salida": proc.returncode, "salida": proc.stdout[-60000:],
                      "errores": proc.stderr[-20000:]}
        except subprocess.TimeoutExpired as exc:
            timeout = True
            result = {"codigo_salida": -2, "salida": (exc.stdout or "")[-60000:] if isinstance(exc.stdout, str)
                      else "", "errores": f"Tiempo agotado ({job.get('timeout_s', 1800)} s)"}
        result = {"id": rid, "script": target.name, "args": args, "instancia": env["INVENTORIA_INSTANCIA"],
                  "segundos": round(time.time() - t0, 1), **result}
        print(f"    -> código {result['codigo_salida']} en {result['segundos']} s", flush=True)
    except Exception as exc:  # noqa: BLE001
        result = {"id": rid, "codigo_salida": -1, "errores": repr(exc)}
        print(f"    -> error: {exc}", flush=True)
    res_file.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    if job_file.exists():
        try:
            job_file.replace(job_file.with_suffix(".hecho"))       # pisa un .hecho viejo con el mismo nombre
        except OSError as exc:
            print(f"    -> no pude marcar {job_file.name} como hecho: {exc}", flush=True)
            job_file.unlink(missing_ok=True)
    # limpieza del Inventor privado
    if priv["app"] is not None:
        if timeout:
            estado("El pedido se pasó de tiempo: reinicio el Inventor privado")
            cerrar_privado(forzar=True)
        else:
            try:
                priv["app"].SilentOperation = True
                priv["app"].Documents.CloseAll()
            except Exception:  # noqa: BLE001
                pass


atexit.register(cerrar_privado)
try:                                   # cerrar la ventana del vigilante también cierra el Inventor privado
    import win32api
    win32api.SetConsoleCtrlHandler(lambda ev: (cerrar_privado(), False)[1], True)
except Exception:  # noqa: BLE001
    pass
print(f"Vigilante activo. Carpeta de pedidos: {JOBS}", flush=True)
_h = limpiar_huerfanos()
if _h:
    print(f"Cerré {len(_h)} Inventor oculto(s) huérfano(s): {_h}", flush=True)
if COMPARTIDO:
    estado("Modo compartido: los pedidos usan el Inventor del usuario")
else:
    abrir_privado()
(JOBS / "vigilante.activo").write_text(datetime.now().isoformat(), encoding="utf-8")
try:
    while True:
        for f in sorted(JOBS.glob("*.json")):
            if f.name.endswith(".resultado.json"):
                continue
            run(f)
        (JOBS / "vigilante.activo").write_text(datetime.now().isoformat(), encoding="utf-8")
        time.sleep(2)
except KeyboardInterrupt:
    pass
