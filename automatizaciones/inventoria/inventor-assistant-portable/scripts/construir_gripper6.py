"""Gripper de 6 paquetes (DosHermanos): apriete a lo largo del eje de los paquetes, pala fija central y 2 palas
móviles exteriores con Festo DSNU-10-25 y guías miniatura MGW (las del proyecto). Cilindros POR DENTRO, bajo el
chasis en C; brida en U invertida como los demás grippers DEFYMOTION. Chapa de acero de 2 mm.

Coordenadas del gripper (mm): X a lo largo del eje de los paquetes, Y a lo ancho (3 paquetes), Z hacia arriba,
Z = 0 base de los paquetes. Posición dibujada: CERRADO (palas apretando, vástagos retraídos).

Uso: python construir_gripper6.py [--reusar-piezas] [--rehacer Frame ...] [--solo-diseno]
Salida: Documents\\InventorIA\\Generados\\GRIPPER6_DOSHERMANOS\\ (Chapas, Corte_laser, Ensamble, resultado.json)
"""
import argparse
import json
import math
import sys
import time
import traceback
from dataclasses import asdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
from gripper_design import FlatPart, bend_geometry, rounded_rect, hex_grid  # noqa: E402

a = argparse.ArgumentParser()
a.add_argument("--nombre", default="GRIPPER6_DOSHERMANOS")
a.add_argument("--espesor", type=float, default=2.0)
a.add_argument("--reusar-piezas", action="store_true")
a.add_argument("--rehacer", nargs="*", default=[])
a.add_argument("--solo-diseno", action="store_true", help="sólo calcula (sin Inventor)")
x = a.parse_args()

# ============================================================================ parámetros
T = x.espesor
G = bend_geometry(T)
SB, BA = G["setback"], G["ba"]
HEX = {"flats": 20.0, "pitch": 25.0, "margin": 8.0}
MAT = "Acero SAE 1010"
# paquetes Ø90 x 260, 3 a lo ancho (paso 90) x 2 a lo largo, contra la pala fija (X = ±1)
PAQ = {"d": 90.0, "largo": 160.0, "paso_y": 90.0, "n_y": 3, "masa_kg": 0.2}   # galletas de arroz Dos Hermanos
YP = [(i - 1) * PAQ["paso_y"] for i in range(PAQ["n_y"])]
X_PAQ_EXT = 1.0 + PAQ["largo"]                  # cara interior de la pala móvil (cerrado)
CARRERA = 25.0
# chasis en C (alas hacia arriba)
Z_ALMA = 125.0                                  # cara inferior del alma del chasis
X_OUT = X_PAQ_EXT + 2.0                         # cara exterior de la pala móvil (cerrado)
FR = {"ancho": 160.0, "ala": 35.0, "largo": 2 * (X_OUT + CARRERA + 7.0), "ala_punta": 14.0, "ala_plena": 90.0}
# pala móvil en U invertida: cara + ala (bajo las guías) + orejeta (vástago)
PM = {"ancho": 260.0, "z_inf": 35.0, "z_sup": Z_ALMA - 4.0, "x_orejeta": X_OUT - 52.0, "z_orejeta": 100.0}
# guías MGW (riel 50 con agujeros cada 10 en x = -20..20; bloque con 2 agujeros M2 a x -18,78 y -12,28)
GUIA = {"y": 70.0, "x_riel": X_OUT - 12.47, "rieles_x": (-20, -10, 0, 10, 20),
        "bloque_x": (-18.78, -12.28), "d_riel": 2.0, "d_bloque": 2.4}
# cilindro DSNU-10-25: origen del modelo (cara de la tuerca de montaje) en X0, eje a Z_CIL
CIL = {"x0": X_OUT - 52.0 - 11.0, "z": 110.0, "d_rosca": 12.5, "d_vastago": 4.5}
SOP = {"ancho": 40.0, "alto": 30.0, "ala": 20.0, "x_cara": CIL["x0"] - 6.33, "d_frame": 4.5, "y_ag": 12.0}
PF = {"ancho": 260.0, "alto": 95.0, "ala": 30.0, "z_inf": Z_ALMA - 95.0, "y_ag": (-50.0, 0.0, 50.0)}
BR = {"largo": 100.0, "pata": 45.0, "solape": 22.0, "d_pata": 5.5, "x_ag": (-30.0, 30.0),
      "centro_d": 20.0, "pcd": 44.0, "pcd_d": 6.6, "pcd_ang": (0, 90, 180, 270)}
