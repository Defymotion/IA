"""Planos de fabricación de una reja generada con construir_reja.py.

- PIEZAS (A4, una hoja por pieza): columnas y caños horizontales con su sección ampliada, paneles y hoja del portón
  de frente con cotas de agujeros y detalle de esquina, base de columna con agujeros acotados; lista de cortes
  en cada hoja.
- CONJUNTO (A4): hoja 1 planta acotada (ejes de columnas, aberturas y paso del portón);
  hoja 2 elevación con alturas, isométrica y lista de piezas.

Uso: python planos_reja.py --nombre REJA_CROQUIS
Salida: Generados\\<nombre>\\Ensamble\\Fabricacion\\Planos (+ PDF)
"""
import argparse
import json
import math
import sys
import time
import traceback
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
import inventor_mcp as inv  # noqa: E402
import pythoncom  # noqa: E402

a = argparse.ArgumentParser()
a.add_argument("--nombre", required=True)
a.add_argument("--solo", default="", help="piezas | conjunto (por defecto ambos)")
x = a.parse_args()

S = inv._safe
OUT = Path.home() / "Documents" / "InventorIA" / "Generados" / x.nombre
RES = json.loads((OUT / "resultado.json").read_text(encoding="utf-8"))
ASM = OUT / "Ensamble" / f"{x.nombre}.iam"
PL = OUT / "Ensamble" / "Fabricacion" / "Planos"
PDF = PL / "PDF"
PDF.mkdir(parents=True, exist_ok=True)
log = {"hojas": [], "avisos": [], "errores": []}
T0 = time.time()

COL_A, PANEL_A, PANEL_E, HOJA_A, HOJA_B, HOJA_E = 60.0, 30.0, 2.6, 60.0, 30.0, 2.0
T316 = 4.7625
MAX_CC, D_PORTON, N_PORTON = 1736.0, 860.0, 75.0
ISO = 10759                       # kIsoTopRightViewOrientation
SCALES = (2.0, 1.0, 0.5, 0.2, 0.1, 0.05, 1 / 30, 0.025, 0.02, 0.01)


def etapa(t):
    print(f"[{time.time() - T0:6.1f} s] {t}", flush=True)


def lbl(s):
    return inv._scale_label(s) if s not in (1 / 30, 0.025) else f"1:{round(1 / s)}"


app = inv._inventor(start_if_needed=False)
tg = app.TransientGeometry
P = tg.CreatePoint2d
app.SilentOperation = True
TEMPLATE = app.FileManager.GetTemplateFile(inv.K_DRAWING_DOCUMENT)


def P3(x_mm, y_mm, z_mm):
    return tg.CreatePoint(x_mm / 10, y_mm / 10, z_mm / 10)


# ============================================================================ geometría de vistas
class Vista:
    """Curvas de una vista en coordenadas de hoja + búsqueda por coordenadas de modelo."""

    def __init__(self, view):
        self.v = view
        self.lines, self.circles = [], []
        dc = view.DrawingCurves
        try:
            n = dc.Count
        except Exception:  # noqa: BLE001
            dc = view.DrawingCurves()
            n = dc.Count
        for i in range(1, n + 1):
            c = dc.Item(i)
            cp, sp, ep = S(lambda: c.CenterPoint), S(lambda: c.StartPoint), S(lambda: c.EndPoint)
            if cp is not None:
                if sp is None:
                    self.circles.append({"c": c, "x": cp.X, "y": cp.Y})
                continue
            if sp is None or ep is None:
                continue
            self.lines.append({"c": c, "x1": min(sp.X, ep.X), "x2": max(sp.X, ep.X),
                               "y1": min(sp.Y, ep.Y), "y2": max(sp.Y, ep.Y),
                               "v": abs(sp.X - ep.X) < 1e-5, "h": abs(sp.Y - ep.Y) < 1e-5})

    def hoja(self, xm, ym, zm):
        p = self.v.ModelToSheetSpace(P3(xm, ym, zm))
        return p.X, p.Y

    def linea(self, tipo, coord, rango=None, tol=0.006):
        """Línea vertical ('v', x de hoja) u horizontal ('h', y de hoja) que se superpone con 'rango'."""
        best = None
        for l in self.lines:
            if not l[tipo]:
                continue
            c = l["x1"] if tipo == "v" else l["y1"]
            if abs(c - coord) > tol:
                continue
            lo, hi = (l["y1"], l["y2"]) if tipo == "v" else (l["x1"], l["x2"])
            if rango and (hi < min(rango) - 1e-4 or lo > max(rango) + 1e-4):
                continue
            ln = hi - lo
            if best is None or ln > best[0]:
                best = (ln, l["c"])
        return best and best[1]

    def circulo(self, xs, ys, tol=0.02):
        c = [k for k in self.circles if abs(k["x"] - xs) < tol and abs(k["y"] - ys) < tol]
        return c and c[0]["c"]


class Cotas:
    def __init__(self, sheet):
        self.sheet = sheet
        self.gd = sheet.DrawingDimensions.GeneralDimensions
        self.ok, self.fallidas = 0, []
        self.centro = None            # PointIntentEnum del centro (se descubre la primera vez)

    def _prec(self, d):
        mm = S(lambda: d.ModelValue * 10, 0)
        S(lambda: setattr(d, "Precision", 0 if abs(mm - round(mm)) < 1e-3 else 1))
        return mm

    def lineal(self, nombre, c1, c2, tx, ty, tipo=None, esperado=None):
        if c1 is None or c2 is None:
            self.fallidas.append(f"{nombre}: curva no encontrada")
            return None
        try:
            i1 = c1 if S(lambda: c1.CurveType) is None else self.sheet.CreateGeometryIntent(c1)
            i2 = c2 if S(lambda: c2.CurveType) is None else self.sheet.CreateGeometryIntent(c2)
            d = self.gd.AddLinear(P(tx, ty), i1, i2) if tipo is None else self.gd.AddLinear(P(tx, ty), i1, i2, tipo)
            mm = self._prec(d)
            if esperado is not None and abs(mm - esperado) > 0.6:
                self.fallidas.append(f"{nombre}: dio {mm:.1f}, esperado {esperado:.1f}")
                S(lambda: d.Delete())
                return None
            self.ok += 1
            return d
        except Exception as exc:  # noqa: BLE001
            self.fallidas.append(f"{nombre}: {exc}")
            return None

    def centro_de(self, circ):
        """GeometryIntent al centro de un círculo: el intent del círculo sin punto acota al centro."""
        gi = S(lambda: self.sheet.CreateGeometryIntent(circ))
        return [(None, gi)] if gi is not None else []

    def a_centro(self, nombre, circ, linea, tx, ty, esperado, tipo=None):
        """Cota de una línea al centro de un agujero, verificando el valor."""
        if circ is None or linea is None:
            self.fallidas.append(f"{nombre}: curva no encontrada")
            return None
        li = self.sheet.CreateGeometryIntent(linea)
        for k, gi in self.centro_de(circ):
            try:
                d = self.gd.AddLinear(P(tx, ty), gi, li) if tipo is None else self.gd.AddLinear(P(tx, ty), gi, li, tipo)
            except Exception:  # noqa: BLE001
                continue
            mm = self._prec(d)
            if abs(mm - esperado) < 0.3:
                self.centro = k
                self.ok += 1
                return d
            S(lambda: d.Delete())
        self.fallidas.append(f"{nombre}: no se pudo acotar al centro")
        return None

    def diametro(self, nombre, circ, tx, ty):
        if circ is None:
            self.fallidas.append(f"{nombre}: círculo no encontrado")
            return None
        try:
            d = self.gd.AddDiameter(P(tx, ty), self.sheet.CreateGeometryIntent(circ))
            self._prec(d)
            self.ok += 1
            return d
        except Exception as exc:  # noqa: BLE001
            self.fallidas.append(f"{nombre}: {exc}")
            return None


