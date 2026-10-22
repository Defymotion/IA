"""Sólo lectura: lista documentos con ventana (y los sin guardar) en Inventor. Uso: python listar_abiertos.py"""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
import inventor_mcp as inv  # noqa: E402

S = inv._safe
app = inv._inventor(start_if_needed=False)
out = []
for d in inv._items(app.Documents):
    v = S(lambda: d.Views.Count, 0)
    f = str(S(lambda: d.FullFileName, ""))
    if v or not f or S(lambda: d.Dirty, False):
        out.append({"nombre": S(lambda: d.DisplayName), "archivo": f, "ventanas": v, "sin_guardar": bool(S(lambda: d.Dirty, False))})
print(json.dumps({"total": app.Documents.Count, "con_ventana_o_sin_guardar": out}, ensure_ascii=False, indent=1))
