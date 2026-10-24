"""L3N v5: arma la escena de la simulación de planta con las dos celdas (copia; los originales no se tocan).
1) Gripper A: copia con un módulo de pala móvil por archivo (cada garra abre/cierra con su restricción "Apertura").
2) Piezas propias: caja de la celda B (LEAF 24x200 sin sorbete), bandas de film, pallets llenos A y B (con la luz entre
   filas que usa el plan).
3) Copia del layout (SaveAs copia de LayoutL3N_Celdas.iam -> L3N_SIM5_Planta.iam): se ocultan los proxies que se
   mueven y se agregan, en el primer nivel, las copias móviles SIM_* del plan.
4) Gripper B (ADECO2, el original colocado en la copia): sus módulos no tienen restricción de apertura; en el contexto de
   la escena se ocultan las piezas móviles de cada módulo y las bandejas del CAD, y se agregan copias de primer nivel
   (SIM_B_PM_g_k) que el renderizador traslada sobre el eje del apriete. Su matriz respecto del gripper va a escena.json.
Uso: python armar_l3n_sim5.py <plan_l3n_v5.json> [--rehacer-piezas]
"""
import json
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
PLAN = Path(sys.argv[1])
REHACER = "--rehacer-piezas" in sys.argv
LAYOUT = Path(r"C:\DEFYMOTION\L3N\Celdas_IA\LayoutL3N_Celdas.iam")
OUT = Path.home() / "Documents" / "InventorIA" / "Generados" / "L3N_SIM5"
PZ = OUT / "Piezas"
GSIM = OUT / "Gripper_SIM"
ESC = OUT / "L3N_SIM5_Planta.iam"
for d in (OUT, PZ, GSIM):
    d.mkdir(parents=True, exist_ok=True)
plan = json.loads(PLAN.read_text(encoding="utf-8"))
app = inv._inventor(start_if_needed=False)
tg = app.TransientGeometry
log = {"avisos": [], "pasos": []}


def its(x):
    if x is None or isinstance(x, list):
        return x or []
    try:
        return inv._items(x)
    except Exception:  # noqa: BLE001
        return []


def paso(t):
    log["pasos"].append(f"{time.time() - T0:6.1f} s {t}")
    print(log["pasos"][-1], flush=True)


def abrir(p, visible=False):
    d = next((d for d in its(app.Documents) if S(lambda: Path(d.FullFileName).resolve() == Path(p).resolve(), False)), None)
    return d or app.Documents.Open(str(p), visible)


def orto(x_, y_):
    n = sum(v * v for v in x_) ** 0.5
    x_ = [v / n for v in x_]
    d = sum(a_ * b_ for a_, b_ in zip(x_, y_))
    y_ = [b_ - d * a_ for a_, b_ in zip(x_, y_)]
    n = sum(v * v for v in y_) ** 0.5
    y_ = [v / n for v in y_]
    z_ = [x_[1] * y_[2] - x_[2] * y_[1], x_[2] * y_[0] - x_[0] * y_[2], x_[0] * y_[1] - x_[1] * y_[0]]
    return x_, y_, z_


def mx(c):
    """3x4 plana (mm) o lista de filas -> Matrix de Inventor (cm), re-ortonormalizada."""
    if isinstance(c[0], (int, float)):
        c = [c[0:4], c[4:8], c[8:12]]
    ex, ey, ez = orto([c[0][0], c[1][0], c[2][0]], [c[0][1], c[1][1], c[2][1]])
    m = tg.CreateMatrix()
    m.SetCoordinateSystem(tg.CreatePoint(c[0][3] / 10, c[1][3] / 10, c[2][3] / 10),
                          tg.CreateVector(*ex), tg.CreateVector(*ey), tg.CreateVector(*ez))
    return m


def leer(m):
    """Matrix de Inventor -> 3x4 en filas (mm)."""
    return [[m.Cell(r, 1), m.Cell(r, 2), m.Cell(r, 3), m.Cell(r, 4) * 10] for r in (1, 2, 3)]


def inv34(M):
    R = [[M[j][i] for j in range(3)] for i in range(3)]
    t = [-sum(R[i][k] * M[k][3] for k in range(3)) for i in range(3)]
    return [R[i] + [t[i]] for i in range(3)]


def mul34(P, Q):
    return [[sum(P[i][k] * Q[k][j] for k in range(3)) + (P[i][3] if j == 3 else 0.0) for j in range(4)] for i in range(3)]


def plana(M):
    return [round(v, 4) for r in M for v in r]


def caja(o):
    b = o.RangeBox
    return [round(v * 10, 1) for v in (b.MinPoint.X, b.MinPoint.Y, b.MinPoint.Z, b.MaxPoint.X, b.MaxPoint.Y, b.MaxPoint.Z)]


