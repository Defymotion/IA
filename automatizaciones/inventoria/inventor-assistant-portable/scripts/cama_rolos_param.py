"""Cama de rolos paramétrica (largo y ancho) a partir de la mesa CdR1512 de Fademaq.
El original no se toca: las piezas que dependen del largo o del ancho se rehacen nativas (con el mismo perfil y el mismo
sistema de coordenadas de la pieza original, así se colocan con la misma matriz); el resto (patas, motor, piñones,
tensores, rodamientos, extremos, bulonería) se referencia del CAD de Fademaq sin modificarlo.
Convención (la de la CdR1512, mm): X a lo largo (el extremo -X queda fijo y la cama crece hacia +X), Z a lo ancho (el
lado de la transmisión, Z alto, queda fijo y la cama crece hacia -Z), Y arriba. Largo y ancho son los totales de la
mesa como los de la CdR1512 (1565 x 1499).
- Largo: laterales (Chapa 01/02), tapa de cadena (Chapa 03), guía plástica, cubrecadena (Chapa 10); cantidad de rolos
  con el paso original (97,35); transmisión al medio; tensores y tapas con su extremo; patas en los extremos (con
  largo < 600 queda un solo par, al medio). Con largo < 900 no entra la transmisión (motorreductor, piñón 18Z y
  tensores del medio): queda sin motor (a definir: cadena desde la mesa vecina o un motor chico).
- Ancho: caño del rolo, eje del rolo, caños transversales (Caño 03); lateral sin transmisión, patas de ese lado y lo
  que está de ese lado se corren.
Uso: python cama_rolos_param.py --largo <mm> --ancho <mm> --nombre <N> [--destino <carpeta>] [--rel relevamiento.json]
     [--sin-foto] [--x-patas <x local del par de patas, sólo con largo < 600>]
     [--dx-patas-fin <mm: corre el par de patas del extremo +X (p. ej. para esquivar algo del layout)>]
Salida: <destino>\\<N>\\<N>.iam + piezas + resumen.json (+ foto_iso.png).
"""
import json
import math
import sys
import time
import traceback
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import inventor_mcp as inv  # noqa: E402
from cinta_modular import Gen  # noqa: E402

S = inv._safe
T0 = time.time()
A = sys.argv


def arg(n, d=None):
    return A[A.index(n) + 1] if n in A else d


LARGO = float(arg("--largo", 1565))
ANCHO = float(arg("--ancho", 1499))
NOMBRE = arg("--nombre", f"Cama_rolos_{int(LARGO)}x{int(ANCHO)}")
DEST = Path(arg("--destino", str(Path.home() / "Documents" / "InventorIA" / "Generados" / "CAMA_ROLOS_PARAMETRICA"))) / NOMBRE
REL = Path(arg("--rel", str(Path.home() / "Documents" / "InventorIA" / "Analisis" / "L3N" / "cama_rolos" / "relevamiento_CdR1512.json")))
L0, W0 = 1565.0, 1499.0
DL, DW = LARGO - L0, ANCHO - W0
X_A, X_B = -1043.68, 506.32           # laterales (extremos) de la original
Z_MID = 1313.0
rel = json.loads(REL.read_text(encoding="utf-8"))
app = inv._inventor(start_if_needed=False)
tg = app.TransientGeometry
log = {"largo": LARGO, "ancho": ANCHO, "dL": DL, "dW": DW, "avisos": [], "piezas_nuevas": {}}
AP_CHAPA = ["pintura epoxi azul", "azul", "blue", "acero galvanizado", "acero"]
AP_ROLO = ["acero galvanizado", "galvanized", "cromo", "acero"]
AP_PLAST = ["plástico blanco", "blanco", "white", "plástico"]


def mmul(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(4)) for j in range(4)] for i in range(4)]


def m4(M):
    return [list(M[0]), list(M[1]), list(M[2]), [0.0, 0.0, 0.0, 1.0]]


def tras(M, dx=0.0, dy=0.0, dz=0.0):
    M = [list(r) for r in M]
    M[0][3] += dx
    M[1][3] += dy
    M[2][3] += dz
    return M


