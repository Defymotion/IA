"""Relevamiento SOLO LECTURA del layout DosHermanos (no guarda nada).
- Layout: componentes de 1er nivel (archivo, caja, color), dónde está el/los gripper y los paquetes.
- Gripper: árbol, cajas, restricciones, masa, imágenes.
Uso: python relevar_doshermanos.py [--layout <iam>] [--gripper <iam>]
Salida: Documents\\InventorIA\\Analisis\\DOSHERMANOS\\ (relevamiento.json + png)"""
import argparse
import json
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
import inventor_mcp as inv  # noqa: E402

BASE = Path.home() / "Documents" / "InventorIA" / "DosHermanos IA" / "Dos Hermanos Tadeo"
a = argparse.ArgumentParser()
a.add_argument("--layout", default=str(BASE / "DosHermanosCompleto_V5.iam"))
a.add_argument("--gripper", default=str(BASE / "Gripper 6 Piezas.iam"))
x = a.parse_args()
S = inv._safe
T0 = time.time()
OUT = Path.home() / "Documents" / "InventorIA" / "Analisis" / "DOSHERMANOS"
OUT.mkdir(parents=True, exist_ok=True)
app = inv._inventor(start_if_needed=False)
app.SilentOperation = True
tg = app.TransientGeometry
res = {"proyecto_activo": S(lambda: app.DesignProjectManager.ActiveDesignProject.FullFileName),
       "docs_abiertos_antes": [d.FullFileName for d in inv._items(app.Documents)]}


def r(v):
    return round(v * 10, 1)


def box(b):
    return [[r(b.MinPoint.X), r(b.MinPoint.Y), r(b.MinPoint.Z)], [r(b.MaxPoint.X), r(b.MaxPoint.Y), r(b.MaxPoint.Z)]]


def mat(m):
    return [[round(m.Cell(i, j) * (10 if (j == 4 and i < 4) else 1), 3) for j in range(1, 5)] for i in range(1, 4)]


def color(o):
    ap = S(lambda: o.Appearance)
    n = S(lambda: ap.DisplayName) if ap is not None else None
    if not n:
        n = S(lambda: o.Definition.Document.ActiveAppearance.DisplayName)
    return n


def abrir(p, vis):
    for d in inv._items(app.Documents):
        if S(lambda: Path(d.FullFileName).resolve() == Path(p).resolve(), False):
            return d, False
    return app.Documents.Open(str(p), vis), True


def foto(doc, nombre, orient=10759, occ=None):
    try:
        doc.Activate()
        v = app.ActiveView
        cam = v.Camera
        cam.ViewOrientationType = orient
        cam.Fit()
        if occ is not None:
            b = occ.RangeBox
            c = tg.CreatePoint((b.MinPoint.X + b.MaxPoint.X) / 2, (b.MinPoint.Y + b.MaxPoint.Y) / 2,
                               (b.MinPoint.Z + b.MaxPoint.Z) / 2)
            ojo = cam.Eye
            tgt = cam.Target
            cam.Target = c
            cam.Eye = tg.CreatePoint(c.X + ojo.X - tgt.X, c.Y + ojo.Y - tgt.Y, c.Z + ojo.Z - tgt.Z)
            dmax = max(b.MaxPoint.X - b.MinPoint.X, b.MaxPoint.Y - b.MinPoint.Y, b.MaxPoint.Z - b.MinPoint.Z) * 1.6
            cam.SetExtents(dmax * 16 / 9, dmax)
        cam.Apply()
        p = OUT / f"{nombre}.png"
        v.SaveAsBitmap(str(p), 1600, 900)
        return str(p)
    except Exception as exc:  # noqa: BLE001
        return repr(exc)


# ---------------- layout
lay, lay_nuevo = abrir(x.layout, True)
cd = lay.ComponentDefinition
comp = []
for o in inv._items(cd.Occurrences):
    fn = S(lambda: o.Definition.Document.FullFileName, "?")
    comp.append({"nombre": o.Name, "archivo": Path(fn).name, "ruta": fn, "visible": S(lambda: o.Visible),
                 "suprimido": S(lambda: o.Suppressed), "fijo": S(lambda: o.Grounded),
                 "tipo": "iam" if S(lambda: o.DefinitionDocumentType) == inv.K_ASSEMBLY_DOCUMENT else "ipt",
                 "caja": S(lambda: box(o.RangeBox)), "M": S(lambda: mat(o.Transformation)), "color": color(o),
                 "flexible": S(lambda: o.Flexible)})
