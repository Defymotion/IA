"""Recursos compartidos: robot aéreo (pallets vacíos para A y B), giratorias A y B, línea en Z (B -> A), línea en X hasta la
envolvedora MP402 (una a la vez) y salida. Reservas simples en orden de pedido."""
import math

from comun import ease, ease5, lerp, trapecio, tr

V_PAL, A_PAL = 450.0, 300.0          # transporte de pallets
T_GIRO = 3.0
T_ENV = 30.0
X_MP = 9865.8
X_ESPERA_MP = 7100.0                 # espera antes de la envolvedora si está ocupada
X_SALIDA_FIN = 12600.0
Y_LINEA = 626.8
Y_MP = 501.3


class Aereo:
    """Robot aéreo: z del carro y dy de la barra; pallets de las pilas 1 y 2 (de arriba hacia abajo)."""

    def __init__(self, aereo, z_park=-33039.0):
        self.Z_PARK = z_park
        self.X = aereo["Pila1_pallet_10"]["M"][0][3]
        self.pilas = []
        for p in (1, 2):
            for k in range(10, 0, -1):
                e = aereo[f"Pila{p}_pallet_{k}"]
                self.pilas.append({"nombre": f"Pila{p}_pallet_{k}", "z": e["M"][2][3], "y_top": e["M"][1][3] + 152.0,
                                   "M": e["M"]})
        self.sig = 0
        self.AER = []
        self.libre = 0.0

    def tramo(self, t0, dur, campo, a, b):
        self.AER.append((t0, t0 + dur, campo, a, b))
        return t0 + dur

    def val(self, campo, t, inicial):
        v = inicial
        for (t0, t1, c, a, b) in self.AER:
            if c != campo:
                continue
            if t >= t1:
                v = b
            elif t >= t0:
                v = lerp(a, b, ease5((t - t0) / (t1 - t0)))
        return v

    def _dur_z(self, d):
        return max(1.2, trapecio(abs(d), 1200.0, 700.0)[0])

    def suministro(self, t_req, z_dep, y_dep_base):
        """Toma el siguiente pallet de las pilas y lo deja sobre la cama de ingreso (z_dep). Devuelve tiempos."""
        p = self.pilas[self.sig]
        self.sig += 1
        t = max(t_req, self.libre)
        z0 = self.val("z", t, self.Z_PARK)
        t = self.tramo(t, self._dur_z(p["z"] - z0), "z", z0, p["z"])
        dy_pick = p["y_top"] - 1680.0
        t = self.tramo(t, 1.1, "dy", 0.0, dy_pick)
        t_ag = t + 0.3
        t = self.tramo(t_ag, 1.1, "dy", dy_pick, 0.0)
        t = self.tramo(t + 0.1, self._dur_z(z_dep - p["z"]), "z", p["z"], z_dep)
        dy_dep = y_dep_base - 1528.0
        t = self.tramo(t, 2.4, "dy", 0.0, dy_dep)
        t_su = t + 0.3
        t = self.tramo(t_su, 2.0, "dy", dy_dep, 0.0)
        t_fin = self.tramo(t + 0.2, self._dur_z(self.Z_PARK - z_dep), "z", z_dep, self.Z_PARK)
        self.libre = t_fin
        return {"pila": p, "t_agarra": t_ag, "t_suelta": t_su, "t_libre": t_fin}


class Giratoria:
    """Modo 0: rodillos para transportar en Z; 1: en X (hacia la celda / la línea)."""

    def __init__(self, nombre, x, z, modo0=0):
        self.n, self.x, self.z = nombre, x, z
        self.ev = []          # (t0, t1, de, a)
        self.modo = modo0
        self.reservas = []    # (t0, t1)

    def girar(self, t, a):
        if a == self.modo:
            return t
        self.ev.append((t, t + T_GIRO, self.modo, a))
        self.modo = a
        return t + T_GIRO

    def frac(self, t):
        f = float(self.ev[0][2]) if self.ev else float(self.modo)
        for (t0, t1, de, a) in self.ev:
            if t >= t1:
                f = float(a)
            elif t >= t0:
                f = lerp(float(de), float(a), ease5((t - t0) / (t1 - t0)))
        return f

    def libre_desde(self, t):
        return max([t] + [r[1] for r in self.reservas if r[1] > t])


def giro_pallet(info, t, grados_por_modo=90.0):
    """Ángulo (grados, convención roty) que acumuló el pallet por los giros de mesa hechos con él arriba."""
    ang = 0.0
    for (g, i) in (info or {}).get("giros", []):
        t0, t1, de, a = g.ev[i]
        if t <= t0:
            continue
        u = 1.0 if t >= t1 else ease5((t - t0) / (t1 - t0))
        ang += grados_por_modo * (a - de) * u
    return ang


