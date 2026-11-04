"""Cierra (mata) sólo las instancias de AutoCAD / AutoCAD LT cuya línea de comandos abre el archivo indicado (las que
abrió la IA con abrir_en_acad.py para revisar una copia). Nunca toca otra instancia.
Uso: python cerrar_acad_de_archivo.py <texto_en_la_linea_de_comandos>
"""
import json
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")
pat = sys.argv[1].lower()
ps = ("Get-CimInstance Win32_Process | Where-Object { $_.Name -match 'acad' } | "
      "Select-Object ProcessId,Name,CommandLine | ConvertTo-Json")
out = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True).stdout
procs = json.loads(out) if out.strip() else []
if isinstance(procs, dict):
    procs = [procs]
res = []
for p in procs:
    cl = (p.get("CommandLine") or "").lower()
    if pat in cl:
        r = subprocess.run(["taskkill", "/PID", str(p["ProcessId"]), "/F"], capture_output=True, text=True)
        res.append({"pid": p["ProcessId"], "cerrado": r.returncode == 0})
    else:
        res.append({"pid": p["ProcessId"], "cmd": cl[-120:], "no_tocado": True})
print(json.dumps(res, ensure_ascii=False, indent=1))
