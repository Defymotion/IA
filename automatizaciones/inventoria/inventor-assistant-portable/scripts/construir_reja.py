"""Reja perimetral cuadrada con portón corredizo (prueba del generador de rejas).

Reglas tomadas del modelo de muestra 12_ADECO2\\rejas (copia):
- Columna: caño 60x60x2 de 1900 sobre base 180x180x3/16" con 4 agujeros Ø12,5 (centros 116).
- Columnas en esquinas, a ambos lados del portón y repartidas parejo a ≤ 1736 entre ejes.
- Paneles: marco de caño 30x30x2,6, dos paneles por vano (uno sobre otro), sin malla por ahora;
  10 mm de luz contra cada columna; panel del lado exterior de la línea de columnas; Ø8 para fijar.
- Portón corredizo como el de muestra (puerta.iam): hoja 1250x2080 de caño 60x30x2 sobre 2 ruedas Ø75,
  columna de portón 2200 corrida 75 mm hacia afuera, guía superior y guías inferiores con rodillos.
  La hoja corre por la línea de la reja; el tramo siguiente queda corrido 75 mm hacia afuera para que pase.
Todas las piezas quedan fijas en su posición (sin restricciones en esta prueba).

Uso: python construir_reja.py [--nombre REJA_PRUEBA] [--lado 6000] [--alto 1900] [--porton-x 1600]
Salida: Documents\\InventorIA\\Generados\\<nombre>\\ (Estructura, Chapas, Corte_laser, Ensamble, diseno.json)
"""
import argparse
import atexit
import json
import math
import sys
import time
import traceback
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
import inventor_mcp as inv  # noqa: E402
from gripper_design import FlatPart, rounded_rect  # noqa: E402
from dataclasses import asdict  # noqa: E402

a = argparse.ArgumentParser()
a.add_argument("--nombre", default="REJA_PRUEBA")
a.add_argument("--lado", type=float, default=6000)
a.add_argument("--alto", type=float, default=1900)
a.add_argument("--porton-x", type=float, default=1600, help="eje de la columna donde arranca el portón")
a.add_argument("--planta", default="", help="JSON (texto o ruta): {tramos:[[[x,y],...],...], porton:{tramo,segmento,desde}}"
               " — cada tramo es una poligonal con reja; recorrer con el exterior a la derecha")
a.add_argument("--muestra", default=str(Path.home() / "Documents" / "InventorIA" / "12_ADECO2" / "rejas"))
a.add_argument("--reusar-piezas", action="store_true")
x = a.parse_args()

S = inv._safe
T316 = 4.7625
COL = {"a": 60.0, "e": 2.0}
PANEL = {"a": 30.0, "e": 2.6, "luz": 10.0, "desde_piso": 150.0, "entre": 10.0, "agujero_d": 8.0, "agujero_y": 100.0}
HOJA = {"W": 1250.0, "H": 2080.0, "a": 60.0, "b": 30.0, "e": 2.0}
MAX_CC = 1736.0
BASE = {"lado": 180.0, "d": 12.5, "c": 116.0, "r": 5.0}

OUT = Path.home() / "Documents" / "InventorIA" / "Generados" / x.nombre
EST, CH, DXF, ENS = OUT / "Estructura", OUT / "Chapas", OUT / "Corte_laser", OUT / "Ensamble"
for p in (EST, CH, DXF, ENS):
    p.mkdir(parents=True, exist_ok=True)
log = {"nombre": x.nombre, "piezas": [], "avisos": [], "errores": []}
T0 = time.time()


def etapa(t):
    print(f"[{time.time() - T0:6.1f} s] {t}", flush=True)


# =============================================================================== diseño (planta)
L, ALTO = x.lado, x.alto
A = x.porton_x
H_PAN = (ALTO - PANEL["desde_piso"] - PANEL["entre"]) / 2
Z_PAN = (PANEL["desde_piso"], PANEL["desde_piso"] + H_PAN + PANEL["entre"])
D_PORTON, N_PORTON = 860.0, 75.0          # columna de portón respecto de la columna normal (de la muestra)
UP = (0.0, 0.0, 1.0)


def cross(u, v):
    return (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])


