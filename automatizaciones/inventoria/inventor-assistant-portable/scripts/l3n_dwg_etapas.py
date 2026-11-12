"""DWG de planta L3N separado en etapas 1 y 2: copia el DWG v2 (etapa 1) a "... ETAPAS 1 Y 2 DEFYMOTION v3.dwg", le aplica
con AutoCAD LT los reemplazos de texto (acad/defy_e1_editar.lsp: leyenda por etapa, rótulos "ETAPA 2:") y renombra a
DEFY_E2_* las capas de la etapa 2; después aparta el v2 en Planos_IA\\_anterior (no se borra nada).
Uso: python l3n_dwg_etapas.py
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
D = Path(r"C:\DEFYMOTION\L3N\Planos_IA")
V2 = D / "Revamping E2 - Defymotion - Integracion V1 - ETAPA 1 DEFYMOTION v2.dwg"
V3 = D / "Revamping E2 - Defymotion - Integracion V1 - ETAPAS 1 Y 2 DEFYMOTION v3.dwg"
REN = ";".join(["DEFY_E1_ROBOT_AEREO_EXTENSION_Y_BUFFER_CARTONES>DEFY_E2_ROBOT_AEREO_EXTENSION_Y_BUFFER_CARTONES",
                "DEFY_E1_RESERVA_ETAPA2_PALLET_CAUTIVO>DEFY_E2_PALLET_CAUTIVO",
                "DEFY_E1_RECORRIDO_INSUMOS_CARTONES>DEFY_E2_RECORRIDO_INSUMOS_CARTONES",
                "DEFY_E1_PUERTA_A_REUBICAR>DEFY_E2_PUERTA_A_REUBICAR"])
res = {}
if Path(str(V2)[:-4] + ".dwl").exists():
    sys.exit("el DWG v2 está abierto en AutoCAD: cerralo primero")
if not V3.exists():
    shutil.copy2(V2, V3)
r = subprocess.run([sys.executable, str(Path(__file__).with_name("acad_editar_v2.py")), str(V3), "x.dxf", "x.json",
                    "--solo-textos", "--renombrar", REN, "--timeout", "900"], capture_output=True, text=True,
                   encoding="utf-8", errors="replace")
res["salida"] = r.stdout[-5000:]
res["errores"] = r.stderr[-2000:]
res["codigo"] = r.returncode
if r.returncode == 0 and "textos cambiados" in r.stdout:
    ant = D / "_anterior"
    ant.mkdir(exist_ok=True)
    for f in (V2, D / "L3N Etapa 1 - Plano de modificaciones A3.pdf"):
        if f.exists():
            shutil.move(str(f), str(ant / f.name))
            res.setdefault("apartados", []).append(str(ant / f.name))
    for f in D.glob("*_respaldo_*.dwg"):
        shutil.move(str(f), str(ant / f.name))
res["v3"] = str(V3)
print(json.dumps(res, ensure_ascii=False, indent=1))
