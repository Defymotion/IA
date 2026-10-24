"""Lista lo que está oculto DENTRO de los archivos de celda (Celda_A_L3N, Celda_B_existente), en su propio contexto, hasta 3
niveles. En el layout esas ocultaciones no se ven (cada ensamble guarda su propia visibilidad), así que la escena de la
simulación las tiene que repetir. Escribe Analisis\\L3N\\ocultos_celdas.json. Uso: python l3n_listar_ocultos.py
"""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
import inventor_mcp as inv  # noqa: E402

S = inv._safe
CELDAS = {"Celda_A_L3N:1": Path(r"C:\DEFYMOTION\L3N\Celdas_IA\Celda_A_L3N.iam"),
          "Celda_B_existente:1": Path(r"C:\DEFYMOTION\L3N\Celdas_IA\Celda_B_existente.iam")}
OUT = Path.home() / "Documents" / "InventorIA" / "Analisis" / "L3N" / "ocultos_celdas.json"
app = inv._inventor(start_if_needed=False)
res = {}


def its(x):
    if x is None or isinstance(x, list):
        return x or []
    try:
        return inv._items(x)
    except Exception:  # noqa: BLE001
        return []


def recorrer(occs, pref, nivel, out):
    for o in occs:
        nm = pref + o.Name
        if not S(lambda: o.Visible, True):
            out.append(nm)
            continue
        if nivel < 3:
            recorrer(its(S(lambda: o.SubOccurrences, None)), nm + "/", nivel + 1, out)


app.SilentOperation = True
try:
    for clave, f in CELDAS.items():
        d = next((d for d in its(app.Documents) if S(lambda: Path(d.FullFileName).resolve() == f.resolve(), False)), None)
        d = d or app.Documents.Open(str(f), False)
        out = []
        recorrer(its(d.ComponentDefinition.Occurrences), "", 1, out)
        res[clave] = out
finally:
    S(lambda: setattr(app, "SilentOperation", False))
OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps(res, ensure_ascii=False, indent=1))
