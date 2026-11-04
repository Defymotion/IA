"""Plano técnico en PDF (A1 apaisado, 1:75) de la zona modificada de la etapa 1 L3N, a partir del DXF recortado del DWG de
planta: plano base en gris claro, cambios con sus colores, marcas numeradas y tabla de cambios, referencias y rótulo.
Uso: python plano_pdf.py <zona.dxf> <salida.pdf> [--png <preview.png>]
"""
import math
import sys

import ezdxf
import matplotlib
from ezdxf.addons.drawing import Frontend, RenderContext
from ezdxf.addons.drawing.config import Configuration, LineweightPolicy
from ezdxf.addons.drawing.matplotlib import MatplotlibBackend

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Circle, Rectangle  # noqa: E402

SRC, OUT = sys.argv[1], sys.argv[2]
PNG = sys.argv[sys.argv.index("--png") + 1] if "--png" in sys.argv else None
plt.rcParams["font.family"] = "DejaVu Sans"
MM = 1 / 25.4
W, H = 841.0, 594.0                       # A1 apaisado (mm)
ESC = 75.0
DA, IA = (3843.973, 1293.966), (-6503.2, -35622.3)


def toD(X, Z):
    return (DA[0] - (Z - IA[1]) / 1000.0, DA[1] - (X - IA[0]) / 1000.0)


COL = {
    "DEFY_E1_TRANSPORTES_NUEVOS": "#EF7D00", "DEFY_E1_ENVOLVEDORA": "#C2185B", "DEFY_E1_CELDA_A_NUEVA": "#1F5FD1",
    "DEFY_E1_ROBOT_AEREO_EXTENSION_Y_BUFFER_CARTONES": "#00A3B4", "DEFY_E1_RESERVA_ETAPA2_PALLET_CAUTIVO": "#2E8B3A",
    "DEFY_E1_PASILLOS_PASO_INSUMOS": "#7A7A7A", "DEFY_E1_ZONA_AUTOELEVADOR": "#D62828",
    "DEFY_E1_RECORRIDO_REPOSICION_PALLETS": "#E0453A", "DEFY_E1_RECORRIDO_INSUMOS_CARTONES": "#7B1E2B",
    "DEFY_E1_PUERTA_A_REUBICAR": "#B08800", "DEFY_E1_TEXTOS": "#1E1E1E", "DEFY_E1_COTAS": "#1E1E1E",
}
GRIS_EXIST = "#8C8C8C"
GRIS_BASE = "#BDBDBD"


def hex2rgb(h):
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


doc = ezdxf.readfile(SRC)
msp = doc.modelspace()
ents = []
for e in msp:
    lay = e.dxf.layer
    if e.dxftype() == "MTEXT" and "envolvedora girada" in e.text and "T2 S-11259" in e.text:
        e.text = "Envolvedora girada 90\u00b0\\Psobre T2 S-11259"
        e.dxf.rotation = 0
        if e.dxf.hasattr("text_direction"):
            e.dxf.discard("text_direction")
        e.dxf.insert = (3836.7, 1279.1)
    if lay == "DEFY_E1_TEXTOS" and e.dxftype() == "MTEXT" and e.text.startswith("MODIFICACIONES DEFYMOTION"):
        continue                                  # la leyenda del DWG: en el PDF va la tabla
    if lay.startswith("DEFY"):
        c = COL.get(lay, GRIS_EXIST)
    else:
        c = GRIS_BASE
    try:
        e.rgb = hex2rgb(c)
    except Exception:  # noqa: BLE001
        pass
    if e.dxftype() == "HATCH" and not lay.startswith("DEFY"):
        try:
            e.rgb = hex2rgb("#E2E2E2")
        except Exception:  # noqa: BLE001
            pass
    ents.append(e)

fig = plt.figure(figsize=(W * MM, H * MM))
fig.patch.set_facecolor("white")


def ax_mm(x, y, w, h):
    a = fig.add_axes([x / W, y / H, w / W, h / H])
    return a


# ------------------------------------------------------------------ marco
fr = ax_mm(0, 0, W, H)
fr.set_xlim(0, W)
fr.set_ylim(0, H)
fr.axis("off")
fr.add_patch(Rectangle((10, 10), W - 20, H - 20, fill=False, lw=1.2, ec="#222"))
DX0, DY0, DW, DH = 15.0, 15.0, 485.0, 564.0
fr.add_patch(Rectangle((DX0, DY0), DW, DH, fill=False, lw=0.6, ec="#222"))
# ------------------------------------------------------------------ dibujo a escala
cx, cy = 3848.0, 1287.6
ax = ax_mm(DX0 + 0.3, DY0 + 0.3, DW - 0.6, DH - 0.6)
from ezdxf.addons.drawing.config import ColorPolicy  # noqa: E402
base = [e for e in ents if not e.dxf.layer.startswith("DEFY")]
defy = [e for e in ents if e.dxf.layer.startswith("DEFY")]
cfg_b = Configuration(color_policy=ColorPolicy.MONOCHROME_LIGHT_BG, custom_fg_color=GRIS_BASE,
                      lineweight_policy=LineweightPolicy.RELATIVE, lineweight_scaling=0.5, min_lineweight=0.1)
