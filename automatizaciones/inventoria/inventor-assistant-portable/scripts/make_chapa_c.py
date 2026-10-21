"""Genera la chapa plegada en C, su DXF de corte y el plano de fabricación.

Uso (desde la carpeta del complemento):
    .\\.venv\\Scripts\\python.exe .\\scripts\\make_chapa_c.py
Salida: Documents\\InventorIA\\Chapa_C_100x100x25\\ (Modelos, Planos, Planos\\PDF, Corte_laser)
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
import inventor_mcp as inv  # noqa: E402

out = Path.home() / "Documents" / "InventorIA" / "Chapa_C_100x100x25"
res = json.loads(inv.inventor_create_c_channel(
    web_mm=100, flange_mm=25, length_mm=100, thickness="3/16 in",
    output_dir=str(out), overwrite=True))
print(json.dumps(res, indent=2, ensure_ascii=False))
print("OK" if res["verified"] and all(res["files_exist"].values()) else "REVISAR")
