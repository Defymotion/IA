"""Gripper de apriete de N cajas DESDE CERO: diseño → chapas y gomas → módulo de pala móvil → ensamble
con restricciones (sin neumática; con cilindros ADN, guías HIWIN y tuercas del vástago).

- Chapas y gomas: generadas por gripper_design (nada se copia de ADECO2).
- Comerciales (cuerpo y vástago ADN-25-80, riel y bloque HGH15, tuerca DIN 439 M8): se toman de la copia de
  ADECO2, con la misma posición relativa que tienen en su módulo (vástago retraído = gripper abierto).
- Restricciones: Insertar entre agujeros que coinciden (chapa-chapa, riel-frame, etc.) y, donde no hay
  agujeros, Nivelación/Coincidencia entre planos de origen con desfase. El grupo móvil (bloques, empuja palas,
  pala, goma, placa de empuje, vástago y tuercas) desliza sobre los rieles y queda fijado por la restricción
  "Apertura" de cada módulo: cambiando ese valor se abre/cierra la pala.

Uso: .\\.venv\\Scripts\\python.exe .\\scripts\\construir_gripper.py --nombre GRIPPER_3xTBA200 --cajas 3
     [--fila 161 --apriete 333 --alto 130 --masa 7 --paso 160 --ancho-pala 140] [--reusar-piezas]
Salida: Documents\\InventorIA\\Generados\\<nombre>\\ (Chapas, Corte_laser, Ensamble, diseno.json, resultado.json)
"""
import argparse
import atexit
import itertools
import json
import math
import sys
import time
import traceback
from dataclasses import asdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
import inventor_mcp as inv  # noqa: E402
from gripper_calc import Caja  # noqa: E402
from gripper_design import disenar_gripper, T_316, T_18, MOD  # noqa: E402

a = argparse.ArgumentParser()
a.add_argument("--nombre", default="GRIPPER_3xTBA200")
a.add_argument("--fila", type=float, default=161)
a.add_argument("--apriete", type=float, default=333)
a.add_argument("--alto", type=float, default=130)
a.add_argument("--masa", type=float, default=7.0)
a.add_argument("--cajas", type=int, default=3)
a.add_argument("--paso", type=float, default=160)
a.add_argument("--ancho-pala", type=float, default=140)
a.add_argument("--reusar-piezas", action="store_true", help="no reconstruir las piezas que ya existen")
a.add_argument("--rehacer", nargs="*", default=[], help="piezas a reconstruir aunque se usen las existentes")
a.add_argument("--referencia", default=str(Path.home() / "Documents" / "InventorIA" / "12_ADECO2" / "Gripper"
                                           / "Gripper_ADECO2_V1.iam"))
a.add_argument("--modulo-ref", default="pala_movil_apriete:1")
a.add_argument("--alas-rectas", action="store_true")
a.add_argument("--sin-logo", action="store_true")
a.add_argument("--liviano", action="store_true", help="versión liviana: alas cortas, alma y brida alivianadas")
a.add_argument("--alto-palas", type=float, default=0, help="alto de la pala móvil (0 = alto de caja + 2)")
a.add_argument("--robot", default=None, help="patrón de brida (gripper_design.ROBOT_BRIDAS), p. ej. KR_IONTEC")
a.add_argument("--ala-frame", type=float, default=0, help="alto de las alas del frame (0 = según versión)")
x = a.parse_args()

S = inv._safe
BASE = Path.home() / "Documents" / "InventorIA" / "Generados" / x.nombre
CH, DXF, ENS = BASE / "Chapas", BASE / "Corte_laser", BASE / "Ensamble"
for p in (CH, DXF, ENS):
    p.mkdir(parents=True, exist_ok=True)
app = inv._inventor(start_if_needed=False)
tg = app.TransientGeometry
app.SilentOperation = True
atexit.register(lambda: S(lambda: setattr(app, "SilentOperation", False)))
T0 = time.time()
log = {"nombre": x.nombre, "piezas": [], "modulo": {}, "ensamble": {}, "avisos": [], "errores": []}


def etapa(txt):
    print(f"[{time.time() - T0:6.1f} s] {txt}", flush=True)


# =============================================================================== matrices (mm)
def mread(m):
    return [[m.Cell(r, c) * (10 if (c == 4 and r < 4) else 1) for c in range(1, 5)] for r in range(1, 5)]


def mmul(A, B):
    return [[sum(A[i][k] * B[k][j] for k in range(4)) for j in range(4)] for i in range(4)]


def mmake(M):
    m = tg.CreateMatrix()
    m.SetCoordinateSystem(tg.CreatePoint(M[0][3] / 10, M[1][3] / 10, M[2][3] / 10),
                          tg.CreateVector(M[0][0], M[1][0], M[2][0]),
                          tg.CreateVector(M[0][1], M[1][1], M[2][1]),
                          tg.CreateVector(M[0][2], M[1][2], M[2][2]))
    return m


def ptx(M, p):
    return [M[i][0] * p[0] + M[i][1] * p[1] + M[i][2] * p[2] + M[i][3] for i in range(3)]


def vtx(M, v):
    return [M[i][0] * v[0] + M[i][1] * v[1] + M[i][2] * v[2] for i in range(3)]


def trasl(dx, dy, dz):
    return [[1, 0, 0, dx], [0, 1, 0, dy], [0, 0, 1, dz], [0, 0, 0, 1]]


def mdiff(A, B):
    return max(max(abs(A[i][3] - B[i][3]) for i in range(3)),
               100 * max(abs(A[i][j] - B[i][j]) for i in range(3) for j in range(3)))


def box_tx(M, b):
    pts = [ptx(M, [b[i][0], b[j][1], b[k][2]]) for i in (0, 1) for j in (0, 1) for k in (0, 1)]
    return [[min(p[q] for p in pts) for q in range(3)], [max(p[q] for p in pts) for q in range(3)]]


def rotaciones():
    out = []
    for perm in itertools.permutations(range(3)):
        for sg in itertools.product((1, -1), repeat=3):
            R = [[0] * 3 for _ in range(3)]
            for i in range(3):
                R[i][perm[i]] = sg[i]
            det = (R[0][0] * (R[1][1] * R[2][2] - R[1][2] * R[2][1]) - R[0][1] * (R[1][0] * R[2][2] - R[1][2]
                   * R[2][0]) + R[0][2] * (R[1][0] * R[2][1] - R[1][1] * R[2][0]))
            if det == 1:
                out.append(R)
    return out


