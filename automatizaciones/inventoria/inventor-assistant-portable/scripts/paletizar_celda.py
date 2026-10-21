"""Prueba de paletizado en la celda KR 140 + gripper 4x12 kg.

Escena (ensamble aparte: Celda_KR140_paletizado.iam, se arma UNA vez y después se reutiliza):
- la celda existente (base + robot + gripper), sin modificarla (se guarda como copia)
- cinta de entrada de cajas (Straight Belt Conveyor de ADECO2, tangente al robot, a 90°)
- cama de rolos de ADECO2 con un pallet europeo encima (al frente del robot)
- 32 cajas 200 x 250 x 250 (única pieza nueva: la caja)
Animación: entran filas de 4 cajas, el robot toma la fila, la deja en el pallet; 2 pisos de 4 filas.
Los ángulos de los ejes salen de una cinemática inversa simple (celda_kin). No guarda cambios al animar.

Uso: python paletizar_celda.py [--rearmar] [--ancho 1280 --alto 720] [--sin-animar]
Salida: Generados\\CELDA_KR140\\Paletizado\\cuadros.zip + escena.json + resultado.json
"""
import argparse
import json
import math
import sys
import time
import traceback
import zipfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import inventor_mcp as inv  # noqa: E402
import celda_kin as K  # noqa: E402

a = argparse.ArgumentParser()
a.add_argument("--rearmar", action="store_true")
a.add_argument("--sin-animar", action="store_true")
a.add_argument("--ancho", type=int, default=1280)
a.add_argument("--alto", type=int, default=720)
a.add_argument("--filas", type=int, default=8, help="filas de 4 cajas a paletizar (4 por piso)")
x = a.parse_args()

S = inv._safe
DOCS = Path.home() / "Documents" / "InventorIA"
ADECO = DOCS / "12_ADECO2"
CEL = DOCS / "Generados" / "CELDA_KR140"
OUT = CEL / "Paletizado"
OUT.mkdir(parents=True, exist_ok=True)
ESC = CEL / "Celda_KR140_paletizado.iam"
CAJA = CEL / "Cajas" / "Caja 200x250x250.ipt"
CINTA = ADECO / "Factory Assets" / "Straight Belt Conveyor_85EDC29E8DF53868E77BB14496FF8421.ipt"
MESA = (ADECO / "STEP Fademaq" / "00.Ensamblaje Mesa de Rolos Completa_[CdR-STD]_[CdR1512]" /
        "00.Ensamblaje Mesa de Rolos Completa_[CdR-STD]_[CdR1512].iam")
PALLET = ADECO / "European Pallet_3BC37FCD47819CDEC205D0C1A80F9DF2.ipt"
cfg = json.loads((CEL / "celda.json").read_text(encoding="utf-8"))
log = {"avisos": []}
T0 = time.time()

BOX = (250.0, 250.0, 200.0)        # X apriete (radial), Y alto, Z fila
Y_PISO = -818.16                   # piso de la base del robot en la celda
EJE = (cfg["T_robot"][0][3], cfg["T_robot"][2][3])     # eje A1 en la celda (x, z)
R_TOMA, R_PALLET = 1700.0, 1900.0
CINTA_TOPE = 840.0                 # altura de la banda (como en ADECO2)
MESA_MIN, PALLET_BASE = 64.0, 532.0  # como en ADECO2 (mesa de rolos y pallet sobre ella)

app = inv._inventor(start_if_needed=False)
tg = app.TransientGeometry
app.SilentOperation = True


def etapa(t):
    print(f"[{time.time() - T0:6.1f} s] {t}", flush=True)


def mmake(M):
    m = tg.CreateMatrix()
    m.SetCoordinateSystem(tg.CreatePoint(M[0][3] / 10, M[1][3] / 10, M[2][3] / 10),
                          tg.CreateVector(M[0][0], M[1][0], M[2][0]), tg.CreateVector(M[0][1], M[1][1], M[2][1]),
                          tg.CreateVector(M[0][2], M[1][2], M[2][2]))
    return m


def mread(m):
    return [[m.Cell(r, c) * (10 if (c == 4 and r < 4) else 1) for c in range(1, 5)] for r in range(1, 5)]


