"""Escena de simulación L3N celda A (COPIA; nada existente se modifica).

Copias: Celdas_IA\\Celda_A_L3N.iam -> Generados\\L3N_SIM\\CeldaA_simulacion.iam
        Generados\\GRIPPER_7xTBA250\\Ensamble\\Gripper_GRIPPER_7xTBA250.iam -> Generados\\L3N_SIM\\Gripper_sim.iam
Robot de 4 ejes (KR 180 R3200-2 PA, misma cinemática que el KR 140 de ADECO): el gripper queda SIEMPRE paralelo al
piso. Como en NewPack2, el robot no se mueve por restricciones de Inventor sino por matrices (celda_kin.py):
se oculta el robot armado del layout y se agregan sus 5 eslabones sueltos (V01 fijo), con la muñeca corregida a
horizontal (phi0) y el gripper colgado de la brida con el largo a lo largo de X (la cinta). Los módulos de pala móvil
del gripper copia quedan registrados con su restricción "Apertura" para abrir/cerrar cada garra en la simulación.
El pallet lleno de la celda se oculta y se agregan un pallet vacío y N cajas (ocultas) para paletizar.
Uso: python armar_l3n.py [--rearmar] [--cajas 136]
Salida: Generados\\L3N_SIM\\ (escena.json, foto escena_q0_iso.png)
"""
import argparse
import json
import math
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import inventor_mcp as inv  # noqa: E402
import celda_kin as K  # noqa: E402

a = argparse.ArgumentParser()
a.add_argument("--rearmar", action="store_true")
a.add_argument("--cajas", type=int, default=136)
x = a.parse_args()
S = inv._safe
T0 = time.time()
DOCS = Path.home() / "Documents" / "InventorIA"
LAYOUT = Path(r"C:\DEFYMOTION\L3N\Celdas_IA\Celda_A_L3N.iam")
GRIP = DOCS / "Generados" / "GRIPPER_7xTBA250" / "Ensamble" / "Gripper_GRIPPER_7xTBA250.iam"
ADECO_ROBOT = DOCS / "12_ADECO2" / "KUKA" / "KUKA-KR_140_R3200_2_PA-ASM.iam"
CAJA = Path(r"C:\DEFYMOTION\L3N\Celdas_IA\Producto\Caja_TBA250_3x8.ipt")
PALLET_IPT = Path(r"C:\DEFYMOTION\L3N\ADECO 12-12-25\European Pallet_3BC37FCD47819CDEC205D0C1A80F9DF2.ipt")
OUT = DOCS / "Generados" / "L3N_SIM"
OUT.mkdir(parents=True, exist_ok=True)
ESC = OUT / "CeldaA_simulacion.iam"
GSIM = OUT / "Gripper_sim.iam"
# gripper generado: largo +Y, cara de montaje de la brida en z mín (normal -Z), palas hacia +Z
BRIDA_G = (387.0, 546.0, -245.2)            # centro de la cara de montaje (local del gripper)
R_WD = [[0, 1, 0], [0, 0, -1], [-1, 0, 0]]  # local gripper -> mundo con q6=0: Y_g -> X (largo a lo largo de la cinta),
                                            # Z_g -> -Y (la brida mira al robot), X_g -> -Z
app = inv._inventor(start_if_needed=False)
tg = app.TransientGeometry
app.SilentOperation = True
log = {"avisos": []}


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


def box(b):
    return [[b.MinPoint.X * 10, b.MinPoint.Y * 10, b.MinPoint.Z * 10],
            [b.MaxPoint.X * 10, b.MaxPoint.Y * 10, b.MaxPoint.Z * 10]]


def abierto(p):
    for d in inv._items(app.Documents):
        if S(lambda: Path(d.FullFileName).resolve() == Path(p).resolve(), False):
            return d
    return None


def abrir(p, visible=False):
    return abierto(p) or app.Documents.Open(str(p), visible)


def stem(o):
    return Path(S(lambda: o.Definition.Document.FullFileName, "") or "").stem


def nombres_restr(c):
    return {S(lambda: c.OccurrenceOne.Name, "") or "", S(lambda: c.OccurrenceTwo.Name, "") or ""}


def apply(M, p):
    return [sum(M[i][k] * p[k] for k in range(3)) + M[i][3] for i in range(3)]


