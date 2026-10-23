"""Rótulos sobre los cuadros: leyenda del tramo (abajo), reloj de proceso y velocidad (abajo a la derecha), marca.
Uso: python rotular.py <carpeta_png> <plan_meta.json> <carpeta_salida> [--desde N --hasta M]
"""
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

src, meta_p, dst = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
dst.mkdir(parents=True, exist_ok=True)
meta = json.loads(meta_p.read_text(encoding="utf-8"))
LEY = {r[0]: r for r in meta["leyendas"]}
F_LEY = ImageFont.truetype("/usr/share/fonts/opentype/inter/Inter-Medium.otf", 30)
F_RELOJ = ImageFont.truetype("/usr/share/fonts/opentype/inter/Inter-SemiBold.otf", 30)
F_MARCA = ImageFont.truetype("/usr/share/fonts/opentype/inter/Inter-SemiBold.otf", 24)
F_VEL = ImageFont.truetype("/usr/share/fonts/opentype/inter/Inter-Bold.otf", 30)
AZUL = (22, 44, 84)
NARANJA = (232, 119, 34)
T0 = 0.0          # reloj: segundos desde que el robot aéreo arranca a buscar el pallet (t = 0 del plan)

for png in sorted(src.glob("c*.png")):
    i = int(png.stem[1:])
    r = LEY.get(i)
    im = Image.open(png).convert("RGB")
    W, H = im.size
    d = ImageDraw.Draw(im, "RGBA")
    # marca arriba a la izquierda
    d.rounded_rectangle((24, 22, 24 + 560, 22 + 48), 10, fill=(255, 255, 255, 215))
    d.text((40, 32), "DEFYMOTION · Adecoagro Chivilcoy L3N · Celda A", font=F_MARCA, fill=AZUL)
    if r:
        _, seg, vel, ley, t = r
        tw = d.textlength(ley, font=F_LEY)
        bw = min(W - 48 - 300, tw + 48)
        d.rounded_rectangle((24, H - 92, 24 + bw, H - 28), 12, fill=(22, 44, 84, 225))
        d.text((48, H - 77), ley, font=F_LEY, fill=(255, 255, 255))
        tt = max(0.0, t - T0)
        reloj = f"{int(tt // 60):02d}:{int(tt % 60):02d}"
        vtxt = "×1" if abs(vel - 1) < 1e-6 else f"×{vel:g}"
        d.rounded_rectangle((W - 272, H - 92, W - 24, H - 28), 12, fill=(255, 255, 255, 225))
        d.text((W - 252, H - 77), reloj, font=F_RELOJ, fill=AZUL)
        d.text((W - 108, H - 77), vtxt, font=F_VEL, fill=NARANJA if vel > 1 else AZUL)
    im.save(dst / png.name.replace(".png", ".jpg"), quality=93)
