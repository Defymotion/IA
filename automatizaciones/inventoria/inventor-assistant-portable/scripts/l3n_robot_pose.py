"""Celda A (archivo propio Celda_A_L3N.iam): deja el KUKA en una pose válida de robot de 4 ejes y el gripper colgado
de la brida.

El robot armado de ADECO (KUKA-KR_140_R3200_2_PA-ASM, original: no se toca) tiene la muñeca girada 46° (la brida no
mira hacia abajo: "robot torcido") y el gripper había quedado suelto. Igual que la escena de simulación
(armar_l3n.py / celda_kin.py): se oculta el robot armado y se ponen sus 5 eslabones sueltos (IA_Robot_V01..V05) con
la muñeca corregida a horizontal (phi0), en la pose pedida, y el gripper en la brida con el largo a lo largo de X.

Pose por defecto: TOMA sobre la cinta interna (7 cajas al final de la cinta, palas 15 mm sobre la banda). La IK
(q1, q2, q3) se resuelve por Gauss-Newton sobre la posición de la brida; q6 = -q1 deja el gripper a lo largo de X.
Uso: python l3n_robot_pose.py [--q q1,q2,q3,q6] [--sobre-banda 15]
"""
import json
import math
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import inventor_mcp as inv  # noqa: E402
import celda_kin as K  # noqa: E402

S = inv._safe
CELDA = Path(r"C:\DEFYMOTION\L3N\Celdas_IA\Celda_A_L3N.iam")
BRIDA_G = (387.0, 546.0, -245.2)            # centro de la cara de montaje (local del gripper generado)
R_WD = [[0, 1, 0], [0, 0, -1], [-1, 0, 0]]  # local gripper -> mundo con q1+q6 = 0 (largo a lo largo de X)
Y_BANDA = 800.0
Z_EJE = -36697.0 + 35622.3                  # eje de la cinta interna (local de la celda)
SOBRE = float(sys.argv[sys.argv.index("--sobre-banda") + 1]) if "--sobre-banda" in sys.argv else 15.0
Q_MAN = [float(v) for v in sys.argv[sys.argv.index("--q") + 1].split(",")] if "--q" in sys.argv else None
app = inv._inventor(start_if_needed=False)
tg = app.TransientGeometry
log = {"avisos": []}


def mmake(M):
    m = tg.CreateMatrix()
    m.SetCoordinateSystem(tg.CreatePoint(M[0][3] / 10, M[1][3] / 10, M[2][3] / 10),
                          tg.CreateVector(M[0][0], M[1][0], M[2][0]), tg.CreateVector(M[0][1], M[1][1], M[2][1]),
                          tg.CreateVector(M[0][2], M[1][2], M[2][2]))
    return m


def mread(m):
    return [[m.Cell(r, c) * (10 if (c == 4 and r < 4) else 1) for c in range(1, 5)] for r in range(1, 5)]


def caja(o):
    b = o.RangeBox
    return [round(v * 10, 1) for v in (b.MinPoint.X, b.MinPoint.Y, b.MinPoint.Z, b.MaxPoint.X, b.MaxPoint.Y, b.MaxPoint.Z)]


def apply(M, p):
    return [sum(M[i][k] * p[k] for k in range(3)) + M[i][3] for i in range(3)]


def resolver3(A, b):
    """Sistema 3x3 por eliminación de Gauss con pivoteo."""
    M = [A[i][:] + [b[i]] for i in range(3)]
    for c in range(3):
        p = max(range(c, 3), key=lambda r: abs(M[r][c]))
        M[c], M[p] = M[p], M[c]
        if abs(M[c][c]) < 1e-12:
            raise ValueError("Jacobiano singular")
        for r in range(3):
            if r != c:
                f = M[r][c] / M[c][c]
                M[r] = [M[r][k] - f * M[c][k] for k in range(4)]
    return [M[i][3] / M[i][i] for i in range(3)]


