"""Sólo lectura. En LayoutL3N_Celdas.iam (abierto): releva las rejas de la celda B (ADECOAGRO2_Layout[Fademaq]) y las
puertas/rejas de A y C, y chequea solape de cajas (mm, coordenadas del layout) contra rieles, columnas y travesaños
del robot aéreo. Escribe Analisis\\L3N\\rejas.json. Uso: python l3n_chequeo_rejas.py
"""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
import inventor_mcp as inv  # noqa: E402

S = inv._safe
LAYOUT = Path(r"C:\DEFYMOTION\L3N\Celdas_IA\LayoutL3N_Celdas.iam")
SAL = Path.home() / "Documents" / "InventorIA" / "Analisis" / "L3N" / "rejas.json"
app = inv._inventor(start_if_needed=False)
doc = next(d for d in inv._items(app.Documents) if S(lambda: Path(d.FullFileName).resolve() == LAYOUT.resolve(), False))


def caja(o):
    b = o.RangeBox
    return [round(v * 10, 1) for v in (b.MinPoint.X, b.MinPoint.Y, b.MinPoint.Z, b.MaxPoint.X, b.MaxPoint.Y, b.MaxPoint.Z)]


def solapa(a, b, margen=0.0):
    return all(a[i] - margen < b[i + 3] and b[i] - margen < a[i + 3] for i in range(3))


top = {o.Name: o for o in inv._items(doc.ComponentDefinition.Occurrences)}
robot = next(o for n, o in top.items() if n.startswith("Robot_Aereo"))
obst = [{"n": s.Name, "caja": caja(s)} for s in inv._items(robot.SubOccurrences)
        if s.Name.startswith(("Riel", "Columna", "Travesano"))]
res = {"obstaculos": obst, "celdas": {}}
for n, o in top.items():
    if not n.startswith("Celda_"):
        continue
    filas = []
    for s in inv._items(o.SubOccurrences):
        nm = s.Name
        es_reja = nm.startswith(("Puerta", "ADECOAGRO2_Layout", "Reja", "Cerco", "Pared"))
        if not es_reja:
            continue
        c = caja(s)
        fila = {"n": nm, "caja": c, "alto": round(c[4]), "choca": [x["n"] for x in obst if solapa(c, x["caja"])]}
        if nm.startswith("ADECOAGRO2_Layout"):   # desglosar la reja Fademaq
            fila["hijos"] = []
            def walk(o, ruta, prof):
                for h in inv._items(o.SubOccurrences):
                    ch = S(lambda: caja(h))
                    if ch is None:
                        continue
                    ch_choca = [x["n"] for x in obst if solapa(ch, x["caja"])]
                    hijos = S(lambda: h.SubOccurrences.Count, 0)
                    if ch_choca and hijos and prof < 3:
                        walk(h, ruta + "/" + h.Name, prof + 1)      # desglosar sólo lo que choca
                    elif ch_choca or prof == 1:
                        fila["hijos"].append({"n": ruta + "/" + h.Name, "caja": ch, "alto": round(ch[4]), "choca": ch_choca})
            walk(s, "", 1)
        filas.append(fila)
    res["celdas"][n] = filas
SAL.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
resumen = {k: [(f["n"], f["alto"], f["choca"]) for f in v] for k, v in res["celdas"].items()}
print(json.dumps(resumen, ensure_ascii=False, indent=1)[:20000])
