"""Celda A con el pallet girado 90° (1000 en X, 1200 en Z): ¿el KUKA de A llega a todas las cajas desde donde está?
Python puro con los módulos de l3n_sim5 (mismo IK y mismo patrón 17x8 que la simulación). Prueba la posición actual del
pallet (celda A v6, -300 en X) y corrimientos del pallet; para cada caja de cada toma: alcance en la posición de dejar
y LIFT_MIN arriba, y choques del gripper con lo fijo (rejas, barrera, cinta interna).
Uso: python alcance_A.py rel.json salida.json
"""
import copy
import json
import math
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI.parent / "l3n_sim5"))
from config5 import celda_A  # noqa: E402
from celda5 import LIFT_MIN  # noqa: E402
from comun import roty, apply  # noqa: E402

REL0 = json.load(open(sys.argv[1], encoding="utf-8"))
MOVER = [["00.Ensamblaje Mesa de Rolos Completa", -300], ["IA_Pallet_TBA250", -300], ["Barrera_", -300], ["Reja_Este_", -300],
         ["Reja_Sur_col_5", -300], ["Reja_Norte_interna_col_5", -300], ["Reja_Sur_panel_bajo_4", -150],
         ["Reja_Sur_panel_alto_4", -150], ["Reja_Norte_interna_panel_bajo_4", -150], ["Reja_Norte_interna_panel_alto_4", -150]]


def rel_v6(dxp=-300.0, dzp=0.0):
    R = copy.deepcopy(REL0)
    for e in R["celda_A"]:
        for pref, dx in MOVER:
            if e["n"].startswith(pref):
                if e.get("M"):
                    e["M"][0][3] += dx
                if e.get("c"):
                    e["c"][0] += dx
                    e["c"][3] += dx
                break
    R["pallet_lleno"]["M_layout"][0][3] += dxp
    R["pallet_lleno"]["M_layout"][2][3] += dzp
    return R


def girar_capas(A, grados):
    """Gira el patrón (cajas relativas al pallet) alrededor del eje vertical del pallet."""
    G = roty(grados)
    Rg = [r[:3] for r in G[:3]]
    for cap in A.capas:
        for t in cap["tomas"]:
            nuevas = []
            for (R, p) in t["cajas"]:
                R2 = [[sum(Rg[i][k] * R[k][j] for k in range(3)) for j in range(3)] for i in range(3)]
                p2 = apply(G, p)
                nuevas.append((R2, list(p2)))
            t["cajas"] = nuevas
            d = t["dir"]
            t["dir"] = tuple(apply(G, d))


def evaluar(grados, dxp, dzp):
    A = celda_A(rel_v6(dxp, dzp))
    if grados:
        girar_capas(A, grados)
    P, rob = A.pinza, A.robot
    sub = lambda pp, d: (pp[0], [pp[1][0], pp[1][1] + d, pp[1][2]])
    res = {"giro": grados, "dx_pallet": dxp, "dz_pallet": dzp, "cajas": 0, "sin_alcance": 0, "choques": 0, "r_max": 0.0,
           "detalle": []}
    bx, bz = rob.base_xz
    for ic, cap in enumerate(A.capas):
        for it, t in enumerate(cap["tomas"]):
            n = len(t["cajas"])
            garras = list(range(P.n - n, P.n))
            mejor = None
            for flip in (0, 1):
                malos, chq, rmax = 0, 0, 0.0
                if t["tipo"] == "grupo":
                    Mbs = [A.pat_world(R, p, flip) for (R, p) in t["cajas"]]
                    Mg = P.gripper_para(Mbs[0], P.n - n)
                    pts = [Mg]
                else:
                    pts = [P.gripper_para(A.pat_world(R, p, flip), g_) for (R, p), g_ in zip(t["cajas"], reversed(garras))]
                for Mg in pts:
                    o = A.org_de(Mg)
                    ok = rob.alcanza(o) and rob.alcanza(sub(o, LIFT_MIN))
                    malos += 0 if ok else 1
                    chq += 1 if A.choca_estatico(Mg, []) else 0
                    F = apply(Mg, rob.BRIDA_G)
                    rmax = max(rmax, math.hypot(F[0] - bx, F[2] - bz))
                cand = (malos, chq, rmax, flip)
                mejor = cand if mejor is None or cand < mejor else mejor
            res["cajas"] += n
            res["sin_alcance"] += mejor[0]
            res["choques"] += mejor[1]
            res["r_max"] = max(res["r_max"], round(mejor[2], 1))
            if mejor[0] or mejor[1]:
                res["detalle"].append({"capa": ic, "toma": it, "tipo": t["tipo"], "n": n, "sin_alcance": mejor[0],
                                       "choques": mejor[1], "r": round(mejor[2], 1)})
    res["pallet_centro"] = [round(v, 1) for v in A.PAL_O]
    res["base_robot_xz"] = [round(bx, 1), round(bz, 1)]
    return res


out = []
for grados, dx, dz in [(0, -300, 0), (90, -300, 0), (90, -300, -100), (90, -300, -200), (90, -100, 0), (90, -500, 0),
                       (90, -300, 100)]:
    r = evaluar(grados, dx, dz)
    out.append(r)
    print(f"giro {grados:3d}  pallet dx {dx:5.0f} dz {dz:5.0f}  centro {r['pallet_centro']}  sin alcance {r['sin_alcance']:3d}"
          f"  choques {r['choques']:3d}  r_max brida {r['r_max']:.0f}", flush=True)
Path(sys.argv[2]).write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