def nota(sheet, xs, ys, texto):
    return S(lambda: sheet.DrawingNotes.GeneralNotes.AddFitted(P(xs, ys), texto))


def sin_rotulo(v):
    S(lambda: setattr(v, "ShowLabel", False))


def rotulo(sheet, v, texto, arriba=0.5):
    sin_rotulo(v)
    nota(sheet, v.Center.X - v.Width / 2, v.Center.Y + v.Height / 2 + arriba, f"<StyleOverride Bold='True'>{texto}</StyleOverride>")


def vista_base(sheet, doc, xs, ys, sc, orient):
    v = sheet.DrawingViews.AddBaseView(doc, P(xs, ys), sc, orient, inv.K_STYLE_HLR)
    sin_rotulo(v)
    return v


def iso(sheet, doc, xs, ys, sc):
    v = sheet.DrawingViews.AddBaseView(doc, P(xs, ys), sc, ISO, inv.K_STYLE_HLR)
    sin_rotulo(v)
    return v


def detalle(sheet, parent, pos, centro, radio, sc, label):
    views = sheet.DrawingViews
    intentos = (
        lambda: views.AddDetailView(parent, P(*pos), inv.K_STYLE_FROM_BASE, True, P(*centro), radio,
                                    pythoncom.Missing, sc, False, label),
        lambda: views.AddDetailView(parent, P(*pos), inv.K_STYLE_FROM_BASE, True, P(*centro), radio,
                                    pythoncom.Missing, sc),
        lambda: views.AddDetailView(parent, P(*pos), inv.K_STYLE_FROM_BASE, True, P(*centro),
                                    P(centro[0] + radio, centro[1])),
    )
    err = None
    for f in intentos:
        try:
            v = f()
            S(lambda: setattr(v, "ScaleFromBase", False))
            S(lambda: setattr(v, "Scale", sc))
            S(lambda: setattr(v, "Position", P(*pos)))
            return v
        except Exception as exc:  # noqa: BLE001
            err = exc
    raise RuntimeError(f"Vista de detalle: {err}")


def zona(sheet):
    """Área útil (cm): márgenes del borde y cajetín abajo a la derecha."""
    W, H = sheet.Width, sheet.Height
    tb = S(lambda: sheet.TitleBlock.RangeBox)
    tb_top = tb.MaxPoint.Y if tb else 5.0
    tb_left = tb.MinPoint.X if tb else W - 12
    return W, H, tb_top, tb_left


def elegir_escala(ancho_mm, alto_mm, ancho_cm, alto_cm, escalas=SCALES):
    for s in escalas:
        if ancho_mm * s / 10 <= ancho_cm and alto_mm * s / 10 <= alto_cm:
            return s
    return escalas[-1]


# ============================================================================ hojas de piezas
LINEA = 0.58         # alto de renglón de las notas (cm)
NOTAS_X = 12.6       # notas de pieza: columna derecha, sobre el cajetín


def rotulo_xy(sheet, xs, ys, texto):
    nota(sheet, xs, ys, f"<StyleOverride Bold='True'>{texto}</StyleOverride>")


def notas_pieza(sheet, lineas, x=NOTAS_X):
    """Bloque de notas a la derecha, apoyado sobre el cajetín (renglones de hasta ~58 caracteres).
    Devuelve la altura de su borde superior."""
    tb_top = zona(sheet)[2]
    top = tb_top + 0.4 + LINEA * len(lineas)
    nota(sheet, x, top, "<Br/>".join(lineas))
    return top


def masa(doc):
    return S(lambda: round(doc.ComponentDefinition.MassProperties.Mass, 2))


def hoja_cano(sheet, doc, qty, nombre, largo, a_, e_, uso):
    W, H, tb_top, tb_left = zona(sheet)
    notas_pieza(sheet, [
        f"<StyleOverride Bold='True'>PIEZA: {nombre}  —  CANTIDAD: {qty}</StyleOverride>",
        f"CAÑO estructural {a_:g}x{a_:g}x{e_:g} mm, acero SAE 1010",
        f"CORTE: {qty} x {largo:g} mm, a 90°, sin rebabas",
        uso,
        f"MASA: {masa(doc)} kg c/u  —  medidas en mm",
    ])
    x_ini, x_fin, yc = 6.0, W - 1.6, H - 5.0
    sc = elegir_escala(largo, a_, x_fin - x_ini, 5)
    v = vista_base(sheet, doc, x_ini + largo * sc / 20, yc, sc, inv.K_VIEW_RIGHT)   # eje del caño horizontal
    sheet.Update()
    V = Vista(v)
    xa, _ = V.hoja(0, 0, 0)
    xb, _ = V.hoja(0, 0, largo)
    yt, yb_ = V.hoja(0, a_ / 2, 0)[1], V.hoja(0, -a_ / 2, 0)[1]
    ct = Cotas(sheet)
    ct.lineal("largo", V.linea("v", xa, (yt, yb_)), V.linea("v", xb, (yt, yb_)), (xa + xb) / 2, min(yt, yb_) - 1.0,
              esperado=largo)
    rotulo_xy(sheet, min(xa, xb), max(yt, yb_) + 1.0, f"VISTA LATERAL  ({lbl(sc)})")
    # vista de punta ampliada, alineada a la izquierda
    ss = 0.5 if a_ <= 80 else 0.2
    s_ = sheet.DrawingViews.AddProjectedView(v, P(3.0, yc), inv.K_STYLE_FROM_BASE)
    S(lambda: setattr(s_, "ScaleFromBase", False))
    S(lambda: setattr(s_, "Scale", ss))
    S(lambda: setattr(s_, "Position", P(3.0, yc)))
    sin_rotulo(s_)
    sheet.Update()
    Vs = Vista(s_)
    xl, yl = Vs.hoja(-a_ / 2, -a_ / 2, 0)
    xr, yr = Vs.hoja(a_ / 2, a_ / 2, 0)
    x0, x1, y0, y1 = min(xl, xr), max(xl, xr), min(yl, yr), max(yl, yr)
    ct.lineal("punta ancho", Vs.linea("v", x0), Vs.linea("v", x1), (x0 + x1) / 2, y0 - 0.9, esperado=a_)
    ct.lineal("punta alto", Vs.linea("h", y0), Vs.linea("h", y1), x1 + 0.7, (y0 + y1) / 2, esperado=a_)
    ei = e_ * ss / 10
    ct.lineal("espesor", Vs.linea("v", x0, tol=0.004), Vs.linea("v", x0 + ei, tol=0.004), x0 - 0.3, y1 + 0.8,
              esperado=e_)
    rotulo_xy(sheet, 1.5, y1 + 2.2, f"PUNTA  ({lbl(ss)})")
    iso(sheet, doc, 6.5, 6.5, sc / 2 if sc >= 0.1 else sc)
    return {"escala": lbl(sc), "cotas": ct.ok, "fallidas": ct.fallidas}