ROTS = rotaciones()
# ADECO2 (coordenadas del ensamble) -> coordenadas del FRAME generado (x a lo ancho del alma, y a lo largo,
# z: 0 = cara superior del alma, +z hacia las cajas). Obtenida registrando el Frame generado contra el original.
GINV = [[0, 0, -1, 412.437], [1, 0, 0, -398.135], [0, -1, 0, -684.026], [0, 0, 0, 1]]


# =============================================================================== geometría de piezas
_FIRMAS = {}


def firma(doc):
    """Circunferencias completas (centro, normal, diámetro) y caja, en mm y coordenadas de la pieza."""
    key = doc.FullFileName
    if key in _FIRMAS:
        return _FIRMAS[key]
    cd = doc.ComponentDefinition
    pts = []
    for body in inv._items(cd.SurfaceBodies):
        for e in inv._items(body.Edges):
            if S(lambda: e.CurveType) in (5122, 5123):
                continue
            g = S(lambda: e.Geometry)
            if g is None or S(lambda: g.StartAngle) is not None:
                continue
            c, r, n = S(lambda: g.Center), S(lambda: g.Radius), S(lambda: g.Normal)
            if c is None or r is None or n is None or r * 20 > 90:
                continue
            pts.append(((c.X * 10, c.Y * 10, c.Z * 10), (n.X, n.Y, n.Z), round(r * 20, 3)))
    b = cd.RangeBox
    bx = [[b.MinPoint.X * 10, b.MinPoint.Y * 10, b.MinPoint.Z * 10],
          [b.MaxPoint.X * 10, b.MaxPoint.Y * 10, b.MaxPoint.Z * 10]]
    _FIRMAS[key] = (pts, bx)
    return pts, bx


def circulos_en(M, doc):
    pts, _ = firma(doc)
    return [(ptx(M, c), vtx(M, n), d) for c, n, d in pts]


def dist_eje(p, c, n):
    v = [p[i] - c[i] for i in range(3)]
    k = sum(v[i] * n[i] for i in range(3))
    w = [v[i] - k * n[i] for i in range(3)]
    return w, math.sqrt(sum(q * q for q in w))


def registrar(doc, box_t, ejes=None, mismo_d=True):
    """Matriz pieza -> destino tal que la caja coincide con box_t y los agujeros caen sobre los ejes objetivo
    [(centro, normal, d)]. Devuelve (M, info)."""
    P, bp = firma(doc)
    dt = [box_t[1][i] - box_t[0][i] for i in range(3)]
    ct = [(box_t[0][i] + box_t[1][i]) / 2 for i in range(3)]
    best = None
    for R in ROTS:
        M = [[R[0][0], R[0][1], R[0][2], 0], [R[1][0], R[1][1], R[1][2], 0], [R[2][0], R[2][1], R[2][2], 0],
             [0, 0, 0, 1]]
        bb = box_tx(M, bp)
        err = sum(abs((bb[1][i] - bb[0][i]) - dt[i]) for i in range(3))
        if err > 1.5:
            continue
        t = [ct[i] - (bb[0][i] + bb[1][i]) / 2 for i in range(3)]
        ok, dev = 0, 0.0
        if ejes:
            for lim in (3.0, 0.3, 0.1):
                Mt = [row[:] for row in M]
                for i in range(3):
                    Mt[i][3] = t[i]
                res = []
                for c, n, d in P:
                    pc = ptx(Mt, c)
                    cand = [dist_eje(pc, ec, en) for ec, en, ed in ejes if (not mismo_d or abs(ed - d) < 0.3)]
                    if cand:
                        w, dd = min(cand, key=lambda q: q[1])
                        if dd < lim:
                            res.append(w)
                if len(res) >= 2:
                    corr = [-sum(w[i] for w in res) / len(res) for i in range(3)]
                    t = [t[i] + corr[i] for i in range(3)]
            Mt = [row[:] for row in M]
            for i in range(3):
                Mt[i][3] = t[i]
            ds = []
            for c, n, d in P:
                pc = ptx(Mt, c)
                cand = [dist_eje(pc, ec, en)[1] for ec, en, ed in ejes if (not mismo_d or abs(ed - d) < 0.3)]
                if cand:
                    ds.append(min(cand))
            ok = sum(1 for v in ds if v < 0.2)
            dev = max([v for v in ds if v < 0.2], default=0.0)
            # circunferencias que caen sobre una del objetivo (cara de contacto): define el sentido y el ajuste fino
            pares3 = []
            for c, nn_, dd_ in P:
                pc = ptx(Mt, c)
                ec = min((e[0] for e in ejes), key=lambda q: math.dist(pc, q))
                if math.dist(pc, ec) < 0.6:
                    pares3.append([ec[q] - pc[q] for q in range(3)])
            n3d = len(pares3)
            if n3d >= 2:
                corr = [sum(v[q] for v in pares3) / n3d for q in range(3)]
                for q in range(3):
                    Mt[q][3] += corr[q]
                t = [Mt[q][3] for q in range(3)]
        else:
            n3d = 0
        score = (-n3d, -ok, err)
        if best is None or score < best[0]:
            Mt = [row[:] for row in M]
            for i in range(3):
                Mt[i][3] = t[i]
            best = (score, Mt, {"agujeros_ok": ok, "en_contacto": n3d, "agujeros_pieza": len(P),
                                "desvio_mm": round(dev, 3),
                                "error_caja_mm": round(err, 3)})
    if best is None:
        raise RuntimeError(f"{Path(doc.FullFileName).name}: ninguna orientación coincide con la caja {dt}")
    return best[1], best[2]


# =============================================================================== documentos
def abrir(path, visible=False):
    path = Path(path)
    for d in inv._items(app.Documents):
        if S(lambda: Path(d.FullFileName).resolve() == path.resolve(), False):
            return d
    return app.Documents.Open(str(path), visible)


def cerrar_carpeta(folder):
    for tipo in (inv.K_ASSEMBLY_DOCUMENT, inv.K_PART_DOCUMENT):
        for d in inv._items(app.Documents):
            if S(lambda: folder.resolve() in Path(d.FullFileName).resolve().parents, False) and \
                    S(lambda: d.DocumentType) == tipo:
                S(lambda: d.Close(True))


def nuevo_ensamble():
    return app.Documents.Add(inv.K_ASSEMBLY_DOCUMENT, app.FileManager.GetTemplateFile(inv.K_ASSEMBLY_DOCUMENT),
                             True)


# =============================================================================== restricciones
TOL = 0.05          # mm: desplazamiento admitido al verificar una restricción