def tramo(p1, p2):
    """Columnas intermedias y vanos de un tramo recto p1 -> p2 (p1 y p2 tienen columna)."""
    dx, dy = p2[0] - p1[0], p2[1] - p1[1]
    ln = math.hypot(dx, dy)
    n = max(1, math.ceil(ln / MAX_CC - 1e-9))
    pts = [(p1[0] + dx * i / n, p1[1] + dy * i / n) for i in range(n + 1)]
    d = (dx / ln, dy / ln, 0.0)
    return pts, d, ln / n


if x.planta:
    pl = json.loads(Path(x.planta).read_text(encoding="utf-8") if x.planta.strip()[0] not in "[{" else x.planta)
else:
    pl = {"tramos": [[[0, 0], [L, 0], [L, L], [0, L], [0, 0]]], "porton": {"tramo": 0, "segmento": 0, "desde": A}}
polis = [[tuple(map(float, p)) for p in t] for t in pl["tramos"]]
pt_ = pl.get("porton")
tramos = []
gate_normal = gate_col = None
D_GATE = (1.0, 0.0, 0.0)
for k, poli in enumerate(polis):
    poli = list(poli)
    if pt_ and pt_["tramo"] == k:
        i = pt_["segmento"]
        p1, p2 = poli[i], poli[i + 1]
        ln = math.dist(p1, p2)
        d = ((p2[0] - p1[0]) / ln, (p2[1] - p1[1]) / ln, 0.0)
        n = cross(d, UP)
        A = float(pt_["desde"])
        if A + D_PORTON + HOJA["W"] + 60 > ln + 1e-6:
            log["avisos"].append(f"El portón necesita {A + D_PORTON + HOJA['W'] + 60:.0f} mm de tramo, hay {ln:.0f}")
        gate_normal = (p1[0] + d[0] * A, p1[1] + d[1] * A)
        gate_col = (gate_normal[0] + d[0] * D_PORTON + n[0] * N_PORTON, gate_normal[1] + d[1] * D_PORTON + n[1] * N_PORTON)
        D_GATE = d
        q2 = (p2[0] + n[0] * N_PORTON, p2[1] + n[1] * N_PORTON)   # el tramo siguiente corre afuera para la hoja
        if poli[0] == poli[-1] and i + 1 == len(poli) - 1:
            poli[0] = q2
        poli[i + 1] = q2
        tramos += [(poli[j], poli[j + 1]) for j in range(i)]
        tramos += [(p1, gate_normal), (gate_col, q2)]
        tramos += [(poli[j], poli[j + 1]) for j in range(i + 1, len(poli) - 1)]
    else:
        tramos += [(poli[j], poli[j + 1]) for j in range(len(poli) - 1)]
columnas, vanos = [], []
for p1, p2 in tramos:
    pts, d, cc = tramo(p1, p2)
    for pt in pts:
        if (gate_col is None or math.dist(pt, gate_col) > 1) and all(math.dist(pt, c) > 1 for c in columnas):
            columnas.append(pt)
    for i in range(len(pts) - 1):
        vanos.append({"p1": pts[i], "d": d, "cc": cc, "ancho": round(cc - COL["a"] - 2 * PANEL["luz"], 2)})
anchos = sorted({v["ancho"] for v in vanos})
log["diseno"] = {"tramos": [[list(map(lambda v: round(v, 1), p)) for p in t] for t in tramos], "alto": ALTO, "columnas": len(columnas) + 1, "vanos": len(vanos),
                 "paneles": 2 * len(vanos), "anchos_panel": anchos, "alto_panel": H_PAN}
etapa(f"Diseño: {len(columnas)} columnas + 1 de portón, {len(vanos)} vanos, paneles {anchos} x {H_PAN}")

# =============================================================================== piezas
app = inv._inventor(start_if_needed=False)
tg = app.TransientGeometry
app.SilentOperation = True
atexit.register(lambda: S(lambda: setattr(app, "SilentOperation", False)))
for dd in inv._items(app.Documents):                    # cerrar lo abierto de una corrida anterior
    if S(lambda: OUT.resolve() in Path(dd.FullFileName).resolve().parents, False):
        S(lambda: dd.Close(True))

archivos = {}