Z_ALA_TOP = Z_ALMA + FR["ala"]
Z_AG_BRIDA = Z_ALA_TOP - BR["solape"] / 2       # mitad del solape ala-pata


# ============================================================================ chapas (desarrollos)
def frame():
    W_out, H_ala, L = FR["ancho"], FR["ala"], FR["largo"]
    fl, web = H_ala - SB, W_out - 2 * SB
    W = 2 * fl + web + 2 * BA
    b1, b2 = fl + BA / 2, W - fl - BA / 2
    xc = W / 2

    def xy(X, Y):
        return (round(xc + Y, 3), round(X + L / 2, 3))
    circ = []
    for s in (-1, 1):
        for yr in (-GUIA["y"], GUIA["y"]):
            for dx in GUIA["rieles_x"]:
                circ.append((*xy(s * (GUIA["x_riel"] + dx), yr), GUIA["d_riel"]))
        x_sop = s * (SOP["x_cara"] - 2 - (SOP["ala"] - SB) / 2 - 2)          # centro del ala del soporte
        for yy in (-SOP["y_ag"], SOP["y_ag"]):
            circ.append((*xy(x_sop, yy), SOP["d_frame"]))
    for yy in PF["y_ag"]:
        circ.append((*xy(-1 + PF["ala"] - (PF["ala"] - SB) / 2, yy), 4.5))
    for xb in BR["x_ag"]:                                                     # brida en las alas
        zz = Z_ALA_TOP - Z_AG_BRIDA
        circ += [(zz, xb + L / 2, BR["d_pata"]), (W - zz, xb + L / 2, BR["d_pata"])]
    # alivianado del alma fuera de rieles, soportes y pala fija
    ko = []
    for s in (-1, 1):
        x0, x1 = sorted((s * (GUIA["x_riel"] - 27), s * (GUIA["x_riel"] + 27)))
        ko += [(xy(x0, -GUIA["y"] - 6)[0], xy(x0, 0)[1], xy(x1, -GUIA["y"] + 6)[0], xy(x1, 0)[1]),
               (xy(x0, GUIA["y"] - 6)[0], xy(x0, 0)[1], xy(x1, GUIA["y"] + 6)[0], xy(x1, 0)[1])]
        x0, x1 = sorted((s * (SOP["x_cara"] - SOP["ala"] - 4), s * (SOP["x_cara"] + 2)))
        ko.append((xy(0, -SOP["ancho"] / 2)[0], xy(x0, 0)[1], xy(0, SOP["ancho"] / 2)[0], xy(x1, 0)[1]))
    ko.append((xy(0, -70)[0], xy(-6, 0)[1], xy(0, 70)[0], xy(PF["ala"] + 4, 0)[1]))
    hexes = hex_grid(fl + BA, 0, fl + BA + web, L, ko, pitch=HEX["pitch"], flats=HEX["flats"], margin=HEX["margin"])
    # alas a altura plena en la zona de la brida (±ala_plena) y bajando en recta hasta ala_punta en los extremos
    d_ = H_ala - FR["ala_punta"]
    y_a, y_b = L / 2 - FR["ala_plena"], L / 2 + FR["ala_plena"]
    cont = [(d_, 0, 0), (W - d_, 0, 0), (W - d_, 0.001, 0), (W, y_a, 0), (W, y_b, 0), (W - d_, L - 0.001, 0),
            (W - d_, L, 0), (d_, L, 0), (d_, L - 0.001, 0), (0, y_b, 0), (0, y_a, 0), (d_, 0.001, 0)]
    cont = [(d_, 0, 0), (W - d_, 0, 0), (W, y_a, 0), (W, y_b, 0), (W - d_, L, 0), (d_, L, 0), (0, y_b, 0),
            (0, y_a, 0)]
    return FlatPart(nombre="Chasis", cantidad=1, espesor=T, material=MAT, contorno=cont,
                    circulos=circ, hexagonos=hexes, hex_flats=HEX["flats"],
                    pliegues=[{"eje": "x", "pos": b1, "angulo": 90, "sentido": 1},
                              {"eje": "x", "pos": b2, "angulo": 90, "sentido": 1}],
                    envolvente_plegada=(W_out, H_ala, L),
                    notas=["Chasis en C (alas hacia arriba); brida atornillada por dentro de las alas."])