def hoja_marco(sheet, doc, qty, nombre, Wm, Hm, a_, b_, e_, agujeros, travesanos, uso):
    W, H, tb_top, tb_left = zona(sheet)
    izq = sorted([h for h in agujeros if h[0] < Wm / 2], key=lambda h: h[1])
    lineas = [
        f"<StyleOverride Bold='True'>PIEZA: {nombre}  —  CANTIDAD: {qty}</StyleOverride>",
        (f"MARCO SOLDADO sin malla, caño {a_:g}x{b_:g}x{e_:g} SAE 1010" if a_ == b_ else
         f"MARCO SOLDADO, caño {a_:g}x{b_:g}x{e_:g} SAE 1010 (cara {a_:g} en el plano)"),
        f"CORTES: {2} x {Hm:g} (montantes), {2 + len(travesanos)} x {Wm - 2 * a_:g} (largueros)",
    ]
    if agujeros:
        lineas.append(f"AGUJEROS: {len(agujeros)} x Ø{agujeros[0][2]:g} pasantes (fijación a columna)")
    if travesanos:
        lineas.append(f"TRAVESAÑO: eje a {travesanos[0]:g} mm del borde inferior")
    lineas += ([uso] if uso else []) + ["SOLDADURA: filete continuo, escuadrado; amolar y pintar.",
               f"MASA: {masa(doc)} kg c/u  —  medidas en mm"]
    top_notas = notas_pieza(sheet, lineas)
    x_ini, y_max = 3.6, H - (2.8 if agujeros else 2.4)
    x_lim = W - 9.0 if agujeros else W - 2.0
    sc = SCALES[-1]
    for s_ in SCALES:
        w_, h_ = Wm * s_ / 10, Hm * s_ / 10
        piso = (top_notas + 1.3) if x_ini + w_ > NOTAS_X - 0.4 else 2.8
        if x_ini + w_ <= x_lim and y_max - h_ >= piso:
            sc = s_
            break
    v = vista_base(sheet, doc, x_ini + Wm * sc / 20, y_max - Hm * sc / 20, sc, inv.K_VIEW_FRONT)
    sheet.Update()
    V = Vista(v)
    ct = Cotas(sheet)
    (x0, y0), (x1, y1) = V.hoja(0, 0, 0), V.hoja(Wm, Hm, 0)
    x0, x1, y0, y1 = min(x0, x1), max(x0, x1), min(y0, y1), max(y0, y1)
    ct.lineal("ancho", V.linea("v", x0), V.linea("v", x1), (x0 + x1) / 2, y0 - 1.0, esperado=Wm)
    ct.lineal("alto", V.linea("h", y0), V.linea("h", y1), x0 - 1.8, (y0 + y1) / 2, esperado=Hm)
    for t in travesanos:
        yt0 = V.hoja(Wm / 2, t - a_ / 2, 0)[1]
        ct.lineal("travesaño", V.linea("h", y0), V.linea("h", yt0, (x0, x1)), x1 + 0.8, (y0 + yt0) / 2,
                  esperado=t - a_ / 2)
    rotulo_xy(sheet, x1 - 4.0, y1 + 0.9, f"FRENTE  ({lbl(sc)})")
    det = None
    if izq:
        circ = [V.circulo(*V.hoja(hx, hy, 0)) for hx, hy, d in izq]
        if len(circ) >= 2 and all(circ):
            ys0 = V.hoja(0, izq[0][1], 0)[1]
            ys1 = V.hoja(0, izq[-1][1], 0)[1]
            ct.a_centro("agujero inferior", circ[0], V.linea("h", y0), x0 - 0.8, (y0 + ys0) / 2, izq[0][1])
            g0, g1 = ct.centro_de(circ[0]), ct.centro_de(circ[-1])
            if g0 and g1:
                ct.lineal("entre agujeros", g0[0][1], g1[0][1], x0 - 0.8, (ys0 + ys1) / 2,
                          esperado=izq[-1][1] - izq[0][1])
        # detalle de la esquina superior izquierda
        hx, hy, d = izq[-1]
        R = max(Hm - hy, hx) + 40
        cen = V.hoja(hx + 15, hy + (Hm - hy) / 2 - 5, 0)
        ds = 0.2 if 2 * R * 0.2 / 10 <= 7 else 0.1
        det = detalle(sheet, v, (W - 5.0, H - 7.0), cen, R * sc / 10, ds, "A")
        sheet.Update()
        D = Vista(det)
        dx0, dy_top = D.hoja(0, Hm, 0)
        dxa = D.hoja(a_, Hm, 0)[0]
        hs = D.hoja(hx, hy, 0)
        cc = D.circulo(*hs, tol=0.05)
        rango_y = (D.hoja(0, Hm - 2 * R, 0)[1], dy_top)
        lv = D.linea("v", dx0, rango_y, tol=0.01)
        lh = D.linea("h", dy_top, (dx0, dxa + 2), tol=0.01)
        ct.diametro("Ø agujero", cc, hs[0] + 1.8, hs[1] - 1.0)
        ct.a_centro("agujero desde arriba", cc, lh, dx0 - 0.9, (hs[1] + dy_top) / 2, Hm - hy)
        ct.lineal("caño", lv, D.linea("v", dxa, rango_y, tol=0.01), (dx0 + dxa) / 2, hs[1] - 1.6, esperado=a_)
        ct.a_centro("agujero desde el borde", cc, lv, (hs[0] + dx0) / 2, dy_top + 0.7, hx)
    if x1 < 13:                     # vista angosta: isométrica a su derecha
        iso(sheet, doc, (x1 + 1.5 + (W - 9.5 if izq else W - 1.5)) / 2, (y0 + y1) / 2, sc / 2)
    else:                           # vista ancha: isométrica debajo, a la izquierda
        iso(sheet, doc, 6.5, (y0 - 1.6 + 1.5) / 2, sc / 2)
    return {"escala": lbl(sc), "detalle": det is not None, "cotas": ct.ok, "fallidas": ct.fallidas}


