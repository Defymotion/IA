"""Inventario (sólo lectura) de todo lo que usa InventorIA en esta PC: carpetas con tamaño, entorno Python, acceso
directo del vigilante, copias del repositorio, Blender, Inventor (proyecto activo y Content Center), app de Claude/Codex.
No modifica nada. Uso: python info_instalacion.py [--rapido]   (--rapido: sin tamaños de carpetas)
Escribe Documents\\InventorIA\\Generados\\_info\\info_instalacion.json
"""
import json
import os
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
T0 = time.time()
RAPIDO = "--rapido" in sys.argv
HOME = Path.home()
DOCS = HOME / "Documents"
BASE = DOCS / "InventorIA"
PORT = BASE / "inventor-assistant-portable"
APPDATA = Path(os.environ.get("APPDATA", HOME / "AppData" / "Roaming"))
LOCAL = Path(os.environ.get("LOCALAPPDATA", HOME / "AppData" / "Local"))
out = {"usuario": str(HOME), "avisos": []}


def tam(p, limite_s=120.0):
    """(GB, archivos) recorriendo la carpeta; corta si tarda demasiado."""
    t = time.time()
    n, b = 0, 0
    for r, ds, fs in os.walk(p):
        for f in fs:
            try:
                b += os.stat(os.path.join(r, f)).st_size
                n += 1
            except OSError:
                pass
        if time.time() - t > limite_s:
            return {"gb": round(b / 1e9, 2), "archivos": n, "parcial": True}
    return {"gb": round(b / 1e9, 3), "archivos": n}


def carpeta(p, hijos=False):
    p = Path(p)
    d = {"ruta": str(p), "existe": p.exists()}
    if not p.exists():
        return d
    if p.is_file():
        d["mb"] = round(p.stat().st_size / 1e6, 1)
        return d
    if not RAPIDO:
        d.update(tam(p))
    if hijos:
        h = []
        for c in sorted(p.iterdir(), key=lambda x: x.name.lower()):
            e = {"nombre": c.name + ("\\" if c.is_dir() else "")}
            if c.is_dir() and not RAPIDO:
                e.update(tam(c, 60))
            elif c.is_file():
                e["mb"] = round(c.stat().st_size / 1e6, 2)
            h.append(e)
        d["contenido"] = h
    return d


# ------------------------------------------------------------- carpetas de InventorIA y del proyecto
out["inventoria"] = carpeta(BASE, hijos=True)
out["complemento"] = carpeta(PORT, hijos=True)
out["generados"] = carpeta(BASE / "Generados", hijos=True)
out["l3n"] = carpeta(r"C:\DEFYMOTION\L3N", hijos=True)
out["l3n_celdas_ia"] = carpeta(r"C:\DEFYMOTION\L3N\Celdas_IA", hijos=True)
out["l3n_inventoria"] = carpeta(r"C:\DEFYMOTION\L3N\InventorIA", hijos=True)

# ------------------------------------------------------------- Python
cfg = PORT / ".venv" / "pyvenv.cfg"
py = {"venv": str(PORT / ".venv"), "existe": cfg.exists()}
if cfg.exists():
    for li in cfg.read_text(encoding="utf-8", errors="replace").splitlines():
        if "=" in li:
            k, v = [s.strip() for s in li.split("=", 1)]
            py[k] = v
sp = PORT / ".venv" / "Lib" / "site-packages"
if sp.exists():
    py["paquetes"] = sorted({c.name.split("-")[0] for c in sp.iterdir() if c.name.endswith(".dist-info")})
py["este_python"] = sys.executable
out["python"] = py

# ------------------------------------------------------------- acceso directo del vigilante
escritorios = {HOME / "Desktop", HOME / "Escritorio", HOME / "OneDrive" / "Desktop", HOME / "OneDrive" / "Escritorio",
               Path(os.environ.get("PUBLIC", r"C:\Users\Public")) / "Desktop"}
for od in HOME.glob("OneDrive*"):
    escritorios |= {od / "Desktop", od / "Escritorio"}
try:
    import win32com.client
    sh = win32com.client.Dispatch("WScript.Shell")
    escritorios.add(Path(sh.SpecialFolders("Desktop")))
except Exception as e:  # noqa: BLE001
    sh = None
    out["avisos"].append(f"WScript.Shell: {e!r}"[:120])
accesos = []
for d in escritorios:
    if d.exists():
        for lnk in d.glob("*.lnk"):
            if "vigilante" in lnk.name.lower() or "inventoria" in lnk.name.lower():
                e = {"ruta": str(lnk)}
                try:
                    s = sh.CreateShortcut(str(lnk))
                    e["destino"] = s.TargetPath
                except Exception:  # noqa: BLE001
                    pass
                accesos.append(e)