Frontend(RenderContext(doc), MatplotlibBackend(ax), config=cfg_b).draw_entities(base)
cfg_d = Configuration(lineweight_policy=LineweightPolicy.RELATIVE, lineweight_scaling=1.0, min_lineweight=0.3)
Frontend(RenderContext(doc), MatplotlibBackend(ax), config=cfg_d).draw_entities(defy)
wm, hm = (DW - 0.6) * ESC / 1000.0, (DH - 0.6) * ESC / 1000.0
ax.set_xlim(cx - wm / 2, cx + wm / 2)
ax.set_ylim(cy - hm / 2, cy + hm / 2)
ax.set_aspect("equal", adjustable="box")
ax.axis("off")
ax.set_facecolor("white")
# marcas numeradas (en coordenadas del DWG)
def px(u, v):          # posición elegida sobre la vista previa (px de 2000 de ancho) -> DWG
    return (3829.8 + (u - 36) / 31.8, 1308.7 - (v - 36) / 31.75)


MARCAS = [(1, px(300, 372)), (2, px(358, 432)), (3, px(308, 542)), (4, px(423, 773)), (5, px(560, 1072)),
          (6, px(188, 975)), (7, px(313, 1025)), (8, px(300, 912)), (9, px(168, 1047)), (10, px(1150, 352)),
          (11, px(627, 913)), (12, px(280, 662)), (13, px(657, 868)), (14, px(798, 280))]
for n, (x, y) in MARCAS:
    ax.add_patch(Circle((x, y), 0.42, fc="white", ec="#111", lw=1.0, zorder=50))
    ax.text(x, y, str(n), ha="center", va="center", fontsize=7.5, fontweight="bold", zorder=51)
# barra de escala (5 m)
bx, by = cx - wm / 2 + 1.5, cy - hm / 2 + 1.2
for i in range(5):
    ax.add_patch(Rectangle((bx + i, by), 1, 0.18, fc="#111" if i % 2 == 0 else "white", ec="#111", lw=0.5, zorder=60))
ax.text(bx, by + 0.45, "0", fontsize=6, ha="center", zorder=60)
ax.text(bx + 5, by + 0.45, "5 m", fontsize=6, ha="center", zorder=60)
ax.text(bx + 2.5, by - 0.55, "ESCALA 1:75", fontsize=6.5, ha="center", fontweight="bold", zorder=60)