def hacer(nombre, ruta, fn):
    archivos[nombre] = ruta
    if x.reusar_piezas and ruta.exists():
        return
    etapa(f"Pieza {nombre}")
    try:
        r = fn()
        doc = r.pop("documento")
        S(lambda: doc.Close(True))
        log["piezas"].append(r)
    except Exception as exc:  # noqa: BLE001
        log["errores"].append({"pieza": nombre, "error": repr(exc), "traza": traceback.format_exc()[-1500:]})


hacer("col1900", EST / "Columna 60x60x2 L1900.ipt",
      lambda: inv.build_tube_part(app, "Columna L1900", COL["a"], COL["a"], COL["e"], ALTO,
                                  EST / "Columna 60x60x2 L1900.ipt"))
hacer("col2200", EST / "Columna porton 60x60x2 L2200.ipt",
      lambda: inv.build_tube_part(app, "Columna porton L2200", COL["a"], COL["a"], COL["e"], 2200.0,
                                  EST / "Columna porton 60x60x2 L2200.ipt"))
for w in anchos:
    nom = f"Panel {w:g}x{H_PAN:g}"
    agu = [(PANEL["a"] / 2, y_, PANEL["agujero_d"]) for y_ in (PANEL["agujero_y"], H_PAN - PANEL["agujero_y"])]
    agu += [(w - PANEL["a"] / 2, y_, d_) for _, y_, d_ in agu]
    hacer(nom, EST / f"{nom}.ipt",
          lambda w=w, nom=nom, agu=agu: inv.build_frame_part(app, nom, w, H_PAN, PANEL["a"], PANEL["a"], PANEL["e"],
                                                             EST / f"{nom}.ipt", agujeros=agu))
hacer("hoja", EST / "Hoja porton 1250x2080.ipt",
      lambda: inv.build_frame_part(app, "Hoja porton", HOJA["W"], HOJA["H"], HOJA["a"], HOJA["b"], HOJA["e"],
                                   EST / "Hoja porton 1250x2080.ipt", travesanos=(HOJA["H"] / 2,)))
B_ = BASE
base_spec = asdict(FlatPart(
    nombre="Base columna", cantidad=len(columnas) + 1, espesor=T316, material="Acero SAE 1010",
    contorno=rounded_rect(0, 0, B_["lado"], B_["lado"], B_["r"]),
    circulos=[(B_["lado"] / 2 + sx * B_["c"] / 2, B_["lado"] / 2 + sy * B_["c"] / 2, B_["d"])
              for sx in (-1, 1) for sy in (-1, 1)],
    envolvente_plegada=(B_["lado"], B_["lado"], T316)))
base_spec["desarrollo"] = (B_["lado"], B_["lado"])
hacer("base", CH / "Base columna.ipt",
      lambda: {k: v for k, v in inv.build_flat_part(app, base_spec, CH / "Base columna.ipt",
                                                    DXF / "Base columna.dxf").items()})
if log["errores"]:
    print(json.dumps(log, ensure_ascii=False, indent=1, default=str))
    sys.exit("Errores construyendo piezas")


# =============================================================================== matrices
def mread(m):
    return [[m.Cell(r, c) * (10 if (c == 4 and r < 4) else 1) for c in range(1, 5)] for r in range(1, 5)]


def mmul(P, Q):
    return [[sum(P[i][k] * Q[k][j] for k in range(4)) for j in range(4)] for i in range(4)]


def mmake(M):
    m = tg.CreateMatrix()
    m.SetCoordinateSystem(tg.CreatePoint(M[0][3] / 10, M[1][3] / 10, M[2][3] / 10),
                          tg.CreateVector(M[0][0], M[1][0], M[2][0]), tg.CreateVector(M[0][1], M[1][1], M[2][1]),
                          tg.CreateVector(M[0][2], M[1][2], M[2][2]))
    return m


def tr(dx, dy, dz):
    return [[1, 0, 0, dx], [0, 1, 0, dy], [0, 0, 1, dz], [0, 0, 0, 1]]


def frame(o, ex, ey, ez):
    return [[ex[0], ey[0], ez[0], o[0]], [ex[1], ey[1], ez[1], o[1]], [ex[2], ey[2], ez[2], o[2]], [0, 0, 0, 1]]


# =============================================================================== portón: disposición de la muestra
etapa("Leyendo el portón de muestra (sólo lectura)")
pdoc = app.Documents.Open(str(Path(x.muestra) / "puerta.iam"), False)
occs = {o.Name: o for o in inv._items(pdoc.ComponentDefinition.Occurrences)}