class _V(tuple):
    """Variante (tipo, signo) que se imprime legible."""
    def __str__(self):
        return f"{self[0][0]} {'+' if self[1] > 0 else '-'}"

    def __repr__(self):
        return str(self)


class Restrictor:
    """Agrega restricciones verificando que no muevan nada (cada pieza ya está en su lugar)."""

    def __init__(self, doc, fijas=()):
        self.doc, self.cd = doc, doc.ComponentDefinition
        self.C = self.cd.Constraints
        self.plan = {}            # occ.Name -> matriz planificada
        self.fijas = set(fijas)   # nombres que quedan fijos al final
        self.hechas = []
        self._circ = {}

    def registrar_plan(self, occ):
        self.plan[occ.Name] = mread(occ.Transformation)

    def occs(self):
        return inv._items(self.cd.Occurrences)

    def _solo_libre(self, libre):
        for o in self.occs():
            want = o.Name != libre.Name
            if S(lambda: o.Grounded) != want:
                S(lambda: setattr(o, "Grounded", want))

    def _movio(self, occ):
        return mdiff(mread(occ.Transformation), self.plan[occ.Name]) > TOL

    def _desvio(self, occ):
        return mdiff(mread(occ.Transformation), self.plan[occ.Name])

    def _cumple_plan(self, libres_occ):
        """¿La posición planificada satisface las restricciones? Si el solver corrió la pieza por un grado de
        libertad todavía libre, se la vuelve a poner en su lugar y se verifica que se quede ahí."""
        mov = max(self._desvio(o) for o in libres_occ)
        if mov <= TOL:
            return True, mov
        for o in libres_occ:
            if self._desvio(o) > TOL:
                S(lambda: setattr(o, "Transformation", mmake(self.plan[o.Name])))
        self.doc.Update()
        mov2 = max(self._desvio(o) for o in libres_occ)
        return mov2 <= TOL, mov2

    def _probar(self, occ, crear, desc, variantes, grupo=None):
        """crear(v) agrega la restricción con la variante v; se queda con la primera que no mueve nada.
        grupo: piezas que quedan libres durante la prueba (por defecto sólo occ)."""
        libres = {o.Name for o in (grupo or [occ])}
        for o in self.occs():
            want = o.Name not in libres
            if S(lambda: o.Grounded) != want:
                S(lambda: setattr(o, "Grounded", want))
        libres_occ = [o for o in self.occs() if o.Name in libres]
        intentos = []
        for v in variantes:
            try:
                c = crear(v)
            except Exception as exc:  # noqa: BLE001
                intentos.append(f"{v}: {exc!r}"[:120])
                continue
            self.doc.Update()
            ok, mov = self._cumple_plan(libres_occ)
            if ok:
                self.hechas.append({"pieza": occ.Name, "tipo": desc, "variante": str(v)})
                return c
            S(lambda: c.Delete())
            self.doc.Update()
            for o in libres_occ:            # volver al lugar planificado
                if self._desvio(o) > TOL:
                    S(lambda: setattr(o, "Transformation", mmake(self.plan[o.Name])))
            self.doc.Update()
            intentos.append(f"{v}: movía {mov:.2f}")
        log["avisos"].append(f"{self.doc.DisplayName}: no se pudo restringir {occ.Name} ({desc}): {intentos}")
        return None

    # --- circunferencias con su arista (en coords del ensamble), para Insertar
    def aristas_circ(self, occ, dmax=20.0):
        key = occ.Name if S(lambda: occ.ParentOccurrence) is None else \
            occ.ParentOccurrence.Name + "/" + occ.Name
        if key in self._circ:
            return self._circ[key]
        out = []
        for body in inv._items(occ.SurfaceBodies):
            for e in inv._items(body.Edges):
                if S(lambda: e.CurveType) in (5122, 5123):
                    continue
                g = S(lambda: e.Geometry)
                if g is None or S(lambda: g.StartAngle) is not None:
                    continue
                c, r, n = S(lambda: g.Center), S(lambda: g.Radius), S(lambda: g.Normal)
                if c is None or r is None or n is None or r * 20 > dmax:
                    continue
                out.append(((c.X * 10, c.Y * 10, c.Z * 10), (n.X, n.Y, n.Z), r * 20, e))
        self._circ[key] = out
        return out

    def pares_coaxiales(self, oa, ob, n=2, dmax=20.0):
        A, B = self.aristas_circ(oa, dmax), self.aristas_circ(ob, dmax)
        pares = []
        for ca, na, da, ea in A:
            for cb, nb, db, eb in B:
                if math.dist(ca, cb) < 0.05 and abs(sum(na[i] * nb[i] for i in range(3))) > 0.999:
                    if all(math.dist(ca, p[0]) > 5 for p in pares):
                        pares.append((ca, ea, eb))
                    break
            if len(pares) >= n:
                break
        return pares

    def insertar(self, occ, otra, n=2, dmax=20.0):
        """Inserta 'occ' en 'otra' por n pares de agujeros coaxiales en contacto. Devuelve cuántos agregó."""
        k = 0
        for _, ea, eb in self.pares_coaxiales(occ, otra, n, dmax):
            if self._probar(occ, lambda v: self.C.AddInsertConstraint(ea, eb, v, 0), f"Insertar en {otra.Name}",
                            (True, False)):
                k += 1
        return k

    def fijar(self, occ, otra, dmax=20.0):
        """Dos Insertar entre agujeros coaxiales en contacto; si no hay dos pares, planos respecto de 'otra'."""
        pares = self.pares_coaxiales(occ, otra, 2, dmax)
        hechas = []
        if len(pares) == 2:
            for _, ea, eb in pares:
                c = self._probar(occ, lambda v: self.C.AddInsertConstraint(ea, eb, v, 0),
                                 f"Insertar en {otra.Name}", (True, False))
                if c is None:
                    break
                hechas.append(c)
        if len(hechas) == 2:
            return "insertar"
        for c in hechas:
            S(lambda: c.Delete())
            self.hechas.pop()
        self.planos(occ, otra)
        return "planos"

    def planos(self, occ, padre=None, ejes=(0, 1, 2), nombre=None, grupo=None):
        """Nivelación/Coincidencia entre los planos de origen de occ y los de padre (o del ensamble) con el
        desfase que tienen ahora. ejes: ejes LOCALES de occ a fijar."""
        Mc = mread(occ.Transformation)
        Mp = mread(padre.Transformation) if padre is not None else trasl(0, 0, 0)
        hechas = []
        for i in ejes:
            nc = [Mc[r][i] for r in range(3)]
            j, dot = max(((j, sum(nc[r] * Mp[r][j] for r in range(3))) for j in range(3)), key=lambda q: abs(q[1]))
            if abs(dot) < 0.999:
                log["avisos"].append(f"{occ.Name}: eje {i} no paralelo a {padre.Name if padre else 'origen'}")
                continue
            npj = [Mp[r][j] for r in range(3)]
            d = sum((Mc[r][3] - Mp[r][3]) * npj[r] for r in range(3))
            e1 = occ.CreateGeometryProxy(occ.Definition.WorkPlanes.Item(i + 1))
            e2 = padre.CreateGeometryProxy(padre.Definition.WorkPlanes.Item(j + 1)) if padre is not None \
                else self.cd.WorkPlanes.Item(j + 1)
            fl, ma = ("Nivelación", self.C.AddFlushConstraint), ("Coincidencia", self.C.AddMateConstraint)
            c = self._plano_calibrado(occ, e1, e2, npj, [fl, ma] if dot > 0 else [ma, fl], grupo,
                                      f"plano {i}->{j} de {padre.Name if padre else 'origen'}", d)
            if c is not None:
                if nombre:
                    S(lambda: setattr(c, "Name", nombre))
                    S(lambda: setattr(c.Offset, "Name", nombre.replace(" ", "_")))
                hechas.append(c)
        return hechas

    def _plano_calibrado(self, occ, e1, e2, normal, tipos, grupo, desc, d_geo=0.0):
        """Agrega Nivelación/Coincidencia con desfase 0, mide cuánto se corrió la pieza a lo largo de la normal y
        prueba ese desfase (y el geométrico) con los dos signos, hasta que la posición planificada cumpla.
        Así no depende de la convención de signos de Inventor."""
        libres = {o.Name for o in (grupo or [occ])}
        for o in self.occs():
            want = o.Name not in libres
            if S(lambda: o.Grounded) != want:
                S(lambda: setattr(o, "Grounded", want))
        libres_occ = [o for o in self.occs() if o.Name in libres]

        def restaurar():
            for o in libres_occ:
                if self._desvio(o) > TOL:
                    S(lambda: setattr(o, "Transformation", mmake(self.plan[o.Name])))
            self.doc.Update()

        intentos = []
        for nombre_t, fn in tipos:
            try:
                c = fn(e1, e2, 0)
            except Exception as exc:  # noqa: BLE001
                intentos.append(f"{nombre_t}: {exc!r}"[:100])
                continue
            self.doc.Update()
            M = mread(occ.Transformation)
            P_ = self.plan[occ.Name]
            delta = sum((P_[q][3] - M[q][3]) * normal[q] for q in range(3))
            cands = []
            for v in (0.0, delta, -delta, d_geo, -d_geo):
                if all(abs(v - w) > 1e-4 for w in cands):
                    cands.append(v)
            for v in cands:
                S(lambda: setattr(c.Offset, "Expression", f"{v:.4f} mm"))
                self.doc.Update()
                ok, mov = self._cumple_plan(libres_occ)
                if ok:
                    self.hechas.append({"pieza": occ.Name, "tipo": desc, "variante": f"{nombre_t} {v:.3f}"})
                    return c
                intentos.append(f"{nombre_t} {v:.2f}: {mov:.2f}")
            S(lambda: c.Delete())
            restaurar()
        log["avisos"].append(f"{self.doc.DisplayName}: no se pudo restringir {occ.Name} ({desc}): {intentos}")
        return None

    def cerrar(self):
        """Libera todo salvo lo fijo, actualiza y verifica que nada se haya movido."""
        for o in self.occs():
            S(lambda: setattr(o, "Grounded", o.Name in self.fijas))
        self.doc.Update()
        movidas = {o.Name: round(self._desvio(o), 2) for o in self.occs()
                   if o.Name in self.plan and self._movio(o)}
        salud = {}
        for c in inv._items(self.C):
            h = str(S(lambda: c.HealthStatus))
            salud[h] = salud.get(h, 0) + 1
        return {"restricciones": self.C.Count, "movidas": movidas, "estado_restricciones": salud}


