"""Sólo lectura: estado del KUKA y del gripper en Celda_A_L3N. Para cada sub-ocurrencia del robot (hasta 2 niveles):
caja, matriz, suprimida/visible, y si es flexible / tiene restricciones; brida de V05 (punto y normal según
l3n_montar_gripper) y la brida del gripper. Uso: python l3n_diag_robot.py <salida.json>
"""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
import inventor_mcp as inv  # noqa: E402

S = inv._safe
CELDA = Path(r"C:\DEFYMOTION\L3N\Celdas_IA\Celda_A_L3N.iam")
salida = Path(sys.argv[1])
app = inv._inventor(start_if_needed=False)
app.SilentOperation = True
res = {}


def caja(o):
    b = o.RangeBox
    return [round(v * 10, 1) for v in (b.MinPoint.X, b.MinPoint.Y, b.MinPoint.Z, b.MaxPoint.X, b.MaxPoint.Y, b.MaxPoint.Z)]


def mread(m):
    return [[round(m.Cell(r, c) * (10 if c == 4 else 1), 4) for c in range(1, 5)] for r in range(1, 4)]


try:
    cel = next((d for d in inv._items(app.Documents) if S(lambda: Path(d.FullFileName).resolve() == CELDA.resolve(), False)), None)
    cel = cel or app.Documents.Open(str(CELDA), False)
    cd = cel.ComponentDefinition
    robot = next(o for o in inv._items(cd.Occurrences) if o.Name.startswith("KUKA"))
    res["robot"] = {"nombre": robot.Name, "caja": caja(robot), "M": mread(robot.Transformation),
                    "flexible": S(lambda: robot.Flexible), "archivo": S(lambda: robot.ReferencedDocumentDescriptor.FullDocumentName),
                    "rep_posicional": S(lambda: robot.ActivePositionalRepresentation),
                    "n_restr_robot_doc": S(lambda: robot.Definition.Constraints.Count),
                    "n_juntas_robot_doc": S(lambda: robot.Definition.Joints.Count)}
    subs = []

    def rec(occ, prof):
        for s in inv._items(occ.SubOccurrences):
            subs.append({"ruta": "/".join(x.Name for x in s.OccurrencePath), "caja": S(lambda: caja(s)),
                         "M": S(lambda: mread(s.Transformation)), "suprimida": S(lambda: s.Suppressed),
                         "visible": S(lambda: s.Visible), "fijada": S(lambda: s.Grounded)})
            if prof < 1 and S(lambda: s.SubOccurrences.Count, 0):
                rec(s, prof + 1)

    rec(robot, 0)
    res["subs"] = subs
    v05 = next((s for s in inv._items(robot.SubOccurrences) if "v05" in s.Name.lower()), None)
    if v05 is not None:
        Mv = mread(v05.Transformation)
        PL, NL = (1850.0, 0.0, 1745.0), (0.0, 0.0, -1.0)
        res["brida_robot"] = {"P": [round(sum(Mv[i][k] * PL[k] for k in range(3)) + Mv[i][3], 1) for i in range(3)],
                              "n": [round(sum(Mv[i][k] * NL[k] for k in range(3)), 4) for i in range(3)]}
    # restricciones del robot en la celda (si hay)
    res["restr_celda_robot"] = [c.Name for c in inv._items(cd.Constraints)
                                if robot.Name in (S(lambda: c.OccurrenceOne.Name, ""), S(lambda: c.OccurrenceTwo.Name, ""))]
    g = next((o for o in inv._items(cd.Occurrences) if o.Name.startswith("IA_Gripper")), None)
    if g is not None:
        res["gripper"] = {"caja": caja(g), "M": mread(g.Transformation)}
        b = next((s for s in inv._items(g.SubOccurrences) if s.Name.lower().startswith("brida")), None)
        if b is not None:
            res["gripper"]["brida_caja"] = caja(b)
finally:
    S(lambda: setattr(app, "SilentOperation", False))
salida.parent.mkdir(parents=True, exist_ok=True)
salida.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps({k: v for k, v in res.items() if k != "subs"}, ensure_ascii=False, indent=1))
print(json.dumps([[s["ruta"][-60:], s["caja"], s["suprimida"]] for s in res.get("subs", [])], ensure_ascii=False))
