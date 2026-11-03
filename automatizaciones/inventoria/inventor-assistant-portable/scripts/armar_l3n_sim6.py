"""L3N v6 (etapa 1): arma la escena de la simulación sobre una COPIA del layout liviano v7 (el original no se toca).
1) Reusa el gripper A de simulación y las bandas de film de L3N_SIM5 (no se rehacen).
2) Piezas propias en L3N_SIM6\\Piezas: hoja de cartón, pallets llenos A y B simplificados (shrinkwrap de los de SIM5).
3) SaveAs copia de LayoutL3N_liviano_v7.iam -> L3N_SIM6_Planta.iam: oculta lo que se mueve y agrega en el primer nivel
   las copias SIM_* del plan. Releva nombres y cajas de lo que puede estorbar (camas viejas, giratoria A, MP402).
Uso: python armar_l3n_sim6.py <plan6.json> [--rehacer-piezas] [--solo-relevar]
"""
import glob
import json
import sys
import time
import traceback
from pathlib import Path

import pythoncom

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import inventor_mcp as inv  # noqa: E402
from cinta_modular import Gen  # noqa: E402

S = inv._safe
T0 = time.time()
PLAN = Path(sys.argv[1])
REHACER = "--rehacer-piezas" in sys.argv
LAYOUT = Path(r"C:\DEFYMOTION\L3N\Celdas_IA\LayoutL3N_liviano_v7.iam")
G5 = Path.home() / "Documents" / "InventorIA" / "Generados" / "L3N_SIM5"
OUT = Path.home() / "Documents" / "InventorIA" / "Generados" / "L3N_SIM6"
PZ = OUT / "Piezas"
ESC = OUT / "L3N_SIM6_Planta.iam"
for d in (OUT, PZ):
    d.mkdir(parents=True, exist_ok=True)
plan = json.loads(PLAN.read_text(encoding="utf-8"))
app = inv._inventor(start_if_needed=False)
tg = app.TransientGeometry
log = {"avisos": [], "pasos": []}
esc5 = json.loads((G5 / "escena.json").read_text(encoding="utf-8"))
log["signo_abre"] = esc5.get("signo_abre", 1)
log["modulo_prueba"] = esc5.get("modulo_prueba")


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


def enums(nombres):
    out = {}
    for t in glob.glob(r"C:\Program Files\Autodesk\Inventor 2025\Bin\RxInventor.tlb"):
        tlb = pythoncom.LoadTypeLib(t)
        for i in range(tlb.GetTypeInfoCount()):
            if tlb.GetTypeInfoType(i) != pythoncom.TKIND_ENUM:
                continue
            ti = tlb.GetTypeInfo(i)
            for j in range(ti.GetTypeAttr().cVars):
                vd = ti.GetVarDesc(j)
                nm = ti.GetNames(vd.memid)[0]
                if nm in nombres:
                    out[nm] = vd.value
    return out


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
    if isinstance(c[0], (int, float)):
        c = [c[0:4], c[4:8], c[8:12]]
    ex, ey, ez = orto([c[0][0], c[1][0], c[2][0]], [c[0][1], c[1][1], c[2][1]])
    m = tg.CreateMatrix()
    m.SetCoordinateSystem(tg.CreatePoint(c[0][3] / 10, c[1][3] / 10, c[2][3] / 10),
                          tg.CreateVector(*ex), tg.CreateVector(*ey), tg.CreateVector(*ez))
    return m


def caja(o):
    b = o.RangeBox
    return [round(v * 10, 1) for v in (b.MinPoint.X, b.MinPoint.Y, b.MinPoint.Z, b.MaxPoint.X, b.MaxPoint.Y, b.MaxPoint.Z)]


def top_de(top_cd, nombre):
    tops = {o.Name: o for o in its(top_cd.Occurrences)}
    for cand in (nombre, nombre.split(":")[0], nombre + ":1"):
        if cand in tops:
            return tops[cand]
    return None


def proxy(top_cd, ruta):
    partes = ruta.split("/")
    o = top_de(top_cd, partes[0])
    for p in partes[1:]:
        if o is None:
            return None
        o = next((h for h in its(o.SubOccurrences) if h.Name == p), None)
    return o


def shrinkwrap(src, dest, K):
    if dest.exists() and not REHACER:
        return str(dest)
    pd = app.Documents.Add(inv.K_PART_DOCUMENT, app.FileManager.GetTemplateFile(inv.K_PART_DOCUMENT), False)
    try:
        sws = pd.ComponentDefinition.ReferenceComponents.ShrinkwrapComponents
        d = sws.CreateDefinition(str(src))
        for prop, val in (("DeriveStyle", K.get("kDeriveAsMultipleBodies")), ("RemoveInternalParts", True),
                          ("RemoveAllInternalVoids", True), ("RemoveHolesStyle", K.get("kShrinkwrapRemoveAll"))):
            if val is not None:
                S(lambda prop=prop, val=val: setattr(d, prop, val))
        sw = sws.Add(d)
        S(lambda: sw.BreakLinkToFile())
        pd.Update()
        inv._iprop(pd, "Design Tracking Properties", "Description", f"Simplificado (shrinkwrap) de {src.name} - simulación")
        if dest.exists():
            dest.unlink()
        pd.SaveAs(str(dest), False)
    finally:
        S(lambda: pd.Close(True))
    return str(dest)


