"""Vista en planta (2D) del flujo de la etapa 1 para validar la lógica antes del render de Inventor.
Uso: python flujo6.py <planta_segs.pkl> <salida_dir> [--hasta 1260] [--x 10] [--fps 20] [--solo-datos]
"""
import json
import math
import pickle
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import linea6 as L  # noqa: E402

ARG = sys.argv
SEGS, OUT = ARG[1], Path(ARG[2])
OUT.mkdir(parents=True, exist_ok=True)
T_FIN = float(ARG[ARG.index("--hasta") + 1]) if "--hasta" in ARG else 1260.0
VX = float(ARG[ARG.index("--x") + 1]) if "--x" in ARG else 10.0
FPS = int(ARG[ARG.index("--fps") + 1]) if "--fps" in ARG else 20
DT = 0.05

PL = L.Planta()
t = 0.0
while t < T_FIN:
    PL.paso(t)
    t += DT

# ------------------------------------------------------------------ resumen
res = {"retirados": len(PL.av["retiros"]), "envueltos": len(PL.envueltos),
       "pallets_por_celda": {}, "espera_celda_A_s": [], "aereo_ocupado_pct": None, "viajes_aereo": [x[2] for x in PL.aer.log]}
for cel in "ABC":
    ps = [p for p in PL.pallets if p.celda == cel and p.lleno is not None]
    res["pallets_por_celda"][cel] = {"completos": len(ps), "retirados": len([p for p in ps if p.t_fin]),
                                     "transito_s": [round((p.t_fin or T_FIN) - p.lleno, 0) for p in ps]}
occ_t = sum(b - a for (a, b, _) in [(x[0], x[1], 0) for x in PL.aer.log])
res["aereo_ocupado_pct"] = round(100 * occ_t / T_FIN, 1)
res["env_ocupada_pct"] = round(100 * sum(b - a for a, b, _ in PL.envueltos) / T_FIN, 1)
# cambio de pallet en la estación (desde que se completó hasta que el nuevo quedó listo)
for cel in "ABC":
    ps = sorted([p for p in PL.pallets if p.celda == cel and getattr(p, "listo", None) is not None and p.listo > 0], key=lambda p: p.listo)
    llenos = sorted([p.lleno for p in PL.pallets if p.celda == cel and p.lleno is not None])
    res.setdefault("cambio_estacion_s", {})[cel] = [round(q.listo - l, 1) for l, q in zip(llenos, ps)]
