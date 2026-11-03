import ezdxf, collections, json
from ezdxf import recover, bbox
from shapely.geometry import Polygon, box
POL=[(3837.77,1299.11),(3848.6,1299.11),(3848.6,1294.8),(3854.0,1294.8),(3854.0,1299.11),(3864.44,1299.11),(3864.44,1290.05),(3846.52,1290.05),(3846.52,1267.85),(3837.77,1267.85)]
P=Polygon(POL)
BOR={'Maquinas','PL_Packaging_Line_1','PL_Leg_Conveyor','PL_Cable_Trench','Designación de equipos','Equipos existentes','CAJA 9X3 250 CC','2','1'}
d,_=recover.readfile('/tmp/claude-0/dxfpl/zona.dxf')
msp=d.modelspace(); n=0; quedan=collections.Counter()
for e in list(msp):
    if e.dxf.layer not in BOR: continue
    try: b=bbox.extents([e],fast=True)
    except Exception: continue
    if not b.has_data: continue
    bx=box(b.extmin.x,b.extmin.y,b.extmax.x,b.extmax.y)
    if P.contains(bx): msp.delete_entity(e); n+=1
    elif P.intersects(bx): quedan[(e.dxf.layer,e.dxftype(),round(b.size.x,1),round(b.size.y,1))]+=1
print('borrados',n); print(quedan.most_common(15))
d.saveas('zona_limpia.dxf'); json.dump(POL,open('poligono.json','w'))
