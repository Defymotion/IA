"""Arma el ensamble de un gripper generado tomando como referencia el ensamble de ADECO2 (copia).

Criterio (validación "replicar ADECO2"):
- Se crea un ensamble NUEVO, sin restricciones, con todo fijo (grounded).
- Las chapas generadas (Frame, Pala fija, Pala movil) reemplazan a las originales. Su posición se calcula
  "registrando" la pieza nueva contra la original: se buscan los centros de agujeros de las dos piezas y la
  rotación (24 posibles) + traslación que mejor los superpone. Así no importa cómo quedó orientado el modelo
  generado.
- El módulo de pala móvil (pala_movil_apriete.iam) se rearma como subensamble nuevo con la pala generada.
- El resto (brida, cilindros, guías, neumática, bulonería) se reutiliza de la copia de ADECO2 en su lugar.
- Las bandejas (producto) no se incluyen.
- Al final compara cajas envolventes con el original y (opcional) corre interferencias en ambos ensambles.

Uso: .\\.venv\\Scripts\\python.exe .\\scripts\\construir_ensamble.py [--nombre ADECO2_GEN] [--sin-interferencias]
Salida: Documents\\InventorIA\\Generados\\<nombre>\\Ensamble\\ (Gripper_<nombre>.iam, Modulo pala movil.iam,
        ensamble_resultado.json)
"""
import argparse
import itertools
import json
import math
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
import inventor_mcp as inv  # noqa: E402

S = inv._safe
a = argparse.ArgumentParser()
a.add_argument("--nombre", default="ADECO2_GEN")
a.add_argument("--referencia", default=str(Path.home() / "Documents" / "InventorIA" / "12_ADECO2" / "Gripper"
                                           / "Gripper_ADECO2_V1.iam"))
a.add_argument("--sin-interferencias", action="store_true")
x = a.parse_args()

BASE = Path.home() / "Documents" / "InventorIA" / "Generados" / x.nombre
CHAPAS = BASE / "Chapas"
OUT = BASE / "Ensamble"
OUT.mkdir(parents=True, exist_ok=True)
REF = Path(x.referencia)
MODULO_REF = "pala_movil_apriete.iam"
REEMPLAZOS_TOP = {"frame_principal_v1.ipt": CHAPAS / "Frame.ipt", "pala fija.ipt": CHAPAS / "Pala fija.ipt"}
REEMPLAZOS_MOD = {"pala movil 2 cajas.ipt": CHAPAS / "Pala movil.ipt"}
EXCLUIR = ("bandeja",)

app = inv._inventor(start_if_needed=False)
tg = app.TransientGeometry
t0 = time.time()
app.SilentOperation = True          # sin diálogos durante todo el armado (se restaura al final)
import atexit  # noqa: E402
atexit.register(lambda: S(lambda: setattr(app, "SilentOperation", False)))
log = {"referencia": str(REF), "registro": {}, "colocados": [], "omitidos": [], "avisos": []}


# ---------------------------------------------------------------- utilidades de matrices (mm)
def mat_read(m):
    return [[m.Cell(r, c) * (10 if (c == 4 and r < 4) else 1) for c in range(1, 5)] for r in range(1, 5)]


def mat_mul(A, B):
    return [[sum(A[i][k] * B[k][j] for k in range(4)) for j in range(4)] for i in range(4)]


def mat_make(M):
    m = tg.CreateMatrix()
    m.SetCoordinateSystem(tg.CreatePoint(M[0][3] / 10, M[1][3] / 10, M[2][3] / 10),
                          tg.CreateVector(M[0][0], M[1][0], M[2][0]),
                          tg.CreateVector(M[0][1], M[1][1], M[2][1]),
                          tg.CreateVector(M[0][2], M[1][2], M[2][2]))
    return m


def rot_apply(R, p):
    return [sum(R[i][k] * p[k] for k in range(3)) for i in range(3)]


def rotaciones():
    out = []
    for perm in itertools.permutations(range(3)):
        for signs in itertools.product((1, -1), repeat=3):
            R = [[0] * 3 for _ in range(3)]
            for i in range(3):
                R[i][perm[i]] = signs[i]
            det = (R[0][0] * (R[1][1] * R[2][2] - R[1][2] * R[2][1]) - R[0][1] * (R[1][0] * R[2][2] - R[1][2]
                   * R[2][0]) + R[0][2] * (R[1][0] * R[2][1] - R[1][1] * R[2][0]))
            if det == 1:
                out.append(R)
    return out