def hoja_base(sheet, doc, qty, lado, d, c, r, t):
    W, H, tb_top, tb_left = zona(sheet)
    notas_pieza(sheet, [
        f"<StyleOverride Bold='True'>PIEZA: Base de columna  —  CANTIDAD: {qty}</StyleOverride>",
        f"CHAPA {lado:g} x {lado:g} x 3/16\" ({t:.2f} mm) SAE 1010",
        "LÁSER: Corte_laser\\Base columna.dxf (1:1)",
        f"4 agujeros Ø{d:g} (anclaje M10 al piso) — esquinas R{r:g}",
        "Soldar centrada al pie de la columna.",
    ], x=14.8)
    sc = 0.5
    v = vista_base(sheet, doc, 9.3, 13.6, sc, inv.K_VIEW_FRONT)
    sheet.Update()
    V = Vista(v)
    ct = Cotas(sheet)
    xs_ = sorted(l["x1"] for l in V.lines if l["v"])
    ys_ = sorted(l["y1"] for l in V.lines if l["h"])
    x0, x1, y0, y1 = xs_[0], xs_[-1], ys_[0], ys_[-1]
    circ = V.circles
    if circ:
        k0 = min(circ, key=lambda k: (k["x"] + k["y"]))
        k_der = max([k for k in circ if abs(k["y"] - k0["y"]) < 0.05], key=lambda k: k["x"])
        k_arr = max([k for k in circ if abs(k["x"] - k0["x"]) < 0.05], key=lambda k: k["y"])
        e_ = (lado - c) / 2
        ct.a_centro("borde-agujero x", k0["c"], V.linea("v", x0), (x0 + k0["x"]) / 2, y0 - 0.8, e_)
        ct.a_centro("borde-agujero y", k0["c"], V.linea("h", y0), x0 - 0.8, (y0 + k0["y"]) / 2, e_)
        g0 = ct.centro_de(k0["c"])
        for kk, nm in ((k_der, "x"), (k_arr, "y")):
            g1 = ct.centro_de(kk["c"])
            if g0 and g1:
                tx = (k0["x"] + kk["x"]) / 2 if nm == "x" else x0 - 1.6
                ty = y0 - 1.6 if nm == "x" else (k0["y"] + kk["y"]) / 2
                ct.lineal(f"entre agujeros {nm}", g0[0][1], g1[0][1], tx, ty, esperado=c)
        ct.diametro("Ø agujero", k_arr["c"], k_arr["x"] + 1.6, k_arr["y"] - 1.4)
    ct.lineal("lado x", V.linea("v", x0), V.linea("v", x1), (x0 + x1) / 2, y0 - 2.4, esperado=lado)
    ct.lineal("lado y", V.linea("h", y0), V.linea("h", y1), x0 - 2.4, (y0 + y1) / 2, esperado=lado)
    rotulo_xy(sheet, x0, y1 + 1.0, f"CHAPA BASE  ({lbl(sc)})")
    # vista lateral para el espesor
    lat = sheet.DrawingViews.AddProjectedView(v, P(x1 + 2.5, (y0 + y1) / 2), inv.K_STYLE_FROM_BASE)
    sin_rotulo(lat)
    sheet.Update()
    L_ = Vista(lat)
    lv_ = sorted([l for l in L_.lines if l["v"]], key=lambda l: l["x1"])
    if len(lv_) >= 2:
        ct.lineal("espesor", lv_[0]["c"], lv_[-1]["c"], lv_[-1]["x1"] + 0.6, y1 + 0.7, esperado=t)
    iso(sheet, doc, 22.5, 14.0, 0.25)
    return {"escala": lbl(sc), "cotas": ct.ok, "fallidas": ct.fallidas}



# ============================================================================ conjuntos soldados (columna + base)
def _stem_occ(o):
    return Path(S(lambda: o.Definition.Document.FullFileName, "") or "").stem


def crear_soldado(asm, tubo_stem, nombre):
    """Subensamble soldado: el caño de columna + su base (+ chapa de refuerzo de la muestra si la tiene),
    con las mismas posiciones que en el ensamble general."""
    occs = list(inv._items(asm.ComponentDefinition.Occurrences))
    tubo = next(o for o in occs if _stem_occ(o) == tubo_stem)
    t0 = tubo.Transformation.Translation

    def dist(o):
        b = o.RangeBox
        cx, cz = (b.MinPoint.X + b.MaxPoint.X) / 2, (b.MinPoint.Z + b.MaxPoint.Z) / 2
        return math.hypot(cx - t0.X, cz - t0.Z) * 10
    extras = [min([o for o in occs if _stem_occ(o) == "Base columna"], key=dist)]
    extras += [o for o in occs if _stem_occ(o).lower().startswith("chapa 05") and dist(o) < 300]
    path = EST / f"{nombre}.iam"
    for d in inv._items(app.Documents):
        if S(lambda: Path(d.FullFileName).resolve() == path.resolve(), False):
            S(lambda: d.Close(True))
    if path.exists():
        path.unlink()
    sd = app.Documents.Add(inv.K_ASSEMBLY_DOCUMENT, app.FileManager.GetTemplateFile(inv.K_ASSEMBLY_DOCUMENT), True)
    cd = sd.ComponentDefinition
    for o in [tubo] + extras:
        n_ = cd.Occurrences.Add(o.Definition.Document.FullFileName, o.Transformation)
        S(lambda: setattr(n_, "Grounded", True))
    sd.Update()
    inv._iprop(sd, "Design Tracking Properties", "Part Number", nombre[:inv.MAX_PART_NUMBER])
    inv._iprop(sd, "Design Tracking Properties", "Description", f"CONJUNTO SOLDADO {nombre}".upper())
    sd.SaveAs(str(path), False)
    return sd, len(extras)


def _caja(cd_occ):
    b = cd_occ.RangeBox
    return [b.MinPoint.X * 10, b.MinPoint.Y * 10, b.MinPoint.Z * 10, b.MaxPoint.X * 10, b.MaxPoint.Y * 10,
            b.MaxPoint.Z * 10]


