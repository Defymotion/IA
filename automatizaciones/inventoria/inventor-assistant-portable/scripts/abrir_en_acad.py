"""Abre un DWG en AutoCAD LT (o AutoCAD) para que el usuario lo vea; no espera ni modifica nada.
Uso: python abrir_en_acad.py <archivo.dwg>"""
import subprocess
import sys
from pathlib import Path

cands = []
for base in (Path(r"C:\Program Files\Autodesk"), Path(r"C:\Program Files (x86)\Autodesk")):
    if base.exists():
        cands += sorted(base.glob("AutoCAD*/acad.exe")) + sorted(base.glob("AutoCAD LT*/acadlt.exe"))
if not cands:
    sys.exit("no encontré AutoCAD")
p = subprocess.Popen([str(cands[0]), "/nologo", sys.argv[1]], close_fds=True,
                     creationflags=0x00000008 | 0x00000200)        # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
print("abierto", cands[0], sys.argv[1], "pid", p.pid)
