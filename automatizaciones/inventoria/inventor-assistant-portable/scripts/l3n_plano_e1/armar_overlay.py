"""Lleva la geometría en planta de Inventor (DXF por grupo, 1 u = 1 mm, vista superior) al sistema del DWG de planta
(metros; x = -Z, y = -X) y agrega pasillos, recorridos y textos. Sale overlay DXF (INSUNITS 4 como el DWG de planta)."""
import json, math, sys
import ezdxf
from ezdxf.addons import Importer
from ezdxf.math import Matrix44
from ezdxf import bbox
SRC='/mnt/user-data/uploads/L3N/Planos_IA/planta_dxf/'
R=json.load(open(SRC+'L3N_planta_nuevos_resultado.json'))['grupos']
OUT=sys.argv[1]
DA, IA = (3843.973, 1293.966), (-6503.2, -35622.3)
def toD(X, Z):
    return (DA[0]-(Z-IA[1])/1000.0, DA[1]-(X-IA[0])/1000.0)
doc=ezdxf.new('R2018', setup=True)
doc.header['$INSUNITS']=4
doc.header['$LUNITS']=2
msp=doc.modelspace()
CAPAS={'TRANSPORTES':('DEFY_E1_TRANSPORTES_NUEVOS',30),'ENVOLVEDORA':('DEFY_E1_ENVOLVEDORA_MP402',6),
       'ROBOT_AEREO_EXT':('DEFY_E1_ROBOT_AEREO_EXTENSION_Y_BUFFER_CARTONES',4),'RESERVA_ETAPA2':('DEFY_E1_RESERVA_ETAPA2_PALLET_CAUTIVO',3),
       'CELDA_A':('DEFY_E1_CELDA_A_NUEVA',5)}
for n,c in [*CAPAS.values(),('DEFY_E1_PASILLOS_TRANSPALETA',8),('DEFY_E1_ZONA_AUTOELEVADOR',1),('DEFY_E1_RECORRIDO_REPOSICION_PALLETS',1),
            ('DEFY_E1_RECORRIDO_INSUMOS_CARTONES',14),('DEFY_E1_TEXTOS',7),('DEFY_E1_COTAS',7),('DEFY_E1_PUERTA_A_REUBICAR',2)]:
    if n not in doc.layers: doc.layers.add(n, color=c)
for g,(lay,col) in CAPAS.items():
    s=ezdxf.readfile(SRC+f'L3N_planta_nuevos_{g}.dxf')
    o=R[g]['m2s_cm']['o']
    imp=Importer(s, doc)
    ents=list(s.modelspace())
    imp.import_entities(ents, msp)
    imp.finalize()
    # (u, v) -> (v/1000 + cx, -u/1000 + cy)
    cx=DA[0]-o[1]+IA[1]/1000.0*0-35.6223*0  # placeholder, se recalcula abajo
    cx=3843.973 - o[1] - 35.6223
    cy=1293.966 + o[0] - 6.5032
    M=Matrix44([0,-0.001,0,0, 0.001,0,0,0, 0,0,1,0, cx,cy,0,1])
    nuevos=[e for e in msp if e.dxf.layer=='Visible (ISO)' or getattr(e,'_nuevo',False)]
    for e in nuevos:
        try:
            e.transform(M)
        except Exception as ex:
            e.destroy(); continue
        e.dxf.layer=lay
        e.dxf.color=256
        e.dxf.linetype='BYLAYER'
        try: e.dxf.lineweight=-1
        except Exception: pass
    print(g, len(nuevos))
if 'Visible (ISO)' in doc.layers:
    try: doc.layers.remove('Visible (ISO)')
    except Exception: pass

def poly(pts_inv, lay, cerrada=True, ancho=0.0):
    p=[toD(*q) for q in pts_inv]
    return msp.add_lwpolyline(p, close=cerrada, dxfattribs={'layer':lay,'const_width':ancho})
def rect(X0,X1,Z0,Z1): return [(X0,Z0),(X1,Z0),(X1,Z1),(X0,Z1)]
def hatch(pts_inv, lay, patron='ANSI31', esc=0.25, color=256):
    h=msp.add_hatch(color=color, dxfattribs={'layer':lay})
    h.set_pattern_fill(patron, scale=esc)
    h.paths.add_polyline_path([toD(*q) for q in pts_inv], is_closed=True)
def texto(t, X, Z, h=0.25, lay='DEFY_E1_TEXTOS', rot=0, col=256):
    x,y=toD(X,Z)
    m=msp.add_mtext(t, dxfattribs={'layer':lay,'char_height':h,'insert':(x,y),'attachment_point':5,'rotation':rot,'color':col})
    return m
def flecha(pts_inv, lay, ancho=0.12):
    p=[toD(*q) for q in pts_inv]
    msp.add_lwpolyline(p, dxfattribs={'layer':lay,'const_width':ancho})
    (x0,y0),(x1,y1)=p[-2],p[-1]
    a=math.atan2(y1-y0,x1-x0); L=0.6
    msp.add_lwpolyline([(x1,y1),(x1-L*math.cos(a)+0.3*math.sin(a), y1-L*math.sin(a)-0.3*math.cos(a)),
                        (x1-L*math.cos(a)-0.3*math.sin(a), y1-L*math.sin(a)+0.3*math.cos(a))], close=True,
                       dxfattribs={'layer':lay,'const_width':0.0})
    h=msp.add_hatch(color=256,dxfattribs={'layer':lay}); h.paths.add_polyline_path([(x1,y1),(x1-L*math.cos(a)+0.3*math.sin(a), y1-L*math.sin(a)-0.3*math.cos(a)),
                        (x1-L*math.cos(a)-0.3*math.sin(a), y1-L*math.sin(a)+0.3*math.cos(a))], is_closed=True)
def cota(X0,Z0,X1,Z1,t):
    (x0,y0),(x1,y1)=toD(X0,Z0),toD(X1,Z1)
    L='DEFY_E1_COTAS'
    msp.add_line((x0,y0),(x1,y1),dxfattribs={'layer':L})
    a=math.atan2(y1-y0,x1-x0); n=(-math.sin(a),math.cos(a))
    for (x,y) in ((x0,y0),(x1,y1)):
        msp.add_line((x-0.15*n[0],y-0.15*n[1]),(x+0.15*n[0],y+0.15*n[1]),dxfattribs={'layer':L})
        msp.add_line((x-0.08*math.cos(a+0.8),y-0.08*math.sin(a+0.8)),(x+0.08*math.cos(a+0.8),y+0.08*math.sin(a+0.8)),dxfattribs={'layer':L})
    rot=math.degrees(a)
    if rot>90 or rot<-90: rot+=180
    msp.add_mtext(t,dxfattribs={'layer':L,'char_height':0.2,'insert':((x0+x1)/2+0.18*n[0],(y0+y1)/2+0.18*n[1]),'attachment_point':8,'rotation':rot})
exec(open(sys.argv[2]).read())
doc.saveas(OUT)
e=bbox.extents(msp,fast=True); print('ext',e.extmin,e.extmax)