def pala_movil():
    w = PM["ancho"]
    h_cara = PM["z_sup"] - PM["z_inf"]                       # 91
    l_ala = (X_PAQ_EXT + T) - PM["x_orejeta"]                # 52
    h_or = PM["z_sup"] - PM["z_orejeta"]                     # 21
    cf, al, orj = h_cara - SB, l_ala - 2 * SB, h_or - SB
    H = cf + BA + al + BA + orj
    y1, y2 = cf + BA / 2, cf + BA + al + BA / 2
    x_out = X_PAQ_EXT + T                                    # cara exterior de la pala (cerrado)
    circ = []
    for yr in (-GUIA["y"], GUIA["y"]):
        for bx in GUIA["bloque_x"]:
            X = GUIA["x_riel"] + bx
            circ.append((w / 2 + yr, round(cf + BA + (x_out - SB - X), 3), GUIA["d_bloque"]))
    circ.append((w / 2, round(H - (CIL["z"] - PM["z_orejeta"]), 3), CIL["d_vastago"]))
    hexes = hex_grid(0, 0, w, cf, [], pitch=HEX["pitch"], flats=HEX["flats"], margin=HEX["margin"])
    return FlatPart(nombre="Pala movil", cantidad=2, espesor=T, material=MAT, contorno=rounded_rect(0, 0, w, H, 5),
                    circulos=circ, hexagonos=hexes, hex_flats=HEX["flats"],
                    pliegues=[{"eje": "y", "pos": y1, "angulo": 90, "sentido": 1},
                              {"eje": "y", "pos": y2, "angulo": 90, "sentido": 1}],
                    envolvente_plegada=(w, l_ala, h_cara))


def pala_fija():
    w, H_, ala = PF["ancho"], PF["alto"], PF["ala"]
    fl, cf = ala - SB, H_ - SB
    H = fl + BA + cf
    circ = [(w / 2 + yy, round(fl / 2, 3), 4.5) for yy in PF["y_ag"]]
    return FlatPart(nombre="Pala fija", cantidad=1, espesor=T, material=MAT, contorno=rounded_rect(0, 0, w, H, 5),
                    circulos=circ, pliegues=[{"eje": "y", "pos": fl + BA / 2, "angulo": 90, "sentido": 1}],
                    envolvente_plegada=(w, ala, H_), notas=["Sin hexágonos (regla DEFYMOTION)."])


def soporte():
    w, h, ala = SOP["ancho"], SOP["alto"], SOP["ala"]
    cf, fl = h - SB, ala - SB
    H = cf + BA + fl
    z_inf = Z_ALMA - h
    circ = [(w / 2, round(CIL["z"] - z_inf, 3), CIL["d_rosca"])]
    circ += [(w / 2 + yy, round(cf + BA + fl / 2, 3), SOP["d_frame"]) for yy in (-SOP["y_ag"], SOP["y_ag"])]
    return FlatPart(nombre="Soporte cilindro", cantidad=2, espesor=T, material=MAT,
                    contorno=rounded_rect(0, 0, w, H, 4), circulos=circ,
                    pliegues=[{"eje": "y", "pos": cf + BA / 2, "angulo": 90, "sentido": 1}],
                    envolvente_plegada=(w, ala, h))