def apply(M, p):
    return [sum(M[i][k] * (list(p) + [1])[k] for k in range(4)) for i in range(3)]


def abrir(p, visible=False):
    for d in inv._items(app.Documents):
        if S(lambda: Path(d.FullFileName).resolve() == Path(p).resolve(), False):
            return d
    return app.Documents.Open(str(p), visible)


def caja_local(path):
    d = abrir(path)
    b = d.ComponentDefinition.RangeBox
    return [b.MinPoint.X * 10, b.MinPoint.Y * 10, b.MinPoint.Z * 10, b.MaxPoint.X * 10, b.MaxPoint.Y * 10,
            b.MaxPoint.Z * 10]


def ubicar(path, centro_xz, y_min, largo_en="z", arriba="y"):
    """Matriz para ubicar una pieza (eje vertical local 'arriba') con su lado largo en x o z de la celda,
    centrada en planta en centro_xz y con su cara inferior en y_min."""
    bx = caja_local(path)
    R = K.tr(0, 0, 0)
    if arriba == "z":                                   # local Z arriba -> Y de la celda
        R = [[1, 0, 0, 0], [0, 0, 1, 0], [0, -1, 0, 0], [0, 0, 0, 1]]
    pts = [apply(R, (bx[i], bx[j], bx[k])) for i in (0, 3) for j in (1, 4) for k in (2, 5)]
    dx = max(p[0] for p in pts) - min(p[0] for p in pts)
    dz = max(p[2] for p in pts) - min(p[2] for p in pts)
    if (largo_en == "z") != (dz >= dx):
        R = K.mmul(K.rot_y(90), R)
        pts = [apply(K.rot_y(90), p) for p in pts]
    c = [(max(p[i] for p in pts) + min(p[i] for p in pts)) / 2 for i in range(3)]
    ymin = min(p[1] for p in pts)
    M = K.mmul(K.tr(centro_xz[0] - c[0], y_min - ymin, centro_xz[1] - c[2]), R)
    dims = [round(max(p[i] for p in pts) - min(p[i] for p in pts), 1) for i in range(3)]
    return M, dims


def polar(theta, r):
    return (EJE[0] + r * math.sin(math.radians(theta)), EJE[1] + r * math.cos(math.radians(theta)))


# ============================================================================ escena
def crear_caja():
    CAJA.parent.mkdir(exist_ok=True)
    doc = app.Documents.Add(inv.K_PART_DOCUMENT, app.FileManager.GetTemplateFile(inv.K_PART_DOCUMENT), False)
    cd = doc.ComponentDefinition
    sk = cd.Sketches.Add(cd.WorkPlanes.Item(2))          # plano XZ
    p1 = sk.ModelToSketchSpace(tg.CreatePoint(-BOX[0] / 20, 0, -BOX[2] / 20))
    p2 = sk.ModelToSketchSpace(tg.CreatePoint(BOX[0] / 20, 0, BOX[2] / 20))
    sk.SketchLines.AddAsTwoPointRectangle(p1, p2)
    for direc in (20993, 20994):
        f = cd.Features.ExtrudeFeatures.AddByDistanceExtent(sk.Profiles.AddForSolid(), BOX[1] / 10, direc, 20481)
        doc.Update()
        if cd.RangeBox.MaxPoint.Y * 10 > BOX[1] - 0.1:
            break
        f.Delete()
    eds = app.TransientObjects.CreateEdgeCollection()
    for e in inv._items(cd.SurfaceBodies.Item(1).Edges):
        eds.Add(e)
    S(lambda: cd.Features.FilletFeatures.AddSimple(eds, 0.3))
    ap = None
    for lib in inv._items(app.AssetLibraries):
        for asset in inv._items(S(lambda: lib.AppearanceAssets, []) or []):
            nm = (S(lambda: asset.DisplayName, "") or "").lower()
            if any(k in nm for k in ("cartón", "carton", "cardboard", "corrugated")):
                ap = asset
                break
        if ap:
            break
    if ap is not None:
        S(lambda: setattr(doc, "ActiveAppearance", ap.CopyTo(doc)))
    log["apariencia_caja"] = S(lambda: ap.DisplayName) if ap else None
    inv._iprop(doc, "Design Tracking Properties", "Part Number", "Caja 200x250x250")
    doc.SaveAs(str(CAJA), False)
    doc.Close(True)


