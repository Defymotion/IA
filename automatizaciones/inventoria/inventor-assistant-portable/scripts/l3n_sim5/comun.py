"""Utilidades comunes del planificador v5 (Python puro): álgebra 4x4, perfiles, segmentos de movimiento con
superposición (blending tipo C_PTP), trayectoria del robot y choques en planta (SAT) y en 3D (puntos vs caja)."""
import math

import celda_kin as K


def I4():
    return [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]


def mm(P, Q):
    return K.mmul(P, Q)


def inv(M):
    return K.inv_rt(M)


def tr(x, y, z):
    return K.tr(x, y, z)


def roty(deg, cx=0.0, cz=0.0):
    return K.rot_y(deg, (cx, cz))


def apply(M, p):
    return [sum(M[i][k] * p[k] for k in range(3)) + M[i][3] for i in range(3)]


def lerp(a, b, u):
    return a + (b - a) * u


def ease(u):
    u = max(0.0, min(1.0, u))
    return u * u * (3 - 2 * u)


def ease5(u):
    u = max(0.0, min(1.0, u))
    return u * u * u * (u * (6 * u - 15) + 10)


def comp(M):
    return [round(M[i][j], 4 if j < 3 else 2) for i in range(3) for j in range(4)]


def yaw_of(M):
    return math.degrees(math.atan2(-M[2][0], M[0][0]))


def dpsi_corto(a, b):
    return ((b - a) + 180.0) % 360.0 - 180.0


def box_M(R, c):
    return [R[0] + [c[0]], R[1] + [c[1]], R[2] + [c[2]], [0, 0, 0, 1]]


def bb_de(M, xs, ys, zs):
    pts = [apply(M, (x, y, z)) for x in xs for y in ys for z in zs]
    return [min(p[i] for p in pts) for i in range(3)] + [max(p[i] for p in pts) for i in range(3)]


# ------------------------------------------------------------------ perfiles
def trapecio(D, v=450.0, a=300.0):
    """(T, pos(t)) para recorrer D con velocidad máx v y aceleración a."""
    if D <= 1e-9:
        return 0.0, (lambda t: 0.0)
    ta = v / a
    da = 0.5 * a * ta * ta
    if 2 * da > D:
        ta = math.sqrt(D / a)
        T = 2 * ta

        def pos(t):
            t = max(0.0, min(T, t))
            return 0.5 * a * t * t if t < ta else D - 0.5 * a * (T - t) ** 2
        return T, pos
    T = 2 * ta + (D - 2 * da) / v

    def pos(t):
        t = max(0.0, min(T, t))
        if t < ta:
            return 0.5 * a * t * t
        if t < T - ta:
            return da + v * (t - ta)
        return D - 0.5 * a * (T - t) ** 2
    return T, pos


# ------------------------------------------------------------------ segmentos y trayectoria con superposición
class Seg:
    """Movimiento del gripper: pose (psi, origen) de a hacia b en [t0, t1] con perfil ease5. giro = grados con signo
    (si es None se toma el giro más corto). En la trayectoria los desplazamientos de segmentos superpuestos se suman
    (blending: el camino corta la esquina en los puntos de paso, como un C_PTP)."""

    def __init__(self, t0, dur, a, b, arco=0.0, nota="", giro=None):
        self.t0, self.t1, self.a, self.b, self.arco, self.nota = t0, t0 + dur, a, b, arco, nota
        self.giro = giro if giro is not None else dpsi_corto(a[0], b[0])

    def u(self, t):
        return ease5((t - self.t0) / max(1e-6, self.t1 - self.t0))

    def pose(self, t):
        u = self.u(t)
        (pa, xa), (pb, xb) = self.a, self.b
        p = [lerp(xa[i], xb[i], u) for i in range(3)]
        p[1] += self.arco * math.sin(math.pi * u)
        return pa + self.giro * u, p

    def desplaza(self, t):
        """(dpsi, dx, dy, dz) acumulado hasta t."""
        u = self.u(t)
        (pa, xa), (pb, xb) = self.a, self.b
        return self.giro * u, [(xb[i] - xa[i]) * u + (self.arco * math.sin(math.pi * u) if i == 1 else 0.0) for i in range(3)]

    def desplaza_total(self):
        (pa, xa), (pb, xb) = self.a, self.b
        return self.giro, [xb[i] - xa[i] for i in range(3)]