def hoja_soldado(sheet, sd, qty, nombre, largo):
    W, H, tb_top, tb_left = zona(sheet)
    occs = list(inv._items(sd.ComponentDefinition.Occurrences))
    tubo = next(o for o in occs if "columna" in _stem_occ(o).lower())
    base = next(o for o in occs if _stem_occ(o) == "Base columna")
    refuerzo = [o for o in occs if _stem_occ(o).lower().startswith("chapa 05")]
    tb, bb = _caja(tubo), _caja(base)
    cx, cz = (tb[0] + tb[3]) / 2, (tb[2] + tb[5]) / 2
    off = [tb[0] - bb[0], bb[3] - tb[3], tb[2] - bb[2], bb[5] - tb[5]]
    centrado = max(off) - min(off) < 0.5
    lineas = [
        f"<StyleOverride Bold='True'>CONJUNTO SOLDADO: {nombre}</StyleOverride>",
        f"<StyleOverride Bold='True'>CANTIDAD: {qty}</StyleOverride>",
        f"1 x {'Columna porton 60x60x2 L2200' if '2200' in nombre else 'Columna 60x60x2 L1900'}",
        "1 x Base columna 180x180x3/16\"" + (" + chapa refuerzo" if refuerzo else ""),
        ("Caño centrado en la base (60 a cada borde)." if centrado else
         "Caño desplazado en la base: ver planta."),
        "SOLDADURA caño-base: filete a = 3 mm",
        "   todo alrededor (4 caras).",
    ]
    if refuerzo:
        lineas.append("Chapa de refuerzo: filete a3 a caño y base.")
    lineas += ["Electrodo E6013 o MIG ER70S-6.",
               "Puntear, escuadrar a 90° y completar.",
               "Limpiar, amolar salpicaduras y pintar."]
    nota(sheet, 1.5, 1.5 + LINEA * len(lineas), "<Br/>".join(lineas))
    ct = Cotas(sheet)
    # elevación completa
    alto = tb[4] - bb[1]
    sc = elegir_escala(180, alto, 6, H - 2.6 - (1.5 + LINEA * len(lineas) + 0.6), (0.1, 0.05, 0.04, 1 / 30, 0.025))
    ev = vista_base(sheet, sd, 4.2, H - 2.6 - alto * sc / 20, sc, inv.K_VIEW_FRONT)
    sheet.Update()
    V = Vista(ev)
    xb0, _ = V.hoja(bb[0], 0, cz)
    xb1, _ = V.hoja(bb[3], 0, cz)
    y_piso = V.hoja(cx, bb[1], cz)[1]
    y_top = V.hoja(cx, tb[4], cz)[1]
    xt0, xt1 = V.hoja(tb[0], 0, cz)[0], V.hoja(tb[3], 0, cz)[0]
    ct.lineal("alto total", V.linea("h", y_piso, (xb0, xb1)), V.linea("h", y_top, (xt0, xt1)), min(xb0, xb1) - 0.8,
              (y_piso + y_top) / 2, esperado=alto)
    rotulo_xy(sheet, 1.6, y_top + 1.2, f"ELEVACIÓN ({lbl(sc)})")
    # detalle del pie
    R_ = 115.0
    cen = V.hoja(cx, bb[1] + 40, cz)
    ds = 0.5
    det = detalle(sheet, ev, (14.0, H - 3.4 - R_ * ds / 10), cen, R_ * sc / 10, ds, "B")
    sheet.Update()
    D = Vista(det)
    piso_det = 1.5 + LINEA * len(lineas) + 2.4
    delta = piso_det - D.hoja(cx, bb[1], cz)[1]
    if delta > 0:
        S(lambda: setattr(det, "Position", P(det.Center.X, det.Center.Y + delta)))
        sheet.Update()
        D = Vista(det)
    sin_rotulo(det)
    rotulo_xy(sheet, det.Center.X - det.Width / 2, min(det.Center.Y + det.Height / 2 + 0.6, H - 1.4),
              f"DETALLE DEL PIE — UNIÓN SOLDADA ({lbl(ds)})")
    dxb0, dxb1 = D.hoja(bb[0], 0, cz)[0], D.hoja(bb[3], 0, cz)[0]
    dxt0, dxt1 = D.hoja(tb[0], 0, cz)[0], D.hoja(tb[3], 0, cz)[0]
    dyp, dyb = D.hoja(cx, bb[1], cz)[1], D.hoja(cx, bb[4], cz)[1]
    lb0 = D.linea("v", dxb0, (dyp, dyb), tol=0.01)
    lb1 = D.linea("v", dxb1, (dyp, dyb), tol=0.01)
    lt0 = D.linea("v", dxt0, (dyb, dyb + 3), tol=0.01)
    lt1 = D.linea("v", dxt1, (dyb, dyb + 3), tol=0.01)
    ct.lineal("base", lb0, lb1, (dxb0 + dxb1) / 2, dyp - 1.6, esperado=bb[3] - bb[0])
    ct.lineal("borde-caño", lb0, lt0, (dxb0 + dxt0) / 2, dyp - 0.8, esperado=abs(tb[0] - bb[0]))
    ct.lineal("caño", lt0, lt1, (dxt0 + dxt1) / 2, dyb + 3.2, esperado=tb[3] - tb[0])
    ct.lineal("espesor base", D.linea("h", dyp, (dxb0, dxb1), tol=0.01), D.linea("h", dyb, (dxb0, dxt0), tol=0.01),
              max(dxb0, dxb1) + 0.8, (dyp + dyb) / 2, esperado=bb[4] - bb[1])
    # llamadas de soldadura a ambos lados del caño
    try:
        for xw, sgn in ((dxt0, -1), (dxt1, 1)):
            pts = app.TransientObjects.CreateObjectCollection()
            pts.Add(P(xw + sgn * 2.2, dyb + 3.8))
            pts.Add(P(xw + sgn * 0.08, dyb + 0.08))
            sheet.DrawingNotes.LeaderNotes.Add(pts, "FILETE a3<Br/>TODO ALREDEDOR")
    except Exception as exc:  # noqa: BLE001
        ct.fallidas.append(f"llamada de soldadura: {exc}")
    # planta 1:5: caño centrado en la base
    pv = vista_base(sheet, sd, W - 3.9, H - 6.0, 0.2, inv.K_VIEW_TOP)
    sheet.Update()
    Pv = Vista(pv)
    px0, px1 = Pv.hoja(bb[0], 0, cz)[0], Pv.hoja(bb[3], 0, cz)[0]
    ptx0 = Pv.hoja(tb[0], 0, cz)[0]
    pz0, pz1 = Pv.hoja(cx, 0, bb[2])[1], Pv.hoja(cx, 0, bb[5])[1]
    ptz0 = Pv.hoja(cx, 0, tb[2])[1]
    lo, hi = min(pz0, pz1), max(pz0, pz1)
    ct.lineal("planta base x", Pv.linea("v", px0, (lo, hi), tol=0.01), Pv.linea("v", px1, (lo, hi), tol=0.01),
              (px0 + px1) / 2, lo - 1.4, esperado=bb[3] - bb[0])
    ct.lineal("planta borde-caño x", Pv.linea("v", px0, (lo, hi), tol=0.01),
              Pv.linea("v", ptx0, None, tol=0.01), (px0 + ptx0) / 2, lo - 0.7, esperado=abs(tb[0] - bb[0]))
    lz = Pv.linea("h", pz0, (min(px0, px1), max(px0, px1)), tol=0.01)
    ct.lineal("planta borde-caño z", lz, Pv.linea("h", ptz0, None, tol=0.01),
              min(px0, px1) - 0.7, (pz0 + ptz0) / 2, esperado=abs(tb[2] - bb[2]))
    rotulo_xy(sheet, min(px0, px1), hi + 1.0, "PLANTA (1:5)")
    return {"escala": lbl(sc), "cotas": ct.ok, "fallidas": ct.fallidas}


