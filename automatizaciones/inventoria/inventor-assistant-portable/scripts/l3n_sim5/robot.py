"""Robot KUKA de 4 ejes útiles (A1, A2, A3, A6; la brida queda horizontal) con el gripper colgado: IK con codo arriba,
poses de eslabones y modelo de tiempos con las velocidades de catálogo."""
import math

import celda_kin as K
from comun import apply, mm, roty, yaw_of, ease5, dpsi_corto

T_ACC = (0.45, 0.40, 0.40, 0.25)          # s hasta la velocidad máxima (estimado; KUKA no publica aceleraciones)
CODO_MIN = 0.12
# límites de ejes del KR PA en la convención de celda_kin (q = 0 en la pose del CAD: brazo vertical, antebrazo
# horizontal = A2 -90°, A3 +90° de KUKA): A2 -140..-5 -> q2 -85..+50; A3 0..155 -> q3 -65..+90
Q2_LIM = (-85.0, 50.0)
Q3_LIM = (-65.0, 90.0)


def en_limites(q):
    return Q2_LIM[0] <= q[1] <= Q2_LIM[1] and Q3_LIM[0] <= q[2] <= Q3_LIM[1]


class Robot:
    def __init__(self, nombre, T_rob, links_rel, brida_g, R_wd, vel, gripper_local):
        """links_rel: {"V02": M_rel, ...} relativas al ensamble del robot; brida_g: punto de la brida en coordenadas del
        gripper; R_wd: rotación gripper respecto de la muñeca; vel: (A1, A2, A3, A6) °/s."""
        self.nombre, self.T_ROB, self.vel = nombre, T_rob, vel
        self.BRIDA_G = brida_g
        self.GL = gripper_local
        v5 = links_rel["V05"]
        nb = [-v5[i][2] for i in range(3)]
        self.PHI0 = -90.0 - math.degrees(math.atan2(nb[1], nb[0]))
        F_orig = apply(v5, (1850.0, 0.0, 1745.0))
        self.F0 = apply(K.rot_z(self.PHI0, K.W), F_orig)
        Rr = [row[:3] for row in T_rob[:3]]
        Rt = [[Rr[j][i] for j in range(3)] for i in range(3)]
        R_G = [[sum(Rt[i][k] * R_wd[k][j] for k in range(3)) for j in range(3)] for i in range(3)]
        t_g = [self.F0[i] - sum(R_G[i][k] * brida_g[k] for k in range(3)) for i in range(3)]
        self.CFG = {"T_robot": T_rob, "phi0": self.PHI0, "M": {k: links_rel[k] for k in ("V02", "V03", "V04", "V05")},
                    "brida_robot_q0": self.F0,
                    "M_gripper_q0": [R_G[0] + [t_g[0]], R_G[1] + [t_g[1]], R_G[2] + [t_g[2]], [0, 0, 0, 1]]}
        P0 = self.poses([0, 0, 0, 0])
        self.MG0 = P0["gripper"]
        self.PSI_G0 = yaw_of(self.MG0)
        self.codo_abajo = 0
        self.base_xz = (T_rob[0][3], T_rob[2][3])

    # ---- cinemática
    def brida(self, q):
        T1 = K.rot_y(q[0])
        T3 = K.mmul(K.mmul(T1, K.rot_z(q[1], K.A2)), K.rot_z(q[2], K.A3))
        Tg = K.mmul(K.mmul(T3, K.rot_z(self.PHI0 - q[1] - q[2], K.W)), K.inv_rt(K.rot_z(self.PHI0, K.W)))
        return apply(K.mmul(self.T_ROB, Tg), self.F0)

    def poses(self, q):
        return K.poses(self.CFG, q[0], q[1], q[2], q[3])

    @staticmethod
    def _solve3(A, b):
        M = [A[i][:] + [b[i]] for i in range(3)]
        for c in range(3):
            p = max(range(c, 3), key=lambda r: abs(M[r][c]))
            M[c], M[p] = M[p], M[c]
            for r in range(3):
                if r != c:
                    f = M[r][c] / M[c][c]
                    M[r] = [M[r][k] - f * M[c][k] for k in range(4)]
        return [M[i][3] / M[i][i] for i in range(3)]

    def ik(self, target, q0):
        q = list(q0[:3])
        e = 1e9
        for _ in range(150):
            f = self.brida(q)
            r = [f[i] - target[i] for i in range(3)]
            e = math.sqrt(sum(v * v for v in r))
            if e < 0.05:
                break
            J = [[0.0] * 3 for _ in range(3)]
            for j in range(3):
                qq = q[:]
                qq[j] += 0.01
                fj = self.brida(qq)
                for i in range(3):
                    J[i][j] = (fj[i] - f[i]) / 0.01
            try:
                dq = self._solve3(J, [-v for v in r])
            except ZeroDivisionError:
                break
            m = max(abs(v) for v in dq)
            if m > 8:
                dq = [v * 8 / m for v in dq]
            q = [q[i] + dq[i] for i in range(3)]
        return q, e

    @staticmethod
    def codo(q):
        T2 = K.rot_z(q[1], K.A2)
        T3 = K.mmul(T2, K.rot_z(q[2], K.A3))
        a3 = apply(T2, (K.A3[0], K.A3[1], 0.0))
        w = apply(T3, (K.W[0], K.W[1], 0.0))
        ax, ay = w[0] - K.A2[0], w[1] - K.A2[1]
        bx, by = a3[0] - K.A2[0], a3[1] - K.A2[1]
        return (ax * by - ay * bx) / (math.hypot(ax, ay) * math.hypot(bx, by))

    def q_para(self, Mg, qprev):
        F = apply(Mg, self.BRIDA_G)
        q3, e = self.ik(F, qprev)
        valido = lambda qq: self.codo(qq) >= CODO_MIN and en_limites(qq)
        if e > 0.2 or not valido(q3):
            mejor = (q3, e) if valido(q3) else (q3, 1e9)
            a1 = math.degrees(math.atan2(-(F[2] - self.T_ROB[2][3]), F[0] - self.T_ROB[0][3]))
            for seed in ([qprev[0], -40.0, 90.0], [qprev[0], -20.0, 30.0], [qprev[0], -40.0, 40.0], [qprev[0], 0.0, 0.0],
                         [qprev[0], -60.0, 60.0], [qprev[0], 20.0, -20.0], [qprev[0], -20.0, 60.0], [qprev[0], 0.0, 20.0],
                         [qprev[0], -50.0, 70.0]):
                q3b, eb = self.ik(F, seed)
                if valido(q3b) and eb < mejor[1]:
                    mejor = (q3b, eb)
                if mejor[1] < 0.05:
                    break
            if mejor[1] < 1e8:
                q3, e = mejor
            else:
                self.codo_abajo += 1
        psi = yaw_of(Mg)
        q6 = psi - self.PSI_G0 - q3[0]
        while q6 - qprev[3] > 180:
            q6 -= 360
        while q6 - qprev[3] < -180:
            q6 += 360
        return [q3[0], q3[1], q3[2], q6], e

    def gripper_pose(self, psi, pos):
        R = mm(roty(psi - self.PSI_G0), [self.MG0[0][:3] + [0], self.MG0[1][:3] + [0], self.MG0[2][:3] + [0], [0, 0, 0, 1]])
        R[0][3], R[1][3], R[2][3] = pos
        return R

    def alcanza(self, p, q0=(0.0, -40.0, 90.0, 0.0)):
        n0 = self.codo_abajo
        q, e = self.q_para(self.gripper_pose(*p), list(q0) if q0 is not None else [0.0, -40.0, 90.0, 0.0])
        self.codo_abajo = n0
        return e < 0.3 and self.codo(q) >= CODO_MIN + 0.03 and en_limites(q)

    # ---- tiempos
    def duracion(self, a, b, giro, q0=None, v_lin=2000.0, t_min=0.15, n=8):
        """Duración del tramo a->b (perfil ease5) que respeta las velocidades y aceleraciones de los ejes y una
        velocidad cartesiana máxima v_lin (mm/s). Devuelve (T, q_final)."""
        q = list(q0) if q0 is not None else [0.0, -40.0, 90.0, 0.0]
        qs = []
        for i in range(n + 1):
            u = i / n
            p = [a[1][k] + (b[1][k] - a[1][k]) * u for k in range(3)]
            q, _ = self.q_para(self.gripper_pose(a[0] + giro * u, p), q)
            qs.append(q)
        # derivadas máximas dq/du por eje (diferencias)
        dmax = [0.0] * 4
        for i in range(n):
            for k in range(4):
                dmax[k] = max(dmax[k], abs(qs[i + 1][k] - qs[i][k]) * n)
        T = t_min
        for k in range(4):
            v = self.vel[k]
            acc = v / T_ACC[k]
            T = max(T, 1.875 * dmax[k] / v, math.sqrt(5.774 * dmax[k] / acc) if dmax[k] > 0 else 0.0)
        L = math.dist(a[1], b[1])
        T = max(T, 1.875 * L / v_lin)
        return T, qs[-1]