app.SilentOperation = True
try:
    cel = next((d for d in inv._items(app.Documents) if S(lambda: Path(d.FullFileName).resolve() == CELDA.resolve(), False)), None)
    if cel is None or not S(lambda: cel.Views.Count, 0):
        cel = app.Documents.Open(str(CELDA), True)          # con ventana: Visible no "prende" sin ventana
    cel.Activate()
    cd = cel.ComponentDefinition
    occs = {o.Name: o for o in inv._items(cd.Occurrences)}
    kuka = next(o for n, o in occs.items() if n.startswith("KUKA"))
    g = next(o for n, o in occs.items() if n.startswith("IA_Gripper"))
    cin = next(o for n, o in occs.items() if n.startswith("Cinta_Interna"))
    T = mread(kuka.Transformation)
    M, files = {}, {}
    for o in inv._items(kuka.Definition.Occurrences):
        k = "V0" + o.Name.split("_V0")[-1][:1]
        M[k] = mread(o.Transformation)
        files[k] = o.Definition.Document.FullFileName
    # ---- muñeca horizontal (phi0) y gripper en la brida con q = 0
    n = [-M["V05"][i][2] for i in range(3)]
    phi0 = -90.0 - math.degrees(math.atan2(n[1], n[0]))
    F0 = apply(K.rot_z(phi0, K.W), apply(M["V05"], (1850.0, 0.0, 1745.0)))
    Rr = [row[:3] for row in T[:3]]
    Rt = [[Rr[j][i] for j in range(3)] for i in range(3)]
    R_G = [[sum(Rt[i][k] * R_WD[k][j] for k in range(3)) for j in range(3)] for i in range(3)]
    t_g = [F0[i] - sum(R_G[i][k] * BRIDA_G[k] for k in range(3)) for i in range(3)]
    cfg = {"T_robot": T, "phi0": phi0, "M": {k: M[k] for k in ("V02", "V03", "V04", "V05")}, "brida_robot_q0": F0,
           "M_gripper_q0": [R_G[0] + [t_g[0]], R_G[1] + [t_g[1]], R_G[2] + [t_g[2]], [0, 0, 0, 1]]}
    log["phi0"] = round(phi0, 3)
    log["normal_brida_armado"] = [round(v, 4) for v in n]

    def brida(q):
        T1 = K.rot_y(q[0])
        T3 = K.mmul(K.mmul(T1, K.rot_z(q[1], K.A2)), K.rot_z(q[2], K.A3))
        Tg = K.mmul(K.mmul(T3, K.rot_z(phi0 - q[1] - q[2], K.W)), K.inv_rt(K.rot_z(phi0, K.W)))
        return apply(K.mmul(T, Tg), F0)

    # ---- objetivo: gripper sobre las últimas 7 cajas de la cinta interna
    bg = g.Definition.RangeBox
    gl = [bg.MinPoint.X * 10, bg.MinPoint.Y * 10, bg.MinPoint.Z * 10, bg.MaxPoint.X * 10, bg.MaxPoint.Y * 10, bg.MaxPoint.Z * 10]
    alto = gl[5] - BRIDA_G[2]                                # de la cara de montaje a la punta de las palas
    largo = gl[4] - gl[1]
    d_loc = ((gl[0] + gl[3]) / 2 - BRIDA_G[0], (gl[1] + gl[4]) / 2 - BRIDA_G[1], 0.0)
    d_w = [sum(R_WD[i][k] * d_loc[k] for k in range(3)) for i in range(3)]   # centro del gripper respecto de la brida
    cc = caja(cin)
    x_fin = cc[3] - 100.0 - 30.0                             # fin útil de la banda (eje de cabeza) con margen
    centro = [x_fin - largo / 2, Y_BANDA + SOBRE + alto, Z_EJE]
    objetivo = [centro[0] - d_w[0], centro[1], centro[2] - d_w[2]]
    log["gripper_local"] = {"caja": [round(v, 1) for v in gl], "alto_montaje_a_palas": round(alto, 1), "largo": round(largo, 1)}
    log["objetivo_brida"] = [round(v, 1) for v in objetivo]
    if Q_MAN:
        q = Q_MAN[:3]
        q6 = Q_MAN[3] if len(Q_MAN) > 3 else -q[0]
    else:
        q = [0.0, 0.0, 0.0]
        for it in range(60):
            f = brida(q)
            r = [f[i] - objetivo[i] for i in range(3)]
            if math.sqrt(sum(v * v for v in r)) < 0.2:
                break
            J = [[0.0] * 3 for _ in range(3)]
            for j in range(3):
                qq = q[:]
                qq[j] += 0.01
                fj = brida(qq)
                for i in range(3):
                    J[i][j] = (fj[i] - f[i]) / 0.01
            dq = resolver3(J, [-v for v in r])
            m = max(abs(v) for v in dq)
            if m > 10:
                dq = [v * 10 / m for v in dq]
            q = [q[i] + dq[i] for i in range(3)]
        log["ik_iter"] = it
        q6 = -q[0]
    f = brida(q)
    log["q"] = [round(v, 3) for v in q] + [round(q6, 3)]
    log["residuo_mm"] = round(math.sqrt(sum((f[i] - objetivo[i]) ** 2 for i in range(3))), 2)
    if any(abs(v) > 120 for v in q[1:]):
        log["avisos"].append("ángulos q2/q3 grandes: revisar la pose en la foto")
    P = K.poses(cfg, q[0], q[1], q[2], q6)
    P["V01"] = K.mmul(T, M["V01"])
    # ---- eslabones sueltos (se reutilizan si ya están) y robot armado oculto
    for k in ("V01", "V02", "V03", "V04", "V05"):
        nm = f"IA_Robot_{k}"
        o = occs.get(nm)
        if o is None:
            o = cd.Occurrences.Add(files[k], mmake(P[k]))
            S(lambda: setattr(o, "Name", nm))
        else:
            S(lambda: setattr(o, "Grounded", False))
            o.SetTransformWithoutConstraints(mmake(P[k]))
        S(lambda: setattr(o, "Grounded", True))
        S(lambda: setattr(o, "Visible", True))
    S(lambda: setattr(kuka, "Visible", False))
    log["kuka_armado_visible"] = S(lambda: bool(kuka.Visible))
    S(lambda: setattr(g, "Grounded", False))
    g.SetTransformWithoutConstraints(mmake(P["gripper"]))
    S(lambda: setattr(g, "Grounded", True))
    cel.Update()
    v5 = next(o for o in inv._items(cd.Occurrences) if o.Name == "IA_Robot_V05")
    Mv = mread(v5.Transformation)
    log["normal_brida_nueva"] = [round(-Mv[i][2], 4) for i in range(3)]
    log["brida_nueva"] = [round(v, 1) for v in apply(Mv, (1850.0, 0.0, 1745.0))]
    log["gripper_caja"] = caja(g)
    log["cinta_interna_caja"] = cc
    cel.Save()
finally:
    S(lambda: setattr(app, "SilentOperation", False))
print(json.dumps(log, ensure_ascii=False, indent=1))