# ============================================================================ conjunto
def columnas_diseno():
    dis = RES["diseno"]
    gate_col = tuple(RES.get("porton_columna_xy") or (1e9, 1e9))
    cols = []
    for p1, p2 in dis["tramos"]:
        ln = math.dist(p1, p2)
        n = max(1, math.ceil(ln / MAX_CC - 1e-9))
        for i in range(n + 1):
            pt = (p1[0] + (p2[0] - p1[0]) * i / n, p1[1] + (p2[1] - p1[1]) * i / n)
            if math.dist(pt, gate_col) > 1 and all(math.dist(pt, q) > 1 for q in cols):
                cols.append(pt)
    gate_normal = None
    if gate_col[0] < 1e8:
        gate_normal = min(cols, key=lambda q: abs(math.dist(q, gate_col) - math.hypot(D_PORTON, N_PORTON)))
    return cols, gate_col if gate_col[0] < 1e8 else None, gate_normal


def hoja_planta(sheet, asm):
    W, H, tb_top, tb_left = zona(sheet)
    cols, gcol, gnor = columnas_diseno()
    todas = cols + ([gcol] if gcol else [])
    xs = [p[0] for p in todas]
    ys = [p[1] for p in todas]
    ext_x, ext_y = max(xs) - min(xs) + 400, max(ys) - min(ys) + 400
    ax_x, ax_y = ext_x - 400, ext_y - 400
    alto_disp = H - 1.4 - 1.6 - (tb_top + 0.2) - 2.6            # rótulo arriba, cotas arriba y abajo
    sc = elegir_escala(ax_x + 500, ax_y, 14.0, alto_disp, (0.05, 1 / 30, 0.025, 0.02, 0.01, 0.005))
    cy_v = tb_top + 0.2 + 2.6 + ax_y * sc / 20
    v = vista_base(sheet, asm, 2.8 + (ax_x + 200) * sc / 20, cy_v, sc, inv.K_VIEW_TOP)
    sheet.Update()
    V = Vista(v)

    def hp(px, py, z=0.0):            # diseño (Z arriba) -> hoja
        return V.hoja(px, z, -py)
    # ¿la vista superior muestra el diseño con Y hacia arriba? (si no, se espeja el criterio)
    sx = 1 if hp(1000, 0)[0] > hp(0, 0)[0] else -1
    sy = 1 if hp(0, 1000)[1] > hp(0, 0)[1] else -1
    ct = Cotas(sheet)
    h = COL_A / 2
    bx0, by0 = hp(min(xs), min(ys))
    bx1, by1 = hp(max(xs), max(ys))
    vx0, vx1, vy0, vy1 = min(bx0, bx1), max(bx0, bx1), min(by0, by1), max(by0, by1)
    cx_m, cy_m = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2

    def cara(p, eje):
        """Línea de la cara 'izquierda' (eje x) o 'inferior' (eje y) de la columna en p (en diseño)."""
        if eje == "x":
            xsht, _ = hp(p[0] - h, p[1])
            r = (hp(p[0], p[1] - h)[1], hp(p[0], p[1] + h)[1])
            return V.linea("v", xsht, r)
        _, ysht = hp(p[0], p[1] - h)
        r = (hp(p[0] - h, p[1])[0], hp(p[0] + h, p[1])[0])
        return V.linea("h", ysht, r)

    # cadenas: columnas alineadas en una fila (misma y) o en una columna (misma x)
    usadas = 0
    for eje in ("x", "y"):
        k = 1 if eje == "x" else 0           # filas: misma y -> se acotan distancias en x
        grupos = {}
        for p in todas:
            grupos.setdefault(round(p[k], 0), []).append(p)
        for key, g in grupos.items():
            if len(g) < 2:
                continue
            g.sort(key=lambda p: p[1 - k])
            fuera = (key < (cy_m if eje == "x" else cx_m))
            nivel = 1.0
            for p, q in zip(g, g[1:]):
                dd = abs(q[1 - k] - p[1 - k])
                if eje == "x":
                    yy = (vy0 if (fuera == (sy > 0)) else vy1) + (-nivel if fuera == (sy > 0) else nivel)
                    tx = (hp(p[0], 0)[0] + hp(q[0], 0)[0]) / 2
                    ct.lineal(f"x {p}->{q}", cara(p, "x"), cara(q, "x"), tx, yy, esperado=dd)
                else:
                    xx = (vx0 if (fuera == (sx > 0)) else vx1) + (-nivel if fuera == (sx > 0) else nivel)
                    ty = (hp(0, p[1])[1] + hp(0, q[1])[1]) / 2
                    ct.lineal(f"y {p}->{q}", cara(p, "y"), cara(q, "y"), xx, ty, esperado=dd)
                usadas += 1
    # totales entre ejes extremos
    pxmin, pxmax = min(todas, key=lambda p: p[0]), max(todas, key=lambda p: p[0])
    pymin, pymax = min(todas, key=lambda p: p[1]), max(todas, key=lambda p: p[1])
    ct.lineal("total x", cara(pxmin, "x"), cara(pxmax, "x"), (vx0 + vx1) / 2, vy0 - 1.9 if sy > 0 else vy1 + 1.9,
              esperado=pxmax[0] - pxmin[0])
    ct.lineal("total y", cara(pymin, "y"), cara(pymax, "y"), vx1 + 1.9 if sx > 0 else vx0 - 1.9, (vy0 + vy1) / 2,
              esperado=pymax[1] - pymin[1])
    # paso libre del portón (entre caras de columnas)
    if gcol and gnor:
        d = (gcol[0] - gnor[0], gcol[1] - gnor[1])
        if abs(d[1]) > abs(d[0]):          # portón en un lado vertical
            s_ = 1 if d[1] > 0 else -1
            ya = hp(gnor[0], gnor[1] + s_ * h)[1]
            yb = hp(gcol[0], gcol[1] - s_ * h)[1]
            l1 = V.linea("h", ya, (hp(gnor[0] - h, 0)[0], hp(gnor[0] + h, 0)[0]))
            l2 = V.linea("h", yb, (hp(gcol[0] - h, 0)[0], hp(gcol[0] + h, 0)[0]))
            xl = hp(min(gnor[0], gcol[0]), 0)[0]
            ct.lineal("paso portón", l1, l2, xl + (1.3 if xl - vx0 < 1 else -1.3), (ya + yb) / 2,
                      esperado=abs(d[1]) - COL_A)
            npos = (xl + 1.9, (ya + yb) / 2 + 0.6)
        else:
            s_ = 1 if d[0] > 0 else -1
            xa_ = hp(gnor[0] + s_ * h, gnor[1])[0]
            xb_ = hp(gcol[0] - s_ * h, gcol[1])[0]
            l1 = V.linea("v", xa_, (hp(0, gnor[1] - h)[1], hp(0, gnor[1] + h)[1]))
            l2 = V.linea("v", xb_, (hp(0, gcol[1] - h)[1], hp(0, gcol[1] + h)[1]))
            yl = hp(0, min(gnor[1], gcol[1]))[1]
            ct.lineal("paso portón", l1, l2, (xa_ + xb_) / 2, yl + 1.3, esperado=abs(d[0]) - COL_A)
            npos = ((xa_ + xb_) / 2 - 1.5, yl + 2.4)
        nota(sheet, npos[0], npos[1], "PORTÓN CORREDIZO<Br/>paso libre 800<Br/>hoja 1250x2080")
    # aberturas sin reja: extremos de tramos que no se continúan
    ends = {}
    for p1, p2 in RES["diseno"]["tramos"]:
        for p in (tuple(p1), tuple(p2)):
            ends[p] = ends.get(p, 0) + 1
    tramos_ = [(tuple(p1), tuple(p2)) for p1, p2 in RES["diseno"]["tramos"]]

    def en_tramo(m):
        for p1, p2 in tramos_:
            L2 = math.dist(p1, p2) ** 2
            t = max(0, min(1, ((m[0] - p1[0]) * (p2[0] - p1[0]) + (m[1] - p1[1]) * (p2[1] - p1[1])) / L2))
            if math.dist(m, (p1[0] + t * (p2[0] - p1[0]), p1[1] + t * (p2[1] - p1[1]))) < 1:
                return True
        return False
    libres = [p for p, n in ends.items() if n == 1 and (not gcol or math.dist(p, gcol) > 1)
              and (not gnor or math.dist(p, gnor) > 1)]
    cxs, cys = hp(cx_m, cy_m)
    for p in libres:
        for q in libres:
            if p < q and (abs(p[0] - q[0]) < 1 or abs(p[1] - q[1]) < 1) and not en_tramo(((p[0] + q[0]) / 2, (p[1] + q[1]) / 2)):
                mx, my = hp((p[0] + q[0]) / 2, (p[1] + q[1]) / 2)
                dx_, dy_ = cxs - mx, cys - my
                if abs(p[0] - q[0]) < 1:          # abertura en un lado vertical
                    tx, ty = (mx + 0.7, my + 0.5) if dx_ > 0 else (mx - 3.9, my + 0.5)
                else:
                    tx, ty = (mx - 1.6, my + 1.1) if dy_ > 0 else (mx - 1.6, my - 0.5)
                nota(sheet, tx, ty, f"ABIERTO {math.dist(p, q):.0f}<Br/>(sin reja)")
    rotulo(sheet, v, f"PLANTA — ejes de columnas  ({lbl(sc)})", arriba=2.6)
    dis = RES["diseno"]
    lineas = ["<StyleOverride Bold='True'>NOTAS</StyleOverride>",
              "1. Cotas entre ejes de columnas (mm).",
              f"2. Columnas caño {COL_A:g}x{COL_A:g}x2 L{dis['alto']:g}",
              "    sobre base 180x180x3/16\".",
              "    Columna de portón: L2200.",
              f"3. Alto {dis['alto']:g}: 2 paneles de {dis['alto_panel']:g}",
              "    por vano, desde 150 del piso,",
              "    10 entre paneles.",
              "4. Paneles del lado exterior,",
              "    10 de luz a la columna.",
              "5. Donde corre la hoja del portón",
              "    la reja va 75 hacia afuera.",
              "6. Anclaje: 4 brocas M10x90 por base.",
              f"7. {len(cols)} columnas + 1 de portón,",
              f"    {dis['vanos']} vanos, {dis['paneles']} paneles."]
    nota(sheet, max(vx1 + 2.8, W - 10.0), H - 1.6, "<Br/>".join(lineas))
    return {"escala": lbl(sc), "cotas": ct.ok, "fallidas": ct.fallidas, "cadenas": usadas}


