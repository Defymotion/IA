"""L3N: (1) copia Celda_A_L3N.iam -> <copia> corriendo hacia atrás (en X, mm) las mesas de rolos, el pallet, la barrera de
salida y la reja este, para que la cruz A quede alineada con las camas de B/C sin chocar; (2) borra la franja rayada
(Pasarela:1) de Linea_Pallets.iam con respaldo previo en Celdas_IA\\_respaldos. El original de la celda no se toca.
Uso: python l3n_celda_a_v6.py <plan.json>   (plan: {"copia": ruta, "mover": [[prefijo, dx], ...], "borrar_linea": [nombres]})
"""
import json
import shutil
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
import inventor_mcp as inv  # noqa: E402

S = inv._safe
plan = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
CELDAS = Path(r"C:\DEFYMOTION\L3N\Celdas_IA")
CA = CELDAS / "Celda_A_L3N.iam"
COPIA = Path(plan["copia"])
LINEA = CELDAS / "Linea_Pallets.iam"
app = inv._inventor(start_if_needed=False)
tg = app.TransientGeometry
log = {"movidos": [], "borrados": [], "avisos": []}


def abierto(r):
    return next((d for d in inv._items(app.Documents) if S(lambda d=d: Path(d.FullFileName).resolve() == Path(r).resolve(), False)), None)


app.SilentOperation = True
try:
    # ---------------------------------------------------------------- 1. copia de la celda A
    d = abierto(CA)
    if d is None:
        d = app.Documents.Open(str(CA), False)
    if not COPIA.exists():
        d.SaveAs(str(COPIA), True)
    c = abierto(COPIA)
    propio = c is None
    if propio:
        c = app.Documents.Open(str(COPIA), False)
    for o in inv._items(c.ComponentDefinition.Occurrences):
        for pref, dx in plan["mover"]:
            if o.Name.startswith(pref):
                M = o.Transformation
                M.SetCell(1, 4, M.Cell(1, 4) + dx / 10.0)
                g = S(lambda: o.Grounded, False)
                S(lambda: setattr(o, "Grounded", False))
                o.Transformation = M
                S(lambda: setattr(o, "Grounded", g))
                log["movidos"].append([o.Name, dx])
                break
    c.Save()
    if propio:
        S(lambda: c.Close(True))
    # ---------------------------------------------------------------- 2. franja rayada fuera de la línea de camas
    resp = CELDAS / "_respaldos"
    resp.mkdir(exist_ok=True)
    shutil.copy2(LINEA, resp / f"Linea_Pallets_antes_borrar_franja_{time.strftime('%Y%m%d_%H%M')}.iam")
    lp = abierto(LINEA)
    propio = lp is None
    if propio:
        lp = app.Documents.Open(str(LINEA), False)
    for o in list(inv._items(lp.ComponentDefinition.Occurrences)):
        if o.Name in plan.get("borrar_linea", []):
            n = o.Name
            o.Delete()
            log["borrados"].append(n)
    lp.Save()
    if propio:
        S(lambda: lp.Close(True))
finally:
    app.SilentOperation = False
print(json.dumps(log, ensure_ascii=False, indent=1))
