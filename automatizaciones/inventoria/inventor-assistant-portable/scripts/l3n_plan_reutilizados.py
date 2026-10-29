import json, numpy as np
mods=json.load(open('/tmp/claude-0/mods.json'))
r=json.load(open('/mnt/user-data/uploads/Documents/InventorIA/Analisis/L3N/transportes_nuevos/ensamble_jt.json'))
G={e['n'][:10]: e['M'] for e in r['occ']}
CARP=r'C:\DEFYMOTION\L3N\Relevamiento_planta\2026-10-28\30-07-26-E_01294_A_1_Adecoagro___Anteproyecto_de_Paletizado\30-07-26-E_01294_A_1_Adecoagro___Anteproyecto_de_Paletizado'
def M4(m):
    A=np.eye(4); A[:3,:]=np.array(m).reshape(3,4); return A
bydoc={m['doc']:m for m in mods}
EFF={'S-11253':1404,'S-11250':1404,'S-11255':2804,'S-11259':1531.6,'S-11261':1531.6,'S-11226':1956,'S-11219':1956,'I-07508':2975,'I-07506':1935}
TOP={'S-11231':572.9,'S-11249':597.9,'S-11210':572.9,'I-07507':640.0}
H=626.0
tramos=[
 ('C-B', [0,0,1.], [-6533.5,0,-49732.], 4958, ['S-11255_A;2-Módulo Transporte Cadena 3.0 .iam','S-11253_A;2-Módulo Transporte Cadena 3.0 .iam']),
 ('B-A', [0,0,1.], [-6533.5,0,-43106.], 6666, ['S-11255_A;2-Módulo Transporte Cadena 3.0 _1.iam','S-11255_A;2-Módulo Transporte Cadena 3.0 _2.iam']),
 ('Salida', [1.,0,0], [-5618,0,-35607.5], 14286, ['S-11253_A;2-Módulo Transporte Cadena 3.0 _1.iam','S-11253_A;2-Módulo Transporte Cadena 3.0 _2.iam','S-11253_A;2-Módulo Transporte Cadena 3.0 _3.iam','S-11250_A;2-Módulo Transporte Cadena 3.0 .iam','S-11259_A;2-Módulo Transporte Cadena 3.0 .iam','S-11261_A;2-Módulo Transporte Cadena 3.0 .iam','S-11226_A;2-Módulo Transp. Cadena 3.0 -  .iam','S-11219_A;2-Módulo Transporte Cadena 3.0 .iam']),
 ('Post envolvedora', [1.,0,0], [10420,0,-35607.5], 3282, ['I-07508_A;1-Rodillera 2 Previa Paletizado.ipt']),
]
plan={'modulos':[], 'tramos':[]}
up_t=np.array([0,1.,0])
usados=set()
for nom,u,p0,avail,docs in tramos:
    u=np.array(u); p0=np.array(p0); s=0.0
    for d in docs:
        usados.add(d)
        m=bydoc[d]; gk=m['grupo']
        W=M4(m["M"])   # la transformación de la subocurrencia (proxy) ya está en coordenadas del ensamble principal
        c=m['caja']; lo=np.array(c[:3]); hi=np.array(c[3:]); L=hi-lo
        a=np.array([1.,0,0]) if L[0]>L[1] else np.array([0,1.,0])
        if d[:7] in ('S-11259','S-11261'): a=np.array([1.,0,0])
        eff=EFF[d[:7]]
        ez=np.array([0,0,1.])
        S_=np.column_stack([a,ez,np.cross(a,ez)]); T_=np.column_stack([u,up_t,np.cross(u,up_t)])
        R=T_@S_.T
        ia=0 if a[0]==1 else 1
        anchor=lo[ia]+(L[ia]-eff)/2
        q=(lo+hi)/2; q[ia]=anchor; q[2]=TOP[gk[:7]]
        target=p0+u*s; target[1]=H
        t=target-R@q
        A=np.eye(4); A[:3,:3]=R; A[:3,3]=t
        WL=A@W
        plan['modulos'].append({'tramo':nom,'archivo':CARP+'\\'+d,'nombre':d[:7],'M_mm':[round(float(x),3) for x in WL[:3,:].reshape(-1)],'largo_ef':eff,'inicio':round(float(s),1),
                                'altura_original_mm':round(TOP[gk[:7]]-lo[2],1)})
        s+=eff
    plan['tramos'].append({'tramo':nom,'disponible':avail,'ocupado':round(s,1),'sobra':round(avail-s,1)})
plan['sin_usar']=[m['doc'] for m in mods if m['doc'] not in usados]
for t in plan['tramos']: print(t)
print(plan['sin_usar'])
json.dump(plan,open('/tmp/claude-0/plan_reutil.json','w'),ensure_ascii=False,indent=1)