(OUT / "resumen.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps({k: v for k, v in res.items() if k != "viajes_aereo"}, ensure_ascii=False, indent=1))
print("\n".join(f"{a:7.1f}-{b:7.1f} {s}" for a, b, s in PL.aer.log[:40]))
if "--solo-datos" in ARG:
    sys.exit(0)

# ------------------------------------------------------------------ dibujo
import matplotlib  # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.collections import LineCollection  # noqa: E402
from matplotlib.patches import Polygon, Rectangle  # noqa: E402

segs = pickle.load(open(SEGS, "rb"))
COL = {"A": "#2f6fdf", "B": "#e8871e", "C": "#2aa05a", "?": "#a07850"}
fig = plt.figure(figsize=(19.2, 10.8), dpi=100)
ax = fig.add_axes([0.01, 0.03, 0.74, 0.94])
axt = fig.add_axes([0.76, 0.03, 0.23, 0.94])
axt.axis("off")
ax.add_collection(LineCollection([(s[0], s[1]) for s in segs], colors="#a8a8a8", lw=0.6))
# transportes / zonas
for n, (x, z, y, tp) in L.ZONAS.items():
    w, h = (1400, 1150) if tp == "x" else (1150, 1400)
    if tp == "z" and n.startswith("Z"):
        w, h = 1150, 2000
    if tp in ("cruz", "gir"):
        w, h = 1500, 1500
    if tp == "est":
        w, h = 1300, 1100
    fc = {"cruz": "#efe3ff", "gir": "#efe3ff", "env": "#ffe9d6", "est": "#eef3ff"}.get(tp, "#f2f2f2")
    ax.add_patch(Rectangle((x - w / 2, z - h / 2), w, h, fc=fc, ec="#8a8a8a", lw=0.7, zorder=1))
for cel in "ABC":
    zd = L.EST[cel]["z_dep"]
    x = L.EST[cel]["est"][0]
    ax.add_patch(Rectangle((L.X_RIEL - 650, zd - 550), x - L.X_RIEL + 1300, 1100, fc="#f6f6f6", ec="#b0b0b0", lw=0.6, zorder=0.9))
    ax.text(x, L.EST[cel]["est"][2] - 900, f"Celda {cel}", ha="center", fontsize=11, weight="bold", color=COL[cel])
ax.plot([L.X_RIEL - 785, L.X_RIEL - 785], [-55550, -31350], color="#777", lw=1.2)
ax.plot([L.X_RIEL + 785, L.X_RIEL + 785], [-55550, -31350], color="#777", lw=1.2)
ax.text(L.X_RIEL - 1100, -44000, "riel robot aéreo", rotation=90, fontsize=9, color="#555", va="center")
ax.add_patch(Rectangle((L.X_T2 - 1700, -32879.6 - 1700), 3400, 3400, fc="none", ec="#e07b00", lw=1.2, ls="--"))
ax.text(L.X_T2 + 1800, -32879.6, "MP402", fontsize=10, color="#e07b00", va="center")
ax.text(L.X_T2 + 900, -29083, "retiro\nautoelevador", fontsize=9, color="#555", va="center")
ax.text(-10582 + 900, -32274, "buffer 1\n(normal)", fontsize=8.5, va="center")
ax.text(-10582 + 900, -33804, "buffer 2\n(export.)", fontsize=8.5, va="center")
ax.text(-10582 + 900, -54797, "buffer de\ncartones", fontsize=8.5, va="center")
ax.set_xlim(-14500, 15500)
ax.set_ylim(-28000, -56000)
ax.set_aspect("equal")
ax.set_xticks([])
ax.set_yticks([])

dyn = []


def rect_rot(x, z, w, h, ang):
    a = math.radians(ang)
    c, s = math.cos(a), math.sin(a)
    pts = [(-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2)]
    return [(x + px * c - pz * s, z + px * s + pz * c) for px, pz in pts]


cart_map = {c["id"]: c for c in PL.aer.cartones}
n_fr = int(T_FIN / VX * FPS)
eventos = sorted(PL.eventos)
PARTE = (int(ARG[ARG.index("--parte") + 1]), int(ARG[ARG.index("--parte") + 2])) if "--parte" in ARG else (0, 1)
for fi in range(n_fr):
    if fi % PARTE[1] != PARTE[0]:
        continue
    t = fi * VX / FPS
    for d in dyn:
        d.remove()
    dyn = []
    # pila de cartones
    usados = len([c for c in PL.aer.cartones if c["id"] >= 0 and c["t_toma"] <= t])
    dyn.append(ax.add_patch(Rectangle((-10582 - 600, -54797 - 500), 1200, 1000, fc="#d9b77a", ec="#8a6a30", lw=0.8, zorder=2)))
    dyn.append(ax.text(-10582, -54797, f"{L.H_PILA_CARTON / L.E_CARTON - usados:.0f}", ha="center", va="center", fontsize=8, zorder=3))
    # pallets
    pilas_n = {1: 0, 2: 0}
    for p in PL.pallets:
        r = PL.pallet_pose(p, t)
        if r is None:
            continue
        x, y, z, ang, vis, en_aer = r
        if p.lugar.startswith("pila") and not en_aer and (getattr(p, "t_agarra", None) is None or t < p.t_agarra):
            pilas_n[p.k] += 1
            top = all(not (q.lugar.startswith(f"pila{p.k}_") and q.j > p.j and (getattr(q, "t_agarra", None) is None or t < q.t_agarra))
                      for q in PL.pallets)
            if not top:
                continue
        w, h = 1200, 1000
        lleno = p.lleno is not None and t >= p.lleno
        fc = COL.get(p.celda, "#a07850") if lleno else "#c9a26b"
        envuelto = p.t_env is not None and t >= p.t_env[0]
        poly = Polygon(rect_rot(x, z, w, h, ang), closed=True, fc=fc, ec="k", lw=1.6 if envuelto else 0.7,
                       alpha=1.0, zorder=5 if en_aer else 4, hatch="////" if envuelto and t < p.t_env[1] else None)
        dyn.append(ax.add_patch(poly))
        if envuelto and t >= p.t_env[1]:
            dyn.append(ax.add_patch(Polygon(rect_rot(x, z, w - 120, h - 120, ang), closed=True, fc="none", ec="white", lw=1.2, zorder=6)))
        cid = p.carton
        tiene = cid is not None and (cid <= -1 or (cid in cart_map and t >= cart_map[cid]["t_deja"]))
        if tiene and not lleno:
            dyn.append(ax.add_patch(Polygon(rect_rot(x, z, w - 160, h - 160, ang), closed=True, fc="#e8d3a6", ec="#8a6a30", lw=0.6, zorder=6)))
        if lleno and p.t_env is None or (lleno and t < p.t_env[0]):
            dyn.append(ax.text(x, z, p.celda, ha="center", va="center", fontsize=9, color="white", weight="bold", zorder=7))
    for k, zp in ((1, -32274.0), (2, -33804.0)):
        dyn.append(ax.text(-10582 - 900, zp, f"{pilas_n[k]}", ha="right", va="center", fontsize=9, weight="bold", zorder=7))
    # cartón en el aire
    for c in PL.aer.cartones:
        if c["id"] >= 0 and c["t_toma"] <= t < c["t_deja"]:
            zc = PL.aer.val("z", t)
            dyn.append(ax.add_patch(Rectangle((L.X_RIEL - 520, zc - 420), 1040, 840, fc="#e8d3a6", ec="#8a6a30", lw=0.8, zorder=8)))
    # carro del robot aéreo
    zc = PL.aer.val("z", t)
    dyn.append(ax.add_patch(Rectangle((L.X_RIEL - 950, zc - 600), 1900, 1200, fc="none", ec="#c0392b", lw=2.2, zorder=9)))
    # dispositivos
    for dn in ("CruzA", "Cruz2"):
        f = PL.dev[dn].frac(t, ["cad", "rod"])
        x, z = L.ZONAS[dn][0:2]
        dyn.append(ax.text(x, z + 900, "rodillos ↑" if f > 0.5 else "cadenas", ha="center", fontsize=7.5, color="#6a3d9a", zorder=7))
    # panel de texto
    m, s = divmod(int(t), 60)
    dyn.append(axt.text(0.02, 0.97, f"{m:02d}:{s:02d}", fontsize=40, weight="bold", transform=axt.transAxes, va="top"))
    dyn.append(axt.text(0.02, 0.89, f"tiempo de planta · video ×{VX:.0f}", fontsize=11, transform=axt.transAxes, color="#555"))
    n_ret = {c: len([1 for (tt, pid) in PL.av["retiros"] if tt <= t and PL.pallets[pid].celda == c]) for c in "ABC"}
    n_ll = {c: len([1 for p in PL.pallets if p.celda == c and p.lleno is not None and p.lleno <= t]) for c in "ABC"}
    y0 = 0.82
    for c, txt in (("A", "Celda A (robot nuevo, 136 cajas)"), ("B", "Celda B (salida cada ~9 min)"), ("C", "Celda C (salida cada ~5 min)")):
        dyn.append(axt.text(0.02, y0, f"■ {txt}", color=COL[c], fontsize=11.5, weight="bold", transform=axt.transAxes))
        dyn.append(axt.text(0.06, y0 - 0.03, f"completos {n_ll[c]} · retirados {n_ret[c]}", fontsize=10.5, transform=axt.transAxes))
        y0 -= 0.075
    ultimos = [e for e in eventos if e[0] <= t][-7:]
    y0 -= 0.02
    dyn.append(axt.text(0.02, y0, "Últimos eventos", fontsize=11, weight="bold", transform=axt.transAxes))
    for (te, tx) in reversed(ultimos):
        y0 -= 0.045
        mm_, ss_ = divmod(int(te), 60)
        alpha = 1.0 if t - te < 20 else 0.55
        dyn.append(axt.text(0.02, y0, f"{mm_:02d}:{ss_:02d}  {tx}", fontsize=9.2, transform=axt.transAxes, alpha=alpha, wrap=True))
    y0 = 0.17
    for (fc, ec, txt) in (("#c9a26b", "k", "pallet vacío"), ("#e8d3a6", "#8a6a30", "cartón sobre el pallet"),
                          ("#888", "k", "pallet lleno (color = celda)"), ("white", "#c0392b", "carro del robot aéreo")):
        dyn.append(axt.add_patch(Rectangle((0.02, y0), 0.05, 0.025, fc=fc, ec=ec, transform=axt.transAxes)))
        dyn.append(axt.text(0.09, y0 + 0.004, txt, fontsize=9.5, transform=axt.transAxes))
        y0 -= 0.035
    fig.savefig(OUT / f"f_{fi:05d}.png")
    if fi % 200 == 0:
        print("cuadro", fi, "/", n_fr, flush=True)
