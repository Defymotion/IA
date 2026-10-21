"""Parte un zip de cuadros existente en varios zip de menos de ~350 MB (sin descomprimir a disco).
Uso: python partir_zip_existente.py <zip_origen> <prefijo_salida>"""
import sys
import zipfile
from pathlib import Path

src, pref = Path(sys.argv[1]), sys.argv[2]
LIM = 350 * 1024 * 1024
with zipfile.ZipFile(src) as z:
    infos = sorted(z.infolist(), key=lambda i: i.filename)
    parte, tam, out = 0, 0, None
    for inf in infos:
        if out is None or tam + inf.file_size > LIM:
            if out is not None:
                out.close()
            parte += 1
            out = zipfile.ZipFile(f"{pref}_{parte}.zip", "w", zipfile.ZIP_STORED)
            tam = 0
        out.writestr(inf.filename, z.read(inf.filename))
        tam += inf.file_size
    if out is not None:
        out.close()
print(parte, len(infos))