app.SilentOperation = True
try:
    if "--solo-relevar" not in sys.argv:
        # ------------------------------------------------------------------ 1-2) piezas
        paso("piezas")
        K = enums({"kDeriveAsMultipleBodies", "kShrinkwrapRemoveAll"})
        g = Gen(app, PZ)
        cb = plan["carton"]
        carton = str(g.caja(f"Hoja_carton_{int(cb['L'])}x{int(cb['W'])}x{int(cb['E'])}", cb["L"], cb["E"], cb["W"],
                            "Hoja de cartón separadora sobre el pallet (simulación)",
                            ["cartón", "carton", "cardboard", "papel", "kraft", "madera - pino", "pino", "beige"]))
        archivo_de = {"GRIPPER_A_SIM": str(G5 / "Gripper_SIM" / "Gripper_A_SIM.iam"), "CARTON_SIM": carton,
                      "FILM_A": str(next(iter((G5 / "Piezas").glob("Film_banda_A_*.ipt")))),
                      "FILM_B": str(next(iter((G5 / "Piezas").glob("Film_banda_B_*.ipt"))))}
        for tp in ("A", "B"):
            paso(f"pallet lleno {tp} simplificado")
            archivo_de[f"PALLET_LLENO_{tp}"] = shrinkwrap(G5 / "Piezas" / f"Pallet_lleno_{tp}_sim.iam",
                                                          PZ / f"Pallet_lleno_{tp}_liviano.ipt", K)
        log["archivos"] = archivo_de
        # ------------------------------------------------------------------ 3) copia del layout y objetos SIM
        paso("copia del layout liviano v7")
        for d in list(its(app.Documents)):
            if S(lambda: Path(d.FullFileName).resolve() == ESC.resolve(), False):
                d.Close(True)
        lay = abrir(LAYOUT)
        lay.SaveAs(str(ESC), True)
    esc = app.Documents.Open(str(ESC), True)
    esc.Activate()
    cd = esc.ComponentDefinition
    log["tops"] = [o.Name for o in its(cd.Occurrences)]
    # relevamiento de posibles estorbos
    rel = {}
    for nombre, filtro in (("Linea_Pallets", None), ("Celda_A_L3N", "roller"), ("Envolvedora_MP402", None),
                           ("Celda_C_existente", "roller"), ("Celda_C_existente", "Pallet"), ("Celda_B_existente", "Pallet")):
        t_ = top_de(cd, nombre)
        if t_ is None:
            log["avisos"].append(f"no está {nombre}")
            continue
        for h in its(t_.SubOccurrences):
            if filtro and filtro.lower() not in h.Name.lower():
                continue
            rel[f"{t_.Name}/{h.Name}"] = {"vis": S(lambda: bool(h.Visible), None), "caja": S(lambda: caja(h), None)}
    log["relevados"] = rel
    if "--solo-relevar" in sys.argv:
        raise SystemExit(0)
    ocultos, faltan = 0, []
    for ruta in plan["ocultar"]:
        o = proxy(cd, ruta)
        if o is None:
            faltan.append(ruta)
            continue
        S(lambda: setattr(o, "Visible", False))
        ocultos += 1
    log["ocultos"] = ocultos
    if faltan:
        log["avisos"].append(f"proxies no encontrados ({len(faltan)}): {faltan[:25]}")
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
        for hijo in plan.get("ocultar_en_objeto", {}).get(nm, []):
            h = next((h for h in its(o.SubOccurrences) if h.Name == hijo), None)
            if h is None:
                log["avisos"].append(f"{nm}: no encontré el hijo {hijo}")
            else:
                S(lambda: setattr(h, "Visible", False))
        n_add += 1
        if n_add % 100 == 0:
            paso(f"{n_add} agregados")
    log["agregados"] = n_add
    esc.Update()
    occ = {o.Name: o for o in its(cd.Occurrences)}
    log["cajas_sim"] = {n: caja(occ[n]) for n in ("SIM_A_Gripper", "SIM_Lleno_A_0", "SIM_Lleno_B_0", "SIM_C_Gir_Base",
                                                  "SIM_C_Gir_Deck", "SIM_B_Gir_Deck", "SIM_MP402_Rotor", "SIM_Carton_0999") if n in occ}
    esc.Save()
    log["escena"] = str(ESC)
except SystemExit:
    pass
except Exception as exc:  # noqa: BLE001
    log["error"] = repr(exc)
    log["traza"] = traceback.format_exc()[-2500:]
finally:
    S(lambda: setattr(app, "SilentOperation", False))
log["tiempo_s"] = round(time.time() - T0, 1)
(OUT / "escena.json").write_text(json.dumps(log, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
print(json.dumps({k: v for k, v in log.items() if k != "relevados"}, ensure_ascii=False, indent=1, default=str)[-8000:])
print("relevados:", json.dumps(log.get("relevados", {}), ensure_ascii=False)[:6000])
