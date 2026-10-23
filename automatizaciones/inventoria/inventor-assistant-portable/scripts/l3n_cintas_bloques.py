"""L3N celda A: reemplaza en el layout los módulos BM2000 / "a medida" por los bloques de cinta generados con
cinta_modular.py (Celdas_IA\\Cintas\\<nombre>\\<nombre>.iam).
  - Cinta_Llegada_A.iam: T1, T2 y T3 (banda 203,5) en lugar de BM2000_T* y *_amedida_*; las curvas no se tocan.
  - Celda_A_L3N.iam: BM2000_CeldaA_1 y _2 -> una sola Cinta_Interna_CeldaA (424,8, ruedas), mismo inicio y eje.
Sólo edita archivos propios (Celdas_IA). Uso: python l3n_cintas_bloques.py
"""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
import inventor_mcp as inv  # noqa: E402

S = inv._safe
PROY = Path(r"C:\DEFYMOTION\L3N\Celdas_IA")
CINTA = PROY / "Cinta_Llegada_A.iam"
CELDA = PROY / "Celda_A_L3N.iam"
BLOQ = PROY / "Cintas"
ORG_A = (-6503.2, 0.0, -35622.3)
R = 475.0
X_T1, Z_T1_INI, Z_T2, X_T3, Z_T3_FIN = 4363.0, -20922.0, -30529.0, -12134.0, -37021.0
Z_EJE_INTERNA = -36697.0
INTERNA = sys.argv[1] if len(sys.argv) > 1 else "Cinta_Interna_CeldaA"
ALT = dict(a.split("=", 1) for a in sys.argv[2:] if "=" in a)      # p. ej. T3=Cinta_Llegada_T3b
TRAMOS = [("T1", (X_T1, Z_T1_INI), (X_T1, Z_T2 + R)),
          ("T2", (X_T1 - R, Z_T2), (X_T3 + R, Z_T2)),
          ("T3", (X_T3, Z_T2 - R), (X_T3, Z_T3_FIN))]

app = inv._inventor(start_if_needed=False)
tg = app.TransientGeometry
log = {"avisos": []}


def mmake(M):
    m = tg.CreateMatrix()
    m.SetCoordinateSystem(tg.CreatePoint(M[0][3] / 10, M[1][3] / 10, M[2][3] / 10),
                          tg.CreateVector(M[0][0], M[1][0], M[2][0]), tg.CreateVector(M[0][1], M[1][1], M[2][1]),
                          tg.CreateVector(M[0][2], M[1][2], M[2][2]))
    return m


def caja(o):
    b = o.RangeBox
    return [round(v * 10, 1) for v in (b.MinPoint.X, b.MinPoint.Y, b.MinPoint.Z, b.MaxPoint.X, b.MaxPoint.Y, b.MaxPoint.Z)]


def abrir(p):
    d = next((d for d in inv._items(app.Documents) if S(lambda: Path(d.FullFileName).resolve() == p.resolve(), False)), None)
    return d or app.Documents.Open(str(p), False)


def bloque(nombre):
    r = BLOQ / nombre / f"{nombre}.iam"
    if not r.exists():
        raise FileNotFoundError(r)
    return str(r)


app.SilentOperation = True
try:
    # ---------------------------------------------------------------- 1. cinta de llegada
    cin = abrir(CINTA)
    cd = cin.ComponentDefinition
    borradas = []
    for o in list(inv._items(cd.Occurrences)):
        n = o.Name
        if n.startswith("BM2000_") or "_amedida_" in n or n.startswith("Cinta_Llegada_T"):
            borradas.append(n)
            o.Delete()
    log["llegada_borradas"] = borradas
    log["tramos"] = []
    for nombre, p0, p1 in TRAMOS:
        dx, dz = p1[0] - p0[0], p1[1] - p0[1]
        L = (dx * dx + dz * dz) ** 0.5
        d = (dx / L, dz / L)
        nrm = (-d[1], d[0])                     # Z local = X × Y (lado del motor)
        M = [[d[0], 0.0, nrm[0], p0[0] - ORG_A[0]], [0.0, 1.0, 0.0, 0.0], [d[1], 0.0, nrm[1], p0[1] - ORG_A[2]]]
        o = cd.Occurrences.Add(bloque(ALT.get(nombre, f"Cinta_Llegada_{nombre}")), mmake(M))
        S(lambda: setattr(o, "Name", f"Cinta_Llegada_{nombre}"))
        S(lambda: setattr(o, "Grounded", True))
        log["tramos"].append({"tramo": nombre, "largo_recorrido": round(L), "caja": caja(o)})
    cin.Update()
    cin.Save()
    log["llegada_ocurrencias"] = [o.Name for o in inv._items(cd.Occurrences)]
    # ---------------------------------------------------------------- 2. cinta interna de la celda
    cel = abrir(CELDA)
    cd = cel.ComponentDefinition
    bms = [o for o in inv._items(cd.Occurrences) if o.Name.startswith("BM2000_CeldaA") or o.Name.startswith("Cinta_Interna_CeldaA")]
    if not bms:
        raise RuntimeError("No encontré BM2000_CeldaA_* en la celda")
    cajas = [caja(o) for o in bms]
    x0 = min(c[0] for c in cajas)
    x1 = max(c[3] for c in cajas)
    log["interna_vieja"] = {"ocurrencias": [o.Name for o in bms], "x0": x0, "x1": x1, "largo": round(x1 - x0, 1),
                            "z": [min(c[2] for c in cajas), max(c[5] for c in cajas)]}
    for o in bms:
        o.Delete()
    z_eje = Z_EJE_INTERNA - ORG_A[2]
    M = [[1.0, 0.0, 0.0, x0], [0.0, 1.0, 0.0, 0.0], [0.0, 0.0, 1.0, z_eje]]
    o = cd.Occurrences.Add(bloque(INTERNA), mmake(M))
    S(lambda: setattr(o, "Name", "Cinta_Interna_CeldaA"))
    S(lambda: setattr(o, "Grounded", True))
    log["interna_nueva"] = caja(o)
    caj = next((c for c in inv._items(cd.Occurrences) if c.Name.startswith("IA_Caja_en_cinta")), None)
    if caj is not None:
        b0 = caja(caj)
        dz = z_eje - (b0[2] + b0[5]) / 2               # centrar la caja de muestra en el eje de la banda
        if abs(dz) > 0.5:
            m = caj.Transformation
            m.SetTranslation(tg.CreateVector(m.Translation.X, m.Translation.Y, m.Translation.Z + dz / 10), False)
            S(lambda: setattr(caj, "Grounded", False))
            caj.SetTransformWithoutConstraints(m)
            S(lambda: setattr(caj, "Grounded", True))
        log["caja_en_cinta"] = {"antes": b0, "despues": caja(caj)}
    cel.Update()
    cel.Save()
finally:
    S(lambda: setattr(app, "SilentOperation", False))
print(json.dumps(log, ensure_ascii=False, indent=1))