def armar():
    etapa("Armando escena")
    if not CAJA.exists():
        crear_caja()
    cel = abrir(cfg["celda"], True)
    for d in inv._items(app.Documents):
        if S(lambda: Path(d.FullFileName).resolve() == ESC.resolve(), False):
            S(lambda: d.Close(True))
    if ESC.exists():
        ESC.unlink()
    cel.SaveAs(str(ESC), False)                   # copia de la celda; la celda original queda igual
    doc = cel
    acd = doc.ComponentDefinition
    esc = {"occ": dict(cfg["occ"])}
    # cinta de cajas: tangente al robot a 90°, cajas avanzan en +Z y paran en el punto de toma
    toma = polar(90, R_TOMA)
    largo_cinta = caja_local(CINTA)
    Lc = max(largo_cinta[3] - largo_cinta[0], largo_cinta[5] - largo_cinta[2])
    z_fin = toma[1] + 2 * BOX[2] + 60
    Mc, dc = ubicar(CINTA, (toma[0], z_fin - Lc / 2), Y_PISO, "z", "y")
    oc = acd.Occurrences.Add(str(CINTA), mmake(Mc))
    S(lambda: setattr(oc, "Grounded", True))
    esc["cinta"] = {"occ": oc.Name, "dims": dc, "z_inicio": z_fin - Lc, "z_fin": z_fin}
    # cama de rolos + pallet al frente
    pc = polar(0, R_PALLET)
    Mm, dm = ubicar(MESA, pc, Y_PISO + MESA_MIN, "z", "y")
    om = acd.Occurrences.Add(str(MESA), mmake(Mm))
    S(lambda: setattr(om, "Grounded", True))
    bxp = caja_local(PALLET)
    ext = [bxp[3] - bxp[0], bxp[4] - bxp[1], bxp[5] - bxp[2]]
    arriba = "y" if ext[1] <= min(ext[0], ext[2]) + 1 else "z"
    Mp, dp = ubicar(PALLET, pc, Y_PISO + PALLET_BASE, "z", arriba)
    op = acd.Occurrences.Add(str(PALLET), mmake(Mp))
    S(lambda: setattr(op, "Grounded", True))
    esc["mesa"] = {"occ": om.Name, "dims": dm}
    esc["pallet"] = {"occ": op.Name, "dims": dp, "centro": pc, "tope_y": Y_PISO + PALLET_BASE + dp[1]}
    # cajas
    cajas = []
    for i in range(x.filas * 4):
        o = acd.Occurrences.Add(str(CAJA), mmake(K.tr(toma[0], Y_PISO + CINTA_TOPE, esc["cinta"]["z_inicio"])))
        S(lambda: setattr(o, "Grounded", False))
        cajas.append(o.Name)
    esc["cajas"] = cajas
    esc["toma"] = toma
    occs = {o.Name: o for o in inv._items(acd.Occurrences)}
    for i, nm in enumerate(cajas):                 # guardada con la primera fila en la cinta y el resto oculto
        o = occs[nm]
        if i < 4:
            o.Transformation = mmake(K.tr(toma[0], Y_PISO + CINTA_TOPE, toma[1] + (i - 1.5) * BOX[2]))
        else:
            S(lambda: setattr(o, "Visible", False))
    doc.Update()
    doc.Save()
    (OUT / "escena.json").write_text(json.dumps(esc, ensure_ascii=False, indent=1), encoding="utf-8")
    return doc, esc


if x.rearmar or not ESC.exists() or not (OUT / "escena.json").exists():
    doc, esc = armar()
else:
    doc = abrir(ESC, True)
    esc = json.loads((OUT / "escena.json").read_text(encoding="utf-8"))
doc.Activate()
acd = doc.ComponentDefinition
occ_by_name = {o.Name: o for o in inv._items(acd.Occurrences)}
occ = {k: occ_by_name[n] for k, n in cfg["occ"].items()}
cajas = [occ_by_name[n] for n in esc["cajas"]]
log["escena"] = {k: esc[k] for k in ("cinta", "mesa", "pallet", "toma")}

