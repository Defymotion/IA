"""Escena de simulación NewPack2 (COPIA; los originales no se tocan).

Copias: Simulacion NewPack2\\Layout\\Paletizado.iam -> Generados\\NEWPACK2_SIM\\NewPack2_simulacion.iam
        Simulacion NewPack2\\Gripper\\Gripper.iam   -> Generados\\NEWPACK2_SIM\\Gripper_sim.iam
En la copia del gripper se suprimen las restricciones de los 2 "Ensamble eje" (garras de pallet), de la pala móvil y
del ensamble de empuje: se mueven por matriz durante la simulación. En la escena: se oculta el robot armado y se
agregan sus 5 eslabones (KR 140, misma cinemática que ADECO), se liberan gripper, pallets y paquete, y se agregan
paquetes para 2 pisos.
Uso: python armar_newpack.py [--rearmar] [--test-garras "-60,-30,0,30,60"]
Salida: Generados\\NEWPACK2_SIM\\ (escena.json, test_garras_*.png)
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
a.add_argument("--test-garras", default="")
a.add_argument("--paquetes", type=int, default=10)
a.add_argument("--centrador", action="store_true", help="copia el centrador y libera la chapa de los pistones")
a.add_argument("--vastagos", action="store_true", help="copia los cilindros de los pistones y libera los vástagos")
a.add_argument("--zoom-x", type=float, default=0.0, help="desplazamiento en X del centro de la vista de prueba (mm)")
a.add_argument("--ancho-vista", type=float, default=220.0, help="ancho visible de la prueba (cm)")
x = a.parse_args()
S = inv._safe
T0 = time.time()
DOCS = Path.home() / "Documents" / "InventorIA"
SIMD = DOCS / "Simulacion NewPack2"
LAYOUT = SIMD / "Layout" / "Paletizado.iam"
GRIP = SIMD / "Gripper" / "Gripper.iam"
ADECO_ROBOT = DOCS / "12_ADECO2" / "KUKA" / "KUKA-KR_140_R3200_2_PA-ASM.iam"
OUT = DOCS / "Generados" / "NEWPACK2_SIM"
OUT.mkdir(parents=True, exist_ok=True)
ESC = OUT / "NewPack2_simulacion.iam"
GSIM = OUT / "Gripper_sim.iam"
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
    return [[b.MinPoint.X * 10, b.MinPoint.Y * 10, b.MinPoint.Z * 10], [b.MaxPoint.X * 10, b.MaxPoint.Y * 10,
                                                                        b.MaxPoint.Z * 10]]


def centro(b):
    return [(b[0][i] + b[1][i]) / 2 for i in range(3)]


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


def armar():
    etapa("Copias de la escena y del gripper")
    for p in (ESC, GSIM):
        d = abierto(p)
        if d is not None:
            S(lambda: d.Close(True))
    if abierto(LAYOUT) is not None:
        raise SystemExit("Paletizado.iam está abierto en Inventor: cerralo (sin guardar) y volvé a pedir.")
    doc = app.Documents.Open(str(LAYOUT), True)
    cd = doc.ComponentDefinition
    occs = {o.Name: o for o in inv._items(cd.Occurrences)}
    g = next(o for o in occs.values() if stem(o) == "Gripper")
    gdoc = g.Definition.Document
    for p in (ESC, GSIM):
        if p.exists():
            p.unlink()
    gdoc.SaveAs(str(GSIM), False)               # desde acá el gripper en memoria es la copia
    doc.SaveAs(str(ESC), False)                 # y la escena (copia) referencia al gripper copia
    esc = {"gripper_occ": g.Name}
    # ---- gripper copia: liberar garras, pala móvil y empuje
    gcd = gdoc.ComponentDefinition
    gocc = {o.Name: o for o in inv._items(gcd.Occurrences)}
    moviles = [n for n in gocc if n.split(":")[0] in ("Ensamble eje", "Pala movil", "Ensamble empuje")]
    sup = []
    for c in inv._items(gcd.Constraints):
        if nombres_restr(c) & set(moviles) and not S(lambda: c.Suppressed, False):
            S(lambda: setattr(c, "Suppressed", True))
            sup.append(c.Name)
    for n in moviles:
        S(lambda: setattr(gocc[n], "Grounded", False))
    gdoc.Update()
    esc["gripper_libres"] = {n: mread(gocc[n].Transformation) for n in moviles}
    esc["gripper_suprimidas"] = sup
    esc["gripper_cajas"] = {n: box(o.RangeBox) for n, o in gocc.items()}
    gdoc.Save()
    # ---- escena: liberar gripper, pallets, paquete; ocultar robot armado
    kuka = next(o for o in occs.values() if stem(o).startswith("KUKA"))
    libres = [g.Name, kuka.Name] + [n for n in occs if n.startswith("European Pallet") or n.startswith("Cartom")]
    sup = []
    for c in inv._items(cd.Constraints):
        if nombres_restr(c) & set(libres) and not S(lambda: c.Suppressed, False):
            if kuka.Name in nombres_restr(c) and g.Name not in nombres_restr(c):
                continue                          # el robot sigue atado a su base (queda oculto)
            S(lambda: setattr(c, "Suppressed", True))
            sup.append(c.Name)
    esc["escena_suprimidas"] = sup
    esc["T_robot"] = mread(kuka.Transformation)
    S(lambda: setattr(kuka, "Visible", False))
    ad = abrir(ADECO_ROBOT)
    m_ad = {o.Name.split("_V0")[-1][:1]: mread(o.Transformation) for o in inv._items(ad.ComponentDefinition.Occurrences)}
    esc["links"], esc["M_links"] = {}, {}
    for o in inv._items(kuka.Definition.Occurrences):
        k = "V0" + o.Name.split("_V0")[-1][:1]
        M = m_ad[k[-1]]
        n_ = cd.Occurrences.Add(o.Definition.Document.FullFileName, mmake(K.mmul(esc["T_robot"], M)))
        S(lambda: setattr(n_, "Grounded", k == "V01"))
        esc["links"][k] = n_.Name
        esc["M_links"][k] = M
    esc["pallets"] = {n: mread(o.Transformation) for n, o in occs.items() if n.startswith("European Pallet")}
    cart = next(o for n, o in occs.items() if n.startswith("Cartom"))
    esc["paquete_toma"] = mread(cart.Transformation)
    esc["paquete_caja"] = box(cart.RangeBox)
    paq = [cart.Name]
    for _ in range(x.paquetes - 1):
        o = cd.Occurrences.Add(cart.Definition.Document.FullFileName, cart.Transformation)
        S(lambda: setattr(o, "Visible", False))
        paq.append(o.Name)
    esc["paquetes"] = paq
    esc["G0"] = mread(g.Transformation)
    esc["cajas"] = {n: box(o.RangeBox) for n, o in occs.items() if n.split(":")[0] in
                    ("Ensamble centrador", "Rodillo transportador recto", "topes traseros", "topes delantero derecho",
                     "topes delantero izquierdo", "topes trasero izquierdo", "base_principal_circular")}
    for o in inv._items(cd.Occurrences):
        if o.Name in (g.Name,) or o.Name.startswith("European Pallet") or o.Name.startswith("Cartom"):
            S(lambda: setattr(o, "Grounded", False))
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
log["escena"] = {k: (v if not isinstance(v, dict) or len(json.dumps(v)) < 400 else f"{len(v)} items")
                 for k, v in esc.items() if k not in ("M_links", "gripper_cajas", "cajas", "pallets")}
log["gripper_cajas"] = {k: [[round(q, 1) for q in p] for p in v] for k, v in esc["gripper_cajas"].items()}

# ============================================================================ centrador (copia)
if x.centrador:
    etapa("Copia del centrador")
    cd = doc.ComponentDefinition
    occ = {o.Name: o for o in inv._items(cd.Occurrences)}
    cen = next(o for o in occ.values() if stem(o).startswith("Ensamble centrador"))
    cdoc = cen.Definition.Document
    CSIM = OUT / "Centrador_sim.iam"
    if Path(cdoc.FullFileName).resolve() != CSIM.resolve():
        if CSIM.exists():
            CSIM.unlink()
        cdoc.SaveAs(str(CSIM), False)
    tp = next(o for o in inv._items(cdoc.ComponentDefinition.Occurrences) if o.Name.startswith("Ensamble tope pistones"))
    pdoc = tp.Definition.Document
    PSIM = OUT / "Tope_pistones_sim.iam"
    if Path(pdoc.FullFileName).resolve() != PSIM.resolve():
        if PSIM.exists():
            PSIM.unlink()
        pdoc.SaveAs(str(PSIM), False)
    pocc = {o.Name: o for o in inv._items(pdoc.ComponentDefinition.Occurrences)}
    mov = [n for n in pocc if n.startswith("Chapa tope piston")]
    sup = []
    for c in inv._items(pdoc.ComponentDefinition.Constraints):
        if nombres_restr(c) & set(mov) and not S(lambda: c.Suppressed, False):
            S(lambda: setattr(c, "Suppressed", True))
            sup.append(c.Name)
    for n in mov:
        S(lambda: setattr(pocc[n], "Grounded", False))
    pdoc.Update()
    esc["centrador"] = {"occ": cen.Name, "M_cen": mread(cen.Transformation), "M_pist": mread(tp.Transformation),
                        "pistones_occ": tp.Name, "chapas": {n: mread(pocc[n].Transformation) for n in mov},
                        "suprimidas": sup,
                        "hijos_pistones": {n: [[round(v, 1) for v in p_] for p_ in box(o.RangeBox)]
                                           for n, o in pocc.items()}}
    pdoc.Save()
    cdoc.Save()
    doc.Update()
    doc.Save()
    (OUT / "escena.json").write_text(json.dumps(esc, ensure_ascii=False, indent=1), encoding="utf-8")
    log["centrador"] = {k: v for k, v in esc["centrador"].items()}

# ============================================================================ vástagos de los pistones (copias)
if x.vastagos:
    etapa("Copias de los cilindros del centrador")
    cd = doc.ComponentDefinition
    occ = {o.Name: o for o in inv._items(cd.Occurrences)}
    cen = occ[esc["centrador"]["occ"]]
    tp = next(o for o in inv._items(cen.Definition.Occurrences) if o.Name == esc["centrador"]["pistones_occ"])
    pdoc = tp.Definition.Document
    e1 = [o for o in inv._items(pdoc.ComponentDefinition.Occurrences) if o.Name.startswith("Ensamblaje1")]
    edoc = e1[0].Definition.Document
    ESIM = OUT / "Ensamblaje1_sim.iam"
    if Path(edoc.FullFileName).resolve() != ESIM.resolve():
        if ESIM.exists():
            ESIM.unlink()
        edoc.SaveAs(str(ESIM), False)
    adn = next(o for o in inv._items(edoc.ComponentDefinition.Occurrences) if "ADN" in o.Name)
    adoc = adn.Definition.Document
    ASIM = OUT / "ADN_40_50_sim.iam"
    if Path(adoc.FullFileName).resolve() != ASIM.resolve():
        if ASIM.exists():
            ASIM.unlink()
        adoc.SaveAs(str(ASIM), False)
    aocc = {o.Name: o for o in inv._items(adoc.ComponentDefinition.Occurrences)}
    rod = [n for n in aocc if "(KS)" in n]
    sup = []
    for c in inv._items(adoc.ComponentDefinition.Constraints):
        if nombres_restr(c) & set(rod) and not S(lambda: c.Suppressed, False):
            S(lambda: setattr(c, "Suppressed", True))
            sup.append(c.Name)
    for n in rod:
        S(lambda: setattr(aocc[n], "Grounded", False))
    adoc.Update()
    # cadena de matrices hasta el cilindro (para mover el vástago en +Y del mundo)
    M_e1 = mread(e1[0].Transformation)
    M_adn = mread(adn.Transformation)
    esc["centrador"]["vastagos"] = {"ensamblaje_M": M_e1, "adn_M": M_adn, "rod_M": {n: mread(aocc[n].Transformation)
                                                                                   for n in rod},
                                    "suprimidas": sup, "ensamblajes": [o.Name for o in e1],
                                    "ensamblajes_M": {o.Name: mread(o.Transformation) for o in e1}}
    adoc.Save()
    edoc.Save()
    pdoc.Save()
    cen.Definition.Document.Save()
    doc.Update()
    doc.Save()
    (OUT / "escena.json").write_text(json.dumps(esc, ensure_ascii=False, indent=1), encoding="utf-8")
    log["vastagos"] = esc["centrador"]["vastagos"]

# ============================================================================ prueba de garras
if x.test_garras:
    cd = doc.ComponentDefinition
    occ = {o.Name: o for o in inv._items(cd.Occurrences)}
    g = occ[esc["gripper_occ"]]
    gdoc = g.Definition.Document
    gocc = {o.Name: o for o in inv._items(gdoc.ComponentDefinition.Occurrences)}
    cj = esc["gripper_cajas"]
    ucfl = [centro(v) for k, v in cj.items() if k.startswith("ucfl")]
    ejes = {}
    for n in [k for k in esc["gripper_libres"] if k.startswith("Ensamble eje")]:
        cz = centro(cj[n])[2]
        piv = [p for p in ucfl if (p[2] > 0) == (cz > 0)] or ucfl
        ejes[n] = (sum(p[1] for p in piv) / len(piv), sum(p[2] for p in piv) / len(piv))   # (ly, lz) del eje
    log["ejes_garras"] = ejes
    # gripper sobre el pallet de arriba del almacén, largo del gripper (Z_g) a lo largo de X (lado de 1000)
    top_p = max(esc["pallets"].items(), key=lambda kv: kv[1][2][3])
    pb = esc["cajas"]  # noqa: F841
    Mp = top_p[1]
    pz_top = Mp[2][3] + 152.0
    cx, cy = Mp[0][3], Mp[1][3]
    pal_min_ly = min(v[0][1] for k, v in cj.items() if k.startswith("Pala"))
    xc = (min(v[0][0] for k, v in cj.items() if k.startswith("Chapa principal")) +
          max(v[1][0] for k, v in cj.items() if k.startswith("Chapa principal"))) / 2
    R = [[0, 0, 1], [1, 0, 0], [0, 1, 0]]        # X_g -> +Y, Y_g -> +Z, Z_g -> +X
    t = [cx - 0, cy - xc, pz_top - pal_min_ly + 51]          # palas 51 mm sobre el pallet (como el modelo)
    G = [R[0] + [t[0]], R[1] + [t[1]], R[2] + [t[2]], [0, 0, 0, 1]]
    g.Transformation = mmake(G)
    log["G_test"] = G
    v = app.ActiveView
    cam = v.Camera
    for wp in inv._items(cd.WorkPlanes):
        S(lambda: setattr(wp, "Visible", False))
    base_e = {n: esc["gripper_libres"][n] for n in ejes}
    ocultos = []
    for o in inv._items(cd.Occurrences):
        if o.Name.split(":")[0] in ("topes delantero derecho", "topes delantero izquierdo", "topes trasero izquierdo",
                                    "topes traseros", "Ensamble centrador", "Rodillo transportador recto") \
                and S(lambda: o.Visible):
            S(lambda: setattr(o, "Visible", False))
            ocultos.append(o)
    imgs = []
    for item in x.test_garras.split(","):
        a_neg, a_pos = (float(v) for v in item.split("/")) if "/" in item else (float(item), float(item))
        ang = a_neg
        for n, (ly, lz) in ejes.items():
            sg = 1 if lz > 0 else -1
            ang = a_pos if lz > 0 else a_neg
            Rx = K.mmul(K.mmul(K.tr(0, ly, lz), [[1, 0, 0, 0], [0, math.cos(math.radians(sg * ang)),
                                                                -math.sin(math.radians(sg * ang)), 0],
                                                 [0, math.sin(math.radians(sg * ang)), math.cos(math.radians(sg * ang)),
                                                  0], [0, 0, 0, 1]]), K.tr(0, -ly, -lz))
            gocc[n].Transformation = mmake(K.mmul(Rx, base_e[n]))
        gdoc.Update()
        doc.Update()
        cajas_g = {n: box(gocc[n].RangeBox) for n in ejes}
        zx = cx + x.zoom_x
        cam.Target = tg.CreatePoint(zx / 10, cy / 10, (pz_top + 50) / 10)
        cam.Eye = tg.CreatePoint(zx / 10, cy / 10 - 600, (pz_top + 50) / 10)
        cam.UpVector = tg.CreateUnitVector(0, 0, 1)
        S(lambda: setattr(cam, "Perspective", False))
        cam.SetExtents(x.ancho_vista, x.ancho_vista * 0.625)
        cam.Apply()
        p = OUT / f"test_garras_{item.replace('/', '_')}.png"
        v.SaveAsBitmap(str(p), 1600, 1000)
        imgs.append({"ang": item, "img": str(p), "cajas_eje": {k: [[round(q, 1) for q in pp] for pp in b]
                                                              for k, b in cajas_g.items()}})
    for o in ocultos:
        S(lambda: setattr(o, "Visible", True))
    for n in ejes:
        gocc[n].Transformation = mmake(base_e[n])
    gdoc.Update()
    log["test_garras"] = imgs
log["tiempo_s"] = round(time.time() - T0, 1)
S(lambda: setattr(app, "SilentOperation", False))
(OUT / "armar_resultado.json").write_text(json.dumps(log, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
print(json.dumps(log, ensure_ascii=False, indent=1, default=str)[:30000])