def mx(M):
    def n(v):
        s = math.sqrt(sum(x * x for x in v))
        return [x / s for x in v]
    ex = n([M[0][0], M[1][0], M[2][0]])
    ey = [M[0][1], M[1][1], M[2][1]]
    d = sum(a * b for a, b in zip(ex, ey))
    ey = n([b - d * a for a, b in zip(ex, ey)])
    ez = [ex[1] * ey[2] - ex[2] * ey[1], ex[2] * ey[0] - ex[0] * ey[2], ex[0] * ey[1] - ex[1] * ey[0]]
    m = tg.CreateMatrix()
    m.SetCoordinateSystem(tg.CreatePoint(M[0][3] / 10, M[1][3] / 10, M[2][3] / 10), tg.CreateVector(*ex),
                          tg.CreateVector(*ey), tg.CreateVector(*ez))
    return m


def centro(c):
    return [(c[0] + c[3]) / 2, (c[1] + c[4]) / 2, (c[2] + c[5]) / 2]


def dx_de(xc):
    if xc < -650:
        return 0.0
    if xc > 100:
        return DL
    return DL / 2


def estirada(M, eje_local, x0, delta, mundo, fijo_max):
    """Matriz de una pieza rehecha con delta más de largo a lo largo de eje_local (0 x, 1 y, 2 z), empezando en x0 (local).
    mundo: eje del ensamble que corresponde (0 X, 2 Z). fijo_max False: queda fijo el extremo mínimo (crece hacia +);
    True: queda fijo el extremo máximo (crece hacia -)."""
    col = [M[0][eje_local], M[1][eje_local], M[2][eje_local]]
    s = 1.0 if col[mundo] > 0 else -1.0
    off = [0.0, 0.0, 0.0]
    off[eje_local] = x0
    M2 = mmul(m4(M), [[1, 0, 0, off[0]], [0, 1, 0, off[1]], [0, 0, 1, off[2]], [0, 0, 0, 1]])[:3]
    # crecer: si el eje local apunta al lado que se mueve, nada; si apunta al lado fijo, correr el origen -delta
    hacia_mas = s > 0
    mover = (hacia_mas and fijo_max) or (not hacia_mas and not fijo_max)
    if mover:
        d = [0.0, 0.0, 0.0]
        d[mundo] = -delta if fijo_max else delta
        M2 = tras(M2, *d)
    return M2