def armar():
    etapa("Copias de la escena y del gripper")
    for p in (ESC, GSIM):
        d = abierto(p)
        if d is not None:
            S(lambda: d.Close(True))
    S(lambda: app.Documents.CloseAll(True))
    doc = abrir(LAYOUT, True)
    cd = doc.ComponentDefinition
    occs = {o.Name: o for o in inv._items(cd.Occurrences)}
    g = next((o for n, o in occs.items() if n.startswith("IA_Gripper_7x") or stem(o).startswith("Gripper_GRIPPER_7x")), None)
    if g is None:
        raise SystemExit("La celda A no tiene el gripper de 7 (correr l3n_montar_gripper.py --en-brida)")
    gdoc = g.Definition.Document
    for p in (ESC, GSIM):
        if p.exists():
            p.unlink()
    gdoc.SaveAs(str(GSIM), False)               # desde acá el gripper en memoria es la copia
    doc.SaveAs(str(ESC), False)                 # y la escena (copia) referencia al gripper copia
    esc = {"gripper_occ": g.Name, "layout_origen": str(LAYOUT)}
    # ---- gripper copia: módulos de pala móvil y su restricción de apertura
    gcd = gdoc.ComponentDefinition
    mods = {}
    for o in inv._items(gcd.Occurrences):
        if o.Name.startswith("Modulo pala movil"):
            ap = next((c for c in inv._items(o.Definition.Constraints) if "apertura" in c.Name.lower()), None)
            mods[o.Name] = {"apertura": S(lambda: ap.Name), "valor_mm": S(lambda: ap.Offset.Value * 10),
                            "caja": box(o.RangeBox)}
    esc["gripper_modulos"] = mods
    esc["gripper_caja_local"] = box(gcd.RangeBox)
    esc["BRIDA_G"] = BRIDA_G
    # ---- escena: ocultar el robot armado, liberar gripper y pallets; eslabones sueltos
    kuka = next(o for o in occs.values() if stem(o).startswith("KUKA"))
    libres = [g.Name, kuka.Name]
    sup = []
    for c in inv._items(cd.Constraints):
        if nombres_restr(c) & set(libres) and not S(lambda: c.Suppressed, False):
            S(lambda: setattr(c, "Suppressed", True))
            sup.append(c.Name)
    esc["escena_suprimidas"] = sup
    T = mread(kuka.Transformation)
    esc["T_robot"] = T
    S(lambda: setattr(kuka, "Visible", False))
    ad = abrir(ADECO_ROBOT)
    m_ad = {o.Name.split("_V0")[-1][:1]: mread(o.Transformation) for o in inv._items(ad.ComponentDefinition.Occurrences)}
    esc["links"], esc["M_links"] = {}, {}
    for o in inv._items(kuka.Definition.Occurrences):
        k = "V0" + o.Name.split("_V0")[-1][:1]
        M = m_ad[k[-1]]
        n_ = cd.Occurrences.Add(o.Definition.Document.FullFileName, mmake(K.mmul(T, M)))
        S(lambda: setattr(n_, "Name", f"SIM_{k}"))
        S(lambda: setattr(n_, "Grounded", k == "V01"))
        esc["links"][k] = n_.Name
        esc["M_links"][k] = M
    # ---- muñeca horizontal (phi0, igual que NewPack2) y gripper colgado de la brida con q = 0
    v5 = esc["M_links"]["V05"]
    n = [-v5[i][2] for i in range(3)]                          # normal de la brida (-Z local de V05) en coords. del robot
    phi0 = -90.0 - math.degrees(math.atan2(n[1], n[0]))        # giro sobre W que la deja mirando hacia abajo (NewPack2: -90-atan2(-0.6889, 0.7249))
    log["normal_brida_modelo"] = [round(v, 4) for v in n]
    F_orig = apply(v5, (1850.0, 0.0, 1745.0))                 # círculo de agujeros de la brida (local V05)
    F0 = apply(K.rot_z(phi0, K.W), F_orig)
    Rr = [row[:3] for row in T[:3]]
    Rt = [[Rr[j][i] for j in range(3)] for i in range(3)]       # robot <- mundo
    R_G = [[sum(Rt[i][k] * R_WD[k][j] for k in range(3)) for j in range(3)] for i in range(3)]
    t_g = [F0[i] - sum(R_G[i][k] * BRIDA_G[k] for k in range(3)) for i in range(3)]
    M_g_q0 = [R_G[0] + [t_g[0]], R_G[1] + [t_g[1]], R_G[2] + [t_g[2]], [0, 0, 0, 1]]
    cfg = {"T_robot": T, "phi0": phi0, "M": {k: esc["M_links"][k] for k in ("V02", "V03", "V04", "V05")},
           "brida_robot_q0": F0, "M_gripper_q0": M_g_q0}
    P = K.poses(cfg, 0, 0, 0, 0)
    for k in ("V02", "V03", "V04", "V05"):
        occ_k = next(o for o in inv._items(cd.Occurrences) if o.Name == esc["links"][k])
        occ_k.SetTransformWithoutConstraints(mmake(P[k]))
    S(lambda: setattr(g, "Grounded", False))
    g.SetTransformWithoutConstraints(mmake(P["gripper"]))
    esc.update({"phi0": phi0, "brida_robot_q0": F0, "M_gripper_q0": M_g_q0, "R_WD": R_WD,
                "nota": "4 ejes: V05 corregido con phi0, el gripper queda horizontal para todo q1..q3; q6 gira sobre la brida"})
    # ---- producto: pallet lleno oculto, pallet vacío + cajas (ocultas) para paletizar
    full = next((o for n, o in occs.items() if n.startswith("IA_Pallet_TBA250")), None)
    if full is not None:
        bf = box(full.RangeBox)
        S(lambda: setattr(full, "Visible", False))
        esc["pallet_lleno"] = {"occ": full.Name, "caja": bf}
        tmp = cd.Occurrences.Add(str(PALLET_IPT), mmake([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0]]))
        doc.Update()
        bp = box(tmp.RangeBox)
        off = [-(bp[0][i] + bp[1][i]) / 2 for i in range(3)]
        off[1] = -bp[0][1]
        pos = [(bf[0][0] + bf[1][0]) / 2, bf[0][1], (bf[0][2] + bf[1][2]) / 2]
        tmp.SetTransformWithoutConstraints(mmake([[1, 0, 0, pos[0] + off[0]], [0, 1, 0, pos[1] + off[1]], [0, 0, 1, pos[2] + off[2]]]))
        S(lambda: setattr(tmp, "Name", "SIM_Pallet_vacio"))
        esc["pallet_vacio"] = {"occ": tmp.Name, "base_centro": pos, "alto_pallet": bp[1][1] - bp[0][1]}
    toma = next((o for n, o in occs.items() if n.startswith("IA_Caja_en_cinta")), None)
    esc["caja_toma"] = {"occ": S(lambda: toma.Name), "M": S(lambda: mread(toma.Transformation)),
                        "caja": S(lambda: box(toma.RangeBox))}
    cajas = []
    for i in range(x.cajas):
        o = cd.Occurrences.Add(str(CAJA), mmake([[1, 0, 0, 0], [0, 1, 0, -3000 - 400 * (i % 10)], [0, 0, 1, 5000 + 200 * (i // 10)]]))
        S(lambda: setattr(o, "Name", f"SIM_Caja_{i + 1}"))
        S(lambda: setattr(o, "Visible", False))
        cajas.append(o.Name)
    esc["cajas"] = cajas
    esc["cinta_interna"] = {n: box(o.RangeBox) for n, o in occs.items() if n.startswith("BM2000_CeldaA")}
    esc["mesa_rolos"] = {n: box(o.RangeBox) for n, o in occs.items() if n.startswith("00.Ensamblaje Mesa de Rolos")}
    doc.Update()
    doc.Save()
    (OUT / "escena.json").write_text(json.dumps(esc, ensure_ascii=False, indent=1), encoding="utf-8")
    return doc, esc


if x.rearmar or not ESC.exists() or not (OUT / "escena.json").exists():
    doc, esc = armar()
    # la celda estaba cargada sin ventana (referenciada por el layout): el SaveAs la convirtió en la escena en
    # memoria. Se cierran los documentos propios de Celdas_IA/Generados sin guardar y se reabre la escena desde disco.
    for d in list(inv._items(app.Documents)):
        f = str(S(lambda: d.FullFileName, "")).lower()
        if (f.startswith(r"c:\defymotion\l3n\celdas_ia") or f.startswith(str(OUT).lower())) and S(lambda: d.Views.Count, 0):
            S(lambda: d.Close(True))
    S(lambda: app.Documents.CloseAll(True))
    doc = app.Documents.Open(str(ESC), True)
else:
    doc = abrir(ESC, True)
esc = json.loads((OUT / "escena.json").read_text(encoding="utf-8"))
doc.Activate()
# foto de control (q = 0)
try:
    v = app.ActiveView
    cam = v.Camera
    g = next(o for o in inv._items(doc.ComponentDefinition.Occurrences) if o.Name == esc["gripper_occ"])
    bg = box(g.RangeBox)
    c = [(bg[0][i] + bg[1][i]) / 2 for i in range(3)]
    cam.Target = tg.CreatePoint(c[0] / 10, c[1] / 10, c[2] / 10)
    cam.Eye = tg.CreatePoint(c[0] / 10 + 350, c[1] / 10 + 200, c[2] / 10 + 350)
    cam.UpVector = tg.CreateUnitVector(0, 1, 0)
    cam.Perspective = False
    cam.SetExtents(450, 281)
    cam.Apply()
    p = OUT / "escena_q0_iso.png"
    v.SaveAsBitmap(str(p), 1600, 1000)
    log["foto"] = str(p)
except Exception as exc:  # noqa: BLE001
    log["avisos"].append(f"foto: {exc!r}")
log["escena"] = {k: (v if len(json.dumps(v)) < 300 else f"{type(v).__name__} ({len(v)})") for k, v in esc.items()}
log["gripper_bbox_mundo"] = box(next(o for o in inv._items(doc.ComponentDefinition.Occurrences) if o.Name == esc["gripper_occ"]).RangeBox)
app.SilentOperation = False
print(json.dumps(log, ensure_ascii=False, indent=1))
