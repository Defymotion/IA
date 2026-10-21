"""Sólo en memoria (no guarda): cómo se mueven las palas móviles del gripper ADECO2.
- componentes de pala_movil_apriete (caja en coordenadas del gripper)
- restricciones del gripper que mueven cada pala móvil (se cambia el valor 5 mm, se mide y se vuelve)
- restricciones internas de pala_movil_apriete.iam que mueven alguna pieza
- planos de trabajo visibles en la escena de simulación (el plano verde)
Salida: Documents\\InventorIA\\Analisis\\palas_adeco.json"""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
import inventor_mcp as inv  # noqa: E402

S = inv._safe
DOCS = Path.home() / "Documents" / "InventorIA"
GRIP = DOCS / "12_ADECO2" / "Gripper" / "Gripper_ADECO2_V1.iam"
app = inv._inventor(start_if_needed=False)
app.SilentOperation = True


def abrir(p):
    for d in inv._items(app.Documents):
        if S(lambda: Path(d.FullFileName).resolve() == Path(p).resolve(), False):
            return d
    return app.Documents.Open(str(p), False)


def caja(o):
    b = o.RangeBox
    return [round(b.MinPoint.X * 10, 1), round(b.MinPoint.Y * 10, 1), round(b.MinPoint.Z * 10, 1),
            round(b.MaxPoint.X * 10, 1), round(b.MaxPoint.Y * 10, 1), round(b.MaxPoint.Z * 10, 1)]


res = {}
gd = abrir(GRIP)
cd = gd.ComponentDefinition
palas = [o for o in inv._items(cd.Occurrences) if o.Name.startswith("pala_movil_apriete")]
res["palas"] = {o.Name: {"caja": caja(o), "subs": [{"nombre": s.Name, "caja": caja(s)}
                                                 for s in inv._items(o.SubOccurrences)]} for o in palas}
# restricciones del gripper que mueven pala_movil_apriete:1
p1 = palas[0]
mov = []
for c in inv._items(cd.Constraints):
    nombres = (S(lambda: c.OccurrenceOne.Name, ""), S(lambda: c.OccurrenceTwo.Name, ""))
    off = S(lambda: c.Offset)
    if off is None or not any(n and n.startswith("pala_movil_apriete") for n in nombres):
        continue
    v0 = off.Value
    antes = {o.Name: caja(o) for o in palas}
    try:
        off.Value = v0 + 0.5
        gd.Update()
        despues = {o.Name: caja(o) for o in palas}
        delta = {k: [round(despues[k][i] - antes[k][i], 1) for i in range(3)] for k in antes
                 if any(abs(despues[k][i] - antes[k][i]) > 0.1 for i in range(3))}
    finally:
        off.Value = v0
        gd.Update()
    mov.append({"nombre": c.Name, "occ": nombres, "valor_mm": round(v0 * 10, 2), "mueve": delta})
res["restricciones_gripper"] = mov
# restricciones internas de la pala móvil
pd = p1.Definition.Document
pcd = pd.ComponentDefinition
subs = list(inv._items(pcd.Occurrences))
interno = []
for c in inv._items(pcd.Constraints):
    off = S(lambda: c.Offset)
    if off is None:
        continue
    v0 = off.Value
    antes = {o.Name: caja(o) for o in subs}
    try:
        off.Value = v0 + 0.5
        pd.Update()
        despues = {o.Name: caja(o) for o in subs}
        delta = {k: [round(despues[k][i] - antes[k][i], 1) for i in range(3)] for k in antes
                 if any(abs(despues[k][i] - antes[k][i]) > 0.1 for i in range(3))}
    finally:
        off.Value = v0
        pd.Update()
    interno.append({"nombre": c.Name, "occ": (S(lambda: c.OccurrenceOne.Name), S(lambda: c.OccurrenceTwo.Name)),
                    "valor_mm": round(v0 * 10, 2), "mueve": delta})
res["restricciones_internas"] = interno
res["subs_internos"] = {o.Name: caja(o) for o in subs}
# planos de trabajo visibles en la escena
esc = DOCS / "Generados" / "ADECO_SIM" / "ADECO_simulacion.iam"
if esc.exists():
    sd = abrir(esc)
    vis = []

    def recorrer(occs, camino):
        for o in inv._items(occs):
            if not S(lambda: o.Visible, False):
                continue
            d = S(lambda: o.Definition)
            for wp in inv._items(S(lambda: d.WorkPlanes) or app.TransientObjects.CreateObjectCollection()):
                if S(lambda: wp.Visible, False):
                    vis.append(f"{camino}/{o.Name}: {wp.Name}")
            if S(lambda: o.SubOccurrences.Count, 0):
                recorrer(o.SubOccurrences, f"{camino}/{o.Name}")
    recorrer(sd.ComponentDefinition.Occurrences, "")
    for wp in inv._items(sd.ComponentDefinition.WorkPlanes):
        if S(lambda: wp.Visible, False):
            vis.append(f"(escena): {wp.Name}")
    res["planos_visibles"] = vis[:60]
app.SilentOperation = False
(DOCS / "Analisis" / "palas_adeco.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps({"gripper": len(mov), "interno": len(interno), "planos": len(res.get("planos_visibles", []))}))
