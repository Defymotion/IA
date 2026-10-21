"""Diseñador de grippers de apriete (DEFYMOTION): de la caja al desarrollo de cada chapa.

Cada chapa se define por su DESARROLLO (igual que el DXF de corte):
  - contorno: lista de (x, y, bulge) como en DXF (bulge = tan(ángulo/4); 0 = tramo recto)
  - agujeros redondos, ranuras, hexágonos y rectángulos interiores
  - líneas de plegado (posición, dirección, ángulo)
Inventor luego crea la cara desde el desarrollo y la pliega (ver inventor_mcp).

Reglas medidas en ADECO2 (ver Analisis/Gripper_ADECO2_V1/reglas_geometricas.md).
Sin dependencias de Inventor: se prueba en cualquier PC.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field, asdict

from gripper_calc import Caja, Criterios, dimensionar

T_316 = 4.7625          # 3/16"
T_18 = 3.175            # 1/8"
T_14 = 6.35             # 1/4"
K_FACTOR = 0.44
R_CORNER = 10.0         # radio de esquinas de las chapas
BULGE_90 = math.tan(math.radians(90) / 4)   # 0.4142 → arco de 90°

# --- Hexágonos (estéticos / alivianado) ---
HEX_FLATS = 10.0        # entre caras
HEX_PITCH = 15.0        # entre columnas y entre hexágonos de una columna
HEX_MARGIN = 12.0       # distancia mínima del hexágono a bordes, pliegues y agujeros
HEX_FRAME = {"flats": 20.0, "pitch": 27.0, "margin": 12.0}   # alivianado de frame y brida (versión liviana)

# --- Módulo de pala móvil (ADN-25-80 + 2 × HGH15 riel 150) relativo al centro del módulo ---
# x: a lo ancho del frame desde el centro del alma; y: a lo largo desde el centro del módulo
MODULE_HOLES = {
    "riel_M4": {"d": 4.5, "pts": [(x, y) for x in (55.0, 115.0, 175.0) for y in (-50.0, 50.0)]},
    "soporte_cilindro": {"d": 7.0, "pts": [(x, y) for x in (30.0, 181.0) for y in (-13.0, 13.0)]},
    "paso_16": {"d": 16.0, "pts": [(52.0, 2.6), (159.0, -2.6)]},
}
MODULE_SLOT = {"w": 93.0, "h": 13.0, "x": -16.0, "y_abs": 50.0}    # del lado del extremo más cercano
RAIL_SPACING = 100.0
BLOCK_HOLES = {"d": 3.3, "sq": 26.0, "x_from_tip": 30.70}          # bloque HGH15CA en el ala de la pala

# --- Frame / brida / pala fija ---
FRAME_WEB = 400.0
FRAME_FLANGE = 170.0
BRIDA_HOLES = {"d": 10.0, "from_tip": 20.0, "y_rel": (-105.0, -35.0, 35.0, 105.0)}
PALA_FIJA_FLANGE = 60.0
PALA_FIJA_FRAME_X = (-177.06, -153.41)     # filas de Ø8 en el alma del frame (desde el centro)
PALA_FIJA_HOLE_ROWS = (13.41, 37.06)       # desde la punta del ala de la pala fija
PALA_FIJA_HOLE_D = 8.0
PALA_FIJA_END_HOLE = 45.0                  # primer agujero desde el extremo
PALA_FIJA_MAX_SPAN = 350.0
PALA_MOVIL_FLANGE = 70.0
PALA_MOVIL_NOTCH = {"w": 55.0, "depth_on_face": 25.0, "r": 10.0}


# =============================================================================
def bend_geometry(t: float, r: float | None = None, k: float = K_FACTOR):
    """Descuento de un pliegue de 90° con medidas EXTERIORES: tramo recto = medida - (t + r)."""
    r = t if r is None else r
    ba = math.pi / 2 * (r + k * t)
    return {"t": t, "r": r, "k": k, "ba": ba, "setback": t + r}


def rounded_rect(x0, y0, w, h, r=R_CORNER):
    """Contorno rectangular con esquinas redondeadas, sentido antihorario, formato (x, y, bulge)."""
    b = BULGE_90
    return [(x0 + r, y0, 0), (x0 + w - r, y0, b), (x0 + w, y0 + r, 0), (x0 + w, y0 + h - r, b),
            (x0 + w - r, y0 + h, 0), (x0 + r, y0 + h, b), (x0, y0 + h - r, 0), (x0, y0 + r, b)]


def slot(cx, cy, w, h):
    """Ranura oblonga (w a lo largo de x) como contorno con bulges."""
    r = h / 2
    return [(cx - w / 2 + r, cy - r, 0), (cx + w / 2 - r, cy - r, 1.0),
            (cx + w / 2 - r, cy + r, 0), (cx - w / 2 + r, cy + r, 1.0)]


def hex_grid(x0, y0, x1, y1, keepout: list, pitch=HEX_PITCH, flats=HEX_FLATS, margin=HEX_MARGIN):
    """Hexágonos en grilla intercalada dentro del rectángulo, fuera de las zonas prohibidas.
    keepout: lista de (xmin, ymin, xmax, ymax). Devuelve centros (x, y)."""
    rad = flats / math.sqrt(3)       # radio a vértice
    out = []
    cols = int((x1 - x0 - 2 * margin) // pitch) + 1
    rows = int((y1 - y0 - 2 * margin) // pitch) + 1
    if cols <= 0 or rows <= 0:
        return out
    ox = x0 + (x1 - x0 - (cols - 1) * pitch) / 2
    for c in range(cols):
        x = ox + c * pitch
        off = pitch / 2 if c % 2 else 0.0
        oy = y0 + (y1 - y0 - (rows - 1) * pitch) / 2 + off
        for rr in range(rows):
            y = oy + rr * pitch
            if y + rad > y1 - margin + 1e-6 or y - rad < y0 + margin - 1e-6:
                continue
            if any(kx0 - rad - 2 <= x <= kx1 + rad + 2 and ky0 - rad - 2 <= y <= ky1 + rad + 2
                   for kx0, ky0, kx1, ky1 in keepout):
                continue
            out.append((round(x, 3), round(y, 3)))
    return out


@dataclass
class FlatPart:
    nombre: str
    cantidad: int
    espesor: float
    material: str
    contorno: list                       # [(x, y, bulge)]
    circulos: list = field(default_factory=list)       # [(x, y, d)]
    contornos_interiores: list = field(default_factory=list)   # [[(x, y, bulge)], ...] (ranuras, etc.)
    hexagonos: list = field(default_factory=list)      # [(x, y)] con hex_flats, un vértice hacia +y
    pliegues: list = field(default_factory=list)       # [{"eje": "x"|"y", "pos": .., "angulo": 90, "sentido": 1}]
    envolvente_plegada: tuple = ()        # medidas exteriores esperadas (para verificar)
    notas: list = field(default_factory=list)
    textos: list = field(default_factory=list)   # [{"texto", "x", "y", "alto", "rot_deg", "fuente"}] calados
    hex_flats: float = HEX_FLATS                  # medida entre caras de los hexágonos de esta chapa

    def resumen(self):
        return {"nombre": self.nombre, "cantidad": self.cantidad, "espesor": self.espesor,
                "desarrollo": self.flat_size(), "agujeros": len(self.circulos),
                "ranuras": len(self.contornos_interiores), "hexagonos": len(self.hexagonos),
                "pliegues": len(self.pliegues), "envolvente": self.envolvente_plegada}

    def flat_size(self):
        xs = [p[0] for p in self.contorno]
        ys = [p[1] for p in self.contorno]
        return (round(max(xs) - min(xs), 2), round(max(ys) - min(ys), 2))


# =============================================================================
# Alas curvas (relevadas de ADECO2): alto completo en ±FRAME_CURVA["hz"] del centro (zona de la brida) y luego
# bajan con un empalme, un arco grande y una esquina r20 hasta el extremo. Puntos (dx desde la punta del ala,
# dy desde el inicio de la curva) y bulges, en el orden centro -> extremo. Para otros largos la transición se
# escala uniformemente (arcos y tangencias se conservan).
FRAME_CURVA = {"hz": 118.067, "pts": [(0.0, 0.0), (4.215, 12.282), (120.074, 342.217), (140.072, 361.933)],
               "bulges": (-0.1668, 0.1632, -0.4101)}
LOGO = {"texto": "DEFYMOTION", "alto": 30.0, "desde_pliegue": 35.0}

# Letras tipo stencil (calado láser sin islas): polígonos en unidades de altura (alto = 1), origen abajo-izq.
_S, _G = 0.2, 0.15          # trazo y puente


def _glifo(ch: str):
    s, g = _S, _G
    if ch == "I":
        return 0.2, [[(0, 0), (s, 0), (s, 1), (0, 1)]]
    if ch == "T":
        w = 0.7
        return w, [[(0, 1), (0, 1 - s), (w / 2 - s / 2, 1 - s), (w / 2 - s / 2, 0), (w / 2 + s / 2, 0),
                    (w / 2 + s / 2, 1 - s), (w, 1 - s), (w, 1)]]
    if ch == "E":
        w = 0.7
        return w, [[(0, 0), (w, 0), (w, s), (s, s), (s, 0.5 - s / 2), (0.8 * w, 0.5 - s / 2), (0.8 * w, 0.5 + s / 2),
                    (s, 0.5 + s / 2), (s, 1 - s), (w, 1 - s), (w, 1), (0, 1)]]
    if ch == "F":
        w = 0.7
        return w, [[(0, 0), (s, 0), (s, 0.5 - s / 2), (0.8 * w, 0.5 - s / 2), (0.8 * w, 0.5 + s / 2),
                    (s, 0.5 + s / 2), (s, 1 - s), (w, 1 - s), (w, 1), (0, 1)]]
    if ch == "N":
        w, d = 0.8, 0.32
        return w, [[(0, 0), (s, 0), (s, 1 - d - 0.1), (w - s, 0), (w, 0), (w, 1), (w - s, 1), (w - s, d + 0.1),
                    (s, 1), (0, 1)]]
    if ch == "M":
        w = 0.85
        return w, [[(0, 0), (s, 0), (s, 0.62), (w / 2, 0.22), (w - s, 0.62), (w - s, 0), (w, 0), (w, 1),
                    (w - s, 1), (w / 2, 0.52), (s, 1), (0, 1)]]
    if ch == "Y":
        w = 0.75
        return w, [[(w / 2 - s / 2, 0), (w / 2 + s / 2, 0), (w / 2 + s / 2, 0.45), (w, 1), (w - 0.24, 1),
                    (w / 2, 0.66), (0.24, 1), (0, 1), (w / 2 - s / 2, 0.45)]]
    if ch == "D":                         # palo + panza separados por un puente
        w = 0.72
        x0 = s + g
        return w, [[(0, 0), (s, 0), (s, 1), (0, 1)],
                   [(x0, 0), (0.62 * w, 0), (w, 0.3), (w, 0.7), (0.62 * w, 1), (x0, 1), (x0, 1 - s),
                    (0.62 * w - 0.05, 1 - s), (w - s, 0.7 - 0.05), (w - s, 0.3 + 0.05), (0.62 * w - 0.05, s),
                    (x0, s)]]
    if ch == "O":                         # dos medias lunas con puentes arriba y abajo
        w = 0.72
        m = w / 2 - g / 2
        izq = [(m, 0), (0.3 * w, 0), (0, 0.3), (0, 0.7), (0.3 * w, 1), (m, 1), (m, 1 - s), (0.3 * w + 0.05, 1 - s),
               (s, 0.7 - 0.05), (s, 0.3 + 0.05), (0.3 * w + 0.05, s), (m, s)]
        der = [(w - x_, y_) for x_, y_ in izq]
        return w, [izq, der]
    raise ValueError(f"Letra sin glifo stencil: {ch}")


def logo_stencil(texto: str, alto: float, cx: float, cy: float, rot_deg: float) -> list:
    """Contornos (x, y, bulge) del texto en letras stencil, centrado en (cx, cy) y girado rot_deg
    (+90: se lee hacia +y con la parte de arriba hacia -x)."""
    esp = 0.18
    glifos = [_glifo(c) for c in texto.upper()]
    ancho = sum(w for w, _ in glifos) + esp * (len(glifos) - 1)
    a = math.radians(rot_deg)
    ux, uy = math.cos(a), math.sin(a)            # dirección de lectura
    vx, vy = -math.sin(a), math.cos(a)           # "arriba" de las letras
    loops, x = [], 0.0
    for w, polys in glifos:
        for poly in polys:
            loop = []
            for px, py in poly:
                u, v = (x + px - ancho / 2) * alto, (py - 0.5) * alto
                loop.append((round(cx + u * ux + v * vx, 3), round(cy + u * uy + v * vy, 3), 0))
            loops.append(loop)
        x += w + esp
    return loops


def _contorno_frame_curvo(W: float, L: float):
    """Contorno del desarrollo del frame con alas curvas (x a lo ancho, y a lo largo)."""
    C = FRAME_CURVA
    hz = C["hz"]
    span = C["pts"][-1][1]
    s = min(1.0, (L / 2 - hz) / span)
    if s < 0.35:
        return None
    P = [(dx * s, dy * s) for dx, dy in C["pts"]]
    b1, b2, b3 = C["bulges"]
    yc = L / 2
    up = [(px, yc + hz + py) for px, py in P]           # mitad superior, del centro al extremo
    dn = [(px, yc - hz - py) for px, py in P]           # mitad inferior
    D = P[-1][0]
    # lado izquierdo subiendo: extremo inferior -> centro -> extremo superior
    left = [(dn[3][0], dn[3][1], b3), (dn[2][0], dn[2][1], b2), (dn[1][0], dn[1][1], b1), (dn[0][0], dn[0][1], 0),
            (up[0][0], up[0][1], b1), (up[1][0], up[1][1], b2), (up[2][0], up[2][1], b3), (up[3][0], up[3][1], 0)]
    # lado derecho bajando (espejo en x, recorrido inverso)
    right = [(W - up[3][0], up[3][1], b3), (W - up[2][0], up[2][1], b2), (W - up[1][0], up[1][1], b1),
             (W - up[0][0], up[0][1], 0), (W - dn[0][0], dn[0][1], b1), (W - dn[1][0], dn[1][1], b2),
             (W - dn[2][0], dn[2][1], b3), (W - dn[3][0], dn[3][1], 0)]
    assert abs(up[3][1] - L) < 1e-6 and abs(dn[3][1]) < 1e-6 and D < W / 2
    return left + right


def _contorno_frame_escalon(W: float, L: float, hz: float, caida: float = 35.0, rc: float = 10.0,
                            largo_s: float = 45.0):
    """Alas curvas para frames cortos (donde no entra el perfil de ADECO2): alto completo en ±hz del centro
    (zona de la brida) y una curva en S (dos arcos tangentes) que baja 'caida' mm hacia cada extremo, con
    esquinas de radio rc. Sentido antihorario, formato (x, y, bulge)."""
    sl = min(largo_s, L / 2 - hz - rc - 5)
    if sl < 20:
        return None
    yT1, yB1 = L / 2 + hz, L / 2 - hz
    yT2, yB2 = yT1 + sl, yB1 - sl
    bs = math.tan(math.atan(caida / sl) / 2)
    b, D = BULGE_90, caida
    return [(D + rc, 0, 0), (W - D - rc, 0, b), (W - D, rc, 0), (W - D, yB2, -bs),
            (W - D / 2, (yB1 + yB2) / 2, bs), (W, yB1, 0), (W, yT1, bs), (W - D / 2, (yT1 + yT2) / 2, -bs),
            (W - D, yT2, 0), (W - D, L - rc, b), (W - D - rc, L, 0), (D + rc, L, b), (D, L - rc, 0),
            (D, yT2, -bs), (D / 2, (yT1 + yT2) / 2, bs), (0, yT1, 0), (0, yB1, bs), (D / 2, (yB1 + yB2) / 2, -bs),
            (D, yB2, 0), (D, rc, b)]


def frame_part(n: int, pitch: float, t=T_316, web: float | None = None, curvo: bool = True,
               logo: bool = True, cil: int = 25, dx_mod: float = 0.0, ala: float = FRAME_FLANGE,
               r_esq: float = R_CORNER, alivianar: bool = False, brida_y: tuple | None = None,
               brida_largo: float | None = None) -> FlatPart:
    """Frame en U: alma 'web' (por defecto FRAME_WEB), alas 'ala' (FRAME_FLANGE), largo n × paso.
    curvo: alas con el perfil curvo de ADECO2; logo: DEFYMOTION calado en las dos alas.
    r_esq: radio de las esquinas de las alas (si no son curvas); alivianar: hexágonos grandes en el alma,
    fuera de agujeros, rieles y apoyo de la pala fija; brida_y: posiciones de los agujeros de la brida."""
    g = bend_geometry(t)
    L = n * pitch
    web = web or FRAME_WEB
    flange_flat = ala - g["setback"]
    web_flat = web - 2 * g["setback"]
    W = 2 * flange_flat + web_flat + 2 * g["ba"]
    b1 = flange_flat + g["ba"] / 2
    b2 = W - b1
    xc = W / 2                                   # centro del alma en el desarrollo
    # el módulo de pala móvil se referencia al borde +x del alma (como en ADECO2, alma de 400): x_ref = xc_400 + dx
    x0 = xc + web / 2 - FRAME_WEB / 2 + dx_mod
    C = CILINDROS[cil]
    circ, inner = [], []
    for i in range(n):
        yc = L / 2 + (i - (n - 1) / 2) * pitch
        circ += [(x0 + dx, yc + dy, MODULE_HOLES["riel_M4"]["d"]) for dx, dy in MODULE_HOLES["riel_M4"]["pts"]]
        S_ = C["soporte"]
        for xs in soporte_x_frame(cil):
            circ += [(x0 + xs, yc + sg * S_["sep_frame"] / 2, S_["d_frame"]) for sg in (-1, 1)]
        if C["paso_mangueras"]:
            h = MODULE_HOLES["paso_16"]
            circ += [(x0 + dx, yc + dy, h["d"]) for dx, dy in h["pts"]]
            sy = -MODULE_SLOT["y_abs"] if yc < L / 2 else MODULE_SLOT["y_abs"]
            inner.append(slot(x0 + MODULE_SLOT["x"], yc + sy, MODULE_SLOT["w"], MODULE_SLOT["h"]))
    # brida en las alas
    for yr in (brida_y or BRIDA_HOLES["y_rel"]):
        circ.append((BRIDA_HOLES["from_tip"], L / 2 + yr, BRIDA_HOLES["d"]))
        circ.append((W - BRIDA_HOLES["from_tip"], L / 2 + yr, BRIDA_HOLES["d"]))
    # pala fija
    for yp in pala_fija_hole_positions(L - 20):
        for dx in PALA_FIJA_FRAME_X:
            # filas de la pala fija medidas desde el borde -x del alma (el alma puede cambiar de ancho)
            circ.append((xc - web / 2 + (FRAME_WEB / 2 + dx), 10 + yp, PALA_FIJA_HOLE_D))
    cont = _contorno_frame_curvo(W, L) if curvo else None
    notas = ["Accesorios (válvulas, reguladores, sensores) sin agujeros en esta versión."]
    if curvo and cont is None:                   # frame corto: alas con escalón curvo fuera de la brida
        cont = _contorno_frame_escalon(W, L, (brida_largo or BRIDA["largo"]) / 2 + 8)
        if cont is not None:
            notas.append("Frame corto: alas con curva en S fuera de la zona de la brida.")
    hexes = []
    if alivianar:
        xa0, xa1 = flange_flat + g["ba"], W - flange_flat - g["ba"]          # alma plana
        ko = [(cx - d / 2 - 6, cy - d / 2 - 6, cx + d / 2 + 6, cy + d / 2 + 6) for cx, cy, d in circ
              if xa0 - 20 < cx < xa1 + 20]
        for lp in inner:
            xs_, ys_ = [p[0] for p in lp], [p[1] for p in lp]
            ko.append((min(xs_) - 6, min(ys_) - 6, max(xs_) + 6, max(ys_) + 6))
        for i in range(n):                                                   # apoyo de los rieles
            yc = L / 2 + (i - (n - 1) / 2) * pitch
            for sg in (-1, 1):
                ko.append((x0 + 35, yc + sg * RAIL_SPACING / 2 - 12.5, x0 + 195, yc + sg * RAIL_SPACING / 2 + 12.5))
        ko.append((xa0 - 5, -5, xc - web / 2 + PALA_FIJA_FLANGE + 6, L + 5))   # ala de la pala fija
        hexes = hex_grid(xa0, 0, xa1, L, ko, pitch=HEX_FRAME["pitch"], flats=HEX_FRAME["flats"],
                         margin=HEX_FRAME["margin"])
        notas.append(f"Alma alivianada con {len(hexes)} hexágonos de {HEX_FRAME['flats']:.0f} entre caras.")
    if curvo and cont is None:
        notas.append("Frame demasiado corto para las alas curvas: se hizo con alas rectas.")
    textos = []
    if logo:
        xl = b1 - LOGO["desde_pliegue"]
        inner += logo_stencil(LOGO["texto"], LOGO["alto"], xl, L / 2, 90)
        inner += logo_stencil(LOGO["texto"], LOGO["alto"], W - xl, L / 2, -90)
        notas.append("Logo DEFYMOTION calado en ambas alas (letras stencil con puentes, sin islas).")
    return FlatPart(
        nombre="Frame", cantidad=1, espesor=t, material="Acero SAE 1010",
        contorno=cont or rounded_rect(0, 0, W, L, r_esq), circulos=circ, contornos_interiores=inner,
        hexagonos=hexes, hex_flats=HEX_FRAME["flats"] if alivianar else HEX_FLATS,
        pliegues=[{"eje": "x", "pos": b1, "angulo": 90, "sentido": 1},
                  {"eje": "x", "pos": b2, "angulo": 90, "sentido": 1}],
        envolvente_plegada=(web, ala, L), notas=notas, textos=textos)


def pala_fija_hole_positions(length: float) -> list[float]:
    """Como ADECO2: un agujero a PALA_FIJA_END_HOLE de cada extremo y, entre ellos, agujeros centrados
    cada PALA_FIJA_MAX_SPAN (940 mm → 47 / 297 / 647 / 893)."""
    a, b = PALA_FIJA_END_HOLE, length - PALA_FIJA_END_HOLE
    m = max(0, math.ceil((b - a) / PALA_FIJA_MAX_SPAN) - 1)       # agujeros intermedios
    c = length / 2
    inner = [c + (i - (m - 1) / 2) * PALA_FIJA_MAX_SPAN for i in range(m)]
    return [round(v, 2) for v in [a, *inner, b]]


def pala_fija_part(length: float, clamp_h: float, t=T_316, hexagonos: bool = False) -> FlatPart:
    """Pala fija en L: cara de apriete clamp_h (exterior) y ala de PALA_FIJA_FLANGE atornillada al frame.
    hexagonos: alivianado estético (por defecto NO, a pedido de DEFYMOTION)."""
    g = bend_geometry(t)
    fl = PALA_FIJA_FLANGE - g["setback"]
    cf = clamp_h - g["setback"]
    H = fl + g["ba"] + cf
    bend = fl + g["ba"] / 2
    circ = [(x, y, PALA_FIJA_HOLE_D) for x in pala_fija_hole_positions(length) for y in PALA_FIJA_HOLE_ROWS]
    hexes = hex_grid(0, fl + g["ba"], length, H, keepout=[]) if hexagonos else []
    return FlatPart(
        nombre="Pala fija", cantidad=1, espesor=t, material="Acero SAE 1010",
        contorno=rounded_rect(0, 0, length, H), circulos=circ, hexagonos=hexes,
        pliegues=[{"eje": "y", "pos": bend, "angulo": 90, "sentido": 1}],
        envolvente_plegada=(length, PALA_FIJA_FLANGE, clamp_h))


def pala_movil_part(width: float, clamp_h: float, qty: int, t=T_316) -> FlatPart:
    """Pala móvil en L: cara de apriete width × clamp_h y ala PALA_MOVIL_FLANGE con los 2 bloques HGH15.
    Escotadura en U centrada que atraviesa el pliegue y entra 25 mm en la cara de apriete."""
    g = bend_geometry(t)
    fl = PALA_MOVIL_FLANGE - g["setback"]
    cf = clamp_h - g["setback"]
    Wf = fl + g["ba"] + cf                      # desarrollo a lo largo de x (ala en x=0)
    bend = fl + g["ba"] / 2
    n = PALA_MOVIL_NOTCH
    notch_end = fl + g["ba"] + (n["depth_on_face"] - g["setback"])
    y0, y1 = width / 2 - n["w"] / 2, width / 2 + n["w"] / 2
    r, b = n["r"], BULGE_90
    # contorno con la escotadura sobre el borde x=0 (punta del ala)
    cont = [(r, 0, 0), (Wf - r, 0, b), (Wf, r, 0), (Wf, width - r, b), (Wf - r, width, 0), (r, width, b),
            (0, width - r, 0), (0, y1 + r, b), (r, y1, 0), (notch_end - r, y1, -b), (notch_end, y1 - r, 0),
            (notch_end, y0 + r, -b), (notch_end - r, y0, 0), (r, y0, b), (0, y0 - r, 0), (0, r, b)]
    circ = []
    for yc in (width / 2 - RAIL_SPACING / 2, width / 2 + RAIL_SPACING / 2):
        for dx in (-BLOCK_HOLES["sq"] / 2, BLOCK_HOLES["sq"] / 2):
            for dy in (-BLOCK_HOLES["sq"] / 2, BLOCK_HOLES["sq"] / 2):
                circ.append((BLOCK_HOLES["x_from_tip"] + dx, yc + dy, BLOCK_HOLES["d"]))
    hexes = hex_grid(fl + g["ba"], 0, Wf, width, keepout=[(0, y0, notch_end, y1)])
    return FlatPart(
        nombre="Pala movil", cantidad=qty, espesor=t, material="Acero SAE 1010",
        contorno=cont, circulos=circ, hexagonos=hexes,
        pliegues=[{"eje": "x", "pos": bend, "angulo": 90, "sentido": 1}],
        envolvente_plegada=(width, clamp_h, PALA_MOVIL_FLANGE))


# =============================================================================
# Piezas de unión (generadas) y cilindros
# =============================================================================
T_38 = 9.525            # 3/8"
BRIDA = {"pata": 120.0, "largo": 250.0, "solape": 40.0, "r_esq": 15.0, "luz_lateral": 12.0,
         "centro_d": 80.0, "pcd": 160.0, "pcd_d": 12.0,
         # 12 agujeros cada 20° salvo 50/70/170/190 (relevado del DXF de ADECO2, simétrico respecto del eje x)
         "pcd_ang": (10, 30, 90, 110, 130, 150, 210, 230, 250, 270, 330, 350)}
EMPUJA_PALA = {"ancho": 38.0, "d": 4.5, "sobresale": 5.0}
PART_EMPUJE = {"ancho": 120.0, "ranura_desde_centro": 30.5}       # planchuelas a ±(31..69) del centro
GOMA = {"espesor": 2.5, "alto_fija_menos": 10.0, "alto_movil_menos": 40.0}

# Disposición del módulo de pala móvil (coordenadas del frame de ADECO2: x a lo ancho, alma de 400 con centro en
# 361.723 y borde +x en 561.723; z = 0 cara superior del alma, z = t cara inferior; y desde el centro del módulo)
MOD = {"xc_ref": 361.723, "x_frontal": 407.723,           # cara frontal (lado vástago) del cuerpo del cilindro
       "empuja_x1": 534.437, "agujeros_bloque_x": 515.437,  # fin de la empuja pala / centro de los 4 agujeros
       "z_bloque": 28.0,                                   # cara inferior del bloque HGH15 bajo el alma
       "luz_abierta_extra": 45.48,                         # luz entre gomas abierto = apriete + esto
       "alma_menos_luz": 21.51,                            # alma - luz entre gomas (módulo en su lugar)
       "x_soporte_trasero_max": 181.0}                     # desde el centro del alma de 400 (lejos del pliegue)

# Cilindros ADN-xx-80 y sus soportes de chapa. Medidas de catálogo Festo / relevadas de ADECO2 (25) y del
# gripper Tucumán 2026 (32). 'eje' = distancia del eje del cilindro a la cara inferior del alma.
CILINDROS = {
    25: {"nombre": "ADN-25-80", "tg": 26.0, "eje": 29.0, "largo": 119.0, "tuerca_off": 13.5, "rosca": "M8",
         "d_placa": 8.5, "placa_alto": 20.0, "paso_mangueras": True,
         "soporte": {"t": T_18, "ala_frame": 23.0, "ala_cil": 23.0, "ancho": 38.5, "d_frame": 7.0,
                     "sep_frame": 26.0, "frame_desde_cil": 16.0, "d_cil": 5.5, "cil_desde_frame": 15.17,
                     "luna_r": 5.0, "luna_en": "ambas"},
         "modelo": None},           # se toma del módulo de ADECO2
    32: {"nombre": "ADN-32-80", "tg": 32.5, "eje": 32.0, "largo": 124.0, "tuerca_off": 15.0, "rosca": "M10x1,25",
         "d_placa": 10.5, "placa_alto": 30.0, "paso_mangueras": False,
         "soporte": {"t": T_316, "ala_frame": 30.0, "ala_cil": 25.0, "ancho": 45.0, "d_frame": 7.0,
                     "sep_frame": 30.4, "frame_desde_cil": 21.5, "d_cil": 6.6, "cil_desde_frame": 15.75,
                     "luna_r": 8.0, "luna_en": "cil"},
         # modelo Festo copiado del gripper Tucumán 2026 a InventorIA\Comerciales\ADN-32-80
         "modelo": {"carpeta": "ADN-32-80", "cuerpo": "536267 ADN-80-P---(Z).ipt",
                    "vastago": "536267 ADN-80-P-A_(KS).ipt", "tuerca": "DIN-439-B - M10x1_25(F).ipt",
                    # matrices dentro del ensamble Festo (mm): vástago retraído y tuerca
                    "M_vastago": [[0, 0, -1, 0], [0, -1, 0, 0], [-1, 0, 0, 0], [0, 0, 0, 1]],
                    "M_tuerca": [[1, 0, 0, 0], [0, 0, -1, 0], [0, 1, 0, 15.0], [0, 0, 0, 1]]}},
}


def soporte_x_frame(cil: int) -> tuple:
    """x (desde el centro del alma de 400 de ADECO2, sin corrimiento) de los agujeros de los dos soportes."""
    C = CILINDROS[cil]
    S_ = C["soporte"]
    xf = MOD["x_frontal"] - MOD["xc_ref"]
    return (xf - S_["frame_desde_cil"], xf + C["largo"] + S_["frame_desde_cil"])


def corrimiento_modulo(cil: int) -> float:
    """Corrimiento del módulo hacia -x para que el soporte trasero no caiga en el pliegue del frame."""
    return min(0.0, MOD["x_soporte_trasero_max"] - soporte_x_frame(cil)[1])


def brida_part(ancho: float = 388.0, t=T_38, B: dict | None = None, alivianar: bool = False) -> FlatPart:
    """Brida robot en U invertida: alma con el patrón del robot, patas atornilladas por dentro de las alas del
    frame (solape B['solape'], agujeros Ø10 a 20 de la punta, como el frame).
    B: medidas y patrón (por defecto BRIDA, relevada de ADECO2); alivianar: hexágonos en el alma fuera del
    patrón del robot."""
    g = bend_geometry(t)
    B = {**BRIDA, **(B or {})}
    leg = B["pata"] - g["setback"]
    web = ancho - 2 * g["setback"]
    W = 2 * leg + web + 2 * g["ba"]
    b1 = leg + g["ba"] / 2
    b2 = W - b1
    L = B["largo"]
    circ = []
    for yr in B.get("y_rel", BRIDA_HOLES["y_rel"]):
        circ += [(BRIDA_HOLES["from_tip"], L / 2 + yr, BRIDA_HOLES["d"]),
                 (W - BRIDA_HOLES["from_tip"], L / 2 + yr, BRIDA_HOLES["d"])]
    cx, cy = W / 2, L / 2
    circ.append((cx, cy, B["centro_d"]))
    for a_ in B["pcd_ang"]:
        circ.append((round(cx + B["pcd"] / 2 * math.cos(math.radians(a_)), 3),
                     round(cy + B["pcd"] / 2 * math.sin(math.radians(a_)), 3), B["pcd_d"]))
    for d_, ang_ in B.get("pasadores", ()):                     # agujeros de pasador en el mismo círculo
        circ.append((round(cx + B["pcd"] / 2 * math.cos(math.radians(ang_)), 3),
                     round(cy + B["pcd"] / 2 * math.sin(math.radians(ang_)), 3), d_))
    hexes = []
    if alivianar:
        rk = B["pcd"] / 2 + B["pcd_d"] / 2 + 10
        hexes = hex_grid(leg + g["ba"], 0, W - leg - g["ba"], L, [(cx - rk, cy - rk, cx + rk, cy + rk)],
                         pitch=HEX_FRAME["pitch"], flats=HEX_FRAME["flats"], margin=HEX_FRAME["margin"])
    return FlatPart(
        nombre="Brida", cantidad=1, espesor=t, material="Acero SAE 1010",
        contorno=rounded_rect(0, 0, W, L, B["r_esq"]), circulos=circ, hexagonos=hexes,
        hex_flats=HEX_FRAME["flats"] if alivianar else HEX_FLATS,
        pliegues=[{"eje": "x", "pos": b1, "angulo": 90, "sentido": 1},
                  {"eje": "x", "pos": b2, "angulo": 90, "sentido": 1}],
        envolvente_plegada=(ancho, B["pata"], L),
        notas=[B.get("nota", "Patrón de agujeros del robot relevado de ADECO2: verificar con la brida del robot "
                             "de cada proyecto.")])


def soporte_piston_part(qty: int, cil: int = 25) -> FlatPart:
    """Escuadra para ADN (2 por cilindro): ala al frame con 2 agujeros y ala al cabezal del cilindro con
    2 agujeros a la separación TG. Media luna en la punta del ala del cilindro (paso del vástago)."""
    C = CILINDROS[cil]
    S_ = C["soporte"]
    t = S_["t"]
    g = bend_geometry(t)
    a1 = S_["ala_frame"] - g["setback"]
    a2 = S_["ala_cil"] - g["setback"]
    W = a1 + a2 + g["ba"]                    # desarrollo a lo largo de x: punta ala frame en x = 0
    H = S_["ancho"]
    bend = a1 + g["ba"] / 2
    yc = H / 2
    r = S_["luna_r"]
    cont = [(0, 0, 0), (W, 0, 0), (W, yc - r, -1.0), (W, yc + r, 0), (W, H, 0), (0, H, 0)]
    if S_["luna_en"] == "ambas":
        cont += [(0, yc + r, -1.0), (0, yc - r, 0)]
    xf = S_["ala_frame"] - S_["frame_desde_cil"]
    xcil = W - (S_["ala_cil"] - S_["cil_desde_frame"])
    circ = [(xf, yc + sg * S_["sep_frame"] / 2, S_["d_frame"]) for sg in (-1, 1)]
    circ += [(xcil, yc + sg * C["tg"] / 2, S_["d_cil"]) for sg in (-1, 1)]
    return FlatPart(
        nombre=f"Soporte {C['nombre'][:6]}", cantidad=qty, espesor=t, material="Acero SAE 1010", contorno=cont,
        circulos=circ, pliegues=[{"eje": "x", "pos": bend, "angulo": 90, "sentido": 1}],
        envolvente_plegada=(S_["ala_frame"], S_["ala_cil"], H))


def empuja_pala_part(qty: int, cil: int = 25, t=T_18) -> FlatPart:
    """Planchuela entre bloque HGH15 y ala de la pala móvil, que lleva el empuje del cilindro; pasa por las
    ranuras de la placa de empuje (soldada). Largo según el cilindro."""
    E = EMPUJA_PALA
    x0 = placa_x(cil)[0] - E["sobresale"]
    L = MOD["empuja_x1"] - x0
    W = E["ancho"]
    xh = MOD["agujeros_bloque_x"] - x0
    circ = [(xh + dx, W / 2 + dy, E["d"]) for dx in (-BLOCK_HOLES["sq"] / 2, BLOCK_HOLES["sq"] / 2)
            for dy in (-BLOCK_HOLES["sq"] / 2, BLOCK_HOLES["sq"] / 2)]
    return FlatPart(nombre="Empuja pala", cantidad=qty, espesor=t, material="Acero SAE 1010",
                    contorno=rounded_rect(0, 0, L, W, 5.0), circulos=circ, envolvente_plegada=(L, W, t))


def placa_x(cil: int, t=T_316) -> tuple:
    """(x exterior, x interior) de la placa de empuje: apoyada en la tuerca del vástago retraído."""
    xi = MOD["x_frontal"] - CILINDROS[cil]["tuerca_off"]
    return (xi - t, xi)


def part_empuje_part(qty: int, cil: int = 25, t=T_316) -> FlatPart:
    """Placa en la punta del vástago (entre las dos tuercas) que tira de las dos planchuelas empuja pala.
    Las planchuelas entran en dos ranuras abiertas desde los bordes y se sueldan."""
    P, C = PART_EMPUJE, CILINDROS[cil]
    W, H = P["ancho"], C["placa_alto"]
    yc = H / 2
    # ranura centrada en el eje que cubre la planchuela (z de la planchuela respecto del eje) + 0,2 mm
    z_lo, z_hi = MOD["z_bloque"] - C["eje"], MOD["z_bloque"] + T_18 - C["eje"]
    h = max(abs(z_lo), abs(z_hi)) + 0.2
    xr = W / 2 - P["ranura_desde_centro"]
    cont = [(0, 0, 0), (W, 0, 0), (W, yc - h, 0), (W - xr, yc - h, 0), (W - xr, yc + h, 0), (W, yc + h, 0),
            (W, H, 0), (0, H, 0), (0, yc + h, 0), (xr, yc + h, 0), (xr, yc - h, 0), (0, yc - h, 0)]
    return FlatPart(nombre="Placa empuje", cantidad=qty, espesor=t, material="Acero SAE 1010",
                    contorno=cont, circulos=[(W / 2, yc, C["d_placa"])], envolvente_plegada=(W, H, t),
                    notas=[f"Ranuras para las planchuelas empuja pala (soldar). Vástago {C['rosca']}."])


def gomas(caja: Caja, largo_fija: float, ancho_movil: float, n: int, alto_pala: float | None = None) -> list[dict]:
    """Gomas de apriete (placas macizas, no chapa). alto_pala: alto de la pala móvil (por defecto alto + 2)."""
    G_ = GOMA
    ref = (alto_pala - 2) if alto_pala else caja.alto_mm         # mismas reglas que ADECO2 (pala = alto + 2)
    return [{"nombre": "Goma pala fija", "cantidad": 1, "largo": largo_fija,
             "alto": ref - G_["alto_fija_menos"], "espesor": G_["espesor"], "material": "Caucho"},
            {"nombre": "Goma pala movil", "cantidad": n, "largo": ancho_movil,
             "alto": ref - G_["alto_movil_menos"], "espesor": G_["espesor"], "material": "Caucho"}]


# Versión liviana (robots chicos): alas cortas, alma y brida alivianadas, brida de 1/4" más corta
LIVIANO = {"ala_frame": 110.0, "r_esq_frame": 30.0, "t_brida": T_14,
           "brida": {"largo": 150.0, "pata": 70.0, "solape": 40.0, "y_rel": (-50.0, 0.0, 50.0)}}

# Patrones de brida de robot (ISO 9409-1). 'pcd_ang': ángulos de los agujeros pasantes respecto del eje x de la
# brida (a lo ancho del frame); 'pasadores': [(Ø, ángulo)]; 'centro_d': agujero central (centrado).
ROBOT_BRIDAS = {
    "KR140_ADECO": {},                       # = BRIDA (relevada de ADECO2)
    # KUKA KR IONTEC (KR 30 R2100 / KR 70 R2100): relevada del modelo KR_70_R2100_V01 (Kit Armador de Palets):
    # 9 agujeros M8 en Ø100 sobre una grilla de 30° con 3 huecos a 120°, centrado Ø63, agujero central Ø40.
    "KR_IONTEC": {"pcd": 100.0, "pcd_d": 9.0, "pcd_ang": (30, 60, 90, 150, 180, 210, 270, 300, 330),
                  "centro_d": 40.0,
                  "nota": "Brida KUKA KR IONTEC (ISO 9409-1-A100: 9 × M8 en Ø100) relevada del modelo KR 70 R2100; "
                          "verificar con el KR 30 del proyecto (pasador de posición no incluido)."},
}


def disenar_gripper(caja: Caja, n: int, c: Criterios = Criterios(), paso: float | None = None,
                    ancho_pala: float | None = None, solo_chapas_principales: bool = False,
                    curvo: bool = True, logo: bool = True, web: float | None = None,
                    liviano: bool = False, alto_palas: float | None = None, robot: str | None = None,
                    ala_frame: float | None = None) -> dict:
    """paso / ancho_pala / web permiten forzar valores (p. ej. para replicar un gripper existente).
    El alma del frame se calcula para que, abierto, queden apriete + 45,5 mm entre gomas.
    liviano: versión para robots chicos (LIVIANO); alto_palas: alto de la pala móvil (por defecto alto + 2,
    la fija = alto_palas + 28); robot: patrón de brida de ROBOT_BRIDAS."""
    calc = dimensionar(caja, n, c)
    if paso:
        calc.paso_mm = paso
    if ancho_pala:
        calc.ancho_pala_mm = ancho_pala
    avisos = list(calc.avisos)
    if calc.diametro_mm not in CILINDROS:            # usar el módulo validado inmediato superior
        mayor = min((d_ for d_ in CILINDROS if d_ >= calc.diametro_mm), default=None)
        if mayor is None:
            raise ValueError(f"No tengo módulo para {calc.cilindro} (hay: ADN-25-80, ADN-32-80)")
        f_ = math.pi * (mayor / 2) ** 2 * c.presion_bar * 0.1
        fs_ = 2 * c.mu * f_ / (caja.masa_kg * (9.81 + c.aceleracion_ms2))
        avisos.append(f"El cálculo pide {calc.cilindro} (FS {calc.fs_real}); se usa ADN-{mayor}-80 porque es el "
                      f"módulo validado: {f_:.0f} N, FS {fs_:.2f}.")
        calc.diametro_mm, calc.cilindro = mayor, f"Festo ADN-{mayor}-{calc.carrera_mm}"
        calc.fuerza_cilindro_n, calc.fs_real = round(f_, 1), round(fs_, 2)
    if "HGH15" not in calc.guia:
        avisos.append(f"El cálculo sugiere {calc.guia}; el módulo usa HGH15CA (riel 150), sobrado para "
                      f"{caja.masa_kg} kg.")
        calc.guia, calc.riel_mm = "HIWIN HGH15CA ×2, riel 150 mm", 150
    pitch = calc.paso_mm
    L = n * pitch
    cil = calc.diametro_mm
    if calc.carrera_mm != 80:
        raise ValueError(f"No tengo módulo para {calc.cilindro} (hay: ADN-25-80, ADN-32-80)")
    LV = LIVIANO if liviano else {}
    ala = ala_frame or LV.get("ala_frame", FRAME_FLANGE)
    B = dict(LV.get("brida", {}))
    if robot:
        if robot not in ROBOT_BRIDAS:
            raise ValueError(f"Robot sin patrón de brida: {robot} (hay: {list(ROBOT_BRIDAS)})")
        B.update(ROBOT_BRIDAS[robot])
    B = {**BRIDA, **B}
    t_brida = LV.get("t_brida", T_38)
    H = alto_palas or calc.alto_pala_sugerido_mm
    calc.alto_pala_sugerido_mm = H
    dx = corrimiento_modulo(cil)
    web = web or round((caja.largo_apriete_mm + MOD["luz_abierta_extra"] + MOD["alma_menos_luz"] - dx) * 2) / 2
    # que entren pala fija + módulo: punta del soporte delantero vs ala de la pala fija
    S_ = CILINDROS[cil]["soporte"]
    x_soporte = MOD["x_frontal"] - S_["ala_frame"] - (MOD["xc_ref"] + FRAME_WEB / 2) + dx   # desde el borde +x
    if -web + PALA_FIJA_FLANGE + 10 > x_soporte:
        avisos.append(f"Alma de {web} mm: el soporte del cilindro choca con el ala de la pala fija.")
    g_ = bend_geometry(T_316)
    if liviano and logo and (ala - g_["setback"]) - B["solape"] < LOGO["desde_pliegue"] + LOGO["alto"] / 2 + 5:
        avisos.append("El logo queda tapado por las patas de la brida: subir el ala del frame.")
    parts = [
        frame_part(n, pitch, web=web, curvo=curvo, logo=logo, cil=cil, dx_mod=dx, ala=ala,
                   r_esq=LV.get("r_esq_frame", R_CORNER), alivianar=liviano, brida_y=B.get("y_rel"),
                   brida_largo=B["largo"]),
        pala_fija_part(L - 20, H + 28),
        pala_movil_part(calc.ancho_pala_mm, H, n),
    ]
    if not solo_chapas_principales:
        parts += [brida_part(web - B["luz_lateral"], t=t_brida, B=B, alivianar=liviano),
                  soporte_piston_part(2 * n, cil), empuja_pala_part(2 * n, cil), part_empuje_part(n, cil)]
    comerciales = [
        {"pieza": calc.cilindro, "cantidad": n},
        {"pieza": f"HIWIN HGH15CA riel {calc.riel_mm} mm + bloque", "cantidad": 2 * n},
        {"pieza": f"Tuerca DIN 439 {CILINDROS[cil]['rosca']} (vástago)", "cantidad": 2 * n},
    ]
    modulo = {"cil": cil, "dx": dx, "web": web, "x_frontal": MOD["x_frontal"], "eje": CILINDROS[cil]["eje"],
              "largo_cil": CILINDROS[cil]["largo"], "placa_x": placa_x(cil),
              "placa_alto": CILINDROS[cil]["placa_alto"], "placa_ancho": PART_EMPUJE["ancho"],
              "empuja_x": (placa_x(cil)[0] - EMPUJA_PALA["sobresale"], MOD["empuja_x1"]),
              "soporte": S_, "soporte_x_frame": soporte_x_frame(cil), "tg": CILINDROS[cil]["tg"],
              "modelo": CILINDROS[cil]["modelo"], "alto_pala": H, "alto_pala_fija": H + 28,
              "ancho_pala": calc.ancho_pala_mm, "ala_frame": ala, "t_brida": t_brida,
              "brida": {k: B[k] for k in ("largo", "pata", "solape", "luz_lateral")}}
    return {"calculo": asdict(calc), "chapas": parts,
            "gomas": gomas(caja, L - 20, calc.ancho_pala_mm, n, H), "modulo": modulo,
            "reutilizadas": [], "comerciales": comerciales, "avisos": avisos}


if __name__ == "__main__":
    d = disenar_gripper(Caja(161, 333, 130, 7.0, "TBA200"), 6)
    for p in d["chapas"]:
        print(p.resumen())
    print(d["avisos"])