# ------------------------------------------------------------------ panel derecho
P0 = DX0 + DW + 6                          # 506
PW = W - 10 - 5 - P0                       # ~320
y = H - 15
fr.text(P0, y - 6, "LÍNEA DE PALLETS - ETAPA 1", fontsize=15, fontweight="bold", va="top")
fr.text(P0, y - 15, "Modificaciones propuestas sobre el plano de planta", fontsize=9.5, va="top", color="#333")
fr.plot([P0, P0 + PW], [y - 21, y - 21], color="#222", lw=0.8)
# tabla de cambios
FILAS = [
    (1, "Mesa giratoria de ingreso (celda A)", "Recibe el pallet vacío del robot aéreo y lo gira 90° antes de paletizar: los pallets de A, B y C "
        "salen con el lado de 1200 de frente. Mismo equipo que las giratorias de B y C.", "#1F5FD1"),
    (2, "Cama de rolos del puesto de paletizado (celda A)", "Cama nueva de 1933 mm en lugar de las mesas de rolos actuales; el robot "
        "paletiza sobre ella y el pallet sale hacia la cruz A.", "#1F5FD1"),
    (3, "Cruz A", "Recibe el pallet de la celda A, con los rodillos alineados con las camas de B y C.", "#EF7D00"),
    (4, "Transporte T3", "Acumulación de pallets sobre cadenas (8 módulos) hasta la esquina.", "#EF7D00"),
    (5, "Cruz de esquina", "Cambia el sentido de avance hacia la envolvedora.", "#EF7D00"),
    (6, "Envolvedora girada 90°", "Sobre el transporte T2 de la bajada. Durante el envuelto, el T2 de entrada y la salida 1 "
        "quedan libres (barrido del brazo).", "#C2185B"),
    (7, "Salida de pallets envueltos", "Dos tramos de cadenas; retiro con autoelevador desde la salida 2.", "#EF7D00"),
    (8, "Zona de autoelevador", "4,1 m x 4,5 m para el retiro de los pallets envueltos.", "#D62828"),
    (9, "Reserva etapa 2", "Espacio para el sistema de pallet cautivo (3,5 m x 5,0 m).", "#2E8B3A"),
    (10, "Robot aéreo de pallets", "Riel extendido 2 m y buffer de cartones nuevo junto a la pared este.", "#00A3B4"),
    (11, "Pasillos de paso de insumos", "2,21 m libres al norte del T3 y 3,20 m al este de la envolvedora.", "#7A7A7A"),
    (12, "Reposición de buffers de pallets", "Recorrido de reposición (pallets normales y de exportación).", "#E0453A"),
    (13, "Insumos del buffer de cartones", "Recorrido de abastecimiento de cartones; tramo final a confirmar en planta.", "#7B1E2B"),
    (14, "Puerta a reubicar", "Se anula la puerta junto al buffer de cartones y se reubica en la pared contigua "
        "(ubicación a definir).", "#B08800"),
]
ty = y - 27
fr.text(P0, ty, "CAMBIOS", fontsize=10.5, fontweight="bold", va="top")
ty -= 7
cN, cC, cD = P0, P0 + 9, P0 + 82
fr.add_patch(Rectangle((P0, ty - 6.5), PW, 6.5, fc="#2B2B2B", ec="#2B2B2B", lw=0.5))
for x_, t_ in ((cN + 2, "N°"), (cC + 2, "Cambio"), (cD + 2, "Descripción")):
    fr.text(x_, ty - 3.25, t_, fontsize=8.5, color="white", fontweight="bold", va="center")
ty -= 6.5
import textwrap  # noqa: E402
for i, (n, t_, d_, c_) in enumerate(FILAS):
    lineas_d = textwrap.wrap(d_, 92)
    lineas_c = textwrap.wrap(t_, 30)
    nl = max(len(lineas_d), len(lineas_c))
    hrow = 4.0 + 4.0 * nl
    if i % 2 == 0:
        fr.add_patch(Rectangle((P0, ty - hrow), PW, hrow, fc="#F4F4F4", ec="none"))
    fr.add_patch(Circle((cN + 4.3, ty - hrow / 2), 2.9, fc="white", ec="#111", lw=0.8))
    fr.text(cN + 4.3, ty - hrow / 2, str(n), ha="center", va="center", fontsize=8, fontweight="bold")
    fr.add_patch(Rectangle((cC + 1.5, ty - hrow / 2 - 1.6), 4.5, 3.2, fc=c_, ec="none"))
    for k, l_ in enumerate(lineas_c):
        fr.text(cC + 8, ty - 2.8 - 4.0 * k, l_, fontsize=8.2, fontweight="bold", va="top")
    for k, l_ in enumerate(lineas_d):
        fr.text(cD + 2, ty - 2.8 - 4.0 * k, l_, fontsize=8.0, va="top", color="#222")
    fr.plot([P0, P0 + PW], [ty - hrow, ty - hrow], color="#CCCCCC", lw=0.4)
    ty -= hrow
fr.add_patch(Rectangle((P0, ty), PW, (y - 34) - ty, fill=False, ec="#2B2B2B", lw=0.6))
# referencias
ty -= 8
fr.text(P0, ty, "REFERENCIAS", fontsize=10.5, fontweight="bold", va="top")
ty -= 7
REFS = [("#BDBDBD", "Plano de planta existente (relevamiento)"), (GRIS_EXIST, "Equipos existentes que se mantienen: celdas B y C, "
         "camas y giratorias, robot aéreo"), ("#1E1E1E", "Textos y cotas de ancho libre de pasillos (m)")]
for c_, t_ in REFS:
    fr.add_patch(Rectangle((P0, ty - 3.2), 8, 3.2, fc=c_, ec="none"))
    for k, l_ in enumerate(textwrap.wrap(t_, 90)):
        fr.text(P0 + 11, ty - 0.2 - 3.4 * k, l_, fontsize=8, va="top")
    ty -= 5.5 + 3.4 * (len(textwrap.wrap(t_, 90)) - 1)
fr.text(P0, ty - 2, "Los números en círculo del plano corresponden a la tabla de cambios. Medidas en metros.",
        fontsize=8, va="top", color="#333")