# ---------------------------------------------------------------- registro pieza nueva -> pieza original
def firma(doc):
    """Centros de circunferencias completas (agujeros) y caja envolvente, en mm, coordenadas de la pieza."""
    cd = doc.ComponentDefinition
    pts = []
    for body in inv._items(cd.SurfaceBodies):
        for e in inv._items(body.Edges):
            if S(lambda: e.CurveType) in (5122, 5123):       # rectas: descartar rápido
                continue
            g = S(lambda: e.Geometry)
            if g is None or S(lambda: g.StartAngle) is not None:
                continue
            c, r = S(lambda: g.Center), S(lambda: g.Radius)
            if c is None or r is None or r * 10 > 30:
                continue
            pts.append((round(c.X * 10, 3), round(c.Y * 10, 3), round(c.Z * 10, 3), round(r * 10, 2)))
    b = cd.RangeBox
    box = [[b.MinPoint.X * 10, b.MinPoint.Y * 10, b.MinPoint.Z * 10],
           [b.MaxPoint.X * 10, b.MaxPoint.Y * 10, b.MaxPoint.Z * 10]]
    return sorted(set(pts)), box


def registrar(doc_new, doc_ref):
    P, bp = firma(doc_new)
    Q, bq = firma(doc_ref)
    cq = [(bq[0][i] + bq[1][i]) / 2 for i in range(3)]
    dq = [bq[1][i] - bq[0][i] for i in range(3)]
    mejor = None
    for R in rotaciones():
        corners = [rot_apply(R, [bp[i][0], bp[j][1], bp[k][2]]) for i in (0, 1) for j in (0, 1) for k in (0, 1)]
        lo = [min(c[i] for c in corners) for i in range(3)]
        hi = [max(c[i] for c in corners) for i in range(3)]
        err_box = sum(abs((hi[i] - lo[i]) - dq[i]) for i in range(3))
        if err_box > 5:
            continue
        t = [cq[i] - (lo[i] + hi[i]) / 2 for i in range(3)]
        Pr = [[*[v + t[i] for i, v in enumerate(rot_apply(R, p[:3]))], p[3]] for p in P]

        def nn(p):
            return min((math.dist(p[:3], q[:3]) for q in Q if abs(q[3] - p[3]) < 0.3), default=999.0)
        if Pr and Q:
            d = [nn(p) for p in Pr]
            # ajuste fino de la traslación con los pares cercanos (pasadas de 3, 0,3 y 0,1 mm)
            for lim in (3.0, 0.3, 0.1):
                pares = []
                for p in Pr:
                    q = min((q for q in Q if abs(q[3] - p[3]) < 0.3), key=lambda q: math.dist(p[:3], q[:3]),
                            default=None)
                    if q is not None and math.dist(p[:3], q[:3]) < lim:
                        pares.append([q[i] - p[i] for i in range(3)])
                if len(pares) >= 3:
                    corr = [sum(v[i] for v in pares) / len(pares) for i in range(3)]
                    t = [t[i] + corr[i] for i in range(3)]
                    Pr = [[p[0] + corr[0], p[1] + corr[1], p[2] + corr[2], p[3]] for p in Pr]
            d = [nn(p) for p in Pr]
            ok = sum(1 for v in d if v < 0.5)
            score = (-ok, sorted(d)[len(d) // 2] + err_box)
        else:
            ok, d, score = 0, [], (0, err_box)
        if mejor is None or score < mejor["score"]:
            A = [[R[0][0], R[0][1], R[0][2], t[0]], [R[1][0], R[1][1], R[1][2], t[1]],
                 [R[2][0], R[2][1], R[2][2], t[2]], [0, 0, 0, 1]]
            mejor = {"score": score, "A": A, "coinciden": ok, "circulos_nueva": len(P), "circulos_ref": len(Q),
                     "desvio_max_mm": round(max(v for v in d if v < 0.5), 3) if ok else None,
                     "error_caja_mm": round(err_box, 3)}
    if mejor is None:
        raise RuntimeError(f"No encontré una orientación compatible (cajas distintas) para "
                           f"{Path(doc_new.FullFileName).name}")
    return mejor


# ---------------------------------------------------------------- documentos
def abrir(path, visible=False):
    path = Path(path)
    for d in inv._items(app.Documents):
        if S(lambda: Path(d.FullFileName).resolve() == path.resolve(), False):
            return d, False
    return app.Documents.Open(str(path), visible), True


def nuevo_ensamble(path):
    path = Path(path)
    for d in inv._items(app.Documents):          # si quedó abierto de una corrida anterior, cerrarlo
        if S(lambda: Path(d.FullFileName).resolve() == path.resolve(), False):
            d.Close(True)
    if path.exists():
        path.unlink()
    doc = app.Documents.Add(inv.K_ASSEMBLY_DOCUMENT, app.FileManager.GetTemplateFile(inv.K_ASSEMBLY_DOCUMENT), True)
    return doc


def armar(ref_doc, out_path, reemplazos, sub_reemplazos=None):
    """Copia la estructura de primer nivel de ref_doc en un ensamble nuevo aplicando reemplazos."""
    doc = nuevo_ensamble(out_path)
    occs = doc.ComponentDefinition.Occurrences
    sub_reemplazos = sub_reemplazos or {}
    registros = {}
    for o in inv._items(ref_doc.ComponentDefinition.Occurrences):
        fname = S(lambda: Path(o.Definition.Document.FullFileName).name, "")
        if S(lambda: o.Suppressed, False) or any(k in fname.lower() for k in EXCLUIR):
            log["omitidos"].append(o.Name)
            continue
        T = mat_read(o.Transformation)
        key = fname.lower()
        if key in reemplazos:
            new_path = Path(reemplazos[key])
            if key not in registros:
                nd, _ = abrir(new_path)
                reg = registrar(nd, o.Definition.Document)
                registros[key] = reg
                log["registro"][f"{new_path.name} -> {fname}"] = {k: v for k, v in reg.items() if k != "score"}
                if reg["coinciden"] < min(reg["circulos_nueva"], reg["circulos_ref"]) * 0.9:
                    log["avisos"].append(f"{new_path.name}: sólo {reg['coinciden']} de {reg['circulos_nueva']} "
                                         f"bordes de agujero coinciden con {fname}")
            M = mat_mul(T, registros[key]["A"])
            path = new_path
        elif key in sub_reemplazos:
            M, path = T, Path(sub_reemplazos[key])
        else:
            M, path = T, Path(o.Definition.Document.FullFileName)
        n = occs.Add(str(path), mat_make(M))
        S(lambda: setattr(n, "Grounded", True))
        if S(lambda: o.Visible, True) is False:
            S(lambda: setattr(n, "Visible", False))
        log["colocados"].append({"ensamble": Path(out_path).name, "original": o.Name, "nuevo": n.Name})
    doc.Update()
    doc.SaveAs(str(out_path), False)
    return doc


def caja(o):
    b = o.RangeBox
    return [[round(b.MinPoint.X * 10, 2), round(b.MinPoint.Y * 10, 2), round(b.MinPoint.Z * 10, 2)],
            [round(b.MaxPoint.X * 10, 2), round(b.MaxPoint.Y * 10, 2), round(b.MaxPoint.Z * 10, 2)]]


def copiar_y_reemplazar(ref_doc, out_path, reemplazos):
    """Copia el subensamble original (conserva sus restricciones y el estado flexible de los cilindros) y
    reemplaza las chapas indicadas: borra sus restricciones, las reemplaza y las fija en la posición registrada."""
    out_path = Path(out_path)
    for d in inv._items(app.Documents):
        if S(lambda: Path(d.FullFileName).resolve() == out_path.resolve(), False):
            d.Close(True)
    if out_path.exists():
        out_path.unlink()
    ref_doc.SaveAs(str(out_path), True)                     # SaveCopyAs: el original no cambia
    doc, _ = abrir(out_path, visible=True)
    cd = doc.ComponentDefinition
    for o in list(inv._items(cd.Occurrences)):
        fname = S(lambda: Path(o.Definition.Document.FullFileName).name, "")
        key = fname.lower()
        if key not in reemplazos:
            continue
        new_path = Path(reemplazos[key])
        nd, _ = abrir(new_path)
        reg = registrar(nd, o.Definition.Document)
        log["registro"][f"{new_path.name} -> {fname}"] = {k: v for k, v in reg.items() if k != "score"}
        M = mat_mul(mat_read(o.Transformation), reg["A"])
        borradas = 0
        for c in list(inv._items(o.Constraints)) + list(S(lambda: inv._items(o.Joints), []) or []):
            S(lambda: c.Delete())
            borradas += 1
        o.Replace(str(new_path), False)
        o.Transformation = mat_make(M)
        S(lambda: setattr(o, "Grounded", True))
        log["colocados"].append({"ensamble": out_path.name, "original": fname, "nuevo": o.Name,
                                 "restricciones_borradas": borradas})
    doc.Update()
    doc.Save()
    return doc


def interferencias(asm, es_generada):
    """Interferencias entre las chapas (set 1) y todo lo demás (set 2). Devuelve {par: [cant, vol_mm3]}."""
    s1, s2 = app.TransientObjects.CreateObjectCollection(), app.TransientObjects.CreateObjectCollection()
    for o in inv._items(asm.ComponentDefinition.Occurrences):
        if S(lambda: o.DefinitionDocumentType) == inv.K_ASSEMBLY_DOCUMENT and \
                Path(o.Definition.Document.FullFileName).name.lower() in (MODULO_REF, "modulo pala movil.iam"):
            for so in inv._items(o.SubOccurrences):
                (s1 if es_generada(so) else s2).Add(so)
        else:
            (s1 if es_generada(o) else s2).Add(o)
    res = {}
    for r in inv._items(asm.ComponentDefinition.AnalyzeInterference(s1, s2)):
        k = " / ".join(sorted(Path(S(lambda: oc.Definition.Document.FullFileName, "?")).stem
                              for oc in (r.OccurrenceOne, r.OccurrenceTwo)))
        v = res.setdefault(k, [0, 0.0])
        v[0] += 1
        v[1] = round(v[1] + S(lambda: r.Volume * 1000, 0.0), 1)
    return res


# ---------------------------------------------------------------- armado
# cerrar lo que haya quedado abierto de una corrida anterior (primero los ensambles que referencian)
for _ in range(2):
    for d in inv._items(app.Documents):
        if S(lambda: OUT.resolve() in Path(d.FullFileName).resolve().parents, False) and \
                S(lambda: d.DocumentType) == inv.K_ASSEMBLY_DOCUMENT:
            S(lambda: d.Close(True))
ref, ref_abierto_aqui = abrir(REF)
mod_ref = next((d for d in inv._items(ref.AllReferencedDocuments)
                if Path(d.FullFileName).name.lower() == MODULO_REF), None)
if mod_ref is None:
    sys.exit(f"No encontré {MODULO_REF} en la referencia")

print("Armando módulo de pala móvil...", flush=True)
mod_path = OUT / "Modulo pala movil.iam"
mod_doc = copiar_y_reemplazar(mod_ref, mod_path, REEMPLAZOS_MOD)
print("Armando gripper...", flush=True)
top_path = OUT / f"Gripper_{x.nombre}.iam"
top = armar(ref, top_path, REEMPLAZOS_TOP, {MODULO_REF: mod_path})
log["tiempo_armado_s"] = round(time.time() - t0, 1)

# comparación de cajas envolventes (chapas nuevas vs originales)
ref_occ = {o.Name: o for o in inv._items(ref.ComponentDefinition.Occurrences)}
comp = []
for c in log["colocados"]:
    if c["ensamble"] != top_path.name:
        continue
    ro = ref_occ.get(c["original"])
    no = next((o for o in inv._items(top.ComponentDefinition.Occurrences) if o.Name == c["nuevo"]), None)
    if ro is None or no is None:
        continue
    br, bn = caja(ro), caja(no)
    dmax = round(max(abs(br[i][j] - bn[i][j]) for i in range(2) for j in range(3)), 2)
    if dmax > 0.05 or c["original"] != c["nuevo"]:
        comp.append({"original": c["original"], "nuevo": c["nuevo"], "dif_max_mm": dmax, "caja_ref": br,
                     "caja_nueva": bn})
log["comparacion_cajas"] = comp

GEN_NAMES = {"frame.ipt", "pala fija.ipt", "pala movil.ipt"}
REF_NAMES = {"frame_principal_v1.ipt", "pala fija.ipt", "pala movil 2 cajas.ipt"}


def _es(o, names, carpeta=None):
    p = Path(S(lambda: o.Definition.Document.FullFileName, ""))
    return p.name.lower() in names and (carpeta is None or p.parent.resolve() == carpeta.resolve())


if not x.sin_interferencias:
    print("Interferencias (puede tardar)...", flush=True)
    t1 = time.time()
    log["interferencias_nuevo"] = S(lambda: interferencias(top, lambda o: _es(o, GEN_NAMES, CHAPAS)), "error")
    log["interferencias_ref"] = S(lambda: interferencias(ref, lambda o: _es(o, REF_NAMES)), "error")
    log["tiempo_interferencias_s"] = round(time.time() - t1, 1)

if ref_abierto_aqui:
    S(lambda: ref.Close(True))
top.Activate()
S(lambda: app.ActiveView.Fit())
log["archivos"] = [str(top_path), str(mod_path)]
log["tiempo_total_s"] = round(time.time() - t0, 1)
(OUT / "ensamble_resultado.json").write_text(json.dumps(log, ensure_ascii=False, indent=1), encoding="utf-8")
resumen = {k: v for k, v in log.items() if k not in ("colocados",)}
resumen["colocados"] = len(log["colocados"])
print(json.dumps(resumen, ensure_ascii=False, indent=1))