out["accesos_directos"] = accesos

# ------------------------------------------------------------- copias del repositorio (instalar.ps1 / .git)
raices = [HOME / "Downloads", HOME / "Descargas", HOME / "Desktop", HOME / "Documents", HOME / "source",
          Path(r"C:\DEFYMOTION"), HOME]
raices += list(HOME.glob("OneDrive*"))
vistos, repos = set(), []
t = time.time()
for raiz in raices:
    if not raiz.exists():
        continue
    prof0 = len(raiz.parts)
    for r, ds, fs in os.walk(raiz):
        pr = Path(r)
        if len(pr.parts) - prof0 >= (2 if raiz == HOME else 5) or time.time() - t > 120:
            ds[:] = []
        ds[:] = [x for x in ds if not x.startswith(".") and x not in (
            "AppData", "node_modules", ".venv", "Generados", "_BORRAR", "__pycache__", "Content Center Files")]
        if "instalar.ps1" in fs and (pr / "inventor-assistant-portable").exists() and str(pr) not in vistos:
            vistos.add(str(pr))
            repos.append({"ruta": str(pr), "tipo": "copia del repo (automatizaciones\\inventoria)"})
        for f in fs:
            if f.lower().startswith("ia-") and f.lower().endswith(".zip"):
                repos.append({"ruta": str(pr / f), "tipo": "zip del repo"})
out["copias_repo"] = repos

# ------------------------------------------------------------- Blender
bl = {"instalaciones": [str(p) for p in Path(r"C:\Program Files\Blender Foundation").glob("Blender*/blender.exe")]}
cfgb = APPDATA / "Blender Foundation" / "Blender"
bl["config_usuario"] = carpeta(cfgb, hijos=True) if cfgb.exists() else {"ruta": str(cfgb), "existe": False}
out["blender"] = bl

# ------------------------------------------------------------- Inventor
inv = {"exe": [str(p) for p in Path(r"C:\Program Files\Autodesk").glob("Inventor*/Bin/Inventor.exe")]}
try:
    import win32com.client
    app = win32com.client.GetActiveObject("Inventor.Application")
    pr = app.DesignProjectManager.ActiveDesignProject
    inv["version"] = app.SoftwareVersion.DisplayName
    inv["proyecto_activo"] = pr.FullFileName
    inv["workspace"] = pr.WorkspacePath
    try:
        inv["content_center"] = pr.ContentCenterPath
    except Exception:  # noqa: BLE001
        pass
    try:
        inv["plantillas"] = pr.TemplatesPath
    except Exception:  # noqa: BLE001
        pass
except Exception as e:  # noqa: BLE001
    inv["com"] = f"sin conexión: {e!r}"[:160]
out["inventor"] = inv

# ------------------------------------------------------------- Claude / Codex (sólo nombres de servidores MCP)
cl = {}
for nombre, p in (("claude_desktop_config", APPDATA / "Claude" / "claude_desktop_config.json"),
                  ("claude_code_settings", HOME / ".claude" / "settings.json"),
                  ("claude_code_json", HOME / ".claude.json")):
    e = {"ruta": str(p), "existe": p.exists()}
    if p.exists():
        try:
            j = json.loads(p.read_text(encoding="utf-8"))
            e["servidores_mcp"] = sorted((j.get("mcpServers") or {}).keys())
        except Exception as ex:  # noqa: BLE001
            e["error"] = repr(ex)[:100]
    cl[nombre] = e
for nombre, p in (("claude_code_skills", HOME / ".claude" / "skills"), ("codex", HOME / ".codex")):
    e = {"ruta": str(p), "existe": p.exists()}
    if p.exists():
        e["contenido"] = sorted(c.name for c in p.iterdir())[:40]
        toml = p / "config.toml"
        if toml.exists():
            e["config_menciona_inventor"] = "inventor" in toml.read_text(encoding="utf-8", errors="replace").lower()
    cl[nombre] = e
cl["app_claude"] = {"appdata": (APPDATA / "Claude").exists(), "local": [str(p) for p in LOCAL.glob("AnthropicClaude*")]}
out["claude_codex"] = cl

out["segundos"] = round(time.time() - T0, 1)
dest = BASE / "Generados" / "_info"
dest.mkdir(parents=True, exist_ok=True)
(dest / "info_instalacion.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps(out, ensure_ascii=False, indent=1))