def brida():
    ancho = FR["ancho"] - 2 * T                              # entre las alas del chasis
    leg, web = BR["pata"] - SB, ancho - 2 * SB
    W = 2 * leg + web + 2 * BA
    L = BR["largo"]
    circ = []
    for xb in BR["x_ag"]:
        e_ = BR["solape"] / 2
        circ += [(e_, L / 2 + xb, BR["d_pata"]), (W - e_, L / 2 + xb, BR["d_pata"])]
    cx, cy = W / 2, L / 2
    circ.append((cx, cy, BR["centro_d"]))
    for a_ in BR["pcd_ang"]:
        circ.append((round(cx + BR["pcd"] / 2 * math.cos(math.radians(a_)), 3),
                     round(cy + BR["pcd"] / 2 * math.sin(math.radians(a_)), 3), BR["pcd_d"]))
    return FlatPart(nombre="Brida", cantidad=1, espesor=T, material=MAT, contorno=rounded_rect(0, 0, W, L, 10),
                    circulos=circ,
                    pliegues=[{"eje": "x", "pos": leg + BA / 2, "angulo": 90, "sentido": 1},
                              {"eje": "x", "pos": W - leg - BA / 2, "angulo": 90, "sentido": 1}],
                    envolvente_plegada=(ancho, BR["pata"], L),
                    notas=["Patrón del robot Borunte BRTIRUS0805A A CONFIRMAR (relevado del modelo: PCD 44)."])


CHAPAS = [frame(), pala_movil(), pala_fija(), soporte(), brida()]
# masa estimada (desarrollo - agujeros - hexágonos)
RHO = 7.85e-6


def area_contorno(c):
    return abs(sum(c[i][0] * c[(i + 1) % len(c)][1] - c[(i + 1) % len(c)][0] * c[i][1] for i in range(len(c)))) / 2


EST = {}
for p in CHAPAS:
    A = area_contorno(p.contorno) - sum(math.pi * d * d / 4 for _, _, d in p.circulos) \
        - len(p.hexagonos) * (math.sqrt(3) / 2 * p.hex_flats ** 2)
    EST[p.nombre] = round(A * p.espesor * RHO * p.cantidad, 3)
COMERCIALES = [{"pieza": "Festo DSNU-10-25-P-A + tuerca DIN 439 M12x1,25", "cantidad": 2},
               {"pieza": "Tuerca DIN 439 M12x1,25 adicional (contratuerca soporte)", "cantidad": 2},
               {"pieza": "Tuerca M4 (vástago, a cada lado de la orejeta)", "cantidad": 4},
               {"pieza": "Guía miniatura MGW2C1R50Z0CM (riel 50 + bloque)", "cantidad": 4}]
DIS = {"espesor": T, "masa_chapas_estimada_kg": EST, "total_chapas_kg": round(sum(EST.values()), 2),
       "carga_paquetes_kg": PAQ["masa_kg"] * 6, "comerciales": COMERCIALES,
       "fuerza": {"requerida_por_pala_N": round(3 * PAQ["masa_kg"] * (9.81 + 5) * 2 / (2 * 0.4), 1),
                  "dsnu10_retraer_8bar_N": round((math.pi / 4 * (1.0 ** 2 - 0.4 ** 2)) * 8 * 10, 1)},
       "chapas": [{**p.resumen(), "hexagonos": len(p.hexagonos)} for p in CHAPAS]}
if x.solo_diseno:
    print(json.dumps(DIS, ensure_ascii=False, indent=1))
    sys.exit(0)

# ============================================================================ Inventor
import inventor_mcp as inv  # noqa: E402

S = inv._safe
BASE = Path.home() / "Documents" / "InventorIA" / "Generados" / x.nombre
CH, DXF, ENS = BASE / "Chapas", BASE / "Corte_laser", BASE / "Ensamble"
for p_ in (CH, DXF, ENS):
    p_.mkdir(parents=True, exist_ok=True)
DH = Path.home() / "Documents" / "InventorIA" / "DosHermanos IA"
F_DSNU = DH / "Piston 10x25" / "19184 DSNU-10-25-P-A---(0).iam"
F_GUIA = DH / "MGW2C1R50Z0CM_GW202610004555" / "MGW2C1R50Z0CM_GW202610004555" / "MGW2C1R50Z0CM_GW202610004555.iam"
F_PAQ = Path.home() / "Documents" / "InventorIA" / "Generados" / x.nombre / "Chapas" / "Paquete galletas D90x160.ipt"
app = inv._inventor(start_if_needed=False)
tg = app.TransientGeometry
app.SilentOperation = True
T0 = time.time()
log = {"nombre": x.nombre, "diseno": DIS, "piezas": [], "colocacion": {}, "avisos": [], "errores": []}


