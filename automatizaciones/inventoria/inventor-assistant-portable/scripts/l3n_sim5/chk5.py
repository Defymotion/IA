"""Chequeos de la simulación v5: gripper/cajas contra cajas apoyadas y contra lo fijo, eslabones del robot (nube de puntos)
contra lo fijo y el robot aéreo, y robot aéreo contra lo fijo."""
import sys, io, contextlib, os, collections, math, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.abspath(__file__)))
REL = sys.argv[1] if len(sys.argv) > 1 else 'rel5.json'
T_END = float(sys.argv[2]) if len(sys.argv) > 2 else 570.0
sys.argv = ['plan5.py', REL, 'x_chk.json', '--hasta', str(T_END + 5)]
src = open('plan5.py').read().split('# ================================================================== guion del video')[0]
g = {'__name__': 'x', '__file__': 'plan5.py'}
with contextlib.redirect_stdout(io.StringIO()):
    exec(compile(src, 'plan5', 'exec'), g)
import numpy as np
from comun import prisma, sat, apply, mm, bb_de
from choque_brazo import Brazo
BR = Brazo('kuka_puntos.json')
A, B = g['A'], g['B']
R = g['REL']
AER = g['AER']
aereo = g['aereo']
t0 = time.time()

def aabb_caja(c, M):
    return bb_de(M, (-c.L / 2, c.L / 2), (0, c.H), (-c.W / 2, c.W / 2))

def ov(a, b):
    return min(min(a[3 + i], b[3 + i]) - max(a[i], b[i]) for i in range(3))

res = {}
for c in (A, B):
    drops = sorted(td for cy in c.ciclos for (td, g_, M) in cy['drops'])
    import bisect
    hits = collections.Counter(); first = {}; minluz = 1e9; emax = 0.0; cmin = 9.0; q = [0, -40, 90, 0]
    stat = [(n, cc) for n, cc in c.ESTATICOS]
    # fijos para el brazo: todo lo de la celda salvo el pedestal y lo que el robot toca a propósito
    bx, bz = c.robot.base_xz
    fijos_brazo = [(n, cc) for n, cc in stat if max(cc[0] - bx, bx - cc[3], 0) ** 2 + max(cc[2] - bz, bz - cc[5], 0) ** 2 < 4500 ** 2
                   and not n.startswith(('base_principal', 'Cajas_en_cola', 'Cinta_Interna', 'BM2000'))]
    cajas_brazo = [cc for n, cc in fijos_brazo]
    t = 0.0
    curs = [g['Cursor'](c, b) for b in c.cajas] if 'Cursor' in g else None
    while t < T_END:
        psi, org = c.tray.pose(t)
        Mg = c.robot.gripper_pose(psi, org)
        q, e = c.robot.q_para(Mg, q)
        emax = max(emax, e); cmin = min(cmin, c.robot.codo(q))
        P = c.robot.poses(q)
        Gt = P['gripper']
        GL = c.pinza.GL
        held, placed = [], []
        # cajas colgadas / apoyadas en t (de las claves)
        for b in c.cajas:
            k = None
            for kk in b.keys:
                if kk[0] <= t:
                    k = kk
                else:
                    break
            if k is None:
                continue
            if k[1] == 'held':
                held.append((b.idx, mm(Gt, c.pinza.LB[k[2][1]])))
            elif k[1] == 'placed':
                placed.append((b.idx, k[2], k[0]))
        i_ud = bisect.bisect_right(drops, t) - 1
        ud = drops[i_ud] if i_ud >= 0 else None
        if c.n == 'B':      # palas (a la altura de las cajas) y el resto del gripper por encima de -683
            gbs = [bb_de(Gt, (398.0, 1358.0), (GL[1], -683.0), (GL[2], 251.0)), bb_de(Gt, (GL[0], GL[3]), (-683.0, GL[4]), (GL[2], GL[5]))]
        else:
            gbs = [bb_de(Gt, (GL[0], GL[3]), (GL[1], GL[4]), (GL[2], GL[5]))]
        for bi, Mh in held:
            hb = aabb_caja(c, Mh)
            for pi, Mp, tp in placed:
                o = ov(hb, aabb_caja(c, Mp))
                if o > 1:
                    hits[('caja', 'apoyada')] += 1; first.setdefault(('caja', 'apoyada'), (round(t, 2), bi, pi, round(o, 1)))
        for pi, Mp, tp in placed:
            if ud is not None and abs(tp - ud) < 1e-6:
                continue
            o = max(ov(gb, aabb_caja(c, Mp)) for gb in gbs)
            if o > -30:
                minluz = min(minluz, -o)
            if o > 0.5:
                hits[('gripper', 'apoyada')] += 1; first.setdefault(('gripper', 'apoyada'), (round(t, 2), pi, round(o, 1)))
        # gripper y cajas colgadas contra lo fijo (en planta, girado)
        objs = [('grip', prisma(Gt, (GL[0], GL[3]), (GL[1], GL[4]), (GL[2], GL[5])))]
        objs += [('caja', prisma(Mh, (-c.L / 2, c.L / 2), (0, c.H), (-c.W / 2, c.W / 2))) for bi, Mh in held]
        for nm, (pl, y0, y1, bb) in objs:
            for n_, cc in stat:
                if n_.startswith(('Cinta_Interna', 'Cajas_en_cola', 'BM2000')):
                    continue
                if y0 < cc[4] - 1 and cc[1] + 1 < y1 and sat(pl, cc, -1.0):
                    hits[(nm, n_)] += 1; first.setdefault((nm, n_), (round(t, 2), c.tray.activo(t)))
        # brazo
        pts = BR.puntos_mundo(P)
        for ci, li, pen, npt in BR.choques(pts, cajas_brazo, h=0.0):
            key = ('brazo_' + ('V02', 'V03', 'V04', 'V05')[li], fijos_brazo[ci][0])
            hits[key] += 1; first.setdefault(key, (round(t, 2), pen, npt))
        # brazo contra el robot aéreo (sujeción y pallet colgado)
        z = AER.val('z', t, AER.Z_PARK); dy = AER.val('dy', t, 0.0); dz = z - aereo['Carro']['M'][2][3]
        su = aereo['Sujecion_pallet']['c']
        aer_box = [su[0], su[1] + dy - 160, su[2] + dz, su[3], su[4] + dy, su[5] + dz]
        for ci, li, pen, npt in BR.choques(pts, [aer_box], h=50.0):
            hits[('brazo', 'robot_aereo')] += 1; first.setdefault(('brazo', 'robot_aereo'), (round(t, 2), pen))
        t += 0.1
    res[c.n] = {'choques': {str(k): v for k, v in hits.most_common(20)}, 'primeros': {str(k): v for k, v in list(first.items())[:20]},
                'luz_min_gripper_caja_apoyada': round(minluz, 1), 'ik_max': round(emax, 3), 'codo_min': round(cmin, 3)}