class Trayectoria:
    """Suma de segmentos encadenados (con posible superposición). pose(t) -> (psi, origen)."""

    def __init__(self, segs):
        self.segs = sorted(segs, key=lambda s: s.t0)
        self.p0 = self.segs[0].a if self.segs else (0.0, [0.0, 0.0, 0.0])
        # acumulados "cerrados" (segmentos ya terminados) para evaluar rápido en orden creciente de t
        self.cum = []
        psi, x = self.p0[0], list(self.p0[1])
        for s in self.segs:
            self.cum.append((psi, list(x)))
            g, d = s.desplaza_total()
            psi += g
            x = [x[i] + d[i] for i in range(3)]
        self.fin = (psi, x)
        self.t1s = [s.t1 for s in self.segs]
        self.t0s = [s.t0 for s in self.segs]
        # para cada segmento, el primer índice que todavía puede estar activo
        self.maxt1 = []
        m = -1e18
        for s in self.segs:
            m = max(m, s.t1)
            self.maxt1.append(m)

    def pose(self, t):
        import bisect
        if not self.segs:
            return self.p0
        k = bisect.bisect_right(self.t0s, t)       # segmentos con t0 <= t: 0..k-1
        if k == 0:
            return self.p0[0], list(self.p0[1])
        # el primer segmento no terminado entre 0..k-1
        j = k - 1
        while j > 0 and self.segs[j - 1].t1 > t:
            j -= 1
        psi, x = self.cum[j][0], list(self.cum[j][1])
        for s in self.segs[j:k]:
            g, d = s.desplaza(t)
            psi += g
            x = [x[i] + d[i] for i in range(3)]
        return psi, x

    def activo(self, t):
        """Notas de los segmentos activos en t."""
        return [s.nota for s in self.segs if s.t0 <= t <= s.t1]


# ------------------------------------------------------------------ choques
def prisma(M, xs, ys, zs):
    """Caja local girada sólo en planta: (polígono XZ, y_min, y_max, AABB)."""
    pts = [apply(M, (x, y, z)) for x in xs for y in ys for z in zs]
    ymin, ymax = min(p[1] for p in pts), max(p[1] for p in pts)
    pl = []
    for p in pts:
        q_ = (round(p[0], 3), round(p[2], 3))
        if q_ not in pl:
            pl.append(q_)
    cx, cz = sum(p[0] for p in pl) / len(pl), sum(p[1] for p in pl) / len(pl)
    pl.sort(key=lambda p: math.atan2(p[1] - cz, p[0] - cx))
    bb = [min(p[0] for p in pts), ymin, min(p[2] for p in pts), max(p[0] for p in pts), ymax, max(p[2] for p in pts)]
    return pl, ymin, ymax, bb


def sat(pl, c, h):
    """Polígono convexo (planta) contra el rectángulo [c0,c2]-[c3,c5] agrandado h."""
    rx0, rz0, rx1, rz1 = c[0] - h, c[2] - h, c[3] + h, c[5] + h
    if max(p[0] for p in pl) <= rx0 or min(p[0] for p in pl) >= rx1 or max(p[1] for p in pl) <= rz0 or min(p[1] for p in pl) >= rz1:
        return False
    rect = [(rx0, rz0), (rx1, rz0), (rx1, rz1), (rx0, rz1)]
    for i in range(len(pl)):
        ex, ez = pl[(i + 1) % len(pl)][0] - pl[i][0], pl[(i + 1) % len(pl)][1] - pl[i][1]
        nx, nz = -ez, ex
        a_ = [p[0] * nx + p[1] * nz for p in pl]
        b_ = [p[0] * nx + p[1] * nz for p in rect]
        if max(a_) <= min(b_) or max(b_) <= min(a_):
            return False
    return True


def puntos_en_caja(pts, c, h):
    """¿Algún punto (lista de (x,y,z)) dentro de la caja c agrandada h?"""
    x0, y0, z0, x1, y1, z1 = c[0] - h, c[1] - h, c[2] - h, c[3] + h, c[4] + h, c[5] + h
    for p in pts:
        if x0 < p[0] < x1 and y0 < p[1] < y1 and z0 < p[2] < z1:
            return True
    return False
