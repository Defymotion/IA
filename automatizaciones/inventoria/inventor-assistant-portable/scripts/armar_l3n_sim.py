"""L3N: arma la escena de la simulación completa de planta (copia; los originales no se tocan).
1) Copias del gripper con un módulo de pala móvil por archivo (cada garra abre/cierra sola en el video).
2) Piezas propias: bandas de film (2 tamaños para que no se superpongan) y el pallet lleno con la luz entre filas
   que usa la simulación (Pallet_lleno_sim.iam).
3) Copia del layout (SaveAs copia de LayoutL3N_Celdas.iam -> L3N_SIM_Planta.iam), en la que se ocultan las piezas
   que se mueven (proxies) y se agregan, en el primer nivel, las copias móviles SIM_* que pide el plan.
4) Mide y escribe escena.json: alturas reales de rodillos, eje de los rodillos de la mesa giratoria, sentido de
   apertura del módulo de pala, verificación de matrices (caja de cada SIM_* contra su proxy).
Uso: python armar_l3n_sim.py <plan_l3n.json> [--rehacer-piezas]
"""
import json
import sys
import time
import traceback
from collections import Counter
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import inventor_mcp as inv  # noqa: E402
from cinta_modular import Gen  # noqa: E402

S = inv._safe
T0 = time.time()
PLAN = Path(sys.argv[1])
REHACER = "--rehacer-piezas" in sys.argv
LAYOUT = Path(r"C:\DEFYMOTION\L3N\Celdas_IA\LayoutL3N_Celdas.iam")
OUT = Path.home() / "Documents" / "InventorIA" / "Generados" / "L3N_SIM2"
PZ = OUT / "Piezas"
GSIM = OUT / "Gripper_SIM"
ESC = OUT / "L3N_SIM_Planta.iam"
for d in (OUT, PZ, GSIM):
    d.mkdir(parents=True, exist_ok=True)
plan = json.loads(PLAN.read_text(encoding="utf-8"))
app = inv._inventor(start_if_needed=False)
tg = app.TransientGeometry
log = {"avisos": [], "pasos": []}


def paso(t):
    log["pasos"].append(f"{time.time() - T0:6.1f} s {t}")
    print(log["pasos"][-1], flush=True)


def abrir(p, visible=False):
    d = next((d for d in inv._items(app.Documents) if S(lambda: Path(d.FullFileName).resolve() == Path(p).resolve(), False)), None)
    return d or app.Documents.Open(str(p), visible)


def mx(c):
    """3x4 plana (plan) o lista de filas -> Matrix de Inventor (cm)."""
    if isinstance(c[0], (int, float)):
        c = [c[0:4], c[4:8], c[8:12]]
    ex, ey, _ = orto([c[0][0], c[1][0], c[2][0]], [c[0][1], c[1][1], c[2][1]])
    ez = [ex[1] * ey[2] - ex[2] * ey[1], ex[2] * ey[0] - ex[0] * ey[2], ex[0] * ey[1] - ex[1] * ey[0]]
    m = tg.CreateMatrix()
    m.SetCoordinateSystem(tg.CreatePoint(c[0][3] / 10, c[1][3] / 10, c[2][3] / 10),
                          tg.CreateVector(*ex), tg.CreateVector(*ey), tg.CreateVector(*ez))
    return m


def orto(x_, y_):
    """Gram-Schmidt: el plan trae las rotaciones redondeadas a 4 decimales e Inventor exige ortonormalidad."""
    n = sum(v * v for v in x_) ** 0.5
    x_ = [v / n for v in x_]
    d = sum(a_ * b_ for a_, b_ in zip(x_, y_))
    y_ = [b_ - d * a_ for a_, b_ in zip(x_, y_)]
    n = sum(v * v for v in y_) ** 0.5
    return x_, [v / n for v in y_], None


def caja(o):
    b = o.RangeBox
    return [round(v * 10, 1) for v in (b.MinPoint.X, b.MinPoint.Y, b.MinPoint.Z, b.MaxPoint.X, b.MaxPoint.Y, b.MaxPoint.Z)]


