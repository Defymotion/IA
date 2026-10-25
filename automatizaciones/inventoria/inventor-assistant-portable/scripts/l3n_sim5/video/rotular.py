"""Rótulos sobre los cuadros: leyenda del tramo (abajo), reloj de proceso y velocidad (abajo a la derecha), marca.
Uso: python rotular.py <carpeta_png> <plan_meta.json> <carpeta_salida> [--desde N --hasta M]
"""
import json
import os
import re
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

src, meta_p, dst = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
dst.mkdir(parents=True, exist_ok=True)
meta = json.loads(meta_p.read_text(encoding="utf-8"))
LEY = {r[0]: r for r in meta["leyendas"]}
FONTDIR = os.path.dirname(os.path.abspath(__file__))
F_LEY = ImageFont.truetype(f"{FONTDIR}/Inter-Medium.otf", 30)
F_RELOJ = ImageFont.truetype(f"{FONTDIR}/Inter-SemiBold.otf", 30)
F_MARCA = ImageFont.truetype(f"{FONTDIR}/Inter-SemiBold.otf", 24)
F_VEL = ImageFont.truetype(f"{FONTDIR}/Inter-Bold.otf", 30)
AZUL = (22, 44, 84)
NARANJA = (232, 119, 34)
T0 = 0.0          # reloj: segundos desde que el robot aéreo arranca a buscar el pallet (t = 0 del plan)

LO, HI = (int(sys.argv[4]), int(sys.argv[5])) if len(sys.argv) > 5 else (0, 10 ** 9)
for png in sorted(list(src.glob("c0*.png")) + list(src.glob("c0*.jpg"))):
    if not (LO <= int(png.stem[1:]) <= HI) or (dst / (png.stem + ".jpg")).exists():
        continue
    i = int(png.stem[1:])
    r = LEY.get(i)
    try:
        im = Image.open(png).convert("RGB")
    except OSError as e:                     # PNG leído a medio escribir/sincronizar: se reintenta en otra pasada
        print("saltado", png.name, e)
        continue
    W, H = im.size
    d = ImageDraw.Draw(im, "RGBA")
    # marca arriba a la izquierda
    MARCA = "DEFYMOTION · Adecoagro Chivilcoy L3N · Celdas A y B"
    d.rounded_rectangle((24, 22, 24 + 32 + d.textlength(MARCA, font=F_MARCA), 22 + 48), 10, fill=(255, 255, 255, 215))
    d.text((40, 32), MARCA, font=F_MARCA, fill=AZUL)
    if r:
        _, seg, vel, ley, t = r
        ley = re.sub(r"\s*\(×[\d.,]+\)", "", ley)
        maxw = W - 48 - 300 - 48
        lineas = [ley]
        if d.textlength(ley, font=F_LEY) > maxw:          # partir en dos renglones por la palabra más cercana al medio
            pal = ley.split(" ")
            mejor = min(range(1, len(pal)), key=lambda k: abs(d.textlength(" ".join(pal[:k]), font=F_LEY)
                                                              - d.textlength(" ".join(pal[k:]), font=F_LEY)))
            lineas = [" ".join(pal[:mejor]), " ".join(pal[mejor:])]
        tw = max(d.textlength(li, font=F_LEY) for li in lineas)
        alto = 64 + 40 * (len(lineas) - 1)
        d.rounded_rectangle((24, H - 28 - alto, 24 + tw + 48, H - 28), 12, fill=(22, 44, 84, 225))
        for k, li in enumerate(lineas):
            d.text((48, H - 13 - alto + k * 40), li, font=F_LEY, fill=(255, 255, 255))
        tt = max(0.0, t - T0)
        reloj = f"{int(tt // 60):02d}:{int(tt % 60):02d}"
        vtxt = "×1" if abs(vel - 1) < 1e-6 else f"×{vel:g}"
        d.rounded_rectangle((W - 272, H - 92, W - 24, H - 28), 12, fill=(255, 255, 255, 225))
        d.text((W - 252, H - 77), reloj, font=F_RELOJ, fill=AZUL)
        d.text((W - 108, H - 77), vtxt, font=F_VEL, fill=NARANJA if vel > 1 else AZUL)
    im.save(dst / (png.stem + ".jpg"), quality=93)
