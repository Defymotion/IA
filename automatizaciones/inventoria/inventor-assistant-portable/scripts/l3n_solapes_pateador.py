"""Sólo lectura: solapes a nivel de pieza (cajas) entre el pateador de una celda y las piezas vecinas (cinta de llegada
T3 / cinta Tetra, hasta 4 niveles), para revisar el pateador corrido. Uso: python l3n_solapes_pateador.py [A|B]
"""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
import inventor_mcp as inv  # noqa: E402

S = inv._safe
CUAL = (sys.argv[1] if len(sys.argv) > 1 else "A").upper()
TOP = Path(r"C:\DEFYMOTION\L3N\Celdas_IA\LayoutL3N_Celdas.iam")
app = inv._inventor(start_if_needed=False)


def its(x):
    if x is None or isinstance(x, list):
        return x or []
    try:
        return inv._items(x)
    except Exception:  # noqa: BLE001
        return []


def caja(o):
    b = S(lambda: o.RangeBox, None)
    return None if b is None else [round(v * 10, 1) for v in (b.MinPoint.X, b.MinPoint.Y, b.MinPoint.Z, b.MaxPoint.X, b.MaxPoint.Y, b.MaxPoint.Z)]


def hojas(o, ruta, prof, out):
    subs = its(S(lambda: o.SubOccurrences, None))
    if not subs or prof >= 4:
        if S(lambda: o.Visible, True) and not S(lambda: o.Suppressed, False):
            c = caja(o)
            if c:
                out.append((ruta + o.Name, c))
        return out
    for h in subs:
        hojas(h, ruta + o.Name + "/", prof + 1, out)
    return out


top = next((d for d in its(app.Documents) if S(lambda: Path(d.FullFileName).resolve() == TOP.resolve(), False)), None)
top = top or app.Documents.Open(str(TOP), False)
occ = {o.Name: o for o in its(top.ComponentDefinition.Occurrences)}
cel = occ["Celda_A_L3N:1" if CUAL == "A" else "Celda_B_existente:1"]
sub = {o.Name: o for o in its(cel.SubOccurrences)}
pat = hojas(sub["Ensamble pateador adeco:1"], "", 0, [])
bb = [min(c[i] for _, c in pat) for i in range(3)] + [max(c[i] for _, c in pat) for i in range(3, 6)]
vec = []
for n, o in sub.items():
    if n.startswith("Ensamble pateador"):
        continue
    c = caja(o)
    if c and all(c[i] < bb[3 + i] + 50 and bb[i] - 50 < c[3 + i] for i in range(3)):
        vec += hojas(o, "", 0, [])
sol = []
for na, ca in pat:
    for nb, cb in vec:
        ov = [min(ca[3 + i], cb[3 + i]) - max(ca[i], cb[i]) for i in range(3)]
        if min(ov) > 0.5:
            sol.append({"pateador": na, "vecina": nb, "solape": [round(v, 1) for v in ov], "c_vecina": cb, "c_pat": ca})
print(json.dumps({"celda": CUAL, "caja_pateador": bb, "n_piezas_pateador": len(pat), "n_vecinas": len(vec),
                  "solapes": sol[:60]}, ensure_ascii=False, indent=1))
