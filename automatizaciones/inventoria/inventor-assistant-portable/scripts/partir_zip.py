"""Divide los cuadros de una carpeta en varios zip de menos de ~350 MB cada uno.
Uso: python partir_zip.py <carpeta_cuadros> <prefijo_salida>"""
import sys
import zipfile
from pathlib import Path

src, pref = Path(sys.argv[1]), Path(sys.argv[2])
LIM = 350 * 1024 * 1024
partes, actual, tam = [], [], 0
for f in sorted(src.glob("*.png")):
    s = f.stat().st_size
    if actual and tam + s > LIM:
        partes.append(actual)
        actual, tam = [], 0
    actual.append(f)
    tam += s
if actual:
    partes.append(actual)
for i, fs in enumerate(partes, 1):
    with zipfile.ZipFile(f"{pref}_{i}.zip", "w", zipfile.ZIP_STORED) as z:
        for f in fs:
            z.write(f, f.name)
print(len(partes))