# =============================================================================== 1) diseño
etapa("Diseño")
caja = Caja(x.fila, x.apriete, x.alto, x.masa, x.nombre)
d = disenar_gripper(caja, x.cajas, paso=x.paso or None, ancho_pala=x.ancho_pala or None,
                    curvo=not x.alas_rectas, logo=not x.sin_logo, liviano=x.liviano,
                    alto_palas=x.alto_palas or None, robot=x.robot, ala_frame=x.ala_frame or None)
DM = d["modulo"]
n, paso = x.cajas, d["calculo"]["paso_mm"]
L = n * paso
specs = {}
for p in d["chapas"]:
    s = asdict(p)
    s["desarrollo"] = p.flat_size()
    specs[p.nombre] = s
W_FRAME = specs["Frame"]["desarrollo"][0]
XC = W_FRAME / 2                     # centro del alma (coords del frame)
WEB = DM["web"]
E_ALMA = XC + WEB / 2                # borde +x del alma (coords del frame)
DX_MOD = E_ALMA - (MOD["xc_ref"] + 200.0) + DM["dx"]     # corrimiento del módulo respecto de ADECO2
SOPORTE = next(k for k in specs if k.startswith("Soporte"))
t = T_316
YC = [L / 2 + (i - (n - 1) / 2) * paso for i in range(n)]
(BASE / "diseno.json").write_text(json.dumps({"calculo": d["calculo"], "chapas": list(specs.values()),
                                              "gomas": d["gomas"], "comerciales": d["comerciales"],
                                              "avisos": d["avisos"]}, ensure_ascii=False, indent=1),
                                  encoding="utf-8")
log["calculo"] = {k: d["calculo"][k] for k in ("cilindro", "fuerza_cilindro_n", "fuerza_requerida_n", "fs_real",
                                               "guia", "masa_gripper_kg", "masa_total_kg")}
log["avisos"] += d["avisos"]