def proxy(top_cd, ruta):
    partes = ruta.split("/")
    o = next((o for o in its(top_cd.Occurrences) if o.Name == partes[0]), None)
    for p in partes[1:]:
        if o is None:
            return None
        o = next((h for h in its(o.SubOccurrences) if h.Name == p), None)
    return o


app.SilentOperation = True
try:
    # ------------------------------------------------------------------ 1) gripper A con módulos independientes
    GA = plan["grippers"]["SIM_A_Gripper"]
    mods = GA["modulos"]
    gsim = GSIM / "Gripper_A_SIM.iam"
    if REHACER or not gsim.exists():
        paso("copias del gripper A")
        gdoc0 = abrir(GA["f"])
        mocc0 = {o.Name: o for o in its(gdoc0.ComponentDefinition.Occurrences)}
        mdoc0 = mocc0[mods[0]].Definition.Document
        for k, nm in enumerate(mods):
            mdoc0.SaveAs(str(GSIM / f"Modulo_A_SIM_{k + 1}.iam"), True)
        gdoc0.SaveAs(str(gsim), True)
        gd = app.Documents.Open(str(gsim), False)
        occs = {o.Name: o for o in its(gd.ComponentDefinition.Occurrences)}
        for k, nm in enumerate(mods):
            occs[nm].Replace(str(GSIM / f"Modulo_A_SIM_{k + 1}.iam"), False)
        for k, nm in enumerate(mods):
            o = next((o for o in its(gd.ComponentDefinition.Occurrences)
                      if Path(S(lambda: o.Definition.Document.FullFileName, "")).stem == f"Modulo_A_SIM_{k + 1}"), None)
            if o is not None:
                S(lambda: setattr(o, "Name", nm))
        gd.Update()
        gd.Save()
    gd = abrir(gsim)
    occs = {o.Name: o for o in its(gd.ComponentDefinition.Occurrences)}
    m1 = occs[mods[0]]
    md = m1.Definition.Document
    ap = next(c for c in its(md.ComponentDefinition.Constraints) if "apertura" in c.Name.lower())
    v0 = ap.Offset.Value
    b0 = caja(m1)
    ap.Offset.Value = v0 + 2.2
    md.Update()
    gd.Update()
    b1 = caja(m1)
    ap.Offset.Value = v0
    md.Update()
    gd.Update()
    dxmax, dxmin = b1[3] - b0[3], b1[0] - b0[0]
    log["modulo_prueba"] = {"caja_0": b0, "caja_+22": b1, "dx_max": round(dxmax, 2), "dx_min": round(dxmin, 2), "v0_mm": round(v0 * 10, 2)}
    log["signo_abre"] = 1 if dxmax > 0.5 else (-1 if dxmax < -0.5 else (1 if dxmin > 0 else -1))
    log["gripper_A_sim"] = str(gsim)

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
    cb = plan["caja_B"]
    nombre_cb = f"Caja_LEAF_24x200_sin_sorbete_{int(cb['L'])}x{int(cb['W'])}x{int(cb['H'])}"
    if REHACER and (PZ / f"{nombre_cb}.ipt").exists():
        (PZ / f"{nombre_cb}.ipt").unlink()
    nueva_cb = not (PZ / f"{nombre_cb}.ipt").exists()
    caja_B = str(g.caja(nombre_cb, cb["L"], cb["H"], cb["W"], "Bandeja 24x200 ml LEAF sin sorbete (simulación)", None))
    if nueva_cb:                                    # misma apariencia que la caja de la celda A
        try:
            da = abrir(plan["pallets_llenos"]["A"]["caja"])
            apa = da.ActiveAppearance
            dbx = app.Documents.Open(caja_B, False)
            dbx.ActiveAppearance = apa.CopyTo(dbx)
            dbx.Save()
            dbx.Close(True)
            log["caja_B_apariencia"] = S(lambda: apa.DisplayName)
        except Exception as e:  # noqa: BLE001
            log["avisos"].append(f"apariencia caja B: {e!r}"[:200])
    archivo_de = {"FILM_A": films["FILM_A"], "FILM_B": films["FILM_B"], "CAJA_B_SIM": caja_B, "GRIPPER_A_SIM": str(gsim),
                  "GRIPPER_B_SIM": plan["grippers"]["SIM_B_Gripper"]["f"]}
    for cel, pl in plan["pallets_llenos"].items():
        pll = PZ / f"Pallet_lleno_{cel}_sim.iam"
        archivo_de[f"PALLET_LLENO_{cel}"] = str(pll)
        if REHACER or not pll.exists():
            paso(f"pallet lleno {cel}")
            ens = app.Documents.Add(inv.K_ASSEMBLY_DOCUMENT, app.FileManager.GetTemplateFile(inv.K_ASSEMBLY_DOCUMENT), False)
            cd = ens.ComponentDefinition
            o = cd.Occurrences.Add(pl["pallet"], mx([1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0]))
            S(lambda: setattr(o, "Grounded", True))
            fc = archivo_de.get(pl["caja"], pl["caja"])
            for c in pl["cajas_rel"]:
                o = cd.Occurrences.Add(fc, mx(c))
                S(lambda: setattr(o, "Grounded", True))
            inv._iprop(ens, "Design Tracking Properties", "Description", f"PALLET LLENO CELDA {cel} ({len(pl['cajas_rel'])} CAJAS, SIMULACION)")
            if pll.exists():
                pll.unlink()
            ens.SaveAs(str(pll), False)
            log[f"pallet_lleno_{cel}"] = {"caja": caja(ens.ComponentDefinition), "n": len(pl["cajas_rel"])}
            ens.Close(True)

    # ------------------------------------------------------------------ 3) copia del layout y objetos SIM
    paso("copia del layout")
    for d in list(its(app.Documents)):
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
    paso(f"agregando {len(plan['objetos'])} objetos SIM")
    n_add = 0
    for nm, ob in plan["objetos"].items():
        f = archivo_de.get(ob["f"], ob["f"])
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
        if n_add % 100 == 0:
            paso(f"{n_add} agregados")
    log["agregados"] = n_add
    esc.Update()
    occ = {o.Name: o for o in its(cd.Occurrences)}

    # ------------------------------------------------------------------ 4) gripper B: piezas móviles de primer nivel
    GB = plan["grippers"]["SIM_B_Gripper"]
    gB = occ.get("SIM_B_Gripper")
    partes = []
    if gB is None:
        log["avisos"].append("no está SIM_B_Gripper")
    else:
        Mg = leer(gB.Transformation)
        iMg = inv34(Mg)
        hijos = list(its(gB.SubOccurrences))
        for h in hijos:
            if any(h.Name.startswith(p) for p in GB["ocultar_hijos"]):
                S(lambda: setattr(h, "Visible", False))
        modulos = []
        for h in hijos:
            if h.Name.startswith(GB["modulo"]):
                c = caja(h)
                cen = [(c[0] + c[3]) / 2, (c[1] + c[4]) / 2, (c[2] + c[5]) / 2]
                xl = sum(iMg[0][k] * cen[k] for k in range(3)) + iMg[0][3]
                modulos.append((xl, h))
        modulos.sort(key=lambda v: v[0])
        log["modulos_B"] = [(round(xl, 1), h.Name) for xl, h in modulos]
        for gi, (xl, h) in enumerate(modulos):
            esperado = GB["x_garra0"] + GB["paso_garras"] * gi
            if abs(xl - esperado) > 40.0:
                log["avisos"].append(f"módulo {h.Name}: x local {xl:.1f}, esperaba ~{esperado:.1f} (garra {gi})")
            k = 0
            for s_ in its(h.SubOccurrences):
                if not any(s_.Name.startswith(p) for p in GB["moviles"]):
                    continue
                Mw = leer(s_.Transformation)
                f = s_.Definition.Document.FullFileName
                nm = f"SIM_B_PM_{gi}_{k}"
                o = cd.Occurrences.Add(f, mx(Mw))
                S(lambda: setattr(o, "Name", nm))
                S(lambda: setattr(o, "Grounded", False))
                S(lambda: setattr(s_, "Visible", False))
                partes.append({"nombre": nm, "garra": gi, "pieza": s_.Name, "M_rel": plana(mul34(iMg, Mw))})
                k += 1
        esc.Update()
    log["gripper_B_partes"] = partes
    if len(partes) != 5 * GB["n"]:
        log["avisos"].append(f"piezas móviles del gripper B: {len(partes)} (esperaba {5 * GB['n']})")

    # ------------------------------------------------------------------ 5) verificaciones
    ver = {}
    for a_, b_ in (("SIM_A_Gripper", None), ("SIM_B_Gripper", None), ("SIM_B_V02", None), ("SIM_A_Gir_Deck", None),
                   ("SIM_B_Gir_Deck", None), ("SIM_B_Freno", None), ("SIM_B_Lleno", None), ("SIM_A_Lleno", None)):
        if a_ in occ:
            ver[a_] = caja(occ[a_])
    log["cajas_sim"] = ver
    esc.Save()
    log["escena"] = str(ESC)
except Exception as exc:  # noqa: BLE001
    log["error"] = repr(exc)
    log["traza"] = traceback.format_exc()[-2500:]
finally:
    S(lambda: setattr(app, "SilentOperation", False))
log["tiempo_s"] = round(time.time() - T0, 1)
(OUT / "escena.json").write_text(json.dumps(log, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
print(json.dumps({k: v for k, v in log.items() if k != "gripper_B_partes"}, ensure_ascii=False, indent=1, default=str)[-6000:])
