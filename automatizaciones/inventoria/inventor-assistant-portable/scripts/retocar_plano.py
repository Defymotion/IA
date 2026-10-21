"""Retoca un plano existente sin regenerarlo (o solo lista su contenido).

Uso:
    .\\.venv\\Scripts\\python.exe .\\scripts\\retocar_plano.py                       -> lista el último plano *_CHAPAS
    .\\.venv\\Scripts\\python.exe .\\scripts\\retocar_plano.py --ops cambios.json     -> aplica los cambios
    Opcional: --plano "C:\\...\\plano.dwg"
cambios.json: lista de operaciones, p. ej.
    [{"hoja": 4, "vista": "ISOMÉTRICA", "escala": "1:5"},
     {"hoja": 4, "vista": "ISOMÉTRICA", "mover": {"x": 24, "y": 7}},
     {"hoja": 3, "reacomodar": true}]
"""
import json
import sys

sys.stdout.reconfigure(encoding="utf-8")
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
import inventor_mcp as inv  # noqa: E402


def arg(name):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else None


plano = arg("--plano")
if not plano:
    base = Path.home() / "Documents" / "InventorIA"
    cands = [p for ext in ("dwg", "idw") for p in base.rglob(f"*_CHAPAS*.{ext}") if "OldVersions" not in p.parts]
    if not cands:
        sys.exit("No encontré ningún plano *_CHAPAS; indicá --plano")
    plano = str(max(cands, key=lambda p: p.stat().st_mtime))
ops = None
if arg("--ops"):
    ops_path = Path(arg("--ops"))
    if not ops_path.is_absolute():
        ops_path = Path.home() / "Documents" / "InventorIA" / "_pedidos" / ops_path
    ops = json.loads(ops_path.read_text(encoding="utf-8"))
res = inv.inventor_edit_drawing(plano, ops)
print(res)