res["layout"] = {"archivo": lay.FullFileName, "caja": S(lambda: box(cd.RangeBox)), "n_componentes": len(comp),
                 "componentes": comp,
                 "restricciones": [[c.Name, S(lambda: c.OccurrenceOne.Name), S(lambda: c.OccurrenceTwo.Name),
                                    S(lambda: c.Suppressed)] for c in inv._items(cd.Constraints)][:400],
                 "faltantes": [S(lambda: f.FullFileName) for f in inv._items(lay.File.ReferencedFileDescriptors)
                               if not S(lambda: f.ReferenceMissing is False, True)][:50]}
# resumen por archivo
cuenta = {}
for c in comp:
    k = c["archivo"]
    cuenta.setdefault(k, {"n": 0, "colores": set()})
    cuenta[k]["n"] += 1
    cuenta[k]["colores"].add(str(c["color"]))
res["layout"]["por_archivo"] = {k: {"n": v["n"], "colores": sorted(v["colores"])} for k, v in cuenta.items()}
res["fotos"] = {"layout_iso": foto(lay, "layout_iso"), "layout_planta": foto(lay, "layout_planta", 10754)}
grips = [o for o in inv._items(cd.Occurrences) if "gripper" in Path(S(lambda: o.Definition.Document.FullFileName, "")).stem.lower()]
res["grippers_en_layout"] = [o.Name for o in grips]
for o in grips:
    res["fotos"][f"zoom_{o.Name}"] = foto(lay, f"layout_zoom_{o.Name.replace(':', '_')}", 10759, o)
    hijos = []
    for h in inv._items(S(lambda: o.SubOccurrences, []) or []):
        hijos.append({"nombre": h.Name, "archivo": Path(S(lambda: h.Definition.Document.FullFileName, "")).name,
                      "caja": S(lambda: box(h.RangeBox)), "color": color(h)})
    res.setdefault("grippers_hijos_en_layout", {})[o.Name] = hijos
# ---------------- gripper
if Path(x.gripper).exists():
    g, g_nuevo = abrir(x.gripper, True)
    gcd = g.ComponentDefinition
    occs = []

    def rec(col, nivel, pref=""):
        for o in inv._items(col):
            fn = S(lambda: o.Definition.Document.FullFileName, "?")
            d = {"ruta": pref + o.Name, "archivo": Path(fn).name, "dir": str(Path(fn).parent.name),
                 "caja": S(lambda: box(o.RangeBox)), "color": color(o), "fijo": S(lambda: o.Grounded),
                 "material": S(lambda: o.Definition.Document.ComponentDefinition.Material.Name)
                 if S(lambda: o.DefinitionDocumentType) != inv.K_ASSEMBLY_DOCUMENT else None,
                 "masa_kg": S(lambda: round(o.MassProperties.Mass, 3))}
            occs.append(d)
            if nivel < 3 and S(lambda: o.DefinitionDocumentType) == inv.K_ASSEMBLY_DOCUMENT:
                rec(o.SubOccurrences, nivel + 1, pref + o.Name + "/")
    rec(gcd.Occurrences, 1)
    res["gripper"] = {"archivo": g.FullFileName, "caja": S(lambda: box(gcd.RangeBox)),
                      "masa_kg": S(lambda: round(gcd.MassProperties.Mass, 2)), "componentes": occs,
                      "restricciones": [[c.Name, S(lambda: c.OccurrenceOne.Name), S(lambda: c.OccurrenceTwo.Name),
                                         S(lambda: c.Suppressed),
                                         S(lambda: c.Offset.Expression) or S(lambda: c.Angle.Expression)]
                                        for c in inv._items(gcd.Constraints)],
                      "uniones": [[j.Name, S(lambda: j.OccurrenceOne.Name), S(lambda: j.OccurrenceTwo.Name)]
                                  for j in inv._items(S(lambda: gcd.Joints, []) or [])],
                      "parametros_usuario": [[p.Name, S(lambda: p.Expression)]
                                             for p in inv._items(S(lambda: gcd.Parameters.UserParameters, []) or [])]}
    res["fotos"]["gripper_iso"] = foto(g, "gripper_iso")
    res["fotos"]["gripper_frente"] = foto(g, "gripper_frente", 10764)
    res["fotos"]["gripper_abajo"] = foto(g, "gripper_superior", 10754)
    lay.Activate()
res["segundos"] = round(time.time() - T0, 1)
S(lambda: setattr(app, "SilentOperation", False))
(OUT / "relevamiento.json").write_text(json.dumps(res, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
print(json.dumps({k: v for k, v in res.items() if k not in ("layout", "gripper", "grippers_hijos_en_layout")},
                 ensure_ascii=False, indent=1, default=str))
print(json.dumps(res["layout"]["por_archivo"], ensure_ascii=False, indent=0)[:6000])