def etapa(t_):
    print(f"[{time.time() - T0:6.1f} s] {t_}", flush=True)


def mmake(M):
    m = tg.CreateMatrix()
    m.SetCoordinateSystem(tg.CreatePoint(M[0][3] / 10, M[1][3] / 10, M[2][3] / 10),
                          tg.CreateVector(M[0][0], M[1][0], M[2][0]), tg.CreateVector(M[0][1], M[1][1], M[2][1]),
                          tg.CreateVector(M[0][2], M[1][2], M[2][2]))
    return m


def mmul(A, B):
    return [[sum(A[i][k] * B[k][j] for k in range(4)) for j in range(4)] for i in range(4)]


def ptx(M, p):
    return [M[i][0] * p[0] + M[i][1] * p[1] + M[i][2] * p[2] + M[i][3] for i in range(3)]


def box_tx(M, b):
    pts = [ptx(M, [b[i][0], b[j][1], b[k][2]]) for i in (0, 1) for j in (0, 1) for k in (0, 1)]
    return [[min(p[q] for p in pts) for q in range(3)], [max(p[q] for p in pts) for q in range(3)]]


RZ180 = [[-1, 0, 0, 0], [0, -1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]


def rotaciones():
    import itertools
    out = []
    for perm in itertools.permutations(range(3)):
        for sg in itertools.product((1, -1), repeat=3):
            R = [[0] * 3 for _ in range(3)]
            for i in range(3):
                R[i][perm[i]] = sg[i]
            det = (R[0][0] * (R[1][1] * R[2][2] - R[1][2] * R[2][1]) - R[0][1] * (R[1][0] * R[2][2] - R[1][2]
                   * R[2][0]) + R[0][2] * (R[1][0] * R[2][1] - R[1][1] * R[2][0]))
            if det == 1:
                out.append(R)
    return out


ROTS = rotaciones()


def firma(doc):
    cd = doc.ComponentDefinition
    pts = []
    for body in inv._items(cd.SurfaceBodies):
        for e in inv._items(body.Edges):
            g = S(lambda: e.Geometry)
            if g is None or S(lambda: g.StartAngle) is not None:
                continue
            c, r, n = S(lambda: g.Center), S(lambda: g.Radius), S(lambda: g.Normal)
            if c is None or r is None or n is None or r * 20 > 30:
                continue
            pts.append(((c.X * 10, c.Y * 10, c.Z * 10), (n.X, n.Y, n.Z), round(r * 20, 2)))
    b = cd.RangeBox
    return pts, [[b.MinPoint.X * 10, b.MinPoint.Y * 10, b.MinPoint.Z * 10],
                 [b.MaxPoint.X * 10, b.MaxPoint.Y * 10, b.MaxPoint.Z * 10]]


def dist_eje(p, c, n):
    v = [p[i] - c[i] for i in range(3)]
    k = sum(v[i] * n[i] for i in range(3))
    w = [v[i] - k * n[i] for i in range(3)]
    return math.sqrt(sum(q * q for q in w))


def registrar(doc, box_t, ejes):
    """Orientación (de las 24) y traslación para que la caja coincida con box_t; se elige la que pone más
    agujeros sobre los ejes objetivo [(centro, normal, d)]."""
    P, bp = firma(doc)
    dt = [box_t[1][i] - box_t[0][i] for i in range(3)]
    ct = [(box_t[0][i] + box_t[1][i]) / 2 for i in range(3)]
    best = None
    for R in ROTS:
        M = [[R[0][0], R[0][1], R[0][2], 0], [R[1][0], R[1][1], R[1][2], 0], [R[2][0], R[2][1], R[2][2], 0],
             [0, 0, 0, 1]]
        bb = box_tx(M, bp)
        err = sum(abs((bb[1][i] - bb[0][i]) - dt[i]) for i in range(3))
        if err > 1.5:
            continue
        for i in range(3):
            M[i][3] = ct[i] - (bb[0][i] + bb[1][i]) / 2
        ok = 0
        for c, n, d in P:
            pc = ptx(M, c)
            if any(abs(ed - d) < 0.3 and dist_eje(pc, ec, en) < 0.6 for ec, en, ed in ejes):
                ok += 1
        sc = (ok, -err)
        if best is None or sc > best[0]:
            best = (sc, M)
    if best is None:
        raise RuntimeError(f"{Path(doc.FullFileName).name}: ninguna orientación coincide con {dt}")
    return best[1], {"agujeros_ok": best[0][0], "agujeros_pieza": len(P), "error_caja": round(-best[0][1], 2)}


# ---------------------------------------------------------------------------- 1) chapas
# cerrar (sin guardar) todo lo abierto de esta carpeta: si no, no se pueden sobrescribir las piezas
for tipo in (inv.K_ASSEMBLY_DOCUMENT, inv.K_PART_DOCUMENT):
    for dd in list(inv._items(app.Documents)):
        if S(lambda: BASE.resolve() in Path(dd.FullFileName).resolve().parents, False) and \
                S(lambda: dd.DocumentType) == tipo:
            S(lambda: dd.Close(True))
archivos = {}
for p in CHAPAS:
    s = asdict(p)
    s["desarrollo"] = p.flat_size()
    ipt = CH / f"{p.nombre}.ipt"
    archivos[p.nombre] = ipt
    if x.reusar_piezas and ipt.exists() and p.nombre not in x.rehacer:
        continue
    etapa(f"Chapa {p.nombre} ({len(p.circulos)} agujeros, {len(p.hexagonos)} hexágonos)")
    try:
        for dd in inv._items(app.Documents):
            if S(lambda: Path(dd.FullFileName).resolve() == ipt.resolve(), False):
                dd.Close(True)
        r = inv.build_flat_part(app, s, ipt, DXF / f"{p.nombre}.dxf")
        d_ = r.pop("documento")
        S(lambda: d_.Close(True))
    except Exception as exc:  # noqa: BLE001
        r = {"pieza": p.nombre, "error": repr(exc), "traza": traceback.format_exc()[-1500:]}
        log["errores"].append(r)
    log["piezas"].append(r)

# paquete de galletas (para ver el gripper cargado): cilindro Ø90 x 160 a lo largo de +Z desde el origen
if not F_PAQ.exists() or "Paquete" in x.rehacer:
    etapa("Paquete de galletas")
    pd_ = app.Documents.Add(inv.K_PART_DOCUMENT, app.FileManager.GetTemplateFile(inv.K_PART_DOCUMENT), False)
    pcd_ = pd_.ComponentDefinition
    sk_ = pcd_.Sketches.Add(pcd_.WorkPlanes.Item(3))
    sk_.SketchCircles.AddByCenterRadius(tg.CreatePoint2d(0, 0), PAQ["d"] / 20)
    pcd_.Features.ExtrudeFeatures.AddByDistanceExtent(sk_.Profiles.AddForSolid(), PAQ["largo"] / 10, 20993, 20481)
    S(lambda: setattr(pd_.ComponentDefinition.Material, "Name", pd_.ComponentDefinition.Material.Name))
    pd_.SaveAs(str(F_PAQ), False)
    S(lambda: pd_.Close(True))

# ---------------------------------------------------------------------------- 2) objetivos (cerrado)
ZN, XN, YN = (0, 0, 1), (1, 0, 0), (0, 1, 0)
XO = X_OUT


def obj_pala_movil(s):
    box = [[PM["x_orejeta"], -PM["ancho"] / 2, PM["z_inf"]], [XO, PM["ancho"] / 2, PM["z_sup"]]]
    ejes = [((GUIA["x_riel"] + bx, yr, PM["z_sup"]), ZN, GUIA["d_bloque"]) for yr in (-GUIA["y"], GUIA["y"])
            for bx in GUIA["bloque_x"]] + [((PM["x_orejeta"] + 1, 0, CIL["z"]), XN, CIL["d_vastago"])]
    return espejo(box, ejes, s)


def espejo(box, ejes, s):
    if s > 0:
        return box, ejes
    b2 = [[-box[1][0], -box[1][1], box[0][2]], [-box[0][0], -box[0][1], box[1][2]]]
    return b2, [((-c[0], -c[1], c[2]), n, d) for c, n, d in ejes]


def obj_soporte(s):
    xc = SOP["x_cara"]
    box = [[xc - SOP["ala"], -SOP["ancho"] / 2, Z_ALMA - SOP["alto"]], [xc, SOP["ancho"] / 2, Z_ALMA]]
    x_ag = xc - 2 - (SOP["ala"] - SB) / 2 - 2
    ejes = [((xc - 1, 0, CIL["z"]), XN, CIL["d_rosca"])] + \
           [((x_ag, yy, Z_ALMA - 1), ZN, SOP["d_frame"]) for yy in (-SOP["y_ag"], SOP["y_ag"])]
    return espejo(box, ejes, s)


L = FR["largo"]
obj = {
    "Chasis": ([[-L / 2, -FR["ancho"] / 2, Z_ALMA], [L / 2, FR["ancho"] / 2, Z_ALA_TOP]],
               [((sg * (GUIA["x_riel"] + dx), yr, Z_ALMA + 1), ZN, GUIA["d_riel"]) for sg in (-1, 1)
                for yr in (-GUIA["y"], GUIA["y"]) for dx in GUIA["rieles_x"]] +
               [((xb, yy, Z_AG_BRIDA), YN, BR["d_pata"]) for xb in BR["x_ag"] for yy in (-79, 79)]),
    "Pala fija": ([[-1, -PF["ancho"] / 2, PF["z_inf"]], [-1 + PF["ala"], PF["ancho"] / 2, Z_ALMA]],
                  [((-1 + PF["ala"] - (PF["ala"] - SB) / 2, yy, Z_ALMA - 1), ZN, 4.5) for yy in PF["y_ag"]]),
    "Brida": ([[-BR["largo"] / 2, -(FR["ancho"] / 2 - T), Z_ALA_TOP - BR["solape"]],
               [BR["largo"] / 2, FR["ancho"] / 2 - T, Z_ALA_TOP - BR["solape"] + BR["pata"]]],
              [((xb, yy, Z_AG_BRIDA), YN, BR["d_pata"]) for xb in BR["x_ag"] for yy in (-77, 77)]
              + [((0, 0, Z_ALA_TOP - BR["solape"] + BR["pata"] - 1), ZN, BR["centro_d"])]),
}

# ---------------------------------------------------------------------------- 3) ensamble
etapa("Ensamble")
top_path = ENS / "Gripper6_DosHermanos.iam"
for dd in list(inv._items(app.Documents)):
    if S(lambda: Path(dd.FullFileName).resolve() == top_path.resolve(), False):
        dd.Close(True)
if top_path.exists():
    top_path.unlink()
tdoc = app.Documents.Add(inv.K_ASSEMBLY_DOCUMENT, app.FileManager.GetTemplateFile(inv.K_ASSEMBLY_DOCUMENT), True)
tcd = tdoc.ComponentDefinition
occs = {}


def poner(clave, ruta, M, fija=True):
    o = tcd.Occurrences.Add(str(ruta), mmake(M))
    S(lambda: setattr(o, "Grounded", fija))
    occs.setdefault(clave, []).append(o)
    return o


def abrir_doc(ruta):
    for dd in inv._items(app.Documents):
        if S(lambda: Path(dd.FullFileName).resolve() == Path(ruta).resolve(), False):
            return dd
    return app.Documents.Open(str(ruta), False)


for nombre, (box, ejes) in obj.items():
    try:
        M, info = registrar(abrir_doc(archivos[nombre]), box, ejes)
        poner(nombre, archivos[nombre], M)
        log["colocacion"][nombre] = info
    except Exception as exc:  # noqa: BLE001
        log["errores"].append({"pieza": nombre, "error": repr(exc)})
for s in (1, -1):
    for nombre, f in (("Pala movil", obj_pala_movil), ("Soporte cilindro", obj_soporte)):
        try:
            box, ejes = f(s)
            M, info = registrar(abrir_doc(archivos[nombre]), box, ejes)
            poner(nombre, archivos[nombre], M)
            log["colocacion"][f"{nombre} {'+' if s > 0 else '-'}"] = info
        except Exception as exc:  # noqa: BLE001
            log["errores"].append({"pieza": nombre, "lado": s, "error": repr(exc)})
# comerciales (cerrado: vástagos retraídos)
M_CIL = [[0, 0, 1, CIL["x0"]], [1, 0, 0, 0], [0, 1, 0, CIL["z"]], [0, 0, 0, 1]]
for s in (1, -1):
    Rs = RZ180 if s < 0 else [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]
    try:
        poner("DSNU-10-25", F_DSNU, mmul(Rs, M_CIL))
    except Exception as exc:  # noqa: BLE001
        log["errores"].append({"pieza": "DSNU", "error": repr(exc)})
    for yr in (-GUIA["y"], GUIA["y"]):
        M_G = [[1, 0, 0, GUIA["x_riel"]], [0, 0, 1, yr], [0, -1, 0, Z_ALMA - 2.6], [0, 0, 0, 1]]
        try:
            poner("Guia MGW", F_GUIA, mmul(Rs, M_G))
        except Exception as exc:  # noqa: BLE001
            log["errores"].append({"pieza": "Guia", "error": repr(exc)})
    for yc in YP:
        M_P = [[0, 0, 1, 1.0], [1, 0, 0, yc], [0, 1, 0, PAQ["d"] / 2], [0, 0, 0, 1]]
        try:
            o = poner("Paquete", F_PAQ, mmul(Rs, M_P))
            S(lambda: setattr(o, "Name", f"Paquete {'+' if s > 0 else '-'}{int(yc)}"))
        except Exception as exc:  # noqa: BLE001
            log["errores"].append({"pieza": "Paquete", "error": repr(exc)})
tdoc.Update()
tdoc.SaveAs(str(top_path), False)

# ---------------------------------------------------------------------------- 4) verificación
etapa("Verificación")
def bx(o):
    b = o.RangeBox
    return [[round(b.MinPoint.X * 10, 1), round(b.MinPoint.Y * 10, 1), round(b.MinPoint.Z * 10, 1)],
            [round(b.MaxPoint.X * 10, 1), round(b.MaxPoint.Y * 10, 1), round(b.MaxPoint.Z * 10, 1)]]


masa = 0.0
cajas = {}
for k, lst in occs.items():
    for o in lst:
        cajas[o.Name] = bx(o)
        if k != "Paquete":
            masa += S(lambda: o.MassProperties.Mass, 0.0)
log["masa_gripper_kg"] = round(masa, 3)
log["masa_total_con_paquetes_kg"] = round(masa + 6 * PAQ["masa_kg"], 3)
log["cajas"] = cajas
sin_paq = [o for k, lst in occs.items() if k != "Paquete" for o in lst]
env = [[min(cajas[o.Name][0][i] for o in sin_paq) for i in range(3)],
       [max(cajas[o.Name][1][i] for o in sin_paq) for i in range(3)]]
log["envolvente_gripper"] = env
try:
    col = app.TransientObjects.CreateObjectCollection()
    for k, lst in occs.items():
        for o in lst:
            col.Add(o)
    res_i = tcd.AnalyzeInterference(col)
    log["interferencias"] = [{"o1": S(lambda: it.OccurrenceOne.Name), "o2": S(lambda: it.OccurrenceTwo.Name),
                              "vol_mm3": S(lambda: round(it.Volume * 1000, 2))} for it in inv._items(res_i)]
except Exception as exc:  # noqa: BLE001
    log["interferencias_error"] = repr(exc)
try:
    tdoc.Activate()
    v = app.ActiveView
    for prop in ("ShowAmbientShadows", "ShowObjectShadows"):
        S(lambda: setattr(v, prop, True))
    cam = v.Camera
    imgs = []
    for nm, orient in (("iso", 10759), ("frente", 10764), ("superior", 10754), ("derecha", 10755)):
        cam.ViewOrientationType = orient
        cam.Fit()
        cam.Apply()
        pth = BASE / f"vista_{nm}.png"
        v.SaveAsBitmap(str(pth), 1600, 1000)
        imgs.append(pth.name)
    log["imagenes"] = imgs
except Exception as exc:  # noqa: BLE001
    log["imagenes_error"] = repr(exc)
log["segundos"] = round(time.time() - T0, 1)
S(lambda: setattr(app, "SilentOperation", False))
(BASE / "resultado.json").write_text(json.dumps(log, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
print(json.dumps({k: v for k, v in log.items() if k not in ("cajas",)}, ensure_ascii=False, indent=1,
                 default=str)[:12000])
