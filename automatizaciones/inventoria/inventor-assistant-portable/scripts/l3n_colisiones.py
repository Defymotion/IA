"""Sólo lectura (no guarda): choques de los transportes y la extensión del robot contra todo lo demás en el layout liviano.
1. Filtro por cajas: hojas visibles de cada grupo (celdas, línea, robot, paredes) contra cada módulo de transporte.
2. AnalyzeInterference sólo con los pares candidatos (ensamble estático, sin animación) -> volumen y caja del choque.
3. Releva la envolvedora MP402 (hojas y cajas) para ubicarla después.
Uso: python l3n_colisiones.py <iam> <salida.json> [--tol mm]
"""
import json
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
import inventor_mcp as inv  # noqa: E402

S = inv._safe
ruta, salida = Path(sys.argv[1]), Path(sys.argv[2])
TOL = float(sys.argv[sys.argv.index("--tol") + 1]) if "--tol" in sys.argv else 1.0
app = inv._inventor(start_if_needed=False)
T0 = time.time()
res = {"pares_caja": 0, "choques": [], "cerca_caja": [], "mp402": [], "avisos": []}


def caja(b):
    return [round(b.MinPoint.X * 10, 1), round(b.MinPoint.Y * 10, 1), round(b.MinPoint.Z * 10, 1),
            round(b.MaxPoint.X * 10, 1), round(b.MaxPoint.Y * 10, 1), round(b.MaxPoint.Z * 10, 1)]


def solapa(a, b, tol):
    return all(a[i] < b[i + 3] - tol and b[i] < a[i + 3] - tol for i in range(3))


def hojas(o, camino, out, forzar_visible=False):
    if not forzar_visible and not S(lambda: o.Visible, True):
        return
    if S(lambda: o.Suppressed, False):
        return
    subs = S(lambda: o.SubOccurrences, None)
    n = S(lambda: subs.Count, 0) if subs is not None else 0
    if n:
        for s in inv._items(subs):
            hojas(s, camino + "/" + s.Name, out, forzar_visible)
    else:
        c = S(lambda: caja(o.RangeBox), None)
        if c and (c[3] - c[0]) > 0.1:
            out.append((camino, o, c))


app.SilentOperation = True
try:
    doc = next((d for d in inv._items(app.Documents) if S(lambda d=d: Path(d.FullFileName).resolve() == ruta.resolve(), False)), None)
    if doc is None:
        doc = app.Documents.Open(str(ruta), True)
    cd = doc.ComponentDefinition
    tops = list(inv._items(cd.Occurrences))
    A, B = [], []
    for o in tops:
        n = o.Name
        if n.startswith(("Cruz_", "T1_", "T2_", "T3_")):
            A.append((n, o, caja(o.RangeBox)))
        elif n.startswith("Extension_"):
            hojas(o, n, A)
        else:
            hojas(o, n, B)
        if n.startswith("Linea_Pallets"):
            for s in inv._items(o.SubOccurrences):
                if s.Name.startswith("MP402"):
                    tmp = []
                    hojas(s, "MP402", tmp, forzar_visible=True)
                    res["mp402"] = [[p, c] for p, _, c in tmp]
                    res["mp402_caja"] = caja(s.RangeBox)
    res["n_A"], res["n_B"] = len(A), len(B)
    print(f"[{time.time() - T0:5.0f} s] {len(A)} transportes/extensión, {len(B)} hojas del resto", flush=True)
    # pares candidatos: A contra B y A contra A
    cand = []
    for i, (na, oa, ca) in enumerate(A):
        for nb, ob, cb in B:
            if solapa(ca, cb, -TOL):
                cand.append((na, oa, nb, ob))
        for na2, oa2, ca2 in A[i + 1:]:
            if na.split("/")[0] != na2.split("/")[0] and solapa(ca, ca2, -TOL):
                cand.append((na, oa, na2, oa2))
    res["pares_caja"] = len(cand)
    print(f"[{time.time() - T0:5.0f} s] {len(cand)} pares candidatos por caja", flush=True)
    to = app.TransientObjects
    for k, (na, oa, nb, ob) in enumerate(cand):
        c1 = to.CreateObjectCollection()
        c1.Add(oa)
        c2 = to.CreateObjectCollection()
        c2.Add(ob)
        try:
            r = cd.AnalyzeInterference(c1, c2)
            n = r.Count
        except Exception as ex:  # noqa: BLE001
            res["avisos"].append(f"{na} vs {nb}: {ex!r}"[:200])
            continue
        if n == 0:
            res["cerca_caja"].append([na, nb])
            continue
        for x in inv._items(r):
            v = S(lambda x=x: round(x.Volume * 1000, 0), None)          # cm3 -> mm3
            bx = S(lambda x=x: caja(x.InterferenceBody.RangeBox), None)
            res["choques"].append({"a": na, "b": nb, "vol_mm3": v, "caja": bx})
        if k % 25 == 0:
            print(f"[{time.time() - T0:5.0f} s] {k}/{len(cand)} pares, {len(res['choques'])} choques", flush=True)
finally:
    app.SilentOperation = False
res["choques"].sort(key=lambda c: -(c["vol_mm3"] or 0))
res["s"] = round(time.time() - T0, 1)
salida.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps({k: v for k, v in res.items() if k not in ("cerca_caja", "mp402")}, ensure_ascii=False, indent=1)[:15000])
