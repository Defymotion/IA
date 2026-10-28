"""Convierte DWG a DXF con AutoCAD LT (o AutoCAD) de la PC, sin tocar los originales, y comprime el DXF en .zip.
Uso: python dwg_a_dxf.py <carpeta_salida> <archivo1.dwg> [<archivo2.dwg> ...] [--timeout 600]
Por cada DWG: abre una instancia nueva de AutoCAD LT con un guion (.scr) que hace SAVEAS DXF a la carpeta de salida,
restituye FILEDIA/CMDDIA y sale. Sólo cierra el proceso que abrió (nunca otro AutoCAD del usuario).
Escribe <carpeta_salida>\\dwg_a_dxf_resultado.json
"""
import json
import subprocess
import sys
import time
import zipfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
argv = sys.argv[1:]
TIMEOUT = float(argv[argv.index("--timeout") + 1]) if "--timeout" in argv else 600.0
if "--timeout" in argv:
    i = argv.index("--timeout")
    argv = argv[:i] + argv[i + 2:]
SAL = Path(argv[0])
SAL.mkdir(parents=True, exist_ok=True)
DWGS = [Path(a) for a in argv[1:]]

cands = []
for base in (Path(r"C:\Program Files\Autodesk"), Path(r"C:\Program Files (x86)\Autodesk")):
    if base.exists():
        cands += sorted(base.glob("AutoCAD*/acad.exe")) + sorted(base.glob("AutoCAD LT*/acadlt.exe"))
res = {"exes": [str(c) for c in cands], "archivos": []}
if not cands:
    res["error"] = "no encontré AutoCAD ni AutoCAD LT"
    print(json.dumps(res, ensure_ascii=False, indent=1))
    sys.exit(1)
EXE = cands[0]
res["exe"] = str(EXE)

for dwg in DWGS:
    e = {"dwg": str(dwg), "existe": dwg.exists()}
    res["archivos"].append(e)
    if not dwg.exists():
        continue
    dxf = SAL / (dwg.stem + ".dxf")
    n = 1
    while dxf.exists():
        dxf = SAL / f"{dwg.stem}_{n}.dxf"
        n += 1
    scr = SAL / (dxf.stem + "_guion.scr")
    scr.write_text("\n".join([
        "FILEDIA", "0", "CMDDIA", "0",
        "_.SAVEAS", "_DXF", "", f'"{dxf}"',
        "FILEDIA", "1", "CMDDIA", "1",
        "_.QUIT", "_Y", ""]) + "\n", encoding="utf-8")
    t0 = time.time()
    p = subprocess.Popen([str(EXE), "/nologo", str(dwg), "/b", str(scr)])
    e["pid"] = p.pid
    estable, ultimo = 0, -1
    while time.time() - t0 < TIMEOUT:
        if p.poll() is not None:
            break
        if dxf.exists():
            s = dxf.stat().st_size
            estable = estable + 1 if s == ultimo and s > 0 else 0
            ultimo = s
            if estable >= 10:            # tamaño quieto 10 s: terminó de escribir; le doy 30 s para salir solo
                try:
                    p.wait(30)
                except subprocess.TimeoutExpired:
                    pass
                break
        time.sleep(1)
    if p.poll() is None:
        e["cerrado_a_la_fuerza"] = True
        p.kill()
    e["segundos"] = round(time.time() - t0, 1)
    e["codigo"] = p.poll()
    if dxf.exists() and dxf.stat().st_size > 0:
        e["dxf"] = str(dxf)
        e["dxf_mb"] = round(dxf.stat().st_size / 1e6, 1)
        z = dxf.with_suffix(".zip")
        with zipfile.ZipFile(z, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
            zf.write(dxf, dxf.name)
        e["zip"] = str(z)
        e["zip_mb"] = round(z.stat().st_size / 1e6, 1)
    else:
        e["error"] = "no se generó el DXF (¿diálogo abierto en AutoCAD LT?)"
(SAL / "dwg_a_dxf_resultado.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps(res, ensure_ascii=False, indent=1))
