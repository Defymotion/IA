"""Edita EN EL LUGAR el DWG de planta de la etapa 1 con AutoCAD LT (respaldo previo con fecha):
1) pasa el overlay DXF (celda A con la giratoria) a DWG;
2) en el DWG: carga acad/defy_e1_editar.lsp, reemplaza textos (c:defyrepl), renombra capas, borra lo que está dentro del
   polígono en la capa indicada, inserta explotado el overlay, ZOOM E y QSAVE.
Uso: python acad_editar_v2.py <dwg> <overlay.dxf> <borrar.json> [--capa-borrar CAPA] [--timeout 1200]
     [--renombrar "VIEJA>NUEVA;VIEJA2>NUEVA2"] [--solo-textos]
Log de lo que hizo el LISP: C:\\DEFYMOTION\\L3N\\Planos_IA\\defy_editar_log.txt
"""
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
argv = sys.argv[1:]


def opt(n, d=None):
    return argv[argv.index(n) + 1] if n in argv else d


DWG, OVL, BOR = Path(argv[0]), Path(argv[1]), Path(argv[2])
CAPA = opt("--capa-borrar", "DEFY_E1_CELDA_A_NUEVA")
TIMEOUT = float(opt("--timeout", 1200))
REN = [r.split(">") for r in opt("--renombrar", "").split(";") if ">" in r]
LSP = Path(__file__).resolve().parent / "acad" / "defy_e1_editar.lsp"
LOG = Path(r"C:\DEFYMOTION\L3N\Planos_IA\defy_editar_log.txt")
cands = []
for base in (Path(r"C:\Program Files\Autodesk"), Path(r"C:\Program Files (x86)\Autodesk")):
    if base.exists():
        cands += sorted(base.glob("AutoCAD*/acad.exe")) + sorted(base.glob("AutoCAD LT*/acadlt.exe"))
EXE = cands[0]
res = {"pasos": []}


def correr(archivo, lineas, salida, nombre):
    scr = DWG.parent / f"_{nombre}.scr"
    scr.write_text("\n".join(["FILEDIA", "0", "CMDDIA", "0", *lineas, "FILEDIA", "1", "CMDDIA", "1", "_.QUIT", "_Y", ""]) + "\n",
                   encoding="cp1252", errors="replace")
    m0 = salida.stat().st_mtime if salida.exists() else 0
    t0 = time.time()
    p = subprocess.Popen([str(EXE), "/nologo", str(archivo), "/b", str(scr)])
    e = {"paso": nombre}
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
    res["pasos"].append(e)
    print(json.dumps(e, ensure_ascii=False), flush=True)
    return e["ok"]


if Path(str(DWG)[:-4] + ".dwl").exists():
    sys.exit("el DWG está abierto en AutoCAD (hay .dwl): cerralo primero")
if "--solo-textos" in argv:          # sólo reemplazos de texto y capas (idempotente), sin borrar ni insertar
    resp = DWG.with_name(DWG.stem + time.strftime("_respaldo_%Y%m%d_%H%M%S") + DWG.suffix)
    shutil.copy2(DWG, resp)
    res["respaldo"] = str(resp)
    lsp = str(LSP).replace("\\", "/")
    lin = ["SECURELOAD", "0", f'(load "{lsp}")', "(c:defyrepl)"] + [f'(dfy-ren "{a}" "{b}")' for a, b in REN]
    correr(DWG, lin + ["SECURELOAD", "1", "_.QSAVE"], DWG, "textos")
    res["log_lisp"] = LOG.read_text(encoding="cp1252", errors="replace")[-3000:] if LOG.exists() else None
    (DWG.parent / "acad_editar_v2_resultado.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(res, ensure_ascii=False, indent=1))
    sys.exit(0)
ovl_dwg = OVL.with_suffix(".dwg")
if ovl_dwg.exists():
    ovl_dwg.rename(ovl_dwg.with_name(ovl_dwg.stem + time.strftime("_anterior_%Y%m%d_%H%M%S") + ".dwg"))
ok = correr(OVL, ["_.SAVEAS", "2018", f'"{ovl_dwg}"'], ovl_dwg, "overlay_a_dwg")
if ok:
    resp = DWG.with_name(DWG.stem + time.strftime("_respaldo_%Y%m%d_%H%M%S") + DWG.suffix)
    shutil.copy2(DWG, resp)
    res["respaldo"] = str(resp)
    pts = json.load(open(BOR))
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    lp = "(list " + " ".join(f"(list {x} {y})" for x, y in pts) + ")"
    lsp = str(LSP).replace("\\", "/")
    lineas = ["SECURELOAD", "0", f'(load "{lsp}")', "(c:defyrepl)"]
    lineas += [f'(dfy-ren "{a}" "{b}")' for a, b in REN]
    lineas += ["_.ZOOM", "_W", f"{min(xs) - 2},{min(ys) - 2}", f"{max(xs) + 2},{max(ys) + 2}",
               f'(dfy-borrar {lp} "{CAPA}")',
               "_.-INSERT", f'"*{ovl_dwg}"', "0,0", "1", "0", "_.ZOOM", "_E", "SECURELOAD", "1", "_.QSAVE"]
    correr(DWG, lineas, DWG, "editar")
res["log_lisp"] = LOG.read_text(encoding="cp1252", errors="replace")[-4000:] if LOG.exists() else None
(DWG.parent / "acad_editar_v2_resultado.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps(res, ensure_ascii=False, indent=1))
