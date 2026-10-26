"""L3N v5 -> Blender: exporta desde la escena de Inventor (L3N_SIM5_Planta.iam, reabierta limpia) todo lo visible:
- una malla STL por pieza distinta (coordenadas de la pieza, mm), salteando piezas chicas (tornillería);
- las ocurrencias fijas con su matriz en el mundo (mm), su color (apariencia) y su ruta;
- una "plantilla" por cada archivo de objeto SIM_* (sus piezas relativas al objeto), que Blender mueve con el plan.
No modifica nada (la escena se cierra sin guardar si estaba abierta con un estado de render).
Salida: Generados\\L3N_SIM5\\Blender\\escena_blender.json y Blender\\mallas\\*.stl
Uso: python l3n_blender_exportar.py <plan_l3n_v5.json> [--min-diag 20] [--resolucion 1]
"""
import json
import sys
import time
import traceback
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
import inventor_mcp as inv  # noqa: E402

S = inv._safe
T0 = time.time()
PLAN = Path(sys.argv[1])
MIN_DIAG = float(sys.argv[sys.argv.index("--min-diag") + 1]) if "--min-diag" in sys.argv else 20.0
RESOL = int(sys.argv[sys.argv.index("--resolucion") + 1]) if "--resolucion" in sys.argv else 1
OUT = Path.home() / "Documents" / "InventorIA" / "Generados" / "L3N_SIM5"
ESC = OUT / "L3N_SIM5_Planta.iam"
BL = OUT / "Blender"
MALLAS = BL / "mallas"
MALLAS.mkdir(parents=True, exist_ok=True)
STL_ID = "{533E9A98-FC3B-11D4-8E7E-0010B541CD80}"
K_PART = 12290
plan = json.loads(PLAN.read_text(encoding="utf-8"))
escj = json.loads((OUT / "escena.json").read_text(encoding="utf-8"))
SIM = set(plan["objetos"]) | {p["nombre"] for p in escj.get("gripper_B_partes", [])}
app = inv._inventor(start_if_needed=False)
log = {"avisos": [], "pasos": []}


def paso(t):
    log["pasos"].append(f"{time.time() - T0:7.1f} s {t}")
    print(log["pasos"][-1], flush=True)


def its(x):
    if x is None or isinstance(x, list):
        return x or []
    try:
        return inv._items(x)
    except Exception:  # noqa: BLE001
        return []


def leer(m):
    """Matrix de Inventor -> 3x4 plana por filas, traslación en mm."""
    out = []
    for r in (1, 2, 3):
        out += [round(m.Cell(r, 1), 6), round(m.Cell(r, 2), 6), round(m.Cell(r, 3), 6), round(m.Cell(r, 4) * 10, 3)]
    return out


def inv34(M):
    R = [[M[0], M[1], M[2]], [M[4], M[5], M[6]], [M[8], M[9], M[10]]]
    t = [M[3], M[7], M[11]]
    Rt = [[R[j][i] for j in range(3)] for i in range(3)]
    ti = [-sum(Rt[i][k] * t[k] for k in range(3)) for i in range(3)]
    return [Rt[0][0], Rt[0][1], Rt[0][2], ti[0], Rt[1][0], Rt[1][1], Rt[1][2], ti[1], Rt[2][0], Rt[2][1], Rt[2][2], ti[2]]


def mul(P, Q):
    out = []
    for i in range(3):
        for j in range(4):
            out.append(round(sum(P[i * 4 + k] * Q[k * 4 + j] for k in range(3)) + (P[i * 4 + 3] if j == 3 else 0.0), 6))
    return out


I34 = [1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0]
COLORES = {}


def color_de(o):
    ap = S(lambda: o.Appearance, None)
    if ap is None:
        return [0.75, 0.75, 0.75], "?"
    nm = S(lambda: ap.DisplayName, "?")
    if nm in COLORES:
        return COLORES[nm], nm
    rgb = None
    for clave in ("generic_diffuse", "metal_color", "opaque_albedo", "layered_diffuse", "glazing_transmittance_color",
                  "wallpaint_color", "ceramic_color", "plasticvinyl_color", "solidglass_transmittance_custom_color"):
        v = S(lambda: ap.Item(clave), None)
        c = S(lambda: v.Value, None) if v is not None else None
        if c is not None and S(lambda: c.Red, None) is not None:
            rgb = [round(c.Red / 255.0, 4), round(c.Green / 255.0, 4), round(c.Blue / 255.0, 4)]
            break
    if rgb is None:                                         # cualquier valor de color del asset
        for v in its(ap):
            c = S(lambda: v.Value, None)
            if c is not None and S(lambda: c.Red, None) is not None:
                rgb = [round(c.Red / 255.0, 4), round(c.Green / 255.0, 4), round(c.Blue / 255.0, 4)]
                break
    COLORES[nm] = rgb or [0.75, 0.75, 0.75]
    return COLORES[nm], nm


PIEZAS = {}          # archivo -> {"doc", "diag", "id"}


def pieza(o):
    doc = S(lambda: o.Definition.Document, None)
    if doc is None or S(lambda: doc.DocumentType, 0) != K_PART:
        return None
    f = S(lambda: doc.FullFileName, None)
    if not f:
        return None
    if f not in PIEZAS:
        b = S(lambda: doc.ComponentDefinition.RangeBox, None)
        diag = 0.0
        if b is not None:
            diag = 10 * ((b.MaxPoint.X - b.MinPoint.X) ** 2 + (b.MaxPoint.Y - b.MinPoint.Y) ** 2 + (b.MaxPoint.Z - b.MinPoint.Z) ** 2) ** 0.5
        PIEZAS[f] = {"doc": doc, "diag": diag, "id": None}
    return f if PIEZAS[f]["diag"] >= MIN_DIAG else None