# ============================================================================ gripper: apertura y TCP
def _tiene_apertura(d):
    if S(lambda: d.DocumentType) != inv.K_ASSEMBLY_DOCUMENT:
        return False
    cs = S(lambda: d.ComponentDefinition.Constraints)
    return cs is not None and any(S(lambda: c.Name, "") == "Apertura" for c in inv._items(cs))


mod = next(d for d in inv._items(doc.AllReferencedDocuments) if _tiene_apertura(d))
ap = next(c for c in inv._items(mod.ComponentDefinition.Constraints) if c.Name == "Apertura")
v_abierta = ap.Offset.Value
og = occ["gripper"]


def gomas_x():
    """x (coordenadas del gripper) de la cara de la goma fija y de la goma móvil del primer módulo."""
    G = mread(og.Transformation)
    Gi = K.inv_rt(G)

    def rango(o):
        b = o.RangeBox
        pts = [apply(Gi, (b.MinPoint.X * 10 if i else b.MaxPoint.X * 10, b.MinPoint.Y * 10 if j else b.MaxPoint.Y * 10,
                          b.MinPoint.Z * 10 if k else b.MaxPoint.Z * 10)) for i in (0, 1) for j in (0, 1) for k in (0, 1)]
        return min(p[0] for p in pts), max(p[0] for p in pts)
    subs = list(inv._items(og.SubOccurrences))
    fija = next(o for o in subs if "goma" in o.Name.lower() and "fija" in o.Name.lower())
    modulo = next(o for o in subs if "modulo" in o.Name.lower())
    msubs = list(inv._items(modulo.SubOccurrences))
    movil = next((o for o in msubs if "goma" in o.Name.lower()), None) or \
        next(o for o in msubs if "pala" in o.Name.lower() and "empuja" not in o.Name.lower())
    return rango(fija)[1], rango(movil)[0]


def set_apertura(v):
    if abs(ap.Offset.Value - v) > 1e-6:
        ap.Offset.Value = v
        mod.Update()


f0, m0 = gomas_x()
set_apertura(v_abierta + 8.0)
doc.Update()
f8, m8 = gomas_x()
set_apertura(v_abierta)
doc.Update()
gap0, gap8 = m0 - f0, m8 - f8
v_cerrada = v_abierta + 8.0 * (BOX[0] - gap0) / (gap8 - gap0) if abs(gap8 - gap0) > 1 else v_abierta + 8.0
log["gripper"] = {"luz_abierta": round(gap0, 1), "luz_carrera_80": round(gap8, 1),
                  "apertura_contacto_mm": round((v_cerrada - v_abierta) * 10, 1)}
if not 0 <= (v_cerrada - v_abierta) <= 8.0 + 1e-6:
    log["avisos"].append(f"La caja de {BOX[0]:g} no entra en la carrera: luz {gap0:.0f} -> {gap8:.0f}")
    v_cerrada = min(max(v_cerrada, v_abierta), v_abierta + 8.0)
TCP_G = (f0 + BOX[0] / 2, 400.0, 284.76)       # centro de la fila, cara inferior de las cajas (coord. gripper)
BRIDA_G = (324.24, 400.0, -245.24)
OFF_R, OFF_V = BRIDA_G[0] - TCP_G[0], TCP_G[2] - BRIDA_G[2]

# ============================================================================ cinemática inversa
W0 = K.W
a_vec = (K.A3[0] - K.A2[0], K.A3[1] - K.A2[1])
b_vec = (W0[0] - K.A3[0], W0[1] - K.A3[1])
L2, L3 = math.hypot(*a_vec), math.hypot(*b_vec)
FW = (cfg["brida_robot_q0"][0] - W0[0], cfg["brida_robot_q0"][1] - W0[1])   # muñeca -> brida (plano)
Tinv = K.inv_rt(cfg["T_robot"])


