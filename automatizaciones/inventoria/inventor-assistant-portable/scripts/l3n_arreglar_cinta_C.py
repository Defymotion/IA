"""Celda C: vuelve a poner los 2 módulos BM2000 de la cinta interna (misma matriz que en la celda A, ambas celdas
tienen la misma disposición relativa a su giratoria) desde la biblioteca de Documents, e informa qué documentos
siguen referenciando la copia borrada. Uso: python l3n_arreglar_cinta_C.py
"""
import atexit
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
import inventor_mcp as inv  # noqa: E402

S = inv._safe
BASE = Path(r"C:\DEFYMOTION\L3N\Celdas_IA")
CELDA_A, CELDA_C = BASE / "Celda_A_L3N.iam", BASE / "Celda_C_existente.iam"
BM2000 = Path.home() / "Documents" / "InventorIA" / "Cintas Transportadoras" / "Banda Modular 2000" / "Ensamblaje BM2000.iam"
VIEJA = "_descartar_copia_bm2000"
app = inv._inventor(start_if_needed=False)
atexit.register(lambda: S(lambda: setattr(app, "SilentOperation", False)))
app.SilentOperation = True
tg = app.TransientGeometry


def abrir(p):
    d = next((d for d in inv._items(app.Documents) if S(lambda: Path(d.FullFileName).resolve() == p.resolve(), False)), None)
    return d or app.Documents.Open(str(p), False)


res = {}
A = abrir(CELDA_A)
mats = {}
for o in inv._items(A.ComponentDefinition.Occurrences):
    if o.Name.startswith("BM2000_CeldaA_"):
        M = tg.CreateMatrix()
        M.PutMatrixData(o.Transformation.GetMatrixData())
        mats[o.Name.replace("CeldaA", "CeldaC")] = M
C = abrir(CELDA_C)
cd = C.ComponentDefinition
ya = {o.Name for o in inv._items(cd.Occurrences)}
puestos = []
for nombre, M in mats.items():
    if nombre in ya:
        continue
    o = cd.Occurrences.Add(str(BM2000), M)
    S(lambda: setattr(o, "Name", nombre))
    o.Grounded = True
    puestos.append((nombre, str(o.ReferencedDocumentDescriptor.FullDocumentName)))
C.Update()
C.Save()
res["puestos"] = puestos
S(lambda: app.Documents.CloseAll(True))
quien = {}
for d in inv._items(app.Documents):
    f = str(S(lambda: d.FullFileName, ""))
    if VIEJA in f.lower() and f.lower().endswith("ensamblaje bm2000.iam"):
        quien[f] = [str(S(lambda: r.FullFileName, "")) for r in inv._items(S(lambda: d.ReferencingDocuments, []) or [])]
res["quien_referencia_la_copia_vieja"] = quien
res["abiertos_con_ventana"] = [str(d.FullFileName) for d in inv._items(app.Documents) if S(lambda: d.Views.Count, 0)]
print(json.dumps(res, ensure_ascii=False, indent=1))
