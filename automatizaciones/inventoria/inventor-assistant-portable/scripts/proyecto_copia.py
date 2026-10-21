"""Activa el proyecto (.ipj) de una copia de trabajo y verifica que el gripper use solo la copia.

Uso (desde la carpeta del complemento; con TODOS los documentos cerrados en Inventor):
    .\\.venv\\Scripts\\python.exe .\\scripts\\proyecto_copia.py            -> activa la copia y verifica
    .\\.venv\\Scripts\\python.exe .\\scripts\\proyecto_copia.py --restaurar -> vuelve al proyecto anterior
El proyecto anterior queda anotado en proyecto_anterior.txt (junto a este script).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
import inventor_mcp as inv  # noqa: E402

ROOT = Path.home() / "Documents" / "InventorIA" / "12_ADECO2"
IPJ = ROOT / "ADECOAGRO_Chivilcoy.ipj"
MAIN = ROOT / "Gripper" / "Gripper_ADECO2_V1.iam"
MEMO = Path(__file__).with_name("proyecto_anterior.txt")

app = inv._inventor()
if app.Documents.Count:
    sys.exit(f"Hay {app.Documents.Count} documentos abiertos en Inventor: cerralos todos (sin guardar) y volvé a correr.")
dpm = app.DesignProjectManager


def activate(path: Path):
    for p in inv._items(dpm.DesignProjects):
        if Path(p.FullFileName).resolve() == path.resolve():
            p.Activate(True)
            return p
    p = dpm.DesignProjects.AddExisting(str(path))
    p.Activate(True)
    return p


if "--restaurar" in sys.argv:
    if not MEMO.exists():
        sys.exit("No hay proyecto anterior anotado.")
    prev = Path(MEMO.read_text(encoding="utf-8").strip())
    activate(prev)
    print("Proyecto activo:", dpm.ActiveDesignProject.FullFileName)
    sys.exit(0)

current = Path(dpm.ActiveDesignProject.FullFileName)
if current.resolve() != IPJ.resolve():
    MEMO.write_text(str(current), encoding="utf-8")
    print("Proyecto anterior anotado:", current)
activate(IPJ)
print("Proyecto activo:", dpm.ActiveDesignProject.FullFileName)

app.SilentOperation = True
try:
    doc = app.Documents.Open(str(MAIN), True)
finally:
    app.SilentOperation = False
refs = {d.FullFileName for d in inv._items(doc.AllReferencedDocuments)}
library = [f for f in refs if "content center files" in f.lower()]
outside = sorted(f for f in refs if not f.lower().startswith(str(ROOT).lower()) and f not in library)
print(f"Referencias: {len(refs)} (biblioteca Centro de Contenido: {len(library)})")
if outside:
    print(f"{len(outside)} referencias FUERA de la copia:")
    for f in outside:
        print("  ", f)
else:
    print("OK: el gripper usa solo archivos de la copia en", ROOT)
