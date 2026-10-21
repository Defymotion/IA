"""Verifica que esta PC esté lista para trabajar con la IA (sólo lectura, no modifica nada).
Revisa: Python y paquetes, carpetas de trabajo, vigilante, conexión COM con Inventor y modelos base para
simulaciones. Escribe Documents\\InventorIA\\_pedidos\\verificacion.txt (se ve también en la consola).
Uso: .venv\\Scripts\\python.exe scripts\\verificar_instalacion.py"""
import importlib
import platform
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
DOCS = Path.home() / "Documents" / "InventorIA"
ok_total = True
lineas = []


def chequeo(nombre, ok, detalle=""):
    global ok_total
    ok_total &= bool(ok)
    lineas.append(f"[{'OK ' if ok else 'FALTA'}] {nombre}{(' - ' + detalle) if detalle else ''}")


chequeo("Windows", platform.system() == "Windows", platform.platform())
chequeo("Python >= 3.10", sys.version_info >= (3, 10), sys.version.split()[0])
chequeo("Entorno .venv del complemento", (ROOT / ".venv" / "Scripts" / "python.exe").exists(), str(ROOT / ".venv"))
for mod, pip in (("win32com.client", "pywin32"), ("pythoncom", "pywin32"), ("PIL", "pillow")):
    try:
        importlib.import_module(mod)
        chequeo(f"Paquete {pip}", True)
    except Exception as exc:  # noqa: BLE001
        chequeo(f"Paquete {pip}", False, f"instalar con: .venv\\Scripts\\python.exe -m pip install {pip} ({exc})")
for sub in ("_pedidos", "Generados", "Analisis", "Comerciales"):
    chequeo(f"Carpeta Documents\\InventorIA\\{sub}", (DOCS / sub).is_dir())
chequeo("Complemento dentro de Documents\\InventorIA",
        ROOT.resolve() == (DOCS / "inventor-assistant-portable").resolve(),
        f"está en {ROOT}; los scripts esperan Documents\\InventorIA\\inventor-assistant-portable")
chequeo("vigilante.bat", (ROOT / "scripts" / "vigilante.bat").exists())
for doc in ("Guia_IA_Inventor.md", "InventorIA_contexto.md"):
    chequeo(f"Memoria {doc}", (DOCS / doc).exists() or (ROOT / "docs" / doc).exists())
# Inventor
try:
    sys.path.insert(0, str(ROOT / "server"))
    import inventor_mcp as inv
    app = inv._inventor(start_if_needed=False)
    chequeo("Inventor abierto y accesible por COM", True,
            f"versión {inv._safe(lambda: app.SoftwareVersion.DisplayVersion, '?')}; "
            f"proyecto {inv._safe(lambda: app.DesignProjectManager.ActiveDesignProject.Name, '?')}")
except Exception as exc:  # noqa: BLE001
    chequeo("Inventor abierto y accesible por COM", False,
            f"abrir Inventor (misma sesión de Windows, sin 'ejecutar como administrador') ({exc})")
# modelos base usados por las simulaciones con KUKA KR 140 (no vienen en el repositorio)
kuka = DOCS / "12_ADECO2" / "KUKA" / "KUKA-KR_140_R3200_2_PA-ASM.iam"
lineas.append(f"[{'OK ' if kuka.exists() else 'INFO'}] Robot KUKA KR 140 para simulaciones: "
              f"{'encontrado' if kuka.exists() else 'no está (copiarlo si se van a simular celdas con KR 140)'} - {kuka}")
lineas.append("")
lineas.append("TODO LISTO" if ok_total else "HAY PUNTOS PENDIENTES (ver FALTA)")
txt = "\n".join(lineas)
print(txt)
try:
    (DOCS / "_pedidos").mkdir(parents=True, exist_ok=True)
    (DOCS / "_pedidos" / "verificacion.txt").write_text(txt, encoding="utf-8")
except Exception:  # noqa: BLE001
    pass
sys.exit(0 if ok_total else 1)
