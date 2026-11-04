"""Overlay de la celda A del v9 (giratoria de ingreso + cama de rolos de 1933 + pallet con 1200 de frente) para el DWG de
planta: lleva el DXF de Inventor (vista superior, 1 u = 1 mm) a metros del DWG (x = -Z, y = -X) en la capa
DEFY_E1_CELDA_A_NUEVA y agrega los rótulos. También escribe el polígono (coordenadas del DWG) de lo que hay que borrar de la
celda A vieja (mesas CdR y pallet).
Uso: python armar_giratoria_A.py <dxf_inventor> <resultado.json> <salida.dxf> <salida_borrar.json>
"""
import json
import sys

import ezdxf
from ezdxf import bbox
from ezdxf.addons import Importer
from ezdxf.math import Matrix44

SRC, RES, OUT, BOR = sys.argv[1:5]
info = json.load(open(RES))["grupos"]["GIRATORIA_A"]
DA, IA = (3843.973, 1293.966), (-6503.2, -35622.3)


def toD(X, Z):
    return (DA[0] - (Z - IA[1]) / 1000.0, DA[1] - (X - IA[0]) / 1000.0)


def a_dwg(u, v, o):
    return toD(u - 1000.0 * o[0], -v + 1000.0 * o[1])


doc = ezdxf.new("R2018", setup=True)
doc.header["$INSUNITS"] = 4
doc.header["$LUNITS"] = 2
msp = doc.modelspace()
LAY = "DEFY_E1_CELDA_A_NUEVA"
doc.layers.add(LAY, color=5)
doc.layers.add("DEFY_E1_TEXTOS", color=7)
s_ = ezdxf.readfile(SRC)
o = info["m2s_cm"]["o"]
p0, pu, pv = a_dwg(0, 0, o), a_dwg(1, 0, o), a_dwg(0, 1, o)
M = Matrix44([pu[0] - p0[0], pu[1] - p0[1], 0, 0, pv[0] - p0[0], pv[1] - p0[1], 0, 0, 0, 0, 1, 0, p0[0], p0[1], 0, 1])
imp = Importer(s_, doc)
imp.import_entities(list(s_.modelspace()), msp)
imp.finalize()
n = 0
for e in list(msp):
    if e.dxf.layer != "Visible (ISO)":
        continue
    try:
        e.transform(M)
    except Exception:  # noqa: BLE001
        e.destroy()
        continue
    e.dxf.layer = LAY
    e.dxf.color = 256
    e.dxf.linetype = "BYLAYER"
    try:
        e.dxf.lineweight = -1
    except Exception:  # noqa: BLE001
        pass
    n += 1
if "Visible (ISO)" in doc.layers:
    try:
        doc.layers.remove("Visible (ISO)")
    except Exception:  # noqa: BLE001
        pass
for t, X, Z in (("MESA GIRATORIA DE INGRESO\\Pgira el pallet vac\\U+00EDo 90\\U+00B0: todos salen con 1200 de frente", -10582, -33900),
                ("CAMA DE ROLOS 1933 mm\\P(puesto de paletizado)", -8750, -33900)):
    x, y = toD(X, Z)
    msp.add_mtext(t, dxfattribs={"layer": "DEFY_E1_TEXTOS", "char_height": 0.2, "insert": (x, y), "attachment_point": 5})
doc.saveas(OUT)
ext = bbox.extents(msp, fast=True)
# borrar de la celda A vieja: mesas CdR 1-3 y pallet (ventana en Inventor X -11880..-7778, Z -36442..-34937)
pts = [toD(X, Z) for X, Z in ((-11880, -36442), (-7778, -36442), (-7778, -34937), (-11880, -34937))]
json.dump([[round(a, 4), round(b, 4)] for a, b in pts], open(BOR, "w"))
print("entidades", n, "ext", ext.extmin, ext.extmax, "borrar", pts)