def sub(o, texto):
    return next(s for s in inv._items(o.SubOccurrences) if texto.lower() in s.Name.lower())


col_puerta = next(o for n, o in occs.items() if n.lower().startswith("ensamblaje columna puerta"))
col_normal = next(o for n, o in occs.items() if n.lower().startswith("ensamblaje columna_"))
hoja_occ = next(o for n, o in occs.items() if n.lower().startswith("ensamblaje puerta"))
M_cano_n = mread(sub(col_normal, "caño").Transformation)
M_hoja = mread(sub(hoja_occ, "puerta 02").Transformation)
piso = col_normal.RangeBox.MinPoint.Y * 10
o_s = (M_cano_n[0][3], piso, M_cano_n[2][3])
d_s = (M_hoja[0][0], M_hoja[1][0], M_hoja[2][0])               # eje x de la hoja = dirección de la reja
up_s = (0.0, 1.0, 0.0)
n_s = cross(d_s, up_s)
B_s = frame((0, 0, 0), d_s, up_s, n_s)
d_n, n_n = D_GATE, cross(D_GATE, UP)
B_n = frame((0, 0, 0), d_n, UP, n_n)
Bt = [[B_s[j][i] for j in range(4)] for i in range(4)]          # inversa de la rotación (ortonormal)
Q = mmul(B_n, Bt)
TF = mmul(mmul(tr(gate_normal[0], gate_normal[1], 0), Q), tr(-o_s[0], -o_s[1], -o_s[2]))   # muestra -> reja nueva
M_cano_p = mread(sub(col_puerta, "caño").Transformation)
gp = mmul(TF, M_cano_p)
log["porton_columna_xy"] = [round(gp[0][3], 1), round(gp[1][3], 1)]
if math.dist((gp[0][3], gp[1][3]), gate_col) > 1.0:
    log["avisos"].append(f"Columna de portón de la muestra en {log['porton_columna_xy']}, esperada {gate_col}")
gate_col = (gp[0][3], gp[1][3])

# =============================================================================== ensamble
etapa("Ensamble")
asm_path = ENS / f"{x.nombre}.iam"
if asm_path.exists():
    asm_path.unlink()
adoc = app.Documents.Add(inv.K_ASSEMBLY_DOCUMENT, app.FileManager.GetTemplateFile(inv.K_ASSEMBLY_DOCUMENT), True)
acd = adoc.ComponentDefinition
cuenta = {}


# el diseño se hace con Z vertical; Inventor usa Y vertical: X -> X, Z -> Y, Y -> -Z
G = [[1, 0, 0, 0], [0, 0, 1, 0], [0, -1, 0, 0], [0, 0, 0, 1]]


def poner(path, M, rol):
    o = acd.Occurrences.Add(str(path), mmake(mmul(G, M)))
    S(lambda: setattr(o, "Grounded", True))
    cuenta[rol] = cuenta.get(rol, 0) + 1
    return o


# columnas normales: caño sobre la base
for cx, cy in columnas:
    poner(archivos["base"], tr(cx - B_["lado"] / 2, cy - B_["lado"] / 2, 0), "base")
    poner(archivos["col1900"], tr(cx, cy, T316), "columna")
# paneles: x = largo del vano, y = arriba, z = hacia afuera (mitad exterior de la línea de columnas)
for v in vanos:
    d = v["d"]
    n = cross(d, UP)
    R = frame((0, 0, 0), d, UP, n)
    for z0 in Z_PAN:
        o = (v["p1"][0] + d[0] * (COL["a"] / 2 + PANEL["luz"]) + n[0] * PANEL["a"] / 2,
             v["p1"][1] + d[1] * (COL["a"] / 2 + PANEL["luz"]) + n[1] * PANEL["a"] / 2, z0)
        M = R[:]
        M = [row[:] for row in R]
        for i in range(3):
            M[i][3] = o[i]
        poner(archivos[f"Panel {v['ancho']:g}x{H_PAN:g}"], M, "panel")
