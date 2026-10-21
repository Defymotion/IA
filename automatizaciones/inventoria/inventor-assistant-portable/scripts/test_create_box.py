"""Prueba de humo del servidor: conecta con Inventor y crea una caja paramétrica.

Uso (desde la carpeta del complemento):
    .venv\\Scripts\\python.exe scripts\\test_create_box.py [carpeta_salida]

Crea `prueba_caja_100x60x20.ipt` y falla si las medidas o los parámetros no coinciden.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
import inventor_mcp as inv  # noqa: E402

out_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.home() / "Documents" / "InventorIA"
out_dir.mkdir(parents=True, exist_ok=True)

print("Estado:", inv.inventor_status(start_if_needed=True))

res = json.loads(inv.inventor_create_box(100, 60, 20, str(out_dir / "prueba_caja_100x60x20.ipt"), overwrite=True))
print(json.dumps(res, indent=2, ensure_ascii=False))

errors = []
if not res["verified"]:
    errors.append("Las medidas del sólido no coinciden")
for name in ("Ancho", "Profundidad", "Altura"):
    if name not in res["parameters"]:
        errors.append(f"Falta el parámetro {name}")
if res["sketch_constraint_status"] != inv.K_FULLY_CONSTRAINED:
    errors.append(f"Boceto no totalmente restringido: {res['sketch_constraint_status_label']} "
                  f"({res['sketch_constraint_status']})")
if errors:
    print("FALLÓ:", "; ".join(errors))
    sys.exit(1)
print("OK")