# detalle de la celda A
RY, RH = 15.0, 52.0
DET_ESC = 40.0
dtop, dbot = ty - 14, RY + RH + 8
fr.text(P0, dtop + 8, "DETALLE CELDA A - MESA GIRATORIA Y CAMA DE ROLOS (ESCALA 1:40)", fontsize=10, fontweight="bold", va="top")
dh = dtop - dbot
fr.add_patch(Rectangle((P0, dbot), PW, dh, fill=False, ec="#222", lw=0.6))
axd = ax_mm(P0 + 0.3, dbot + 0.3, PW - 0.6, dh - 0.6)
Frontend(RenderContext(doc), MatplotlibBackend(axd), config=cfg_b).draw_entities(base)
Frontend(RenderContext(doc), MatplotlibBackend(axd), config=cfg_d).draw_entities(
    [e for e in defy if e.dxf.layer != "DEFY_E1_TEXTOS"])
dcx, dcy = 3843.9, 1297.2
dw_, dh_ = (PW - 0.6) * DET_ESC / 1000.0, (dh - 0.6) * DET_ESC / 1000.0
axd.set_xlim(dcx - dw_ / 2, dcx + dw_ / 2)
axd.set_ylim(dcy - dh_ / 2, dcy + dh_ / 2)
axd.set_aspect("equal", adjustable="box")
axd.axis("off")
LLAM = [("1  Mesa giratoria de ingreso (Ø 2,0 m)\n    gira el pallet vacío 90°", toD(-10582, -35622.3), toD(-11400, -38550)),
        ("    Dejada del pallet vacío (robot aéreo)", toD(-10582, -35300), toD(-12300, -38550)),
        ("2  Cama de rolos 1933 mm (puesto de paletizado)", toD(-9300, -35689), toD(-9300, -29950)),
        ("    Pallet 1000 x 1200 con 1200 de frente", toD(-8521, -35617), toD(-8250, -29950)),
        ("    Robot de paletizado (existente en el proyecto)", toD(-8237, -37816), toD(-7300, -38550)),
        ("3  Cruz A: salida hacia el T3", toD(-7000, -35649), toD(-6450, -29950))]
for t_, (x, y), (tx, tyy) in LLAM:
    axd.annotate(t_, xy=(x, y), xytext=(tx, tyy), fontsize=8.2, va="center", ha="left",
                 bbox=dict(boxstyle="round,pad=0.25", fc="white", ec="#1F5FD1", lw=0.6),
                 arrowprops=dict(arrowstyle="-", lw=0.7, color="#1F5FD1"), zorder=60)
# flecha de avance del pallet
(ax0, ay0), (ax1, ay1) = toD(-10582, -34300), toD(-6900, -34300)
axd.annotate("", xy=(ax1, ay1), xytext=(ax0, ay0), arrowprops=dict(arrowstyle="-|>", lw=1.6, color="#1F5FD1"), zorder=60)
axd.text((ax0 + ax1) / 2 - 0.35, (ay0 + ay1) / 2, "avance del pallet", rotation=-90 if ay1 < ay0 else 90, fontsize=7.5,
         color="#1F5FD1", ha="center", va="center", zorder=60)
# rótulo
fr.add_patch(Rectangle((P0, RY), PW, RH, fill=False, ec="#222", lw=0.9))
fr.plot([P0, P0 + PW], [RY + RH - 16, RY + RH - 16], color="#222", lw=0.6)
fr.text(P0 + 4, RY + RH - 4, "DEFYMOTION", fontsize=16, fontweight="bold", va="top", color="#111")
fr.text(P0 + 4, RY + RH - 11.5, "Robótica y paletizado", fontsize=7.5, va="top", color="#444")
fr.text(P0 + PW - 4, RY + RH - 4, "ADECOAGRO", fontsize=12, fontweight="bold", va="top", ha="right")
fr.text(P0 + PW - 4, RY + RH - 10.5, "Planta Chivilcoy - Línea 3", fontsize=8, va="top", ha="right")
filas_r = [("PLANO", "Layout de la línea de pallets - Etapa 1 - Modificaciones"),
           ("BASE", "Revamping E2 - Defymotion - Integracion V1 (relevamiento)"),
           ("ESCALA", "1:75 (A1)"), ("FECHA", "04/11/2026"), ("REVISIÓN", "0")]
yy = RY + RH - 20
for k, v in filas_r:
    fr.text(P0 + 4, yy, k, fontsize=6.5, color="#555", va="top", fontweight="bold")
    fr.text(P0 + 28, yy, v, fontsize=8, va="top")
    yy -= 6.4
fig.savefig(OUT, facecolor="white")
if PNG:
    fig.savefig(PNG, dpi=70, facecolor="white")
print("ok", OUT)