# portón: columna, base y chapa de refuerzo de la muestra, guías, hoja y ruedas
for so in inv._items(col_puerta.SubOccurrences):
    fn = Path(so.Definition.Document.FullFileName).name.lower()
    Ms = mread(so.Transformation)
    if "caño" in fn:
        poner(archivos["col2200"], mmul(TF, Ms), "columna_porton")
    elif "chapa 01" in fn:
        poner(archivos["base"], mmul(mmul(TF, Ms), tr(-B_["lado"] / 2, -B_["lado"] / 2, -T316)), "base")
    else:
        poner(so.Definition.Document.FullFileName, mmul(TF, Ms), "herraje_porton")
for n_, o in occs.items():
    if n_.lower().startswith("ensamblaje guia"):
        poner(o.Definition.Document.FullFileName, mmul(TF, mread(o.Transformation)), "guia_porton")
poner(archivos["hoja"], mmul(mmul(TF, M_hoja), tr(-HOJA["a"] / 2, -HOJA["a"] / 2, 0)), "hoja")
for so in inv._items(hoja_occ.SubOccurrences):
    if "rueda" in so.Name.lower():
        poner(so.Definition.Document.FullFileName, mmul(TF, mread(so.Transformation)), "rueda")
S(lambda: pdoc.Close(True))
adoc.Update()
inv._iprop(adoc, "Design Tracking Properties", "Part Number", x.nombre[:inv.MAX_PART_NUMBER])
adoc.SaveAs(str(asm_path), False)
log["componentes"] = cuenta

# verificación: interferencias entre todo
etapa("Verificación")
try:
    col = app.TransientObjects.CreateObjectCollection()

    def hojas(c):
        for o in inv._items(c):
            if S(lambda: o.DefinitionDocumentType) == inv.K_ASSEMBLY_DOCUMENT:
                hojas(o.SubOccurrences)
            else:
                col.Add(o)
    hojas(acd.Occurrences)
    inter = {}
    for r in inv._items(acd.AnalyzeInterference(col)):
        k = " / ".join(sorted(Path(S(lambda: oc.Definition.Document.FullFileName, "?")).stem
                              for oc in (r.OccurrenceOne, r.OccurrenceTwo)))
        v_ = inter.setdefault(k, [0, 0.0])
        v_[0] += 1
        v_[1] = round(v_[1] + S(lambda: r.Volume * 1000, 0.0), 1)
    log["interferencias"] = inter
except Exception as exc:  # noqa: BLE001
    log["avisos"].append(f"Interferencias: {exc}")
b = acd.RangeBox
log["envolvente_mm"] = [round((b.MaxPoint.X - b.MinPoint.X) * 10, 1), round((b.MaxPoint.Y - b.MinPoint.Y) * 10, 1),
                        round((b.MaxPoint.Z - b.MinPoint.Z) * 10, 1)]
log["masa_kg"] = S(lambda: round(acd.MassProperties.Mass, 1))
try:
    adoc.Activate()
    cam = app.ActiveView.Camera
    cam.ViewOrientationType = 10759
    cam.Fit()
    cam.Apply()
    img = ENS / f"{x.nombre}_iso.png"
    app.ActiveView.SaveAsBitmap(str(img), 1600, 1000)
    log["imagen"] = str(img)
except Exception as exc:  # noqa: BLE001
    log["avisos"].append(f"Imagen: {exc}")
adoc.Save()

# datos para la lista de materiales
log["bom"] = {
    "columnas_1900": len(columnas), "columnas_2200": cuenta.get("columna_porton", 0), "bases": cuenta.get("base", 0),
    "paneles": {f"{w:g}": sum(2 for v in vanos if v["ancho"] == w) for w in anchos}, "alto_panel": H_PAN,
    "panel_cano": f"{PANEL['a']:g}x{PANEL['a']:g}x{PANEL['e']:g}", "col_cano": f"{COL['a']:g}x{COL['a']:g}x{COL['e']:g}",
    "hoja": HOJA, "herrajes": {k: v for k, v in cuenta.items() if k in ("herraje_porton", "guia_porton", "rueda")},
}
log["archivos"] = {"ensamble": str(asm_path), "estructura": str(EST), "chapas": str(CH), "dxf": str(DXF)}
log["tiempo_s"] = round(time.time() - T0, 1)
(OUT / "resultado.json").write_text(json.dumps(log, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
print(json.dumps(log, ensure_ascii=False, indent=1, default=str))