def ik(tcp):
    p = apply(Tinv, tcp)
    q1 = math.degrees(math.atan2(-p[2], p[0]))
    r = math.hypot(p[0], p[2])
    Fr, Fy = r + OFF_R, p[1] + OFF_V
    Wr, Wy = Fr - FW[0], Fy - FW[1]
    d = (Wr - K.A2[0], Wy - K.A2[1])
    D = math.hypot(*d)
    cg = (D * D - L2 * L2 - L3 * L3) / (2 * L2 * L3)
    if abs(cg) > 1:
        raise ValueError(f"Fuera de alcance: {tcp}")
    g = -math.acos(cg)                                   # codo como en el modelo
    ang_a, ang_b = math.atan2(a_vec[1], a_vec[0]), math.atan2(b_vec[1], b_vec[0])
    q3 = math.degrees(ang_a + g - ang_b)
    v = (a_vec[0] + L3 * math.cos(ang_a + g), a_vec[1] + L3 * math.sin(ang_a + g))
    q2 = math.degrees(math.atan2(d[1], d[0]) - math.atan2(v[1], v[0]))
    q3 = (q3 + 180) % 360 - 180
    q2 = (q2 + 180) % 360 - 180
    return {"q1": q1, "q2": q2, "q3": q3, "q6": 0.0}


def tcp_fk(q):
    G = K.poses(cfg, q["q1"], q["q2"], q["q3"], q["q6"])["gripper"]
    return apply(G, TCP_G), G


# ============================================================================ programa
toma = esc["toma"]
pc = esc["pallet"]["centro"]
y_toma = Y_PISO + CINTA_TOPE
y_pallet = esc["pallet"]["tope_y"]
SUBE = 300.0


def pos_fila_cinta(z_centro):
    return [K.tr(toma[0], y_toma, z_centro + (j - 1.5) * BOX[2]) for j in range(4)]


puntos = {"toma": (toma[0], y_toma, toma[1])}
destinos = []
for k in range(x.filas):
    piso, fila = divmod(k, 4)
    radial = R_PALLET + (1.5 - fila) * BOX[0]          # primero la fila más lejana
    c = polar(0, radial)
    destinos.append((c[0], y_pallet + piso * BOX[1], c[1]))
err = 0.0
for p in [puntos["toma"]] + destinos:
    for dy in (0, SUBE + BOX[1]):
        t = (p[0], p[1] + dy, p[2])
        got, _ = tcp_fk(ik(t))
        err = max(err, math.dist(got, t))
log["ik_error_max_mm"] = round(err, 2)
if err > 2:
    log["avisos"].append(f"Error de cinemática inversa {err:.1f} mm")

if x.sin_animar:
    print(json.dumps(log, ensure_ascii=False, indent=1, default=str))
    sys.exit(0)

# ============================================================================ animación
etapa("Animando")
FR = OUT / "cuadros"
FR.mkdir(exist_ok=True)
for f in FR.glob("*.png"):
    f.unlink()
n = 0
estado = {"q": None, "v": v_abierta}
llevando = []                       # (occ, B_rel)
cinta = {}                          # fila -> [z_actual, z_objetivo]
z_ent = esc["cinta"]["z_inicio"] + 2 * BOX[2] + 40
for o in cajas:
    S(lambda: setattr(o, "Visible", False))


def mostrar_fila(k, z):
    for j, M in enumerate(pos_fila_cinta(z)):
        o = cajas[4 * k + j]
        o.Transformation = mmake(M)
        S(lambda: setattr(o, "Visible", True))


def aplicar(q, v):
    P = K.poses(cfg, q["q1"], q["q2"], q["q3"], q["q6"])
    for kk in ("V02", "V03", "V04", "V05", "gripper"):
        occ[kk].Transformation = mmake(P[kk])
    set_apertura(v)
    for o, Br in llevando:
        o.Transformation = mmake(K.mmul(P["gripper"], Br))
    estado["q"], estado["v"] = q, v
    return P


def avanzar_cinta(pasos_restantes):
    for k, (z, zt) in list(cinta.items()):
        if abs(z - zt) < 0.5:
            continue
        nz = z + (zt - z) / max(1, pasos_restantes)
        cinta[k] = [nz, zt]
        mostrar_fila(k, nz)


def cuadro():
    global n
    doc.Update()
    app.ActiveView.SaveAsBitmap(str(FR / f"c{n:04d}.png"), x.ancho, x.alto)
    n += 1