N_HOJAS = {"vistas": 0, "chicas": 0}


def recorrer(occs, ruta, out, base_inv=None, mundo=True):
    for o in occs:
        if not S(lambda: o.Visible, True) or S(lambda: o.Suppressed, False):
            continue
        nm = S(lambda: o.Name, "?")
        r = f"{ruta}/{nm}" if ruta else nm
        subs = its(S(lambda: o.SubOccurrences, None))
        if subs:
            recorrer(subs, r, out, base_inv, mundo)
            continue
        f = pieza(o)
        N_HOJAS["vistas"] += 1
        if f is None:
            N_HOJAS["chicas"] += 1
            continue
        M = leer(o.Transformation)
        if base_inv is not None:
            M = mul(base_inv, M)
        c, apn = color_de(o)
        out.append({"f": f, "M": M, "c": c, "a": apn, "p": r})


app.SilentOperation = True
try:
    for d in list(its(app.Documents)):                     # la escena puede tener el estado del último render
        if S(lambda: Path(d.FullFileName).resolve() == ESC.resolve(), False):
            d.Close(True)
            paso("escena cerrada sin guardar (estado de render)")
    esc = app.Documents.Open(str(ESC), True)
    paso("escena abierta")
    cd = esc.ComponentDefinition
    tops = list(its(cd.Occurrences))
    estaticos = []
    for o in tops:
        nm = S(lambda: o.Name, "?")
        if nm in SIM or nm.startswith("SIM_"):
            continue
        recorrer([o], "", estaticos)
    paso(f"fijos: {len(estaticos)} ocurrencias, {len(PIEZAS)} piezas distintas")
    plantillas, sim = {}, {}
    for o in tops:
        nm = S(lambda: o.Name, "?")
        if not (nm in SIM or nm.startswith("SIM_")):
            continue
        doc = S(lambda: o.Definition.Document, None)
        ftop = S(lambda: doc.FullFileName, "?")
        clave = ftop if nm != "SIM_B_Gripper" else ftop + "#escena"     # el gripper B tiene ocultos propios
        if clave not in plantillas:
            hojas = []
            if S(lambda: doc.DocumentType, 0) == K_PART:
                f = pieza(o)
                if f is not None:
                    c, apn = color_de(o)
                    hojas.append({"f": f, "M": I34, "c": c, "a": apn, "p": nm})
            elif S(lambda: o.Visible, True):
                recorrer(its(o.SubOccurrences), nm, hojas, base_inv=inv34(leer(o.Transformation)))
            else:                                           # oculto al empezar: se recorre su documento
                recorrer(its(doc.ComponentDefinition.Occurrences), nm, hojas)
            plantillas[clave] = hojas
        sim[nm] = clave
    paso(f"objetos SIM: {len(sim)} con {len(plantillas)} plantillas")
    # mallas
    tr_ = next((a for a in its(app.ApplicationAddIns) if S(lambda: a.ClassIdString.upper(), "") == STL_ID), None)
    usadas = {h["f"] for h in estaticos} | {h["f"] for hs in plantillas.values() for h in hs}
    n_ok = 0
    for k, f in enumerate(sorted(usadas)):
        info = PIEZAS[f]
        info["id"] = f"m{k:04d}"
        dst = MALLAS / f"{info['id']}.stl"
        if dst.exists() and dst.stat().st_size > 84:
            n_ok += 1
            continue
        try:
            ctx = app.TransientObjects.CreateTranslationContext()
            ctx.Type = 13059
            opts = app.TransientObjects.CreateNameValueMap()
            if tr_.HasSaveCopyAsOptions(info["doc"], ctx, opts):
                for kk, v in (("ExportUnits", 5), ("Resolution", RESOL), ("OutputFileType", 0)):
                    S(lambda: opts.SetValue(kk, v))
            dm = app.TransientObjects.CreateDataMedium()
            dm.FileName = str(dst)
            tr_.SaveCopyAs(info["doc"], ctx, opts, dm)
            n_ok += dst.exists()
        except Exception as e:  # noqa: BLE001
            log["avisos"].append(f"{Path(f).name}: {e!r}"[:200])
        if k % 100 == 0:
            paso(f"mallas {k}/{len(usadas)}")
    paso(f"mallas exportadas: {n_ok}/{len(usadas)}")

    def sal(h):
        return {"m": PIEZAS[h["f"]]["id"], "M": h["M"], "c": h["c"], "a": h["a"], "p": h["p"]}

    res = {"unidades": "mm, matrices 3x4 por filas (Inventor, Y arriba)", "min_diag": MIN_DIAG,
           "mallas": {PIEZAS[f]["id"]: {"f": f, "diag": round(PIEZAS[f]["diag"], 1)} for f in usadas},
           "estaticos": [sal(h) for h in estaticos],
           "plantillas": {k: [sal(h) for h in v] for k, v in plantillas.items()}, "sim": sim, "colores": COLORES,
           "hojas": N_HOJAS}
    (BL / "escena_blender.json").write_text(json.dumps(res, ensure_ascii=False), encoding="utf-8")
    log["resumen"] = {"estaticos": len(estaticos), "mallas": len(usadas), "plantillas": len(plantillas),
                      "colores": len(COLORES), "hojas": N_HOJAS}
except Exception as exc:  # noqa: BLE001
    log["error"] = repr(exc)
    log["traza"] = traceback.format_exc()[-2500:]
finally:
    S(lambda: setattr(app, "SilentOperation", False))
log["tiempo_s"] = round(time.time() - T0, 1)
(BL / "exportar_log.json").write_text(json.dumps(log, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps(log, ensure_ascii=False, indent=1)[-5000:])
