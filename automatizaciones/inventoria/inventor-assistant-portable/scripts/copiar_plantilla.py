"""Copia un gripper existente a una carpeta de trabajo y verifica sus referencias.

Verificar una copia hecha con Pack and Go (no copia nada):
    .\\.venv\\Scripts\\python.exe .\\scripts\\copiar_plantilla.py --verificar

Uso (desde la carpeta del complemento; CERRAR antes el ensamble original en Inventor):
    .\\.venv\\Scripts\\python.exe .\\scripts\\copiar_plantilla.py
Por defecto copia DEFYMOTION\\12_ADECO2\\Gripper -> Documents\\InventorIA\\Plantillas\\ADECO2
sin OldVersions, Design Data, Templates ni resultados de simulación. El original no se modifica.
Luego abre la copia en Inventor y lista cualquier referencia que siga apuntando fuera de la copia.
"""
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
import inventor_mcp as inv  # noqa: E402

VERIFY_ONLY = "--verificar" in sys.argv
sys.argv = [a for a in sys.argv if a != "--verificar"]
HOME = Path.home() / "Documents"
SRC = Path(sys.argv[1]) if len(sys.argv) > 1 else HOME / "Del C" / "DEFYMOTION" / "12_ADECO2" / "Gripper"
DST = Path(sys.argv[2]) if len(sys.argv) > 2 else HOME / "InventorIA" / "Plantillas" / "ADECO2"
MAIN = sys.argv[3] if len(sys.argv) > 3 else "Gripper_ADECO2_V1.iam"

IGNORE_DIRS = {"OldVersions", "Design Data", "Templates"}
IGNORE_EXT = {".fins", ".fsat", ".ftes", ".fwiz", ".fmsh", ".fres", ".lck", ".bak"}


def ignore(folder, names):
    out = []
    for n in names:
        p = Path(folder) / n
        if (p.is_dir() and n in IGNORE_DIRS) or p.suffix.lower() in IGNORE_EXT:
            out.append(n)
    return out


if VERIFY_ONLY:
    found = list(DST.rglob(MAIN))
    if not found:
        sys.exit(f"No se encontró {MAIN} dentro de {DST}")
    MAIN_PATH = found[0]
else:
    if not (SRC / MAIN).is_file():
        sys.exit(f"No existe {SRC / MAIN}")
    if DST.exists():
        sys.exit(f"La carpeta destino ya existe: {DST}  (borrala o elegí otra)")
    shutil.copytree(SRC, DST, ignore=ignore)
    MAIN_PATH = DST / MAIN
n_files = sum(1 for p in DST.rglob("*") if p.is_file())
size_mb = sum(p.stat().st_size for p in DST.rglob("*") if p.is_file()) / 1e6
print(f"{n_files} archivos ({size_mb:.1f} MB) en {DST}")

# Verificación de referencias con Inventor
app = inv._inventor()
others = [d.FullFileName for d in inv._items(app.Documents)
          if not str(d.FullFileName).lower().startswith(str(DST).lower())]
if others:
    sys.exit("Hay otros documentos abiertos en Inventor; cerralos todos (sin guardar) y volvé a correr. "
             f"Ej.: {others[:2]}")
app.SilentOperation = True
try:
    doc = app.Documents.Open(str(MAIN_PATH), True)
finally:
    app.SilentOperation = False
refs = {d.FullFileName for d in inv._items(doc.AllReferencedDocuments)}
library = sorted(f for f in refs if "content center files" in f.lower())
outside = sorted(f for f in refs if not f.lower().startswith(str(DST).lower()) and f not in library)
print(f"Piezas de biblioteca (Centro de Contenido, OK): {len(library)}")
print(f"Referencias totales: {doc.AllReferencedDocuments.Count}")
if outside:
    print(f"{len(outside)} referencias apuntan FUERA de la copia:")
    for f in outside:
        print("  ", f)
else:
    print("OK: todas las referencias apuntan a la copia.")
