"""Genera planos (PDF), DXF de corte y plano de conjunto del ensamble ACTIVO en Inventor.

Uso (desde la carpeta del complemento):
    .\\.venv\\Scripts\\python.exe .\\scripts\\planos_gripper.py                   -> todas las piezas de chapa
    .\\.venv\\Scripts\\python.exe .\\scripts\\planos_gripper.py --con-conjunto    -> además, plano de conjunto
    .\\.venv\\Scripts\\python.exe .\\scripts\\planos_gripper.py --solo "Pala movil" -> solo piezas que contengan ese texto
    ... --ensamble "C:\\...\\Gripper.iam"   -> ese ensamble en lugar del activo
Salida: <carpeta del ensamble>\\Fabricacion\\ (Planos, Planos\\PDF, Corte_laser, indice.md)
"""
import json
import sys

sys.stdout.reconfigure(encoding="utf-8")
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
import inventor_mcp as inv  # noqa: E402

only = ""
if "--solo" in sys.argv:
    only = sys.argv[sys.argv.index("--solo") + 1]
ens = ""
if "--ensamble" in sys.argv:          # ruta del .iam (si no, el ensamble activo)
    ens = sys.argv[sys.argv.index("--ensamble") + 1]
res = json.loads(inv.inventor_fabrication_package(assembly_path=ens, only=only,
                                                  include_assembly="--con-conjunto" in sys.argv))
print(json.dumps(res, indent=1, ensure_ascii=False))
print(f"\nPiezas: {len(res['piezas'])}  Omitidas: {len(res['omitidas'])}  Errores: {len(res['errores'])}")
print("Carpeta:", res["carpeta"])
