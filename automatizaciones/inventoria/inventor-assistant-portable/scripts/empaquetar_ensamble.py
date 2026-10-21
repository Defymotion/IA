"""Deja un ensamble AUTOCONTENIDO: copia a <carpeta base>\\Comerciales todos los archivos que referencia (en
cualquier nivel) que estén fuera de la carpeta base, y repunta las referencias a esas copias. Los originales no
se tocan. Opcional: genera un .zip de la carpeta (sin OldVersions) para enviar.

Uso: python empaquetar_ensamble.py "<ensamble.iam>" [--base "<carpeta>"] [--sub Comerciales] [--zip]
  --base: carpeta que tiene que contener todo (por defecto, la carpeta padre de la del ensamble).
"""
import argparse
import json
import os
import shutil
import stat
import sys
import zipfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
import inventor_mcp as inv  # noqa: E402

a = argparse.ArgumentParser()
a.add_argument("ensamble")
a.add_argument("--base", default="")
a.add_argument("--sub", default="Comerciales")
a.add_argument("--zip", action="store_true")
x = a.parse_args()
S = inv._safe
top_path = Path(x.ensamble).resolve()
base = Path(x.base).resolve() if x.base else top_path.parent.parent
dest_dir = base / x.sub
dest_dir.mkdir(parents=True, exist_ok=True)
app = inv._inventor(start_if_needed=False)
app.SilentOperation = True
log = {"base": str(base), "copiados": {}, "repuntadas": [], "errores": [], "externos_final": []}


def dentro(p: Path) -> bool:
    try:
        p.resolve().relative_to(base)
        return True
    except ValueError:
        return False


def destino(src: Path) -> Path:
    key = str(src.resolve()).lower()
    if key in log["copiados"]:
        return Path(log["copiados"][key])
    usados = {v.lower() for v in log["copiados"].values()}
    d, i = dest_dir / src.name, 1
    while str(d).lower() in usados or (d.exists() and d.stat().st_size != src.stat().st_size):
        d = dest_dir / f"{src.stem}_{i}{src.suffix}"          # mismo nombre, archivo distinto
        i += 1
    if not d.exists():
        shutil.copy2(src, d)
    os.chmod(d, stat.S_IWRITE | stat.S_IREAD)          # las piezas de biblioteca vienen de solo lectura
    log["copiados"][key] = str(d)
    return d


top = app.Documents.Open(str(top_path), False)
for vuelta in range(6):
    cambios = 0
    docs = [top] + list(inv._items(top.AllReferencedDocuments))
    for d in docs:
        if not dentro(Path(d.FullFileName)):
            continue                                      # se procesa su copia, no el original
        for fd in inv._items(S(lambda: d.File.ReferencedFileDescriptors, []) or []):
            src = Path(S(lambda: fd.FullFileName, "") or "")
            if not src.name or dentro(src):
                continue
            if not src.exists():
                log["errores"].append(f"{Path(d.FullFileName).name}: no existe {src}")
                continue
            try:
                nuevo = destino(src)
                fd.ReplaceReference(str(nuevo))
                log["repuntadas"].append(f"{Path(d.FullFileName).name}: {src.name} -> {nuevo.relative_to(base)}")
                cambios += 1
            except Exception as exc:  # noqa: BLE001
                log["errores"].append(f"{Path(d.FullFileName).name} / {src.name}: {exc!r}")
    if cambios == 0:
        break
    top.Update()
# guardar: el principal con sus dependientes (ReplaceReference en un subensamble no siempre lo marca "Dirty")
guardados = []
for d in [top] + list(inv._items(top.AllReferencedDocuments)):
    if dentro(Path(d.FullFileName)) and d.DocumentType == inv.K_ASSEMBLY_DOCUMENT:
        try:
            d.Save2(True)
            guardados.append(Path(d.FullFileName).name)
        except Exception as exc:  # noqa: BLE001
            log["errores"].append(f"Guardar {Path(d.FullFileName).name}: {exc!r}")
log["guardados"] = guardados
# control final DESDE EL DISCO: cerrar lo de la carpeta y volver a abrir el principal
S(lambda: top.Close(True))                       # cierra también lo que referencia (si nadie más lo usa)
for d in list(inv._items(app.Documents)):
    if dentro(Path(S(lambda: d.FullFileName, "") or "C:/")):
        S(lambda: d.Close(True))
top = app.Documents.Open(str(top_path), False)
for d in inv._items(top.AllReferencedDocuments):
    if not dentro(Path(d.FullFileName)):
        log["externos_final"].append(d.FullFileName)
log["documentos_en_carpeta"] = len(list(inv._items(top.AllReferencedDocuments))) - len(log["externos_final"])
log["faltantes"] = [Path(S(lambda: fd.FullFileName, "?")).name for d in [top] + list(inv._items(top.AllReferencedDocuments))
                    for fd in inv._items(S(lambda: d.File.ReferencedFileDescriptors, []) or [])
                    if not S(lambda: fd.ReferenceMissing, False) is False]
S(lambda: top.Close(True))
S(lambda: setattr(app, "SilentOperation", False))
if x.zip and not log["externos_final"]:
    zp = base.parent / f"{base.name}.zip"
    with zipfile.ZipFile(zp, "w", zipfile.ZIP_DEFLATED) as z:
        for f in base.rglob("*"):
            if f.is_file() and "oldversions" not in [p.lower() for p in f.parts] and f.suffix.lower() != ".lck":
                z.write(f, Path(base.name) / f.relative_to(base))
    log["zip"] = {"ruta": str(zp), "mb": round(zp.stat().st_size / 1e6, 1)}
log["copiados"] = sorted(Path(v).name for v in log["copiados"].values())
print(json.dumps(log, ensure_ascii=False, indent=1))
