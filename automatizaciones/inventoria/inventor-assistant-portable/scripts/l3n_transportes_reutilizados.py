"""L3N: arma Celdas_IA\\Transportes_reutilizados\\Linea_Pallets_Reutilizada.iam con los módulos de transporte nuevos
(del 3D del proveedor, sin copiarlos ni tocarlos) ubicados sobre el recorrido de nuestra línea de pallets según un plan
(matrices en mm calculadas aparte), lo inserta en LayoutL3N_Celdas.iam (respaldo previo del .iam) y oculta, sólo en el
layout, las camas de rodillos que reemplaza. Informa la caja de cada módulo y los choques por caja con celdas y robot aéreo.
Uso: python l3n_transportes_reutilizados.py <plan.json> [--rehacer]
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
REHACER = "--rehacer" in sys.argv
CELDAS = Path(r"C:\DEFYMOTION\L3N\Celdas_IA")
LAY = CELDAS / "LayoutL3N_Celdas.iam"
DIR = CELDAS / "Transportes_reutilizados"
SUB = DIR / "Linea_Pallets_Reutilizada.iam"
NOMBRE_OCC = "IA_Linea_Pallets_Reutilizada"
REEMPLAZADAS = ["IA_Cama_BC_1", "IA_Cama_L2920_3", "Roller_Conveyor_Straight_400V_FlatBelt:2",
                "Roller_Conveyor_Straight_400V_FlatBelt:7", "IA_Cama_L2648_5", "Roller_Conveyor_Straight_400V_FlatBelt:4",
                "Roller_Conveyor_Straight_400V_FlatBelt:8", "Roller_Conveyor_Straight_400V_FlatBelt:6",
                "Roller_Conveyor_Straight_400V_FlatBelt:10", "Roller_Conveyor_Straight_400V_FlatBelt:11",
                "Roller_Conveyor_Straight_400V_FlatBelt:9", "IA_Cama_linea_1", "IA_Cama_L3320_IA_Cama_linea_3"]
app = inv._inventor(start_if_needed=False)
tg = app.TransientGeometry
log = {"modulos": [], "avisos": [], "choques_caja": []}
T0 = time.time()


def matriz(m):
    M = tg.CreateMatrix()
    for i in range(3):
        for j in range(4):
            M.SetCell(i + 1, j + 1, m[i * 4 + j] / (10.0 if j == 3 else 1.0))
    return M


def caja(b):
    return [round(b.MinPoint.X * 10, 1), round(b.MinPoint.Y * 10, 1), round(b.MinPoint.Z * 10, 1),
            round(b.MaxPoint.X * 10, 1), round(b.MaxPoint.Y * 10, 1), round(b.MaxPoint.Z * 10, 1)]


def solapa(a, b, tol=1.0):
    return all(a[i] < b[i + 3] - tol and b[i] < a[i + 3] - tol for i in range(3))


app.SilentOperation = True
try:
    DIR.mkdir(parents=True, exist_ok=True)
    # ---------------------------------------------------------------- subensamble con los módulos
    if REHACER or not SUB.exists():
        sub = app.Documents.Add(12291, app.FileManager.GetTemplateFile(12291), False)
        occs = sub.ComponentDefinition.Occurrences
        for m in plan["modulos"]:
            try:
                o = occs.Add(m["archivo"], matriz(m["M_mm"]))
                o.Grounded = True
                S(lambda: setattr(o, "Name", f'{m["tramo"].replace(" ", "_")}_{m["nombre"]}_{len(log["modulos"]) + 1}'))
                log["modulos"].append({"tramo": m["tramo"], "occ": o.Name, "caja": caja(o.RangeBox)})
            except Exception as ex:  # noqa: BLE001
                log["avisos"].append(f'{m["nombre"]}: {ex!r}'[:200])
        sub.SaveAs(str(SUB), False)
        sub.Close(True)
    # ---------------------------------------------------------------- layout (respaldo + inserción)
    lay = next((d for d in inv._items(app.Documents) if S(lambda d=d: Path(d.FullFileName).resolve() == LAY.resolve(), False)), None)
    abierto = lay is not None
    if not abierto:
        resp = CELDAS / "_respaldos"
        resp.mkdir(exist_ok=True)
        shutil.copy2(LAY, resp / f"LayoutL3N_Celdas_antes_transportes_{time.strftime('%Y%m%d_%H%M')}.iam")
        lay = app.Documents.Open(str(LAY), False)
    else:
        log["avisos"].append("el layout estaba abierto: se trabajó sobre la sesión abierta (sin respaldo de archivo)")
    cd = lay.ComponentDefinition
    viejo = next((o for o in inv._items(cd.Occurrences) if o.Name == NOMBRE_OCC), None)
    if viejo is not None:
        viejo.Delete()
    o = cd.Occurrences.Add(str(SUB), tg.CreateMatrix())
    o.Grounded = True
    o.Name = NOMBRE_OCC
    log["caja_linea_nueva"] = caja(o.RangeBox)
    # ocultar las camas reemplazadas (sólo visibilidad en el layout)
    lp = next((x for x in inv._items(cd.Occurrences) if x.Name == "Linea_Pallets:1"), None)
    ocultas = []
    if lp is not None:
        for s in inv._items(lp.SubOccurrences):
            if s.Name in REEMPLAZADAS:
                S(lambda s=s: setattr(s, "Visible", False))
                ocultas.append(s.Name)
    log["camas_ocultas"] = ocultas
    # choques por caja de cada módulo contra subocurrencias de celdas y robot aéreo
    otras = []
    for x in inv._items(cd.Occurrences):
        if x.Name in ("Celda_A_L3N:1", "Celda_B_existente:1", "Celda_C_existente:1", "Robot_Aereo_Pallets:1", "Paredes:1"):
            for s in inv._items(x.SubOccurrences):
                if S(lambda s=s: s.Visible, True):
                    c = S(lambda s=s: caja(s.RangeBox), None)
                    if c:
                        otras.append((x.Name + "/" + s.Name, c))
        if x.Name == "Linea_Pallets:1":
            for s in inv._items(x.SubOccurrences):
                if s.Name not in REEMPLAZADAS and S(lambda s=s: s.Visible, True):
                    c = S(lambda s=s: caja(s.RangeBox), None)
                    if c:
                        otras.append(("Linea_Pallets/" + s.Name, c))
    for s in inv._items(o.SubOccurrences):
        cs = caja(s.RangeBox)
        for n, c in otras:
            if solapa(cs, c):
                log["choques_caja"].append([s.Name, n, c])
    lay.Save()
    if not abierto:
        S(lambda: lay.Close(True))
finally:
    app.SilentOperation = False
log["s"] = round(time.time() - T0, 1)
out = Path(r"C:\Users\nm\Documents\InventorIA\Analisis\L3N\transportes_nuevos\insercion.json")
out.write_text(json.dumps(log, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps(log, ensure_ascii=False, indent=1)[:15000])
