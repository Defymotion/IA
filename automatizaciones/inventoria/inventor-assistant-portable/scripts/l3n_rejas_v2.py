"""L3N: rearma las rejas de una celda (A o C) para que los paneles queden ENTRE las columnas, como se montan los Fademaq
de la celda B: paso estándar 1320 entre columnas con el panel 03 de 1240 (10 mm de luz a cada caño de 60) y, al final
de cada tramo, bahías cortadas a medida (panel con el mismo diseño, más angosto). Las esquinas comparten UNA columna.
Los tramos de las rejas norte y sur de A que quedan bajo el recorrido del pallet del robot aéreo (hacia los buffers y
hacia la celda B) se arman a 1400 con piezas Fademaq recortadas (columna con caño de 1395 y panel alto de 345).
Mantiene los extremos de cada tramo (columnas de la barrera IFM, pared, etc.). Respaldo: <celda>_antes_rejas_v2.iam.
Piezas nuevas en C:\\DEFYMOTION\\L3N\\Celdas_IA\\Rejas_v2\\ (copias editadas; los originales no se tocan).
Uso: python l3n_rejas_v2.py [A|C] [--probar]   (--probar: sólo calcula y lista, no modifica)
"""
import json
import math
import re
import shutil
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
import inventor_mcp as inv  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parent))
from estirar_pieza import estirar  # noqa: E402

S = inv._safe
BASE = Path(r"C:\DEFYMOTION\L3N\Celdas_IA")
CUAL = (sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("--") else "A").upper()
PROBAR = "--probar" in sys.argv
CELDA = BASE / ("Celda_A_L3N.iam" if CUAL == "A" else "Celda_C_existente.iam")
ORG = {"A": (-6503.1706, 0.0, -35622.3429), "C": (-6483.0, 0.0, -50572.0)}[CUAL]
PZ = BASE / "Rejas_v2"
PASO = 1320.0                 # paso estándar entre columnas (panel 1240 + 2 x 10 + caño 60)
LUZ_CANO = 40.0               # mitad del caño (30) + luz (10)
MIN_BAHIA = 600.0             # bahía cortada mínima; si sobra menos, se reparten las dos últimas
AEREO_X = (-11320.0, -9840.0)  # recorrido del pallet colgado del robot aéreo (con la sujeción de 1300) en A
H_AEREO = 1400.0
LINEAS_AEREO = ("Norte_interna", "Sur")   # tramos que cruza el robot aéreo (hacia los buffers y hacia la celda B)
app = inv._inventor(start_if_needed=False)
tg = app.TransientGeometry
log = {"celda": CUAL, "avisos": [], "lineas": []}


def its(x):
    if x is None or isinstance(x, list):
        return x or []
    try:
        return inv._items(x)
    except Exception:  # noqa: BLE001
        return []


def abrir(p):
    d = next((d for d in its(app.Documents) if S(lambda: Path(d.FullFileName).resolve() == Path(p).resolve(), False)), None)
    return d or app.Documents.Open(str(p), False)


def caja(o):
    b = o.RangeBox
    return [b.MinPoint.X * 10 + ORG[0], b.MinPoint.Y * 10, b.MinPoint.Z * 10 + ORG[2],
            b.MaxPoint.X * 10 + ORG[0], b.MaxPoint.Y * 10, b.MaxPoint.Z * 10 + ORG[2]]


def mread(m):
    return [[m.Cell(r, c) * (10 if c == 4 else 1) for c in range(1, 5)] for r in range(1, 4)]


def mmake(R, t):
    m = tg.CreateMatrix()
    m.SetCoordinateSystem(tg.CreatePoint(t[0] / 10, t[1] / 10, t[2] / 10), tg.CreateVector(R[0][0], R[1][0], R[2][0]),
                          tg.CreateVector(R[0][1], R[1][1], R[2][1]), tg.CreateVector(R[0][2], R[1][2], R[2][2]))
    return m


