"""Corre Blender en segundo plano (blender -b) desde el vigilante y devuelve su salida.
Uso: python bl_correr.py <script_bpy> [--blend archivo.blend] [--timeout s] -- <args del script>
     python bl_correr.py --render <archivo.blend> <salida_patron> (--cuadros 1,2,3 | --rango a b) [--timeout s]
       (render de la animación guardada: salida_patron p. ej. C:\\...\\Cuadros\\c##### -> c00000.png)
El script se busca en scripts\\blender\\ si no es una ruta. Blender: el más nuevo en Program Files\\Blender Foundation.
"""
import json
import subprocess
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
argv = sys.argv[1:]
resto = argv[argv.index("--") + 1:] if "--" in argv else []
argv = argv[:argv.index("--")] if "--" in argv else argv
timeout = float(argv[argv.index("--timeout") + 1]) if "--timeout" in argv else 7000.0
exes = sorted(Path(r"C:\Program Files\Blender Foundation").glob("Blender*/blender.exe"))
if not exes:
    print(json.dumps({"error": "no encontré blender.exe"}))
    sys.exit(1)
if argv[0] == "--render":
    blend, patron = argv[1], argv[2]
    cmd = [str(exes[-1]), "-b", blend, "-o", patron, "-F", "PNG", "-x", "1"]
    if "--cuadros" in argv:
        cmd += ["-f", argv[argv.index("--cuadros") + 1]]
    else:
        a, b = argv[argv.index("--rango") + 1], argv[argv.index("--rango") + 2]
        cmd += ["-s", a, "-e", b, "-a"]
else:
    script = Path(argv[0])
    if not script.is_absolute():
        script = Path(__file__).resolve().parent / "blender" / script
    blend = argv[argv.index("--blend") + 1] if "--blend" in argv else None
    cmd = [str(exes[-1]), "-b"] + ([blend] if blend else ["--factory-startup"]) + ["-P", str(script), "--"] + resto
T0 = time.time()
r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
lineas = r.stdout.splitlines()
res = next((json.loads(li[len("RESULTADO "):]) for li in reversed(lineas) if li.startswith("RESULTADO ")), None)
tiempos = [li for li in lineas if "Time:" in li or "Saved:" in li]
print(json.dumps({"blender": str(exes[-1]), "codigo": r.returncode, "segundos": round(time.time() - T0, 1),
                  "resultado": res, "renders": tiempos[-12:], "salida_final": lineas[-25:], "errores": r.stderr[-3000:]},
                 ensure_ascii=False, indent=1))
