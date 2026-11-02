"""Plan v2: desde la celda A en adelante. Cruz (derivador) en lugar de la giratoria A, cadena derecha hasta la
envolvedora MP402, cama propia bajo la envolvedora, cadena hasta un 2.º derivador (giro) y rodilleras después del giro."""
import json, numpy as np
mods=json.load(open('/tmp/claude-0/mods.json'))
CARP=r'C:\DEFYMOTION\L3N\Relevamiento_planta\2026-10-28\30-07-26-E_01294_A_1_Adecoagro___Anteproyecto_de_Paletizado\30-07-26-E_01294_A_1_Adecoagro___Anteproyecto_de_Paletizado'
def M4(m):
    A=np.eye(4); A[:3,:]=np.array(m).reshape(3,4); return A
bydoc={m['doc']:m for m in mods}
EFF={'S-11253':1404,'S-11250':1404,'S-11255':2804,'S-11259':1531.6,'S-11261':1531.6,'S-11226':1956,'S-11219':1956,'I-07508':2975,'I-07506':1935,
     'S-11256':2330,'S-11217':2093,'S-11211':2330}
TOP={'S-11231':572.9,'S-11249':597.9,'S-11210':572.9,'I-07507':640.0}
TOP_DER={'S-11256':609.6,'S-11217':576.3,'S-11211':576.3}
H=626.0
ZL=-35607.5          # eje de la línea de salida (Z)
XA=-6503.2           # centro de la giratoria A
X_MP=8382.0          # comienzo de la cama bajo la MP402 (se conserva)
X_MP_FIN=10420.0     # fin de la cama bajo la MP402
L2800=['S-11255_A;2-Módulo Transporte Cadena 3.0 .iam','S-11255_A;2-Módulo Transporte Cadena 3.0 _1.iam','S-11255_A;2-Módulo Transporte Cadena 3.0 _2.iam']
L1400=['S-11253_A;2-Módulo Transporte Cadena 3.0 .iam','S-11253_A;2-Módulo Transporte Cadena 3.0 _1.iam','S-11253_A;2-Módulo Transporte Cadena 3.0 _2.iam','S-11253_A;2-Módulo Transporte Cadena 3.0 _3.iam','S-11250_A;2-Módulo Transporte Cadena 3.0 .iam']
T1=['S-11226_A;2-Módulo Transp. Cadena 3.0 -  .iam','S-11219_A;2-Módulo Transporte Cadena 3.0 .iam']
DER=['S-11256_A;1-Módulo Derivación Eléctrico U.iam','S-11211_A;1-Módulo Derivación Eléctrico U.iam','S-11217_A;1-Módulo Derivación Eléctrico U.iam']
ROD=['I-07506_A;1-Rodillera Previa Paletizado A.ipt']*4+['I-07508_A;1-Rodillera 2 Previa Paletizado.ipt']
# ocurrencias distintas para las rodilleras repetidas (mismo archivo)
rods=[m for m in mods if m['doc'].startswith('I-0750')]
up_t=np.array([0,1.,0])
plan={'modulos':[],'tramos':[]}
def poner(m, u, inicio, centro_transv, tramo, top=None):
    d=m['doc']; code=d[:7]
    W=M4(m['M']); c=m['caja']; lo=np.array(c[:3]); hi=np.array(c[3:]); L=hi-lo
    ia=0 if L[0]>=L[1] else 1
    a=np.zeros(3); a[ia]=1
    ez=np.array([0,0,1.])
    S_=np.column_stack([a,ez,np.cross(a,ez)]); T_=np.column_stack([u,up_t,np.cross(u,up_t)])
    R=T_@S_.T
    eff=EFF[code]
    anchor=lo[ia]+(L[ia]-eff)/2
    q=(lo+hi)/2; q[ia]=anchor
    q[2]=top if top is not None else TOP[m['grupo'][:7]]
    target=np.array(centro_transv,float).copy()
    target=target+u*(inicio-np.dot(u,target))
    target[1]=H
    t=target-R@q
    A=np.eye(4); A[:3,:3]=R; A[:3,3]=t
    WL=A@W
    plan['modulos'].append({'tramo':tramo,'archivo':CARP+'\\'+d,'nombre':code,'M_mm':[round(float(x),3) for x in WL[:3,:].reshape(-1)],
                            'inicio':round(float(inicio),1),'largo_ef':eff})
    return inicio+eff
ux=np.array([1.,0,0]); uz=np.array([0,0,1.])
# 1) cruz en la celda A (cadenas en X, rodillos en Z), centrada en la giratoria
der=[bydoc[d] for d in DER]
x=poner(der[0], ux, XA-EFF['S-11256']/2, [0,0,ZL], 'Cruz celda A', TOP_DER['S-11256'])
x0=x
# 2) cadena derecha hasta la cama de la MP402
for d in L2800+[L1400[0]]+T1:
    x=poner(bydoc[d], ux, x, [0,0,ZL], 'Salida a envolvedora')
plan['tramos'].append({'tramo':'Salida a envolvedora','disponible':round(X_MP-x0,1),'ocupado':round(x-x0,1),'sobra':round(X_MP-x,1)})
# 3) después de la envolvedora: 2 cadenas L1400 hasta la 2.ª cruz (giro hacia +Z)
x=X_MP_FIN
for d in L1400[1:3]:
    x=poner(bydoc[d], ux, x, [0,0,ZL], 'Post envolvedora')
xc2=x+EFF['S-11211']/2
x=poner(der[1], ux, x, [0,0,ZL], 'Cruz giro', TOP_DER['S-11211'])
plan['tramos'].append({'tramo':'Cruz giro','centro_x':round(xc2,1),'giratoria_final_centro_x':14587})
# 4) rodilleras después del giro, hacia +Z
z=ZL+1670/2
for i,m in enumerate(rods):
    z=poner(m, uz, z, [xc2,0,0], 'Rodilleras tras el giro')
plan['tramos'].append({'tramo':'Rodilleras tras el giro','desde_z':round(ZL+835,1),'hasta_z':round(z,1)})
plan['sin_usar']=['S-11253_A;2 L1400 x2','S-11259/S-11261 (T2) x2','S-11217 derivador x1']
plan['ocultar']={'Linea_Pallets:1':['Roller_Conveyor_Straight_400V_FlatBelt:4','Roller_Conveyor_Straight_400V_FlatBelt:8','Roller_Conveyor_Straight_400V_FlatBelt:6',
  'Roller_Conveyor_Straight_400V_FlatBelt:10','Roller_Conveyor_Straight_400V_FlatBelt:11','Roller_Conveyor_Straight_400V_FlatBelt:9','IA_Cama_linea_1',
  'IA_Cama_L3320_IA_Cama_linea_3','roller conveyor - rotating:2','Roller_Conveyor_Straight_400V_FlatBelt:13'],
  'Celda_A_L3N:1':['roller conveyor - rotating:1']}
for t in plan['tramos']: print(t)
json.dump(plan,open('/tmp/claude-0/plan_reutil2.json','w'),ensure_ascii=False,indent=1)