def mover(q_fin, v_fin=None, pasos=10, cinta_pasos=None):
    q_ini, v_ini = estado["q"], estado["v"]
    v_fin = v_ini if v_fin is None else v_fin
    for i in range(1, pasos + 1):
        t = (1 - math.cos(math.pi * i / pasos)) / 2
        q = {kk: q_ini[kk] + (q_fin[kk] - q_ini[kk]) * t for kk in q_ini}
        aplicar(q, v_ini + (v_fin - v_ini) * t)
        avanzar_cinta(pasos - i + 1 if cinta_pasos is None else max(1, cinta_pasos - i + 1))
        cuadro()


def arriba(p):
    return (p[0], p[1] + SUBE + BOX[1], p[2])


# cámara
home = {"q1": 45.0, "q2": 0.0, "q3": 0.0, "q6": 0.0}
mostrar_fila(0, toma[1])
cinta[0] = [toma[1], toma[1]]
aplicar(home, v_abierta)
doc.Update()
b = acd.RangeBox
mn = [b.MinPoint.X, b.MinPoint.Y, b.MinPoint.Z]
mx = [b.MaxPoint.X, b.MaxPoint.Y, b.MaxPoint.Z]
cam = app.ActiveView.Camera
cam.ViewOrientationType = 10759
cam.Apply()
cam = app.ActiveView.Camera
dv = [cam.Eye.X - cam.Target.X, cam.Eye.Y - cam.Target.Y, cam.Eye.Z - cam.Target.Z]
c = [(mn[i] + mx[i]) / 2 for i in range(3)]
cam.Target = tg.CreatePoint(*c)
cam.Eye = tg.CreatePoint(c[0] + dv[0], c[1] + dv[1], c[2] + dv[2])
cam.UpVector = tg.CreateUnitVector(0, 1, 0)
S(lambda: setattr(cam, "Perspective", False))
diag = math.dist(mn, mx)
cam.SetExtents(diag * 0.62 * x.ancho / x.alto, diag * 0.62)
cam.Apply()
for _ in range(4):
    cuadro()
try:
    for k in range(x.filas):
        etapa(f"  fila {k + 1}/{x.filas}")
        q_up_toma = ik(arriba(puntos["toma"]))
        q_toma = ik(puntos["toma"])
        mover(q_up_toma, v_abierta, 12)
        mover(q_toma, None, 6)
        mover(q_toma, v_cerrada, 4)
        G = K.poses(cfg, **q_toma)["gripper"]
        Gi = K.inv_rt(G)
        llevando = [(cajas[4 * k + j], K.mmul(Gi, M)) for j, M in enumerate(pos_fila_cinta(toma[1]))]
        cinta.pop(k, None)
        mover(q_up_toma, None, 6)
        if k + 1 < x.filas:                          # entra la fila siguiente mientras el robot deja
            cinta[k + 1] = [z_ent, toma[1]]
            mostrar_fila(k + 1, z_ent)
        dst = destinos[k]
        q_up_dst = ik(arriba(dst))
        q_dst = ik(dst)
        mover(q_up_dst, None, 12, cinta_pasos=30)
        mover(q_dst, None, 6, cinta_pasos=18)
        mover(q_dst, v_abierta, 4, cinta_pasos=12)
        llevando = []
        mover(q_up_dst, None, 6, cinta_pasos=8)
    mover(home, v_abierta, 12)
    for _ in range(6):
        cuadro()
except Exception as exc:  # noqa: BLE001
    log["error_animacion"] = repr(exc)
    log["traza"] = traceback.format_exc()[-1500:]
# deja la escena como estaba guardada: fila 1 en la cinta, resto ocultas, robot en reposo
llevando = []
for o in cajas:
    S(lambda: setattr(o, "Visible", False))
mostrar_fila(0, toma[1])
aplicar({"q1": 0.0, "q2": 0.0, "q3": 0.0, "q6": 0.0}, v_abierta)
doc.Update()
with zipfile.ZipFile(OUT / "cuadros.zip", "w", zipfile.ZIP_STORED) as z:
    for f in sorted(FR.glob("c*.png")):
        z.write(f, f.name)
log["cuadros"] = n
log["tiempo_s"] = round(time.time() - T0, 1)
app.SilentOperation = False
(OUT / "resultado.json").write_text(json.dumps(log, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
print(json.dumps(log, ensure_ascii=False, indent=1, default=str))