# robot aéreo contra lo fijo (todas las celdas, rejas nuevas, línea)
import json as _j
_oc = _j.load(open('ocultos_celdas.json')) if os.path.exists('ocultos_celdas.json') else {}
OCULTOS = {'celda_A': _oc.get('Celda_A_L3N:1', []), 'celda_B': _oc.get('Celda_B_existente:1', [])}
stat = []
for k in ('celda_A', 'celda_B', 'linea'):
    for e in R[k]:
        cc = e['c']; n = e['n']
        if not cc or cc == [0.0] * 6 or e.get('vis') is False:
            continue
        if k != 'celda_B' and '/' in n:
            continue
        if k == 'celda_B' and '/' in n and not n.startswith('ADECOAGRO2_Layout'):
            continue
        if e.get('nh', 0) and n.startswith('ADECOAGRO2_Layout'):
            continue
        if any(n == h or n.startswith(h + '/') for h in OCULTOS.get(k, [])):
            continue
        if n.startswith(('Cinta_Llegada_A', '00.Ensamblaje Mesa', 'Pasarela', 'IA_Robot', 'IA_Gripper', 'KUKA', 'Paredes')):
            continue
        stat.append((k + ':' + n, cc))
hits = collections.Counter(); first = {}
t = -1.0
while t < T_END:
    z = AER.val('z', t, AER.Z_PARK); dy = AER.val('dy', t, 0.0); dz = z - aereo['Carro']['M'][2][3]
    def tb(c0, dx, dyy, dzz):
        return [c0[0] + dx, c0[1] + dyy, c0[2] + dzz, c0[3] + dx, c0[4] + dyy, c0[5] + dzz]
    objs = [('sujecion', tb(aereo['Sujecion_pallet']['c'], 0, dy, dz)), ('barra', tb(aereo['Barra_elevacion']['c'], 0, dy, dz)),
            ('carro', tb(aereo['Carro']['c'], 0, 0, dz))]
    for p in g['PALLETS']:
        if p['t_agarra'] <= t < p['t_suelta']:
            M = g['pallet_M'](p, t) if 'pallet_M' in g else None
            objs.append(('pallet', [AER.X - 600, 1528 + dy, z - 500, AER.X + 600, 1680 + dy, z + 500]))
    for on, bb in objs:
        for n, cc in stat:
            o = [min(bb[3 + i], cc[3 + i]) - max(bb[i], cc[i]) for i in range(3)]
            if min(o) > 3:
                hits[(on, n)] += 1; first.setdefault((on, n), (round(t, 1), [round(v) for v in o]))
    t += 0.1
res['aereo'] = {'choques': {str(k): v for k, v in hits.most_common(20)}, 'primeros': {str(k): v for k, v in list(first.items())[:20]}}
res['seg'] = round(time.time() - t0, 1)
import json
print(json.dumps(res, ensure_ascii=False, indent=1, default=str))