app.SilentOperation = True
docs_cerrar = []
try:
    DEST.mkdir(parents=True, exist_ok=True)
    g = Gen(app, DEST / "Piezas")
    occ = rel["occ"]
    by = {}
    for e in occ:
        by.setdefault(e["n"].split("/")[-1].rsplit("_", 1)[0], []).append(e)

    def una(pref):
        return next(e for e in occ if e["nivel"] == 2 and e["n"].split("/")[-1].startswith(pref))

    # ---------------------------------------------------------------- piezas rehechas (largo)
    LL = lambda v: round(v + DL, 2)
    WW = lambda v: round(v + DW, 2)
    lat1 = g.perfil_x(f"{NOMBRE}_Lateral_motriz_L{LL(1550):.0f}", [(-6.263, 0), (310, 0), (310, -80), (305.2, -80), (305.2, -4.8),
                                                          (-1.463, -4.8), (-1.463, -80), (-6.263, -80)], LL(1550),
                      "Lateral C de cama de rolos (lado transmisión)", AP_CHAPA)
    lat2 = g.perfil_x(f"{NOMBRE}_Lateral_libre_L{LL(1550):.0f}", [(-6.263, 0), (290, 0), (290, -80), (285.2, -80), (285.2, -4.8),
                                                        (-1.463, -4.8), (-1.463, -80), (-6.263, -80)], LL(1550),
                      "Lateral C de cama de rolos (lado libre)", AP_CHAPA)
    tapa = g.perfil_x(f"{NOMBRE}_Tapa_cadena_L{LL(1553):.0f}", [(0, -8.5), (0, -56.5), (-40, -56.5), (-40, -54), (-2.5, -54), (-2.5, -11),
                                                       (-60, -11), (-60, -8.5)], LL(1553), "Tapa de cadena", AP_CHAPA)
    guia = g.perfil_x(f"{NOMBRE}_Guia_plastica_L{LL(1500):.0f}", [(-75.671, 0), (-55.671, 0), (-55.671, 20), (-75.671, 20)], LL(1500),
                      "Guía plástica de cadena", AP_PLAST)
    cubre = g.perfil_x(f"{NOMBRE}_Cubrecadena_L{LL(1558):.0f}", [(-45, 0), (-45, 151), (-3.2, 151), (-3.2, 147), (-41, 147), (-41, 0)],
                       LL(1558), "Cubrecadena", AP_CHAPA)
    # ---------------------------------------------------------------- piezas rehechas (ancho)
    cano = g.cilindro(f"{NOMBRE}_Cano_rolo_D63.5_L{WW(1152):.0f}", 63.5, WW(1152), "x", "Caño de rolo Ø63,5 x 2", AP_ROLO,
                      d_int=59.5, centrado=False)
    eje = g.cilindro(f"{NOMBRE}_Eje_rolo_D17_L{WW(1197):.0f}", 17.0, WW(1197), "z", "Eje de rolo Ø17", AP_ROLO, centrado=False)
    trav = g.perfil_z(f"{NOMBRE}_Travesano_50x100_L{WW(1197):.0f}", [(-25, -50), (25, -50), (25, 50), (-25, 50)], WW(1197),
                      "Travesaño 50x100", AP_CHAPA, simetrico=False)
    # ---------------------------------------------------------------- rolo (subensamble nuevo)
    rolos = sorted([e for e in occ if e["nivel"] == 2 and "02.Ensamblaje Rolo" in e["n"]], key=lambda e: centro(e["c"])[0])
    xs = [centro(e["c"])[0] for e in rolos]
    paso = (xs[-1] - xs[0]) / (len(xs) - 1)
    r0 = rolos[0]
    hijos = [e for e in occ if e["n"].startswith(r0["n"] + "/")]
    XC0 = next(h for h in hijos if h["n"].split("/")[-1].startswith("Eje 01"))["M"][0][3]
    ruta_rolo = DEST / f"{NOMBRE}_Rolo.iam"      # nombres únicos: Inventor no abre dos archivos con el mismo nombre
    if ruta_rolo.exists():
        ruta_rolo.unlink()
    er = app.Documents.Add(inv.K_ASSEMBLY_DOCUMENT, app.FileManager.GetTemplateFile(inv.K_ASSEMBLY_DOCUMENT), False)
    for h in hijos:
        n = h["n"].split("/")[-1]
        M = tras(h["M"], -XC0, 0, 0)
        if n.startswith("Caño 01"):
            f, M = str(cano), estirada(M, 0, 0.0, DW, 2, True)
        elif n.startswith("Eje 01"):
            f, M = str(eje), estirada(M, 2, 0.0, DW, 2, True)
        else:
            f = h["f"]
            if centro(h["c"])[2] < Z_MID:
                M = tras(M, 0, 0, -DW)
        o = er.ComponentDefinition.Occurrences.Add(f, mx(M))
        S(lambda: setattr(o, "Grounded", True))
    er.SaveAs(str(ruta_rolo), False)
    docs_cerrar.append(er)
    # ---------------------------------------------------------------- cama
    ruta = DEST / f"{NOMBRE}.iam"
    if ruta.exists():
        ruta.rename(ruta.with_name(ruta.stem + time.strftime("_anterior_%Y%m%d_%H%M%S") + ".iam"))
    ed = app.Documents.Add(inv.K_ASSEMBLY_DOCUMENT, app.FileManager.GetTemplateFile(inv.K_ASSEMBLY_DOCUMENT), False)
    oc = ed.ComponentDefinition.Occurrences
    puestos = []

    def poner(f, M, nombre=None):
        o = oc.Add(str(f), mx(M))
        S(lambda: setattr(o, "Grounded", True))
        if nombre:
            S(lambda: setattr(o, "Name", nombre))
        puestos.append(nombre or Path(str(f)).stem)
        return o

    x_fin = X_B + DL
    # largo
    for pref, f, x0, fijo in (("Chapa 01", lat1, 0.0, "x"), ("Chapa 02", lat2, 0.0, "x"), ("Chapa 03", tapa, -396.719, "x"),
                              ("Guia Plástica 01", guia, 6.458, "x"), ("Chapa 10", cubre, -2.5, "x")):
        e = una(pref)
        M = estirada(e["M"], 0, x0, DL, 0, False)
        if centro(e["c"])[2] < Z_MID:
            M = tras(M, 0, 0, -DW)
        poner(f, M)
    # travesaños (ancho) en los extremos
    for e in [x for x in occ if x["nivel"] == 2 and x["n"].split("/")[-1].startswith("Caño 03")]:
        M = estirada(e["M"], 2, 0.0, DW, 2, True)
        poner(trav, tras(M, dx_de(centro(e["c"])[0]), 0, 0))
    # rolos
    L_rolos = (xs[-1] - xs[0]) + DL
    n_rolos = max(2, int(math.floor(L_rolos / paso + 1e-6)) + 1)
    sobra = L_rolos - (n_rolos - 1) * paso
    for i in range(n_rolos):
        poner(ruta_rolo, [[1, 0, 0, XC0 + sobra / 2 + i * paso], [0, 1, 0, 0], [0, 0, 1, 0]], f"Rolo_{i + 1}")
    log["rolos"] = {"n": n_rolos, "paso": round(paso, 3)}
    # el resto (sin cambios de forma): se corre con su extremo / al medio / del lado libre
    hechos = ("Chapa 01", "Chapa 02", "Chapa 03", "Guia Plástica 01", "Chapa 10", "Caño 03", "02.Ensamblaje Rolo")
    descartados = []
    for e in occ:
        n = e["n"].split("/")[-1]
        if e["nivel"] == 1 and n.startswith("01.Ensamblaje"):
            continue
        if e["nivel"] == 2 and n.startswith(hechos):
            continue
        if e["nivel"] == 2 and e["n"].startswith("01.Ensamblaje") or (e["nivel"] == 1 and n.startswith("06.Ensamblaje Pata")):
            c = centro(e["c"])
            if n.startswith("06.Ensamblaje Pata"):
                if LARGO < 600:
                    if c[0] > -269:          # con largo corto queda un solo par de patas, al medio
                        continue
                    ddx = (float(arg("--x-patas")) if "--x-patas" in A else (X_A + x_fin) / 2) - (-897.0)
                else:
                    ddx = 0.0 if c[0] < -269 else DL + float(arg("--dx-patas-fin", 0))
            else:
                ddx = dx_de(c[0])
                if LARGO < 900 and -650 <= c[0] <= 100:      # la transmisión del medio no entra en una cama corta
                    descartados.append(n)
                    continue
            xn = c[0] + ddx
            if not (X_A - 10 <= xn <= x_fin + 10):
                descartados.append(n)
                continue
            M = tras(e["M"], ddx, 0, -DW if c[2] < Z_MID else 0.0)
            poner(e["f"], M)
    log["descartados_por_largo"] = descartados
    inv._iprop(ed, "Design Tracking Properties", "Description", f"CAMA DE ROLOS {LARGO:.0f} X {ANCHO:.0f} (PARAMÉTRICA DE CDR1512)")
    for k, v in (("Largo", LARGO), ("Ancho", ANCHO)):
        S(lambda k=k, v=v: ed.ComponentDefinition.Parameters.UserParameters.AddByExpression(k, f"{v} mm", "mm"))
    ed.Update()
    b = ed.ComponentDefinition.RangeBox
    log["caja_mm"] = [round(v * 10, 1) for v in (b.MinPoint.X, b.MinPoint.Y, b.MinPoint.Z, b.MaxPoint.X, b.MaxPoint.Y, b.MaxPoint.Z)]
    log["medidas_mm"] = [round(log["caja_mm"][3] - log["caja_mm"][0], 1), round(log["caja_mm"][4] - log["caja_mm"][1], 1),
                         round(log["caja_mm"][5] - log["caja_mm"][2], 1)]
    log["n_ocurrencias"] = len(puestos)
    ed.SaveAs(str(ruta), False)
    log["ensamble"] = str(ruta)
    if "--sin-foto" not in A:
        ed.Close(True)
        ed2 = app.Documents.Open(str(ruta), True)
        ed2.Activate()
        time.sleep(1)
        v = app.ActiveView
        cam = v.Camera
        cam.ViewOrientationType = inv.K_ISO_TOP_RIGHT
        cam.Fit()
        cam.Apply()
        v.SaveAsBitmap(str(DEST / "foto_iso.png"), 1600, 1000)
        log["foto"] = str(DEST / "foto_iso.png")
        docs_cerrar.append(ed2)
    else:
        docs_cerrar.append(ed)
except Exception as exc:  # noqa: BLE001
    log["error"] = repr(exc)
    log["traza"] = traceback.format_exc()[-2500:]
finally:
    for d in docs_cerrar:
        S(lambda d=d: d.Close(True))
    S(lambda: setattr(app, "SilentOperation", False))
log["s"] = round(time.time() - T0, 1)
DEST.mkdir(parents=True, exist_ok=True)
(DEST / "resumen.json").write_text(json.dumps(log, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps(log, ensure_ascii=False, indent=1)[:5000])