# =============================================================================== 2) piezas
cerrar_carpeta(ENS)
archivos = {}
for nombre, s in specs.items():
    ipt = CH / f"{nombre}.ipt"
    archivos[nombre] = ipt
    if x.reusar_piezas and ipt.exists() and nombre not in x.rehacer:
        continue
    etapa(f"Chapa {nombre} ({len(s['circulos'])} agujeros, {len(s['hexagonos'])} hexágonos)")
    try:
        for dd in inv._items(app.Documents):
            if S(lambda: Path(dd.FullFileName).resolve() == ipt.resolve(), False):
                dd.Close(True)
        r = inv.build_flat_part(app, s, ipt, DXF / f"{nombre}.dxf")
        doc = r.pop("documento")
        S(lambda: doc.Close(True))
    except Exception as exc:  # noqa: BLE001
        r = {"pieza": nombre, "error": repr(exc), "traza": traceback.format_exc()[-1200:]}
        log["errores"].append(r)
    log["piezas"].append(r)
for g in d["gomas"]:
    ipt = CH / f"{g['nombre']}.ipt"
    archivos[g["nombre"]] = ipt
    if x.reusar_piezas and ipt.exists() and g["nombre"] not in x.rehacer:
        continue
    etapa(f"Goma {g['nombre']}")
    try:
        for dd in inv._items(app.Documents):
            if S(lambda: Path(dd.FullFileName).resolve() == ipt.resolve(), False):
                dd.Close(True)
        r = inv.build_plate_part(app, g["nombre"], g["largo"], g["alto"], g["espesor"], ipt)
        doc = r.pop("documento")
        S(lambda: doc.Close(True))
    except Exception as exc:  # noqa: BLE001
        r = {"pieza": g["nombre"], "error": repr(exc), "traza": traceback.format_exc()[-1200:]}
        log["errores"].append(r)
    log["piezas"].append(r)