def hoja_elevacion(sheet, asm):
    W, H, tb_top, tb_left = zona(sheet)
    cols, gcol, gnor = columnas_diseno()
    # elevación mirando el lado de y mínima (frente en Inventor = desde +Z = desde y negativo del diseño)
    xs = [p[0] for p in cols]
    ext_x = max(xs) - min(xs) + 400
    sc = elegir_escala(ext_x, 2300, 15.0, 8.0, (0.05, 1 / 30, 0.025, 0.02, 0.01))
    v = vista_base(sheet, asm, 4.2 + ext_x * sc / 20, H - 2.4 - 2300 * sc / 20, sc, inv.K_VIEW_FRONT)
    sheet.Update()
    V = Vista(v)
    ct = Cotas(sheet)
    fila = sorted([p for p in cols if abs(p[1] - min(p_[1] for p_ in cols)) < 1], key=lambda p: p[0])
    p0 = fila[0]
    # panel del primer vano: x en el medio del vano
    xm = (fila[0][0] + fila[1][0]) / 2 if len(fila) > 1 else p0[0] + 300
    dis = RES["diseno"]
    hp_ = dis["alto_panel"]
    niveles = [0.0, 150.0, 150 + hp_, 160 + hp_, 160 + 2 * hp_]
    xr = (V.hoja(xm - 200, 0, 0)[0], V.hoja(xm + 200, 0, 0)[0])
    xbase = (V.hoja(p0[0] - 90, 0, 0)[0], V.hoja(p0[0] + 90, 0, 0)[0])
    lin = []
    for z in niveles:
        ys = V.hoja(xm, z, 0)[1]
        lin.append(V.linea("h", ys, xbase if z == 0 else xr))
    xl = V.hoja(p0[0] - 400, 0, 0)[0]
    for i in range(len(niveles) - 1):
        ya, yb = V.hoja(xm, niveles[i], 0)[1], V.hoja(xm, niveles[i + 1], 0)[1]
        if niveles[i + 1] - niveles[i] >= 30:
            ct.lineal(f"nivel {i}", lin[i], lin[i + 1], xl - 0.2, (ya + yb) / 2, esperado=niveles[i + 1] - niveles[i])
    ya, yb = V.hoja(xm, 0, 0)[1], V.hoja(xm, niveles[-1], 0)[1]
    ct.lineal("alto total", lin[0], lin[-1], xl - 1.2, (ya + yb) / 2, esperado=niveles[-1])
    rotulo(sheet, v, f"ELEVACIÓN — vista desde el lado inferior de la planta  ({lbl(sc)})", arriba=0.6)
    ys_ = [p[1] for p in cols]
    ext_y = max(ys_) - min(ys_) + 400
    iw, ih = 0.87 * (ext_x + ext_y), 0.5 * (ext_x + ext_y) + 2300
    x_libre = 4.2 + ext_x * sc / 10 + 1.0             # a la derecha de la elevación
    isc = elegir_escala(iw, ih, W - 1.4 - x_libre, H - 2.6 - (tb_top + 0.5), (0.05, 0.025, 0.02, 1 / 75, 0.01))
    icx, icy = (x_libre + W - 1.4) / 2, tb_top + 0.5 + ih * isc / 20
    iso(sheet, asm, icx, icy, isc)
    rotulo_xy(sheet, icx - iw * isc / 20, icy + ih * isc / 20 + 0.9, f"ISOMÉTRICA  ({lbl(isc)})")
    pl = None
    return {"escala": lbl(sc), "cotas": ct.ok, "fallidas": ct.fallidas}


