"""Si lo ejecuta el vigilante VIEJO (InventorIA_viejo_para_borrar), marca el pedido como hecho y cierra los procesos
del vigilante viejo (los python cuya línea de comandos tiene 'viejo' y 'vigilante.py'). Con el vigilante bueno no hace nada.
Uso: python cerrar_vigilante_viejo.py <pNNN>"""
import json, subprocess, sys
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
yo = Path(__file__).resolve()
if "viejo" not in str(yo).lower():
    print(json.dumps({"nada": "vigilante bueno"}))
    sys.exit(0)
jobs = Path.home() / "Documents" / "InventorIA" / "_pedidos"
j = jobs / f"{sys.argv[1]}.json"
if j.exists():
    j.replace(j.with_suffix(".hecho"))
ps = ("Get-CimInstance Win32_Process | Where-Object { $_.ExecutablePath -like '*viejo_para_borrar*' } | "
      "ForEach-Object { $_.ProcessId; taskkill /T /F /PID $_.ProcessId }")
print("cerrando vigilante viejo", flush=True)
subprocess.run(["powershell", "-NoProfile", "-Command", ps])