if log["errores"]:
    (BASE / "resultado.json").write_text(json.dumps(log, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(log, ensure_ascii=False, indent=1))
    sys.exit("Errores construyendo piezas")

# =============================================================================== 3) referencia del módulo
etapa("Leyendo la disposición del módulo de ADECO2 (sólo lectura)")
ref = abrir(x.referencia)
mod_occ = next(o for o in inv._items(ref.ComponentDefinition.Occurrences) if o.Name == x.modulo_ref)
hojas = []


def walk(col):
    for o in inv._items(col):
        if S(lambda: o.Suppressed, False):
            continue
        if S(lambda: o.DefinitionDocumentType) == inv.K_ASSEMBLY_DOCUMENT:
            walk(o.SubOccurrences)
        else:
            hojas.append(o)


walk(mod_occ.SubOccurrences)
ROLES = [("cuerpo", "(Z)"), ("vastago", "(KS)"), ("riel", "0468"), ("bloque", "0485"), ("tuerca", "DIN-439"),
         ("soporte", "soporte piston"), ("goma", "goma pala movil"), ("pala", "pala movil"),
         ("empuja", "empuja pala"), ("placa", "part_empuje")]
refs = {}
ignoradas = []
for o in hojas:
    fn = Path(o.Definition.Document.FullFileName).name
    rol = next((r for r, k in ROLES if k.lower() in fn.lower()), None)
    Mw = mread(o.Transformation)
    # verificación: caja de la definición transformada vs caja de la ocurrencia
    bw = box_tx(Mw, firma(o.Definition.Document)[1])
    rb = o.RangeBox
    bo = [[rb.MinPoint.X * 10, rb.MinPoint.Y * 10, rb.MinPoint.Z * 10],
          [rb.MaxPoint.X * 10, rb.MaxPoint.Y * 10, rb.MaxPoint.Z * 10]]
    if max(abs(bw[i][j] - bo[i][j]) for i in range(2) for j in range(3)) > 1.0:
        log["avisos"].append(f"Referencia {o.Name}: la matriz no coincide con su caja (revisar)")
    if rol is None:
        ignoradas.append(fn)
        continue
    Mf = mmul(GINV, Mw)
    refs.setdefault(rol, []).append({"nombre": o.Name, "archivo": o.Definition.Document.FullFileName,
                                     "doc": o.Definition.Document, "M": Mf})
log["modulo"]["referencia_ignoradas"] = sorted(set(ignoradas))
log["modulo"]["referencia_roles"] = {k: len(v) for k, v in refs.items()}
faltan = [r for r in ("cuerpo", "vastago", "riel", "bloque", "pala", "empuja", "placa", "soporte", "goma")
          if r not in refs]
if faltan:
    log["errores"].append(f"En la referencia no encontré: {faltan}")
_bp = box_tx(refs["pala"][0]["M"], firma(refs["pala"][0]["doc"])[1])
yc_ref = (_bp[0][1] + _bp[1][1]) / 2                   # centro del módulo de referencia (a lo largo del frame)
TM = trasl(0, -yc_ref, 0)            # frame -> módulo de referencia (y relativo al centro del módulo)
for lst in refs.values():
    for r_ in lst:
        r_["M"] = mmul(TM, r_["M"])
        r_["caja"] = box_tx(r_["M"], firma(r_["doc"])[1])
        r_["circ"] = circulos_en(r_["M"], r_["doc"])
# el grupo móvil de la referencia tiene que estar en "abierto" (vástago retraído): si la copia de ADECO2 quedó con
# la pala movida (p. ej. por una animación), se corrige con los agujeros de los bloques (MOD['agujeros_bloque_x'])
_hb = [c[0][0] for r_ in refs.get("bloque", []) for c in r_["circ"] if abs(c[2] - 3.3) < 0.2]
DX_REF = round(MOD["agujeros_bloque_x"] - sum(_hb) / len(_hb), 3) if _hb else 0.0
if abs(DX_REF) > 0.05:
    log["avisos"].append(f"Referencia ADECO2 con la pala corrida {-DX_REF} mm: se lleva a 'abierto'.")
    for rol in ("bloque", "pala", "goma", "vastago", "tuerca"):
        for r_ in refs.get(rol, []):
            r_["M"][0][3] += DX_REF
            r_["caja"] = box_tx(r_["M"], firma(r_["doc"])[1])
            r_["circ"] = circulos_en(r_["M"], r_["doc"])
log["modulo"]["correccion_referencia_mm"] = DX_REF

# =============================================================================== 4) módulo de pala móvil
etapa("Módulo de pala móvil")
mod_path = ENS / "Modulo pala movil.iam"
for f in (mod_path,):
    if f.exists():
        f.unlink()
mdoc = nuevo_ensamble()
mcd = mdoc.ComponentDefinition
R = Restrictor(mdoc)
mo = {}
regs = {}


def colocar(doc_cd, rol, path, M, R_):
    occ = doc_cd.Occurrences.Add(str(path), mmake(M))
    R_.registrar_plan(occ)
    mo.setdefault(rol, []).append(occ)
    return occ


# comerciales: guías HIWIN con la misma posición relativa que en ADECO2
for rol in ("riel", "bloque"):
    for r_ in sorted(refs.get(rol, []), key=lambda q: q["M"][1][3]):
        colocar(mcd, rol, r_["archivo"], r_["M"], R)
# cilindro: ADN-25 de ADECO2 o el modelo Festo copiado en Comerciales
t = T_316
XF, ZE = DM["x_frontal"], t + DM["eje"]
M_CUERPO = [[0, 0, -1, XF], [0, -1, 0, 0], [-1, 0, 0, ZE], [0, 0, 0, 1]]   # eje del cilindro hacia -x
if DM["modelo"] is None:
    for rol in ("cuerpo", "vastago", "tuerca"):
        for r_ in sorted(refs.get(rol, []), key=lambda q: q["M"][1][3]):
            colocar(mcd, rol, r_["archivo"], r_["M"], R)
else:
    md_ = DM["modelo"]
    carpeta = Path.home() / "Documents" / "InventorIA" / "Comerciales" / md_["carpeta"]
    faltan_c = [f for f in (md_["cuerpo"], md_["vastago"], md_["tuerca"]) if not (carpeta / f).exists()]
    if faltan_c:
        sys.exit(f"Faltan archivos del cilindro en {carpeta}: {faltan_c}")
    colocar(mcd, "cuerpo", carpeta / md_["cuerpo"], M_CUERPO, R)
    colocar(mcd, "vastago", carpeta / md_["vastago"], mmul(M_CUERPO, md_["M_vastago"]), R)
    for _ in range(2):
        colocar(mcd, "tuerca", carpeta / md_["tuerca"], mmul(M_CUERPO, md_["M_tuerca"]), R)

# chapas y gomas generadas: caja objetivo + agujeros objetivo (reglas del diseño)
SP = DM["soporte"]
XR = XF + DM["largo_cil"]
ZX, ZY, ZZ = (1, 0, 0), (0, 1, 0), (0, 0, 1)
bp_ref = box_tx(refs["pala"][0]["M"], firma(refs["pala"][0]["doc"])[1])
bg_ref = box_tx(refs["goma"][0]["M"], firma(refs["goma"][0]["doc"])[1]) if refs.get("goma") else None
W_P, H_P = DM["ancho_pala"], DM["alto_pala"]
z_pala = bp_ref[0][2]
z_bloque = t + MOD["z_bloque"]


def ejes_soporte(x_frame, x_cil):
    return ([((x_frame, sg * SP["sep_frame"] / 2, t), ZZ, SP["d_frame"]) for sg in (-1, 1)]
            + [((x_cil, sg * DM["tg"] / 2, t + SP["cil_desde_frame"]), ZX, SP["d_cil"]) for sg in (-1, 1)])


objetivos = [
    ("soporte", SOPORTE, [[XF - SP["ala_frame"], -SP["ancho"] / 2, t], [XF, SP["ancho"] / 2, t + SP["ala_cil"]]],
     ejes_soporte(XF - SP["frame_desde_cil"], XF), True),
    ("soporte", SOPORTE, [[XR, -SP["ancho"] / 2, t], [XR + SP["ala_frame"], SP["ancho"] / 2, t + SP["ala_cil"]]],
     ejes_soporte(XR + SP["frame_desde_cil"], XR), True),
    ("placa", "Placa empuje", [[DM["placa_x"][0], -DM["placa_ancho"] / 2, ZE - DM["placa_alto"] / 2],
                               [DM["placa_x"][1], DM["placa_ancho"] / 2, ZE + DM["placa_alto"] / 2]],
     [((DM["placa_x"][0], 0, ZE), ZX, 0), ((DM["placa_x"][1], 0, ZE), ZX, 0)], False),
]
circ_bloques = [c for r_ in refs.get("bloque", []) for c in r_["circ"]]
for sg in (-1, 1):
    objetivos.append(("empuja", "Empuja pala",
                      [[DM["empuja_x"][0], 50 * sg - 19, z_bloque], [DM["empuja_x"][1], 50 * sg + 19, z_bloque + T_18]],
                      circ_bloques, False))
objetivos.append(("pala", "Pala movil", [[bp_ref[0][0], -W_P / 2, z_pala], [bp_ref[1][0], W_P / 2, z_pala + H_P]],
                  "empuja", False))
galto = d["gomas"][1]["alto"]
gx = (bg_ref[0][0], bg_ref[1][0]) if bg_ref else (bp_ref[1][0] - t - 2.5, bp_ref[1][0] - t)
objetivos.append(("goma", "Goma pala movil", [[gx[0], -W_P / 2, z_pala + H_P - galto], [gx[1], W_P / 2, z_pala + H_P]],
                  None, True))
for rol, nombre, caja_t, ejes, mismo_d in objetivos:
    gdoc = abrir(archivos[nombre])
    if ejes == "empuja":            # la pala se apoya en las empuja pala: sus agujeros en contacto
        ejes = [c for e in mo.get("empuja", []) for c in circulos_en(mread(e.Transformation), e.Definition.Document)]
    try:
        M, info = registrar(gdoc, caja_t, ejes, mismo_d)
    except RuntimeError as exc:
        log["errores"].append(str(exc))
        continue
    regs[f"{nombre} ({rol} {len(mo.get(rol, [])) + 1})"] = info
    colocar(mcd, rol, archivos[nombre], M, R)
log["modulo"]["registro"] = regs
mdoc.Update()


def dims_local(occ):
    b = firma(occ.Definition.Document)[1]
    return [b[1][i] - b[0][i] for i in range(3)], [(b[0][i] + b[1][i]) / 2 for i in range(3)]


# tuercas del vástago: alinear sus ejes con los del vástago y apoyarlas una a cada lado de la placa de empuje
if mo.get("tuerca") and mo.get("vastago") and mo.get("placa"):
    vas = mo["vastago"][0]
    Mv = mread(vas.Transformation)
    dv, _ = dims_local(vas)
    kv = dv.index(max(dv))
    eje = [Mv[q][kv] for q in range(3)]
    otros = [i for i in range(3) if i != kv]
    bpl = box_tx(mread(mo["placa"][0].Transformation), firma(mo["placa"][0].Definition.Document)[1])
    ax = max(range(3), key=lambda q: abs(eje[q]))            # eje del ensamble paralelo al vástago
    p0, p1 = bpl[0][ax], bpl[1][ax]
    pc = (p0 + p1) / 2
    for tu in mo["tuerca"]:
        Mt = mread(tu.Transformation)
        dt_, ct_ = dims_local(tu)
        kt = dt_.index(min(dt_))                              # espesor de la tuerca = su eje
        c_w = ptx(Mt, ct_)
        Rn = [[0] * 3 for _ in range(3)]
        sgn = 1 if sum(Mt[q][kt] * eje[q] for q in range(3)) >= 0 else -1
        for r_ in range(3):
            Rn[r_][kt] = sgn * eje[r_]
        rest = [i for i in range(3) if i != kt]
        for i_, j_ in zip(rest, otros):
            for r_ in range(3):
                Rn[r_][i_] = Mv[r_][j_]
        det = (Rn[0][0] * (Rn[1][1] * Rn[2][2] - Rn[1][2] * Rn[2][1]) - Rn[0][1] * (Rn[1][0] * Rn[2][2] - Rn[1][2]
               * Rn[2][0]) + Rn[0][2] * (Rn[1][0] * Rn[2][1] - Rn[1][1] * Rn[2][0]))
        if det < 0:
            for r_ in range(3):
                Rn[r_][rest[0]] *= -1
        half = dt_[kt] / 2
        # del lado del cuerpo o del lado libre, según dónde estaba
        nuevo_c = list(c_w)
        nuevo_c[ax] = (p1 + half) if c_w[ax] > pc else (p0 - half)
        Mn = [[Rn[0][0], Rn[0][1], Rn[0][2], 0], [Rn[1][0], Rn[1][1], Rn[1][2], 0],
              [Rn[2][0], Rn[2][1], Rn[2][2], 0], [0, 0, 0, 1]]
        off = ptx(Mn, ct_)
        for q in range(3):
            Mn[q][3] = nuevo_c[q] - off[q]
        tu.Transformation = mmake(Mn)
        R.registrar_plan(tu)
    lados = [ptx(mread(tu.Transformation), dims_local(tu)[1])[ax] > pc for tu in mo["tuerca"]]
    if len(set(lados)) == 1 and len(mo["tuerca"]) == 2:   # las dos del mismo lado: pasar una al otro
        tu = mo["tuerca"][0]
        Mt = mread(tu.Transformation)
        dt_, ct_ = dims_local(tu)
        cw = ptx(Mt, ct_)
        half = min(dt_) / 2
        Mt[ax][3] += ((p0 - half) - cw[ax]) if lados[0] else ((p1 + half) - cw[ax])
        tu.Transformation = mmake(Mt)
        R.registrar_plan(tu)
    mdoc.Update()

# restricciones del módulo
etapa("Restricciones del módulo")
LARGO = {}


def eje_largo(occ):
    """Eje local más largo (dirección del riel / del vástago)."""
    b = firma(occ.Definition.Document)[1]
    dims = [b[1][i] - b[0][i] for i in range(3)]
    return dims.index(max(dims))


rieles, bloques = mo.get("riel", []), mo.get("bloque", [])
estrategia = {}
for o in rieles + mo.get("soporte", []):
    R.planos(o)                                                # fijos al origen del módulo
for o in mo.get("cuerpo", []):
    estrategia[o.Name] = R.fijar(o, mo["soporte"][0], 8)       # cilindro abulonado al soporte


def cercano(lista, occ):
    yo = mread(occ.Transformation)[1][3]
    return min(lista, key=lambda q: abs(mread(q.Transformation)[1][3] - yo))


# cadena móvil: bloque0 desliza en riel0 -> empuja0 -> pala -> empuja1 -> bloque1
pala = mo["pala"][0]
emp0, emp1 = sorted(mo["empuja"], key=lambda q: mread(q.Transformation)[1][3])
blq0, blq1 = cercano(bloques, emp0), cercano(bloques, emp1)
rl0 = cercano(rieles, blq0)
k_r = eje_largo(rl0)
Mr = mread(rl0.Transformation)
eje_riel_mod = [Mr[q][k_r] for q in range(3)]
Mb = mread(blq0.Transformation)
R.planos(blq0, rl0, ejes=[i for i in range(3) if abs(sum(Mb[q][i] * eje_riel_mod[q] for q in range(3))) < 0.5])
estrategia[emp0.Name] = R.fijar(emp0, blq0, 8)
estrategia[pala.Name] = R.fijar(pala, emp0, 8)
estrategia[emp1.Name] = R.fijar(emp1, pala, 8)
estrategia[blq1.Name] = R.fijar(blq1, emp1, 8)
for g in mo.get("goma", []):
    R.planos(g, pala)                                          # goma pegada
for pl in mo.get("placa", []):
    R.planos(pl, emp0)                                         # placa soldada a las empuja pala
for v in mo.get("vastago", []):
    k = eje_largo(v)
    R.planos(v, mo["cuerpo"][0], ejes=[i for i in range(3) if i != k])     # coaxial con el cuerpo
    R.planos(v, mo["placa"][0], ejes=[k])                                    # avanza con la placa
for tu in mo.get("tuerca", []):
    R.planos(tu, mo["vastago"][0])
# Apertura: posición de la pala a lo largo del riel respecto del origen del módulo; se prueba con todo el
# grupo móvil libre (si no, la prueba no detecta un signo equivocado)
movil = [blq0, blq1, emp0, emp1, pala] + mo.get("goma", []) + mo.get("placa", []) + mo.get("vastago", []) \
    + mo.get("tuerca", [])
Mp_ = mread(pala.Transformation)
ip = max(range(3), key=lambda i: abs(sum(Mp_[q][i] * eje_riel_mod[q] for q in range(3))))
R.planos(pala, None, ejes=[ip], nombre="Apertura", grupo=movil)
log["modulo"]["estrategia"] = estrategia
log["modulo"]["verificacion"] = R.cerrar()
log["modulo"]["restricciones_detalle"] = R.hechas
for o in R.occs():
    S(lambda: setattr(o, "Grounded", False))
inv._iprop(mdoc, "Design Tracking Properties", "Part Number", "Modulo pala movil")
mdoc.SaveAs(str(mod_path), False)

# =============================================================================== 5) ensamble general
etapa("Ensamble general")
top_path = ENS / f"Gripper_{x.nombre}.iam"
if top_path.exists():
    top_path.unlink()
tdoc = nuevo_ensamble()
tcd = tdoc.ComponentDefinition
RT = Restrictor(tdoc, fijas={"Frame:1"})
mo = {}
frame = colocar(tcd, "frame", archivos["Frame"], trasl(0, 0, 0), RT)
fdoc = frame.Definition.Document
fcirc = circulos_en(trasl(0, 0, 0), fdoc)
H_FL = DM["ala_frame"] - t                                   # punta de las alas en z = -H_FL
X_MIN = E_ALMA - WEB                                       # borde -x del alma
BR = DM["brida"]
ANCHO_BRIDA = WEB - BR["luz_lateral"]
H_PF = DM["alto_pala_fija"]
targets = {
    "Pala fija": ([[X_MIN, 10, t], [X_MIN + 60, L - 10, t + H_PF]],
                  [(c, nn, dd) for c, nn, dd in fcirc if abs(dd - 8) < 0.1], True),
    "Goma pala fija": ([[X_MIN + t, 10, t + H_PF - d["gomas"][0]["alto"]],
                        [X_MIN + t + d["gomas"][0]["espesor"], L - 10, t + H_PF]],
                       None, True),
    "Brida": ([[X_MIN + t, L / 2 - BR["largo"] / 2, -H_FL + BR["solape"] - BR["pata"]],
               [X_MIN + t + ANCHO_BRIDA, L / 2 + BR["largo"] / 2, -H_FL + BR["solape"]]],
              [(c, nn, dd) for c, nn, dd in fcirc if abs(dd - 10) < 0.1], True),
}
treg = {}
for nombre, (bx, ejes, md) in targets.items():
    gdoc = abrir(archivos[nombre])
    M, info = registrar(gdoc, bx, ejes, md)
    treg[nombre] = info
    colocar(tcd, nombre, archivos[nombre], M, RT)
mods = [colocar(tcd, "modulo", mod_path, trasl(DX_MOD, yc, 0), RT) for yc in YC]
log["ensamble"]["registro"] = treg
tdoc.Update()
etapa("Restricciones del ensamble")
S(lambda: setattr(frame, "Grounded", True))
pf, gf, br = mo["Pala fija"][0], mo["Goma pala fija"][0], mo["Brida"][0]
log["ensamble"]["estrategia"] = {pf.Name: RT.fijar(pf, frame, 9), br.Name: RT.fijar(br, frame, 11)}
RT.planos(gf, pf)
for m in mods:
    rails = [so for so in inv._items(m.SubOccurrences) if "0468" in Path(so.Definition.Document.FullFileName).name]
    hechas = []
    for rl in rails:
        for _, ea, eb in RT.pares_coaxiales(rl, frame, 1, 6):
            c = RT._probar(m, lambda v: RT.C.AddInsertConstraint(ea, eb, v, 0), "Insertar riel en frame",
                           (True, False))
            if c is not None:
                hechas.append(c)
    if len(hechas) < 2:
        for c in hechas:
            S(lambda: c.Delete())
            RT.hechas.pop()
        RT.planos(m, frame)
log["ensamble"]["verificacion"] = RT.cerrar()
log["ensamble"]["restricciones_detalle"] = RT.hechas
inv._iprop(tdoc, "Design Tracking Properties", "Part Number", f"Gripper {x.nombre}"[:inv.MAX_PART_NUMBER])
tdoc.SaveAs(str(top_path), False)

# =============================================================================== 6) verificación
etapa("Verificación")
mp = S(lambda: tdoc.ComponentDefinition.MassProperties)
log["ensamble"]["masa_kg"] = S(lambda: round(mp.Mass, 2))
b = tcd.RangeBox
log["ensamble"]["envolvente_mm"] = [round((b.MaxPoint.X - b.MinPoint.X) * 10, 1),
                                    round((b.MaxPoint.Y - b.MinPoint.Y) * 10, 1),
                                    round((b.MaxPoint.Z - b.MinPoint.Z) * 10, 1)]
# distancia entre gomas (abierto) vs caja
try:
    gmov = [so for so in inv._items(mods[0].SubOccurrences) if "goma" in so.Name.lower()][0]
    gx_mov = gmov.RangeBox.MinPoint.X * 10
    gx_fij = gf.RangeBox.MaxPoint.X * 10
    log["ensamble"]["luz_entre_gomas_abierto_mm"] = round(gx_mov - gx_fij, 2)
    log["ensamble"]["apertura_sobre_caja_mm"] = round(gx_mov - gx_fij - caja.largo_apriete_mm, 2)
except Exception as exc:  # noqa: BLE001
    log["avisos"].append(f"No pude medir la luz entre gomas: {exc}")
try:
    col = app.TransientObjects.CreateObjectCollection()

    def leaves(occs_):
        for o in inv._items(occs_):
            if S(lambda: o.DefinitionDocumentType) == inv.K_ASSEMBLY_DOCUMENT:
                leaves(o.SubOccurrences)
            else:
                col.Add(o)
    leaves(tcd.Occurrences)
    inter = {}
    for r_ in inv._items(tcd.AnalyzeInterference(col)):
        k = " / ".join(sorted(Path(S(lambda: oc.Definition.Document.FullFileName, "?")).stem
                              for oc in (r_.OccurrenceOne, r_.OccurrenceTwo)))
        v = inter.setdefault(k, [0, 0.0])
        v[0] += 1
        v[1] = round(v[1] + S(lambda: r_.Volume * 1000, 0.0), 2)
    log["ensamble"]["interferencias"] = inter
except Exception as exc:  # noqa: BLE001
    log["avisos"].append(f"Interferencias: {exc}")
# imagen isométrica
try:
    tdoc.Activate()
    v = app.ActiveView
    cam = v.Camera
    cam.ViewOrientationType = 10759          # kIsoTopRightViewOrientation
    cam.Fit()
    cam.Apply()
    img = ENS / f"Gripper_{x.nombre}_iso.png"
    v.SaveAsBitmap(str(img), 1600, 1000)
    log["ensamble"]["imagen"] = str(img)
except Exception as exc:  # noqa: BLE001
    log["avisos"].append(f"Imagen: {exc}")
tdoc.Save()
log["archivos"] = {"ensamble": str(top_path), "modulo": str(mod_path), "chapas": str(CH), "dxf": str(DXF)}
log["tiempo_s"] = round(time.time() - T0, 1)
(BASE / "resultado.json").write_text(json.dumps(log, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
res = dict(log)
res["modulo"] = {k: v for k, v in log["modulo"].items() if k != "restricciones_detalle"}
res["ensamble"] = {k: v for k, v in log["ensamble"].items() if k != "restricciones_detalle"}
res["restricciones_modulo"] = len(log["modulo"].get("restricciones_detalle", []))
res["restricciones_ensamble"] = len(log["ensamble"].get("restricciones_detalle", []))
print(json.dumps(res, ensure_ascii=False, indent=1, default=str))