def hoja_lista(sheet, asm):
    W, H, tb_top, tb_left = zona(sheet)
    v = iso(sheet, asm, 6.0, tb_top + 3.5, 0.01)
    rotulo_xy(sheet, 1.5, tb_top + 7.0, "CONJUNTO (1:100)")
    pl = S(lambda: sheet.PartsLists.Add(v, P(W - 1.0, H - 1.0)))
    if pl is None:
        log["avisos"].append("No se pudo agregar la lista de piezas")
    return {"lista": pl is not None}


# ============================================================================ main
def abrir(path):
    for d in inv._items(app.Documents):
        if S(lambda: Path(d.FullFileName).resolve() == Path(path).resolve(), False):
            return d
    return app.Documents.Open(str(path), False)


def guardar(ddoc, stem, titulo):
    inv._iprop(ddoc, "Design Tracking Properties", "Part Number", x.nombre[:inv.MAX_PART_NUMBER])
    inv._iprop(ddoc, "Inventor Summary Information", "Title", titulo[:inv.MAX_TITLE].upper())
    ext = ".dwg" if str(TEMPLATE).lower().endswith(".dwg") else ".idw"
    dwg, pdf = PL / f"{stem}{ext}", PDF / f"{stem}.pdf"
    for od in inv._items(app.Documents):
        if S(lambda: Path(od.FullFileName).resolve() == dwg.resolve(), False):
            S(lambda: od.Close(True))
    for f in (dwg, pdf):
        if f.exists():
            try:
                f.unlink()
            except PermissionError:
                log["avisos"].append(f"{f.name} abierto en otro programa")
    S(lambda: ddoc.Sheets.Item(1).Activate())
    ddoc.SaveAs(str(dwg), False)
    inv._export_pdf(app, ddoc, pdf)
    return str(pdf)


asm = abrir(ASM)
counts = inv._leaf_counts(asm)
qty = {Path(k).stem: v for k, v in counts.items()}
EST = OUT / "Estructura"

if x.solo in ("", "piezas"):
    etapa("Plano de piezas")
    ddoc = app.Documents.Add(inv.K_DRAWING_DOCUMENT, TEMPLATE, True)
    first = ddoc.Sheets.Item(1)
    S(lambda: setattr(first, "Size", 9997))
    S(lambda: setattr(first, "Orientation", 10242))
    trabajos = [("Base columna", OUT / "Chapas" / "Base columna.ipt")]
    for p_ in sorted(EST.glob("Columna*.ipt")):
        trabajos.append((p_.stem, p_))
        nom_s = ("Columna porton soldada L2200" if "porton" in p_.stem.lower()
                 else f"Columna soldada L{RES['diseno']['alto']:g}")
        trabajos.append((nom_s, ("soldado", p_)))
    paneles = sorted(EST.glob("Panel *.ipt"), key=lambda p: float(p.stem.split()[1].split("x")[0]))
    trabajos += [(p.stem, p) for p in paneles]
    trabajos += [(p.stem, p) for p in sorted(EST.glob("Hoja*.ipt"))]
    n = 0
    for nombre, path in trabajos:
        soldado = isinstance(path, tuple)
        src = path[1] if soldado else path
        q = qty.get(src.stem, 0)
        if not q or not src.exists():
            continue
        etapa(f"  hoja {nombre}")
        try:
            doc = None if soldado else abrir(path)
            sheet = first if n == 0 else inv._new_sheet(ddoc, first, 9997)
            n += 1
            S(lambda: setattr(sheet, "Name", nombre[:30]))
            if soldado:
                sd, _ = crear_soldado(asm, src.stem, nombre)
                L = 2200.0 if "2200" in nombre else float(RES["diseno"]["alto"])
                r = hoja_soldado(sheet, sd, q, nombre, L)
            elif nombre.startswith("Base"):
                r = hoja_base(sheet, doc, q, 180.0, 12.5, 116.0, 5.0, T316)
            elif nombre.startswith("Columna"):
                L = 2200.0 if "2200" in nombre else float(RES["diseno"]["alto"])
                uso = ("Columna de portón: 75 mm afuera de la línea." if "porton" in nombre.lower()
                       else "Soldar a la base; paneles del lado exterior.")
                r = hoja_cano(sheet, doc, q, nombre, L, COL_A, 2.0, uso)
            elif nombre.startswith("Panel"):
                w_, h_ = (float(t) for t in nombre.split()[1].split("x"))
                agu = [(PANEL_A / 2, y_, 8.0) for y_ in (100.0, h_ - 100.0)]
                agu += [(w_ - PANEL_A / 2, y_, d_) for _, y_, d_ in agu]
                r = hoja_marco(sheet, doc, q, nombre, w_, h_, PANEL_A, PANEL_A, PANEL_E, agu, (),
                               "")
            else:
                r = hoja_marco(sheet, doc, q, nombre, 1250.0, 2080.0, HOJA_A, HOJA_B, HOJA_E, [], (1040.0,),
                               "Hoja del portón: 2 ruedas Ø75 abajo; corre entre guías.")
            r["pieza"] = nombre
            r["cantidad"] = q
            log["hojas"].append(r)
        except Exception as exc:  # noqa: BLE001
            log["errores"].append({"pieza": nombre, "error": repr(exc), "traza": traceback.format_exc()[-1200:]})
    log["pdf_piezas"] = guardar(ddoc, f"{x.nombre}_PIEZAS", f"{x.nombre} - PIEZAS")
    S(lambda: ddoc.Close(True))

if x.solo in ("", "conjunto"):
    etapa("Plano de conjunto")
    ddoc = app.Documents.Add(inv.K_DRAWING_DOCUMENT, TEMPLATE, True)
    first = ddoc.Sheets.Item(1)
    S(lambda: setattr(first, "Size", 9997))
    S(lambda: setattr(first, "Orientation", 10242))
    for i, (nm, fn) in enumerate((("Planta", hoja_planta), ("Elevacion", hoja_elevacion), ("Lista", hoja_lista))):
        try:
            sheet = first if i == 0 else inv._new_sheet(ddoc, first, 9997)
            S(lambda: setattr(sheet, "Name", nm))
            r = fn(sheet, asm)
            r["pieza"] = f"CONJUNTO {nm}"
            log["hojas"].append(r)
        except Exception as exc:  # noqa: BLE001
            log["errores"].append({"pieza": f"CONJUNTO {nm}", "error": repr(exc), "traza": traceback.format_exc()[-1200:]})
    log["pdf_conjunto"] = guardar(ddoc, f"{x.nombre}_CONJUNTO", f"{x.nombre} - CONJUNTO")
    S(lambda: ddoc.Close(True))

app.SilentOperation = False
log["tiempo_s"] = round(time.time() - T0, 1)
print(json.dumps(log, ensure_ascii=False, indent=1, default=str))