def bahias(L):
    """Largos de bahía: estándar y al final una cortada (o dos iguales si la sobra es chica)."""
    n = int(L // PASO)
    r = L - n * PASO
    if r < 1.0:
        return [PASO] * n
    if r >= MIN_BAHIA or n == 0:
        return [PASO] * n + [r]
    return [PASO] * (n - 1) + [(PASO + r) / 2] * 2


def pieza_panel(base_ipt, ancho0, alto0, ancho, alto):
    """Copia del panel Fademaq (sólido importado) estirada/acortada a ancho x alto (X = ancho, Y = alto de la pieza)."""
    nombre = f"{Path(base_ipt).stem}_L{int(round(ancho))}xH{int(round(alto))}.ipt"
    ruta = PZ / nombre
    if ruta.exists():
        return str(ruta)
    origen = base_ipt
    info = None
    if abs(ancho - ancho0) > 0.5:
        info = estirar(app, origen, ruta, 0, 300.0, ancho - ancho0)
        origen = str(ruta)
    if abs(alto - alto0) > 0.5:
        if origen != str(ruta):
            info = estirar(app, origen, ruta, 1, 300.0, alto - alto0)
        else:
            tmp = PZ / ("_tmp_" + nombre)
            shutil.copyfile(ruta, tmp)
            info = estirar(app, tmp, ruta, 1, 300.0, alto - alto0)
            S(lambda: tmp.unlink())
    c = info["caja"] if info else None
    ok = c is not None and abs((c[3] - c[0]) - ancho) < 2 and abs((c[4] - c[1]) - alto) < 2
    log.setdefault("piezas", {})[nombre] = {"caja": c, "ok": ok, "avisos": info.get("avisos") if info else None}
    if not ok:
        log["avisos"].append(f"{nombre}: el estiramiento no dio la medida ({c})")
    return str(ruta)


def columna_corta(base_iam, alto):
    """Copia de la columna (ensamble) con el caño acortado para que la columna mida 'alto'."""
    ruta = PZ / f"{Path(base_iam).stem}_H{int(alto)}.iam"
    if ruta.exists():
        return str(ruta)
    col = abrir(base_iam)
    cano = None
    for o in its(col.ComponentDefinition.Occurrences):
        b = o.RangeBox
        if (b.MaxPoint.Y - b.MinPoint.Y) * 10 > 1000:
            cano = o
    if cano is None:
        log["avisos"].append("no encontré el caño de la columna")
        return None
    cano_f = Path(cano.Definition.Document.FullFileName)
    bd = cano.Definition.RangeBox
    lados = [(bd.MaxPoint.X - bd.MinPoint.X) * 10, (bd.MaxPoint.Y - bd.MinPoint.Y) * 10, (bd.MaxPoint.Z - bd.MinPoint.Z) * 10]
    eje = lados.index(max(lados))
    lo = (bd.MinPoint.X, bd.MinPoint.Y, bd.MinPoint.Z)[eje] * 10
    alto0 = (col.ComponentDefinition.RangeBox.MaxPoint.Y - col.ComponentDefinition.RangeBox.MinPoint.Y) * 10
    delta = alto - alto0
    nuevo_cano = PZ / f"{cano_f.stem}_L{int(round(max(lados) + delta))}.ipt"
    if not nuevo_cano.exists():
        info = estirar(app, str(cano_f), nuevo_cano, eje, lo + 0.4 * max(lados), delta)
        log.setdefault("piezas", {})[nuevo_cano.name] = info
    col.SaveAs(str(ruta), True)
    c2 = app.Documents.Open(str(ruta), False)
    for o in its(c2.ComponentDefinition.Occurrences):
        if Path(o.Definition.Document.FullFileName) == cano_f:
            o.Replace(str(nuevo_cano), False)
    c2.Update()
    c2.Save()
    log.setdefault("piezas", {})[ruta.name] = [round(v * 10, 1) for v in (c2.ComponentDefinition.RangeBox.MinPoint.Y,
                                                                       c2.ComponentDefinition.RangeBox.MaxPoint.Y)]
    c2.Close(True)
    return str(ruta)


app.SilentOperation = True
try:
    PZ.mkdir(parents=True, exist_ok=True)
    cel = abrir(CELDA)
    cd = cel.ComponentDefinition
    occs = list(its(cd.Occurrences))
    rejas = [o for o in occs if o.Name.startswith("Reja_")]
    cols, panels = {}, {}
    plantilla = {}
    for o in rejas:
        if not S(lambda: o.Visible, True):
            continue                                   # ocultas (p. ej. el tramo reemplazado bajo el robot aéreo)
        m = re.match(r"Reja_(.+?)_col_(\d+)$", o.Name)
        mp = re.match(r"Reja_(.+?)_panel_(bajo|alto)_(\d+)$", o.Name)
        f = S(lambda: o.Definition.Document.FullFileName, "")
        if m and "Columna" in f:
            cols.setdefault(m.group(1), []).append(o)
            plantilla.setdefault("col", (f, mread(o.Transformation), caja(o)))
        elif mp and "Panel 03" in Path(f).name:
            panels.setdefault(mp.group(1), []).append((mp.group(2), o))
            c = caja(o)
            eje = "X" if (c[3] - c[0]) > (c[5] - c[2]) else "Z"
            plantilla.setdefault(f"panel_{eje}_{mp.group(2)}", (f, mread(o.Transformation), c))
    faltan = [k for k in ("col", "panel_X_bajo", "panel_X_alto") if k not in plantilla]
    if faltan:
        sys.exit(f"faltan plantillas: {faltan}")
    col_f, col_M, col_c = plantilla["col"]
    pan_f = plantilla["panel_X_bajo"][0]
    pc = plantilla["panel_X_bajo"][2]
    PAN_ANCHO0 = round(max(pc[3] - pc[0], pc[5] - pc[2]))
    PAN_ALTO0 = round(pc[4] - pc[1])
    ALTO_COL = col_c[4] - col_c[1]
    log["plantillas"] = {"columna": Path(col_f).name, "panel": Path(pan_f).name, "panel_ancho": PAN_ANCHO0, "panel_alto": PAN_ALTO0,
                         "alto_columna": round(ALTO_COL)}
    # líneas: centros de columnas ordenados a lo largo de la línea
    LIN = {}
    for nombre, lst in cols.items():
        if nombre.startswith("Norte_aereo"):
            continue
        pts = [((caja(o)[0] + caja(o)[3]) / 2, (caja(o)[2] + caja(o)[5]) / 2) for o in lst]
        ejeX = (max(p[0] for p in pts) - min(p[0] for p in pts)) >= (max(p[1] for p in pts) - min(p[1] for p in pts))
        pts.sort(key=lambda p: p[0] if ejeX else p[1])
        LIN[nombre] = {"eje": "X" if ejeX else "Z", "p0": list(pts[0]), "p1": list(pts[-1]), "n_cols": len(pts)}
        log.setdefault("columnas_actuales", {})[nombre] = [(o.Name, [round(v, 1) for v in p]) for o, p in
                                                           sorted(zip(lst, [((caja(o)[0] + caja(o)[3]) / 2, (caja(o)[2] + caja(o)[5]) / 2) for o in lst]),
                                                                  key=lambda t: t[1][0] if ejeX else t[1][1])]
    # esquinas: extremos de dos líneas perpendiculares a menos de 200 mm -> una sola columna en la intersección
    nombres = list(LIN)
    for i in range(len(nombres)):
        for j in range(i + 1, len(nombres)):
            a, b = LIN[nombres[i]], LIN[nombres[j]]
            if a["eje"] == b["eje"]:
                continue
            ax, bz = (a, b) if a["eje"] == "X" else (b, a)       # ax: línea a lo largo de X (z fija); bz: a lo largo de Z
            esquina = (bz["p0"][0], ax["p0"][1])
            hecho = False
            for la in ("p0", "p1"):
                for lb in ("p0", "p1"):
                    if not hecho and math.dist(ax[la], esquina) < 200 and math.dist(bz[lb], esquina) < 200:
                        ax[la] = [esquina[0], esquina[1]]
                        bz[lb] = [esquina[0], esquina[1]]
                        hecho = True
                        log["avisos"].append(f"esquina {nombres[i]}/{nombres[j]} unificada en {[round(v, 1) for v in esquina]}")
            # columna de esquina compartida: un extremo en la esquina y el otro tramo termina a menos de una bahía
            for (P, Q) in ((ax, bz), (bz, ax)):
                if hecho:
                    break
                for la in ("p0", "p1"):
                    if math.dist(P[la], esquina) < 200:
                        for lb in ("p0", "p1"):
                            otro = Q["p1" if lb == "p0" else "p0"]
                            d_esq, d_otro = math.dist(Q[lb], esquina), math.dist(otro, esquina)
                            if 200 <= d_esq <= 1400 and d_otro > d_esq:
                                Q[lb] = [esquina[0], esquina[1]]
                                P[la] = [esquina[0], esquina[1]]
                                hecho = True
                                log["avisos"].append(f"tramo {nombres[i]}/{nombres[j]} extendido hasta la esquina {[round(v, 1) for v in esquina]}")
                                break
                    if hecho:
                        break
    # plan de cada línea
    plan = []
    for nombre, L in LIN.items():
        p0, p1 = L["p0"], L["p1"]
        largo = math.dist(p0, p1)
        bs = bahias(largo)
        u = ((p1[0] - p0[0]) / largo, (p1[1] - p0[1]) / largo)
        posts, s = [tuple(p0)], 0.0
        for b in bs:
            s += b
            posts.append((p0[0] + u[0] * s, p0[1] + u[1] * s))
        bays = []
        for k, b in enumerate(bs):
            a_, c_ = posts[k], posts[k + 1]
            cx, cz = (a_[0] + c_[0]) / 2, (a_[1] + c_[1]) / 2
            x0, x1 = min(a_[0], c_[0]) + LUZ_CANO, max(a_[0], c_[0]) - LUZ_CANO
            bajo_aereo = (CUAL == "A" and nombre in LINEAS_AEREO and L["eje"] == "X" and x1 > AEREO_X[0] and x0 < AEREO_X[1])
            bays.append({"centro": (cx, cz), "ancho": round(b - 2 * LUZ_CANO), "aereo": bajo_aereo})
        post_info = []
        for k, p in enumerate(posts):
            corto = (CUAL == "A" and nombre in LINEAS_AEREO and AEREO_X[0] - 90 < p[0] < AEREO_X[1] + 90)
            post_info.append({"p": p, "corta": corto})
        plan.append({"linea": nombre, "eje": L["eje"], "largo": round(largo, 1), "bahias": [round(b, 1) for b in bs],
                     "posts": post_info, "bays": bays})
        log["lineas"].append({"linea": nombre, "largo": round(largo, 1), "bahias": [round(b, 1) for b in bs],
                              "columnas_antes": L["n_cols"], "columnas_despues": len(posts),
                              "bajo_aereo": [k + 1 for k, b in enumerate(bays) if b["aereo"]]})
    # columnas compartidas entre líneas (esquinas): se ponen una sola vez
    if not PROBAR:
        resp = CELDA.with_name(CELDA.stem + "_antes_rejas_v2.iam")
        if not resp.exists():
            cel.SaveAs(str(resp), True)
        col_corta = columna_corta(col_f, H_AEREO) if CUAL == "A" else None
        # alturas de los paneles (plantilla: bajo y alto)
        yb0 = plantilla["panel_X_bajo"][2][1]
        ya0 = plantilla["panel_X_alto"][2][1]
        alto_corto = H_AEREO - ya0           # panel alto recortado: de su base (1055) hasta 1400
        borrados = 0
        for o in list(its(cd.Occurrences)):
            if o.Name.startswith("Reja_"):
                o.Delete()
                borrados += 1
        log["borrados"] = borrados
        puestas = set()
        n_add = 0

        def add(f, R, t, nombre):
            global n_add
            o = cd.Occurrences.Add(f, mmake(R, t))
            S(lambda: setattr(o, "Name", nombre))
            S(lambda: setattr(o, "Grounded", True))
            n_add += 1
            return o

        def colocar(f, Mplant, cplant, cx, cz, y0, nombre):
            """Pone la pieza f con la rotación de la plantilla, su centro de caja en (cx, cz) y la base en y0."""
            R = [r[:3] for r in Mplant]
            t = [Mplant[0][3], Mplant[1][3], Mplant[2][3]]
            ccx, ccz = (cplant[0] + cplant[3]) / 2, (cplant[2] + cplant[5]) / 2
            # la caja de la plantilla es la de la pieza original: para otra pieza (más angosta) el centro local puede
            # cambiar; se corrige después midiendo la ocurrencia puesta
            t2 = [t[0] + (cx - ccx) - ORG[0], t[1] + (y0 - cplant[1]), t[2] + (cz - ccz) - ORG[2]]
            o = add(f, R, t2, nombre)
            c = caja(o)
            dx, dy, dz = cx - (c[0] + c[3]) / 2, y0 - c[1], cz - (c[2] + c[5]) / 2
            if max(abs(dx), abs(dy), abs(dz)) > 0.5:
                m = o.Transformation
                v = tg.CreateMatrix()
                v.SetTranslation(tg.CreateVector(dx / 10, dy / 10, dz / 10))
                m.TransformBy(v)
                S(lambda: setattr(o, "Grounded", False))
                o.Transformation = m
                S(lambda: setattr(o, "Grounded", True))
            return o

        for L in plan:
            nombre, eje = L["linea"], L["eje"]
            pb = plantilla.get(f"panel_{eje}_bajo") or plantilla["panel_X_bajo"]
            pa = plantilla.get(f"panel_{eje}_alto") or plantilla["panel_X_alto"]
            for k, pi in enumerate(L["posts"]):
                key = (round(pi["p"][0]), round(pi["p"][1]))
                if key in puestas:
                    continue
                puestas.add(key)
                f = col_corta if (pi["corta"] and col_corta) else col_f
                colocar(f, col_M, col_c, pi["p"][0], pi["p"][1], 0.0, f"Reja_{nombre}_col_{k + 1}" + ("_H1400" if pi["corta"] else ""))
            for k, b in enumerate(L["bays"]):
                fb = pb[0] if abs(b["ancho"] - PAN_ANCHO0) < 1 else pieza_panel(pb[0], PAN_ANCHO0, PAN_ALTO0, b["ancho"], PAN_ALTO0)
                colocar(fb or pb[0], pb[1], pb[2], b["centro"][0], b["centro"][1], pb[2][1], f"Reja_{nombre}_panel_bajo_{k + 1}")
                alto = alto_corto if b["aereo"] else PAN_ALTO0
                fa = pa[0] if (abs(b["ancho"] - PAN_ANCHO0) < 1 and not b["aereo"]) else pieza_panel(pa[0], PAN_ANCHO0, PAN_ALTO0, b["ancho"], alto)
                colocar(fa or pa[0], pa[1], pa[2], b["centro"][0], b["centro"][1], pa[2][1],
                        f"Reja_{nombre}_panel_alto_{k + 1}" + ("_H1400" if b["aereo"] else ""))
        log["agregados"] = n_add
        cel.Update()
        cel.Save()
        # verificación: luz entre cada panel y los caños vecinos (en planta, a lo largo de la línea)
        occ = {o.Name: o for o in its(cd.Occurrences)}
        peor = []
        for L in plan:
            for k, b in enumerate(L["bays"]):
                o = occ.get(f"Reja_{L['linea']}_panel_bajo_{k + 1}")
                if o is None:
                    continue
                c = caja(o)
                ancho = (c[3] - c[0]) if L["eje"] == "X" else (c[5] - c[2])
                peor.append(round(L["bahias"][k] - 60 - ancho, 1))
        log["luz_total_panel_canos_min_max"] = [min(peor), max(peor)] if peor else None
finally:
    S(lambda: setattr(app, "SilentOperation", False))
print(json.dumps(log, ensure_ascii=False, indent=1))
