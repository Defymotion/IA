"""Limpia Celda_A_L3N.iam (archivo propio) con el layout cerrado: borra ocurrencias sobrantes del gripper
(`Gripper_GRIPPER_7xTBA250:N`, restos de corridas fallidas) y deja suprimido + oculto el gripper de ADECO2.
Uso: python l3n_limpiar_celdaA.py
"""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
import inventor_mcp as inv  # noqa: E402

S = inv._safe
CELDA = Path(r"C:\DEFYMOTION\L3N\Celdas_IA\Celda_A_L3N.iam")
PROPIAS = (r"c:\defymotion\l3n\celdas_ia", r"c:\defymotion\l3n\estudio_ia", str(Path.home() / "Documents" / "InventorIA" / "Generados").lower())
app = inv._inventor(start_if_needed=False)
app.SilentOperation = True
res = {"cerrados": [], "borrados": [], "suprimidos": [], "avisos": []}
try:
    for d in list(inv._items(app.Documents)):
        f = str(S(lambda: d.FullFileName, "")).lower()
        if f.startswith(PROPIAS) and S(lambda: d.Views.Count, 0):
            S(lambda: d.Close(True))
            res["cerrados"].append(f)
    for _ in range(3):
        S(lambda: app.Documents.CloseAll(True))
    doc = app.Documents.Open(str(CELDA), True)
    cd = doc.ComponentDefinition
    for o in list(inv._items(cd.Occurrences)):
        n = o.Name
        if n.startswith("Gripper_GRIPPER_7xTBA250"):
            try:
                o.Delete()
                res["borrados"].append(n)
            except Exception as e:  # noqa: BLE001
                res["avisos"].append(f"{n}: {e!r}")
        elif n.startswith("Gripper_ADECO2"):
            S(lambda: setattr(o, "Visible", False))
            ok = S(lambda: o.Suppress(), None)
            res["suprimidos"].append(f"{n} (sup={bool(S(lambda: o.Suppressed, False))})")
    doc.Update()
    doc.Save()
    res["ocurrencias"] = [o.Name for o in inv._items(cd.Occurrences) if "ripper" in o.Name]
    doc.Close(True)
finally:
    S(lambda: setattr(app, "SilentOperation", False))
print(json.dumps(res, ensure_ascii=False, indent=1))
