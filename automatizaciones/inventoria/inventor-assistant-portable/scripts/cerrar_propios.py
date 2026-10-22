"""Cierra SIN guardar los documentos nuevos sin archivo (restos de scripts fallidos: 'PiezaNN', 'EnsamblajeNN') y los
de las carpetas propias indicadas; después suelta los no referenciados. No toca documentos del usuario con archivo
fuera de esas carpetas. Uso: python cerrar_propios.py [carpeta1;carpeta2]
"""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
import inventor_mcp as inv  # noqa: E402

S = inv._safe
carpetas = [c.lower().rstrip("\\") for c in (sys.argv[1].split(";") if len(sys.argv) > 1 else []) if c]
app = inv._inventor(start_if_needed=False)
app.SilentOperation = True
res = {"cerrados": []}
try:
    for d in list(inv._items(app.Documents)):
        f = str(S(lambda: d.FullFileName, ""))
        nombre = str(S(lambda: d.DisplayName, ""))
        propio = (not f and nombre.startswith(("Pieza", "Ensamblaje", "Part", "Assembly"))) or \
                 any(f.lower().startswith(c + "\\") for c in carpetas)
        if propio and (S(lambda: d.Views.Count, 0) or not f):
            S(lambda: d.Close(True))
            res["cerrados"].append(nombre or f)
    for _ in range(3):
        S(lambda: app.Documents.CloseAll(True))
    res["quedan"] = app.Documents.Count
finally:
    S(lambda: setattr(app, "SilentOperation", False))
print(json.dumps(res, ensure_ascii=False, indent=1))
