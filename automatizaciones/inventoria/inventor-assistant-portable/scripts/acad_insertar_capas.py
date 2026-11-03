"""Con AutoCAD LT de la PC: (1) convierte un DXF de capas nuevas a DWG; (2) COPIA un DWG de planta (el original no se
toca) e inserta en la copia, explotado en 0,0 escala 1, el DWG de capas nuevas; guarda la copia.
Uso: python acad_insertar_capas.py <capas.dxf> <planta_original.dwg> <copia_salida.dwg> [--timeout 900]
"""
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
argv = sys.argv[1:]
TIMEOUT = float(argv[argv.index("--timeout") + 1]) if "--timeout" in argv else 900.0
CAPAS, ORIG, COPIA = Path(argv[0]), Path(argv[1]), Path(argv[2])
cands = []
for base in (Path(r"C:\Program Files\Autodesk"), Path(r"C:\Program Files (x86)\Autodesk")):
    if base.exists():
        cands += sorted(base.glob("AutoCAD*/acad.exe")) + sorted(base.glob("AutoCAD LT*/acadlt.exe"))
res = {"exes": [str(c) for c in cands], "pasos": []}
if not cands:
    sys.exit("no encontré AutoCAD ni AutoCAD LT")
EXE = cands[0]


def correr(archivo, lineas, salida, nombre):
    scr = COPIA.parent / f"_{nombre}.scr"
    scr.write_text("\n".join(["FILEDIA", "0", "CMDDIA", "0", *lineas, "FILEDIA", "1", "CMDDIA", "1", "_.QUIT", "_Y", ""]) + "\n",
                   encoding="utf-8")
    m0 = salida.stat().st_mtime if salida.exists() else 0
    t0 = time.time()
    p = subprocess.Popen([str(EXE), "/nologo", str(archivo), "/b", str(scr)])
    e = {"paso": nombre, "pid": p.pid}
    estable, ultimo = 0, -1
    while time.time() - t0 < TIMEOUT:
        if p.poll() is not None:
            break
        if salida.exists() and salida.stat().st_mtime > m0:
            s = salida.stat().st_size
            estable = estable + 1 if s == ultimo and s > 0 else 0
            ultimo = s
            if estable >= 10:
                try:
                    p.wait(40)
                except subprocess.TimeoutExpired:
                    pass
                break
        time.sleep(1)
    if p.poll() is None:
        e["cerrado_a_la_fuerza"] = True
        p.kill()
    e["s"] = round(time.time() - t0, 1)
    e["ok"] = salida.exists() and salida.stat().st_mtime > m0
    e["mb"] = round(salida.stat().st_size / 1e6, 2) if salida.exists() else None
    res["pasos"].append(e)
    print(json.dumps(e, ensure_ascii=False), flush=True)
    return e["ok"]


capas_dwg = CAPAS.with_suffix(".dwg")
if capas_dwg.exists():                       # SAVEAS preguntaría si reemplaza: lo aparto antes
    capas_dwg.rename(capas_dwg.with_name(capas_dwg.stem + time.strftime("_anterior_%Y%m%d_%H%M%S") + ".dwg"))
ok = correr(CAPAS, ["_.SAVEAS", "2018", f'"{capas_dwg}"'], capas_dwg, "capas_a_dwg")
if ok:
    if COPIA.exists():
        COPIA.rename(COPIA.with_name(COPIA.stem + time.strftime("_anterior_%Y%m%d_%H%M") + COPIA.suffix))
    shutil.copy2(ORIG, COPIA)
    time.sleep(1)
    correr(COPIA, ["_.-INSERT", f'"*{capas_dwg}"', "0,0", "1", "0", "_.ZOOM", "_E", "_.QSAVE"], COPIA, "insertar")
res["copia"] = str(COPIA)
(COPIA.parent / "acad_insertar_capas_resultado.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps(res, ensure_ascii=False, indent=1))