class Movimiento:
    """Trayecto de un pallet por tramos rectos (x, z) con perfil trapezoidal por tramo y altura de apoyo por función."""

    def __init__(self):
        self.tramos = []      # (t0, T, pos(t), p0, p1)

    def agregar(self, t0, p0, p1, v=V_PAL, a=A_PAL):
        D = math.dist(p0, p1)
        T, pos = trapecio(D, v, a)
        self.tramos.append((t0, T, pos, p0, p1, D))
        return t0 + T

    def xz(self, t):
        if not self.tramos:
            return None
        if t < self.tramos[0][0]:
            return self.tramos[0][3]
        last = self.tramos[0][3]
        for (t0, T, pos, p0, p1, D) in self.tramos:
            if t < t0:
                return last
            if t <= t0 + T:
                u = pos(t - t0) / D if D > 0 else 1.0
                return (lerp(p0[0], p1[0], u), lerp(p0[1], p1[1], u))
            last = p1
        return last

    def t_de_x(self, x, eje=0):
        """Primer instante en que la coordenada (0: x, 1: z) llega a x (búsqueda)."""
        for (t0, T, pos, p0, p1, D) in self.tramos:
            a, b = p0[eje], p1[eje]
            if (a - x) * (b - x) <= 0 and abs(b - a) > 1e-6:
                lo, hi = 0.0, T
                for _ in range(60):
                    m = (lo + hi) / 2
                    u = pos(m) / D
                    if (lerp(a, b, u) - x) * (b - a) < 0:
                        lo = m
                    else:
                        hi = m
                return t0 + hi
        return None


class Linea:
    def __init__(self, gir_A, gir_B, z_x=None):
        self.gA, self.gB = gir_A, gir_B
        self.z_x = gir_A.z if z_x is None else z_x      # Z de la línea en X (la de la estación de la celda A)
        self.mp_libre = 0.0
        self.envueltos = []        # (t_w0, t_w1, celda, mov)
        self.salidas = {}          # clave -> dict

    def salida(self, clave, celda, t_lleno, pal_o, y_apoyo):
        """Planifica la salida del pallet lleno de 'celda' desde la estación pal_o. Devuelve el dict con el movimiento,
        el instante en que la estación queda libre y los del envuelto."""
        mov = Movimiento()
        info = {"celda": celda, "mov": mov, "T_lleno": t_lleno, "giros": []}   # giros de mesa CON el pallet arriba
        t = t_lleno + 0.3
        p_est = (pal_o[0], pal_o[2])
        if celda == "A":
            t = max(t, self.gA.libre_desde(t))
            t = self.gA.girar(t, 1) + 0.6
            t_ini = t
            pA = (self.gA.x, self.gA.z)
            # hasta la espera de la envolvedora o derecho si está libre a tiempo
            t_mp = mov.agregar(t, p_est, (X_ESPERA_MP, self.z_x))
            info["T_mov0"] = t_ini
            t_libre_gir = mov.t_de_x(self.gA.x + 990.0 + 620.0, 0)
            info["T_estacion_libre"] = mov.t_de_x(pal_o[0] + 1350.0, 0)
            self.gA.reservas.append((t_ini - 3.6, t_libre_gir))
            self.gA.girar(t_libre_gir + 0.3, 0)
            t = t_mp
            pos_esp = (X_ESPERA_MP, self.z_x)
        else:
            gB = self.gB
            t = gB.girar(t, 1) + 0.6
            info["T_mov0"] = t
            t = mov.agregar(t, p_est, (gB.x, gB.z))
            info["T_estacion_libre"] = mov.t_de_x(pal_o[0] + 1350.0, 0) or t
            n0 = len(gB.ev)
            t = gB.girar(t + 0.3, 0) + 0.3                 # la mesa B gira con el pallet arriba
            if len(gB.ev) > n0:
                info["giros"].append((gB, n0))
            # por la línea en Z hasta la giratoria A (en modo Z y libre)
            pA = (self.gA.x, self.z_x)
            D = abs(pA[1] - gB.z)
            T_z = trapecio(D, V_PAL, A_PAL)[0]
            t_llega = t + T_z
            ok = self.gA.libre_desde(t_llega - 6.0)
            if ok > t_llega - 6.0:
                t += ok - (t_llega - 6.0)
            # la giratoria A tiene que estar en Z al llegar
            if self.gA.modo != 0:
                self.gA.girar(max(t, self.gA.libre_desde(t)), 0)
            t_in = t
            t = mov.agregar(t, (gB.x, gB.z), pA)
            gB.girar(t_in + 4.0, 1)          # B vuelve a recibir de su celda
            n0 = len(self.gA.ev)
            t = self.gA.girar(t + 0.3, 1) + 0.6            # la mesa A gira con el pallet de B arriba
            if len(self.gA.ev) > n0:
                info["giros"].append((self.gA, n0))
            t2 = mov.agregar(t, pA, (X_ESPERA_MP, pA[1]))
            t_libre_gir = mov.t_de_x(self.gA.x + 990.0 + 620.0, 0)
            self.gA.reservas.append((t_in, t_libre_gir))
            self.gA.girar(t_libre_gir + 0.3, 0)
            t = t2
            pos_esp = (X_ESPERA_MP, pA[1])
        # envolvedora (una a la vez)
        t = max(t, self.mp_libre - trapecio(X_MP - X_ESPERA_MP, V_PAL, A_PAL)[0])
        t_arr = mov.agregar(t, pos_esp, (X_MP, pos_esp[1]))
        info["T_arr"] = t_arr
        info["T_w0"] = t_arr + 1.0
        info["T_w1"] = info["T_w0"] + T_ENV
        info["T_s0"] = info["T_w1"] + 1.5
        info["T_s1"] = mov.agregar(info["T_s0"], (X_MP, pos_esp[1]), (X_SALIDA_FIN, pos_esp[1]))
        self.mp_libre = info["T_s0"] + 4.0
        self.envueltos.append((info["T_w0"], info["T_w1"], celda, clave))
        self.salidas[clave] = info
        return info
