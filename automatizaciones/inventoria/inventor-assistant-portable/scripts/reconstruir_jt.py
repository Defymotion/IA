"""Reconstruye piezas importadas (sólidos sin historial, p. ej. desde JT/STEP) como piezas PARAMÉTRICAS de Inventor:
bocetos + extrusiones (descomposición 2.5D en una dirección) + agujeros cilíndricos + cortes de ventanas laterales.
No toca los originales: los abre, los lee y los cierra sin guardar. Valida volumen y caja contra el original.
Uso: python reconstruir_jt.py <carpeta_origen> <carpeta_salida> <lista.txt | prefijo1;prefijo2> [--tol 0.5]
     lista.txt: un prefijo de archivo por línea (el nombre de la pieza sin _N ni .ipt).
Escribe <carpeta_salida>\\reconstruccion.json (acumulativo: no rehace las piezas que ya validaron).
"""
import json
import math
import sys
import time
import traceback
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
import inventor_mcp as inv  # noqa: E402

S = inv._safe
ORIG, SAL = Path(sys.argv[1]), Path(sys.argv[2])
arg3 = sys.argv[3]
TOL = float(sys.argv[sys.argv.index("--tol") + 1]) if "--tol" in sys.argv else 0.5   # % de volumen
if arg3.lower().endswith(".txt"):
    PREFS = [li.rstrip("\r\n") for li in Path(arg3).read_text(encoding="utf-8").splitlines() if li.strip()]
else:
    PREFS = [p for p in arg3.split(";") if p]
SAL.mkdir(parents=True, exist_ok=True)
REP = SAL / "reconstruccion.json"
rep = json.loads(REP.read_text(encoding="utf-8")) if REP.exists() else {}

app = inv._inventor(start_if_needed=False)
tg = app.TransientGeometry
K_PLANO, K_CIL = 5890, 5891
JOIN, CUT, NEWB = 20481, 20482, 20485
POS, NEG = 20993, 20994
EPS = 1e-4          # cm


# ------------------------------------------------------------------ vectores
def v(p):
    return (p.X, p.Y, p.Z)


def sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def add(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def mul(a, k):
    return (a[0] * k, a[1] * k, a[2] * k)


def dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def norm(a):
    n = math.sqrt(dot(a, a))
    return (a[0] / n, a[1] / n, a[2] / n) if n > 0 else a


def paralelo(a, b, t=1e-4):
    return abs(abs(dot(a, b)) - 1.0) < t


# ------------------------------------------------------------------ lectura del B-rep
def normal_cara(f):
    g = f.Geometry
    n = norm(v(g.Normal))
    if S(lambda: f.IsParamReversed, False):
        n = mul(n, -1)
    return n


def puntos_arista(e, tol=0.001):
    ev = e.Evaluator
    a, b = ev.GetParamExtents(0.0, 0.0)
    n, c = ev.GetStrokes(a, b, tol, 0, [])
    return [(c[3 * i], c[3 * i + 1], c[3 * i + 2]) for i in range(n)]


def rayo(body, p, d):
    """Distancia al primer cruce del rayo (p, d) con el cuerpo, ignorando el arranque."""
    try:
        ents, pts = body.FindUsingRay(tg.CreatePoint(*p), tg.CreateUnitVector(*d), 1e-5, None, None, False)
    except Exception:  # noqa: BLE001
        return None, None
    mejor = None
    for i in range(1, (pts.Count if pts is not None else 0) + 1):
        q = v(pts.Item(i))
        t = dot(sub(q, p), d)
        if t > 2 * EPS and (mejor is None or t < mejor[0]):
            mejor = (t, ents.Item(i))
    return mejor if mejor else (None, None)


def caras(body):
    out = []
    for f in inv._items(body.Faces):
        e = {"f": f, "tipo": f.SurfaceType, "area": f.Evaluator.Area}
        if e["tipo"] == K_PLANO:
            e["n"] = normal_cara(f)
            e["off"] = dot(e["n"], v(f.Geometry.RootPoint))
        elif e["tipo"] == K_CIL:
            g = f.Geometry
            e["eje"] = norm(v(g.AxisVector))
            e["base"] = v(g.BasePoint)
            e["r"] = g.Radius
        out.append(e)
    return out


def candidatas(cs):
    dirs = []
    for c in cs:
        for k in ("n", "eje"):
            if k in c and not any(paralelo(c[k], d) for d in dirs):
                dirs.append(c[k])
    puntaje = []
    for d in dirs:
        viol = 0.0
        for c in cs:
            if c["tipo"] == K_PLANO:
                if paralelo(c["n"], d) or abs(dot(c["n"], d)) < 1e-4:
                    continue
            elif c["tipo"] == K_CIL:
                if paralelo(c["eje"], d) or abs(dot(c["eje"], d)) < 1e-4:
                    continue   # paralelo (pared de prisma) o perpendicular (agujero lateral)
            viol += c["area"]
        puntaje.append((viol, d))
    puntaje.sort(key=lambda x: x[0])
    return puntaje


# ------------------------------------------------------------------ escritura
class Pieza:
    def __init__(self):
        self.doc = app.Documents.Add(12290, app.FileManager.GetTemplateFile(12290), False)
        self.cd = self.doc.ComponentDefinition
        self.nfeat = 0

    def boceto(self, origen, normal):
        x = (1.0, 0.0, 0.0) if abs(normal[0]) < 0.9 else (0.0, 1.0, 0.0)
        x = norm(sub(x, mul(normal, dot(x, normal))))
        y = cross(normal, x)
        wp = self.cd.WorkPlanes.AddFixed(tg.CreatePoint(*origen), tg.CreateUnitVector(*x), tg.CreateUnitVector(*y))
        wp.Visible = False
        sk = self.cd.Sketches.Add(wp)
        return sk

    def dibujar_aristas(self, sk, aristas):
        pts = {}

        def sp(p):
            q = sk.ModelToSketchSpace(tg.CreatePoint(*p))
            k = (round(q.X, 4), round(q.Y, 4))
            if k not in pts:
                pts[k] = sk.SketchPoints.Add(q, False)
            return pts[k]

        sk.DeferUpdates = True
        for e in aristas:
            g = e.Geometry
            ps = puntos_arista(e)
            cerrada = math.dist(ps[0], ps[-1]) < 1e-5
            r = S(lambda: g.Radius, None)
            if cerrada and r is not None and S(lambda: g.Center, None) is not None and len(ps) > 4:
                c = sk.ModelToSketchSpace(g.Center)
                sk.SketchCircles.AddByCenterRadius(c, r)
            elif r is not None and not cerrada and len(ps) >= 3:
                sk.SketchArcs.AddByThreePoints(sp(ps[0]), sk.ModelToSketchSpace(tg.CreatePoint(*ps[len(ps) // 2])),
                                               sp(ps[-1]))
            elif len(ps) == 2:
                sk.SketchLines.AddByTwoPoints(sp(ps[0]), sp(ps[1]))
            else:
                if cerrada:
                    ps = ps[:-1] + [ps[0]]
                ant = sp(ps[0])
                for p in ps[1:]:
                    q = sp(p)
                    if q is not ant:
                        sk.SketchLines.AddByTwoPoints(ant, q)
                        ant = q
        sk.DeferUpdates = False

    def extruir(self, sk, dist, sentido, op):
        prof = sk.Profiles.AddForSolid()
        ef = self.cd.Features.ExtrudeFeatures
        if self.nfeat == 0 and op == JOIN:
            op = NEWB
        df = ef.CreateExtrudeDefinition(prof, op)
        df.SetDistanceExtent(max(dist, 0.001), sentido)
        ef.Add(df)
        self.nfeat += 1


def es_circulo(lazo):
    eds = list(inv._items(lazo.Edges))
    if len(eds) > 2:
        return False
    rs = [S(lambda e=e: e.Geometry.Radius, None) for e in eds]
    return all(r is not None for r in rs) and max(rs) - min(rs) < 1e-6


def aristas_cara(f, sin_circulos=False):
    out = []
    for lazo in inv._items(f.EdgeLoops):
        if sin_circulos and not S(lambda: lazo.IsOuterEdgeLoop, False) and es_circulo(lazo):
            continue
        out += list(inv._items(lazo.Edges))
    return out


def muestras(f, n=12):
    """Centros de facetas de la cara (puntos interiores), repartidos."""
    try:
        r = f.CalculateFacets(0.05, 0, 0, [], [], [])
        nv, nf, xyz, _, idx = r[0], r[1], r[2], r[3], r[4]
    except Exception:  # noqa: BLE001
        return [v(f.PointOnFace)]
    out = []
    paso = max(1, nf // n)
    for k in range(0, nf, paso):
        a, b, c = idx[3 * k] - 1, idx[3 * k + 1] - 1, idx[3 * k + 2] - 1
        out.append(tuple((xyz[3 * a + j] + xyz[3 * b + j] + xyz[3 * c + j]) / 3 for j in range(3)))
    return out or [v(f.PointOnFace)]


def prof_min(body, f, n):
    """Profundidad mínima del material debajo de la cara plana (normal exterior n), muestreando la cara."""
    ts = []
    for q in muestras(f):
        t, _ = rayo(body, add(q, mul(n, EPS)), mul(n, -1))
        if t is not None:
            ts.append(t - EPS)
    return min(ts) if ts else None


class Vacio:
    """Consulta si un punto está fuera del material del cuerpo ORIGINAL (para validar cada corte)."""

    def __init__(self, body):
        self.body = body
        b = body.RangeBox
        lejos = tg.CreatePoint(b.MaxPoint.X + 10, b.MaxPoint.Y + 10, b.MaxPoint.Z + 10)
        self.fuera = S(lambda: body.IsPointInside(lejos), None)

    def __call__(self, p):
        if self.fuera is None:
            return True
        return S(lambda: self.body.IsPointInside(tg.CreatePoint(*p)), None) == self.fuera


def reconstruir(body, cs, d, P, log, vol0):
    """1) prismas desde cada tapa (normal +d hacia abajo y -d hacia arriba) con la profundidad mínima muestreada,
    sin los agujeros redondos; 2) agujeros cilíndricos cóncavos en cualquier dirección; 3) ventanas no circulares
    de caras laterales; 4) bolsillos (cara lateral rebajada barrida hacia afuera). Los cortes se deshacen si empeoran."""
    for c in cs:
        if c["tipo"] == K_PLANO and paralelo(c["n"], d):
            f, n = c["f"], c["n"]
            t = prof_min(body, f, n)
            if t is None or t < 1e-3:
                continue
            sk = P.boceto(v(f.PointOnFace), n)
            P.dibujar_aristas(sk, aristas_cara(f, sin_circulos=True))
            P.extruir(sk, t, NEG, JOIN)
            log["prismas"] += 1
    vacio = Vacio(body)
    grupos = {}
    for c in cs:
        if c["tipo"] != K_CIL:
            continue
        f = c["f"]
        p = v(f.PointOnFace)
        a, b0 = c["eje"], c["base"]
        if a[0] + a[1] + a[2] < 0 or (abs(a[0] + a[1] + a[2]) < 1e-9 and (a[0] < 0 or a[1] < 0)):
            a = mul(a, -1)
        radial = sub(p, add(b0, mul(a, dot(sub(p, b0), a))))
        if not es_agujero(f, p, radial):
            continue
        pts = []
        for e in aristas_cara(f):
            pts += puntos_arista(e, 0.01)
        ts = [dot(sub(q, b0), a) for q in pts]
        t0, t1 = min(ts), max(ts)
        pie = sub(b0, mul(a, dot(b0, a)))          # punto del eje más cercano al origen
        clave = tuple(round(x, 3) for x in pie) + tuple(round(x, 4) for x in a) + (round(c["r"], 4),)
        g = grupos.setdefault(clave, {"a": a, "pie": pie, "r": c["r"], "t0": [], "t1": [], "ang": 0.0})
        tp = dot(pie, a)
        g["t0"].append(dot(b0, a) + t0 - tp)
        g["t1"].append(dot(b0, a) + t1 - tp)
        L = max(t1 - t0, 1e-6)
        g["ang"] += c["area"] / (c["r"] * L)
    for g in grupos.values():
        if g["ang"] < 2 * math.pi * 0.97:
            continue                 # no da la vuelta completa: no es un agujero (p. ej. fondo de diente)
        t0, t1 = min(g["t0"]), max(g["t1"])
        org = add(g["pie"], mul(g["a"], t0))
        if not vacio(add(org, mul(g["a"], (t1 - t0) / 2))):
            continue
        sk = P.boceto(org, g["a"])
        sk.SketchCircles.AddByCenterRadius(sk.ModelToSketchSpace(tg.CreatePoint(*org)), g["r"])
        P.extruir(sk, t1 - t0, POS, CUT)
        log["agujeros"] += 1
    for c in cs:
        if c["tipo"] != K_PLANO or paralelo(c["n"], d):
            continue
        f, n = c["f"], c["n"]
        for lazo in inv._items(f.EdgeLoops):
            if S(lambda: lazo.IsOuterEdgeLoop, False) or es_circulo(lazo):
                continue
            eds = list(inv._items(lazo.Edges))
            t = prof_min(body, f, n)
            if t is None:
                continue

            pl = []
            for e in eds:
                pl += puntos_arista(e, 0.01)
            cen = tuple(sum(q[j] for q in pl) / len(pl) for j in range(3))
            if not vacio(add(cen, mul(n, -t / 2))):
                log["avisos"].append("ventana con centro macizo: omitida")
                continue
            sk = P.boceto(v(f.PointOnFace), n)
            P.dibujar_aristas(sk, eds)
            P.extruir(sk, t + EPS, NEG, CUT)
            log["ventanas"] += 1
    # bolsillos: caras laterales rebajadas respecto del extremo del cuerpo en su normal
    b = body.RangeBox
    esquinas = [(x, y, z) for x in (b.MinPoint.X, b.MaxPoint.X) for y in (b.MinPoint.Y, b.MaxPoint.Y)
                for z in (b.MinPoint.Z, b.MaxPoint.Z)]
    for c in cs:
        if c["tipo"] != K_PLANO or paralelo(c["n"], d):
            continue
        f, n = c["f"], c["n"]
        ext = max(dot(n, q) for q in esquinas)
        h = ext - c["off"]
        if h < 1e-3:
            continue

        prueba = [add(q, mul(n, min(h / 2, 0.05))) for q in muestras(f, 12)]
        if not all(vacio(q) for q in prueba):
            continue
        # sólo si el bolsillo todavía tiene material en la reconstrucción
        nuevo = P.cd.SurfaceBodies.Item(1) if P.cd.SurfaceBodies.Count else None
        if nuevo is None or all(S(lambda q=q: nuevo.IsPointInside(tg.CreatePoint(*q)), None) == vacio.fuera for q in prueba):
            continue
        sk = P.boceto(v(f.PointOnFace), n)
        eds = []
        for lazo in inv._items(f.EdgeLoops):
            if S(lambda: lazo.IsOuterEdgeLoop, False):
                eds += list(inv._items(lazo.Edges))
        P.dibujar_aristas(sk, eds)
        P.extruir(sk, h + EPS, POS, CUT)
        log.setdefault("bolsillos", 0)
        log["bolsillos"] += 1


def es_agujero(f, p, radial):
    """Cilindro cóncavo: la normal exterior de la cara apunta hacia el eje."""
    try:
        r = f.Evaluator.GetNormalAtPoint(list(p), [])
        nn = r[0] if isinstance(r, tuple) and isinstance(r[0], (tuple, list)) else r
        nn = tuple(nn)[:3]
        return dot(nn, radial) < 0
    except Exception:  # noqa: BLE001
        return True


def caja(cd):
    b = cd.RangeBox
    return [round((b.MaxPoint.X - b.MinPoint.X) * 10, 2), round((b.MaxPoint.Y - b.MinPoint.Y) * 10, 2),
            round((b.MaxPoint.Z - b.MinPoint.Z) * 10, 2)]


def procesar(pref):
    fs = sorted(ORIG.glob(glob_escape(pref) + ".ipt")) or sorted(ORIG.glob(glob_escape(pref) + "*.ipt"))
    if not fs:
        return {"error": "no encontré el archivo"}
    src = fs[0]
    log = {"origen": src.name, "prismas": 0, "agujeros": 0, "ventanas": 0, "avisos": []}
    d0 = app.Documents.Open(str(src), False)
    try:
        cd0 = d0.ComponentDefinition
        bodies = list(inv._items(cd0.SurfaceBodies))
        log["cuerpos"] = len(bodies)
        vol0 = cd0.MassProperties.Volume
        log["vol0"] = round(vol0, 3)
        log["caja0"] = caja(cd0)
        props = {}
        for ps_name, keys in (("Design Tracking Properties", ("Part Number", "Description", "Stock Number")),
                              ("Inventor Summary Information", ("Title", "Comments"))):
            for k in keys:
                props[(ps_name, k)] = S(lambda: d0.PropertySets.Item(ps_name).Item(k).Value, "")
        if len(bodies) != 1:
            log["error"] = f"{len(bodies)} cuerpos: se reconstruye a mano"
            return log
        body = bodies[0]
        cs = caras(body)
        log["caras"] = len(cs)
        mejores = []
        for viol, d in candidatas(cs)[:3]:
            P = Pieza()
            lg = {"prismas": 0, "agujeros": 0, "ventanas": 0, "avisos": []}
            try:
                reconstruir(body, cs, d, P, lg, vol0)
                vol = P.cd.MassProperties.Volume if P.cd.SurfaceBodies.Count else 0.0
                err = abs(vol - vol0) / vol0 * 100 if vol0 else 100
                lg.update(dir=[round(x, 4) for x in d], viol_cm2=round(viol, 2), vol=round(vol, 3),
                          err_pct=round(err, 3), caja=caja(P.cd) if vol else None)
            except Exception as ex:  # noqa: BLE001
                lg["error"] = repr(ex)[:200]
                err = 999
            mejores.append((err, P, lg))
            if err < TOL:
                break
        mejores.sort(key=lambda x: x[0])
        err, P, lg = mejores[0]
        for _, Q, _ in mejores[1:]:
            S(lambda Q=Q: Q.doc.Close(True))
        log.update(lg)
        log["ok"] = err < TOL
        for (ps_name, k), val in props.items():
            S(lambda: P.doc.PropertySets.Item(ps_name).Item(k).__setattr__("Value", val))
        S(lambda: P.doc.PropertySets.Item("Inventor Summary Information").Item("Comments").__setattr__(
            "Value", f"Reconstruida paramétrica desde {src.name} (err vol {err:.3f} %)"))
        nombre = pref.strip().replace(";", "")
        dest = SAL / (("" if log["ok"] else "_REVISAR_") + nombre + ".ipt")
        P.doc.SaveAs(str(dest), False)
        log["archivo"] = str(dest)
        P.doc.Close(True)
        return log
    finally:
        S(lambda: d0.Close(True))


def glob_escape(s):
    return s.replace("[", "[[]")


T0 = time.time()
app.SilentOperation = True
try:
    for pref in PREFS:
        if rep.get(pref, {}).get("ok"):
            continue
        t1 = time.time()
        try:
            r = procesar(pref)
        except Exception:  # noqa: BLE001
            r = {"error": traceback.format_exc()[-600:]}
        r["s"] = round(time.time() - t1, 1)
        rep[pref] = r
        REP.write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"[{time.time() - T0:6.0f} s] {pref[:50]:50s} ok={r.get('ok')} err={r.get('err_pct')} "
              f"p={r.get('prismas')} a={r.get('agujeros')} v={r.get('ventanas')} {r.get('error', '')[:120]}", flush=True)
finally:
    app.SilentOperation = False
print(json.dumps({"total": len(PREFS), "ok": sum(1 for p in PREFS if rep.get(p, {}).get("ok")),
                  "s": round(time.time() - T0, 1)}))