def proxy(top_cd, ruta):
    partes = ruta.split("/")
    occs = {o.Name: o for o in inv._items(top_cd.Occurrences)}
    o = occs.get(partes[0])
    for p in partes[1:]:
        if o is None:
            return None
        o = next((h for h in inv._items(o.SubOccurrences) if h.Name == p), None)
    return o


def hojas(o, out):
    subs = S(lambda: inv._items(o.SubOccurrences), []) or []
    if not subs:
        out.append(o)
    for h in subs:
        hojas(h, out)
    return out


app.SilentOperation = True
try:
    # ------------------------------------------------------------------ 1) gripper con módulos independientes
    gfile = Path(plan["objetos"]["SIM_Gripper"]["f"])
    gsim = GSIM / "Gripper_SIM.iam"
    mods = plan["gripper"]["modulos"]
    if REHACER or not gsim.exists():
        paso("copias del gripper")
        gdoc0 = abrir(gfile)
        mocc0 = {o.Name: o for o in inv._items(gdoc0.ComponentDefinition.Occurrences)}
        mdoc0 = mocc0[mods[0]].Definition.Document
        for k, nm in enumerate(mods):
            mdoc0.SaveAs(str(GSIM / f"Modulo_pala_movil_SIM_{k + 1}.iam"), True)
        gdoc0.SaveAs(str(gsim), True)
        gd = app.Documents.Open(str(gsim), False)
        occs = {o.Name: o for o in inv._items(gd.ComponentDefinition.Occurrences)}
        for k, nm in enumerate(mods):
            o = occs[nm]
            o.Replace(str(GSIM / f"Modulo_pala_movil_SIM_{k + 1}.iam"), False)
        for k, nm in enumerate(mods):                  # el reemplazo puede cambiar el nombre: se restituye
            o = next((o for o in inv._items(gd.ComponentDefinition.Occurrences)
                      if Path(S(lambda: o.Definition.Document.FullFileName, "")).stem == f"Modulo_pala_movil_SIM_{k + 1}"), None)
            if o is not None:
                S(lambda: setattr(o, "Name", nm))
        gd.Update()
        gd.Save()
    gd = abrir(gsim)
    # sentido de apertura: se prueba el módulo 1 (+22 mm) y se mide hacia dónde se va
    occs = {o.Name: o for o in inv._items(gd.ComponentDefinition.Occurrences)}
    m1 = occs[mods[0]]
    md = m1.Definition.Document
    ap = next(c for c in inv._items(md.ComponentDefinition.Constraints) if "apertura" in c.Name.lower())
    v0 = ap.Offset.Value
    b0 = caja(m1)
    ap.Offset.Value = v0 + 2.2
    md.Update()
    gd.Update()
    b1 = caja(m1)
    ap.Offset.Value = v0
    md.Update()
    gd.Update()
    dxmax = b1[3] - b0[3]
    dxmin = b1[0] - b0[0]
    log["modulo_prueba"] = {"caja_0": b0, "caja_+22": b1, "dx_max": round(dxmax, 2), "dx_min": round(dxmin, 2), "v0_mm": round(v0 * 10, 2)}
    # la pala móvil está del lado +X local (x 574..608): abre si su borde exterior se va hacia +X
    log["signo_abre"] = 1 if dxmax > 0.5 else (-1 if dxmax < -0.5 else (1 if dxmin > 0 else -1))
    if abs(dxmax) < 0.5 and abs(dxmin) < 0.5:
        log["avisos"].append("el módulo no se movió al cambiar Apertura: revisar la restricción")
    log["gripper_sim"] = str(gsim)
    log["modulos_sim"] = [S(lambda: o.Name) for o in inv._items(gd.ComponentDefinition.Occurrences)]

    # ------------------------------------------------------------------ 2) piezas propias
    g = Gen(app, PZ)
    films = {}
    for k_, (W, D) in (("A", plan["film"]["A"]), ("B", plan["film"]["B"])):
        nombre = f"Film_banda_{k_}_{int(W)}x{int(D)}"
        if REHACER and (PZ / f"{nombre}.ipt").exists():
            (PZ / f"{nombre}.ipt").unlink()
        a_, b_, t_, gap = W / 2, D / 2, plan["film"]["espesor"], 2.0
        pts = [(a_, gap / 2), (a_, b_), (-a_, b_), (-a_, -b_), (a_, -b_), (a_, -gap / 2), (a_ - t_, -gap / 2),
               (a_ - t_, -b_ + t_), (-a_ + t_, -b_ + t_), (-a_ + t_, b_ - t_), (a_ - t_, b_ - t_), (a_ - t_, gap / 2)]
        films[f"FILM_{k_}"] = str(g.perfil_z(nombre, pts, plan["film"]["alto"], "Banda de film estirable (simulación)",
                                             ["vidrio - transparente", "vidrio transparente", "vidrio", "glass - clear",
                                              "glass", "clear", "plástico transparente"]))
    log["film"] = films
    log["film_apariencia"] = {k: S(lambda: v.DisplayName) for k, v in g._ap.items() if v is not None}
    pll = PZ / "Pallet_lleno_sim.iam"
    if REHACER or not pll.exists():
        paso("pallet lleno de la simulación")
        pl = plan["pallet_lleno"]
        ens = app.Documents.Add(inv.K_ASSEMBLY_DOCUMENT, app.FileManager.GetTemplateFile(inv.K_ASSEMBLY_DOCUMENT), False)
        cd = ens.ComponentDefinition
        o = cd.Occurrences.Add(pl["pallet"], mx([1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0]))
        S(lambda: setattr(o, "Grounded", True))
        for c in pl["cajas_rel"]:
            o = cd.Occurrences.Add(pl["caja"], mx(c))
            S(lambda: setattr(o, "Grounded", True))
        inv._iprop(ens, "Design Tracking Properties", "Description", "PALLET LLENO TBA250 17x8 CON LUZ ENTRE FILAS (SIMULACION)")
        if pll.exists():
            pll.unlink()
        ens.SaveAs(str(pll), False)
        log["pallet_lleno_caja"] = caja(ens.ComponentDefinition)
        ens.Close(True)
    archivo_de = {"FILM_A": films["FILM_A"], "FILM_B": films["FILM_B"], "PALLET_LLENO_SIM": str(pll)}

    # ------------------------------------------------------------------ 3) copia del layout y objetos SIM
    paso("copia del layout")
    for d in list(inv._items(app.Documents)):                 # la copia anterior (nuestra) se cierra para rehacerla
        if S(lambda: Path(d.FullFileName).resolve() == ESC.resolve(), False):
            d.Close(True)
    lay = abrir(LAYOUT)
    lay.SaveAs(str(ESC), True)
    esc = app.Documents.Open(str(ESC), True)
    esc.Activate()
    cd = esc.ComponentDefinition
    ocultos, faltan = [], []
    for ruta in plan["ocultar"]:
        o = proxy(cd, ruta)
        if o is None:
            faltan.append(ruta)
            continue
        S(lambda: setattr(o, "Visible", False))
        ocultos.append(ruta)
    log["ocultos"] = len(ocultos)
    if faltan:
        log["avisos"].append(f"proxies no encontrados: {faltan}")
    for ruta in plan["proxy_dinamicos"]:
        if proxy(cd, ruta) is None:
            log["avisos"].append(f"proxy dinámico no encontrado: {ruta}")
    paso("agregando objetos SIM")
    n_add = 0
    for nm, ob in plan["objetos"].items():
        f = archivo_de.get(ob["f"], ob["f"])
        if nm == "SIM_Gripper":
            f = str(gsim)
        try:
            o = cd.Occurrences.Add(f, mx(ob["M"]))
        except Exception as exc:  # noqa: BLE001
            log["avisos"].append(f"no pude agregar {nm} ({f}): {exc!r}"[:300])
            continue
        S(lambda: setattr(o, "Name", nm))
        S(lambda: setattr(o, "Grounded", False))
        if not ob["vis"]:
            S(lambda: setattr(o, "Visible", False))
        n_add += 1
    log["agregados"] = n_add
    esc.Update()
    # verificación: cada SIM_* puesto en la matriz de su proxy ocupa la misma caja
    occs = {o.Name: o for o in inv._items(cd.Occurrences)}
    ver = {}
    pares = {"SIM_V02": "Celda_A_L3N:1/IA_Robot_V02", "SIM_V05": "Celda_A_L3N:1/IA_Robot_V05",
             "SIM_Gripper": "Celda_A_L3N:1/IA_Gripper_7xTBA250", "SIM_Aereo_Carro": "Robot_Aereo_Pallets:1/Carro",
             "SIM_MP402_Rotor": "Linea_Pallets:1/MP402:1/MP402_Rotor:1",
             "SIM_Pat_chapa_pateador_2": "Celda_A_L3N:1/Ensamble pateador adeco:1/chapa pateador:2"}
    for a_, b_ in pares.items():
        p_ = proxy(cd, b_)
        if a_ in occs and p_ is not None:
            ca, cb = caja(occs[a_]), caja(p_)
            ver[a_] = {"sim": ca, "proxy": cb, "dif_max": round(max(abs(x - y) for x, y in zip(ca, cb)), 1)}
    log["verificacion_matrices"] = ver
    # ------------------------------------------------------------------ 4) mediciones
    paso("midiendo rodillos")
    tops = {}
    for clave, ruta in (("celda_camas", "Celda_A_L3N:1/00.Ensamblaje Mesa de Rolos Completa_[CdR-STD]_[CdR1512]:1"),
                        ("giratoria", "Celda_A_L3N:1/roller conveyor - rotating:1/" + plan["giratoria"]["deck"]),
                        ("linea", "Linea_Pallets:1/Roller_Conveyor_Straight_400V_FlatBelt:4"),
                        ("mp402", "Linea_Pallets:1/MP402:1/Rodillo transportador recto:1"),
                        ("cama_final", "Linea_Pallets:1/IA_Cama_L3320_IA_Cama_linea_3")):
        o = proxy(cd, ruta)
        if o is None:
            tops[clave] = None
            continue
        hs = hojas(o, [])
        cnt = Counter(S(lambda: h.Definition.Document.FullFileName, "?") for h in hs)
        f_, n_ = cnt.most_common(1)[0]
        cs = [caja(h) for h in hs if S(lambda: h.Definition.Document.FullFileName, "?") == f_]
        tops[clave] = {"archivo": Path(f_).name, "n": n_, "y_max": max(c[4] for c in cs), "y_min": min(c[1] for c in cs),
                       "caja_total": caja(o)}
    log["rodillos"] = tops
    # eje de los rodillos de la mesa giratoria (coordenadas locales del deck)
    deck = occs.get("SIM_Gir_Deck")
    if deck is not None:
        dd = deck.Definition.Document
        hs = []
        for o in inv._items(dd.ComponentDefinition.Occurrences):
            hojas(o, hs)
        cnt = Counter(S(lambda: h.Definition.Document.FullFileName, "?") for h in hs)
        f_, n_ = cnt.most_common(1)[0]
        c = caja(next(h for h in hs if S(lambda: h.Definition.Document.FullFileName, "?") == f_))
        largos = [c[3] - c[0], c[4] - c[1], c[5] - c[2]]
        log["giratoria_rodillo"] = {"archivo": Path(f_).name, "n": n_, "caja_local": c, "eje_local": "XYZ"[largos.index(max(largos))]}
    esc.Save()
    log["escena"] = str(ESC)
finally:
    S(lambda: setattr(app, "SilentOperation", False))
log["tiempo_s"] = round(time.time() - T0, 1)
(OUT / "escena.json").write_text(json.dumps(log, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
print(json.dumps(log, ensure_ascii=False, indent=1, default=str)[-6000:])
