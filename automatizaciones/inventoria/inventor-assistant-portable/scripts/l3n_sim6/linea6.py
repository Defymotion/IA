"""L3N sim v6 (etapa 1, layout v7): flujo de pallets de toda la línea, robot aéreo con cartones y autoelevador.
Python puro, por pasos de tiempo. Lo usan flujo6.py (vista en planta para validar) y plan6.py (escena de Inventor).

Modelo
- Zonas de acumulación (una por módulo o media cama/media T3 larga); un pallet pasa a la zona siguiente cuando está libre.
- Dispositivos con modo: giratorias B y C ('X' recibe de la celda, 'Z' manda por las camas; giran CON el pallet),
  cruz A y cruz S-11256 ('cad' cadenas en X, 'rod' rodillos en Z; cambio = subir/bajar rodillos).
- Envolvedora MP402 sobre la T2 S-11259: envuelve con la T2 S-11261 y la salida 1 vacías (barrido del brazo).
- Salida: S-11219 -> S-11226; el autoelevador retira el pallet del final de la S-11226.
- Robot aéreo (carro en Z sobre X = -10582): trae pallets vacíos de los buffers a la cama de ingreso de cada celda;
  cuando está libre, busca un cartón en el buffer de cartones (extremo sur) y lo deja sobre el pallet de arriba de un buffer.
"""
import math
import random

from_trap = None


def trapecio(D, v, a):
    """Duración y posición(t) de un perfil trapezoidal (o triangular) para recorrer D."""
    D = abs(D)
    if D < 1e-9:
        return 0.0, (lambda t: 0.0)
    ta = v / a
    if D < v * ta:                       # triangular
        ta = math.sqrt(D / a)
        T = 2 * ta

        def pos(t):
            t = max(0.0, min(T, t))
            return 0.5 * a * t * t if t < ta else D - 0.5 * a * (T - t) ** 2
        return T, pos
    T = ta + D / v

    def pos(t):
        t = max(0.0, min(T, t))
        if t < ta:
            return 0.5 * a * t * t
        if t < T - ta:
            return 0.5 * a * ta * ta + v * (t - ta)
        return D - 0.5 * a * (T - t) ** 2
    return T, pos


def ease5(u):
    u = max(0.0, min(1.0, u))
    return u * u * u * (u * (6 * u - 15) + 10)


# ---------------------------------------------------------------------------------------------- parámetros
P = {
    "V_CAD": 300.0, "A_CAD": 250.0,         # transportes de cadenas / rodillos (mm/s, mm/s²)
    "V_MESA": 420.0, "A_MESA": 300.0,       # mesas de rolos de las celdas (ingreso -> estación)
    "T_CRUZ": 2.5, "T_GIRO": 3.0,
    "T_ENV": 60.0,                          # envuelto MP402 (s)
    "T_AE_LLEGA": 30.0, "T_AE_CICLO": 90.0,   # autoelevador: llega ~30 s después y tarda 90 s entre retiros
    "T_B": 540.0, "T_C": 300.0, "JIT": 15.0,  # ciclos de las celdas B y C (s) y variación ±
    "T_A_CAJA": 2.5, "N_A": 136,            # celda A (sólo para flujo6; plan6 usa el robot real)
    "V_AER": 1200.0, "A_AER": 700.0, "V_ELEV": 600.0,
    "T_AGARRE": 0.6, "T_VACIO": 0.8,
    "T_REPO": 120.0,                        # reposición de un buffer vacío (autoelevador)
}

X_RIEL = -10582.0
Y_PAL_SUJ = 1528.0                           # base del pallet tomado por la sujeción (dy = 0)
CARTON_PILA = (-10582.0, 152.0, -54797.0)    # base de la pila de cartones (sobre un pallet)
H_PILA_CARTON, E_CARTON = 900.0, 4.0
Z_PARK = -33039.0

# estaciones de pallet de las celdas: (x, y_base, z) estación, z de descarga del aéreo, x de la giratoria
EST = {
    "A": {"est": (-8521.2589, 507.4015, -35617.0609), "z_dep": -35689.6, "buffer": 1},
    "B": {"est": (-8139.8, 531.8, -43870.4), "z_dep": -43943.0, "buffer": 1},
    "C": {"est": (-8127.3, 531.8, -50460.4), "z_dep": -50533.0, "buffer": 2},
}
X_CAMAS = -6533.0
Z_CRUZ_A = -35669.0
Z_T3 = -35670.0
X_T2 = 10639.75

# zonas: nombre -> (x, z, y_base, tipo)
ZONAS = {
    "A_est": (*EST["A"]["est"][0:1], EST["A"]["est"][2], EST["A"]["est"][1], "est"),
    "B_est": (EST["B"]["est"][0], EST["B"]["est"][2], EST["B"]["est"][1], "est"),
    "C_est": (EST["C"]["est"][0], EST["C"]["est"][2], EST["C"]["est"][1], "est"),
    "GirC": (-6518.2, -50572.3, 531.8, "gir"),
    "Z1": (X_CAMAS, -48713.3, 626.8, "z"),
    "Z2": (X_CAMAS, -46234.3, 626.8, "z"),
    "GirB": (-6530.7, -43982.3, 531.8, "gir"),
    "Z4": (X_CAMAS, -42087.3, 626.8, "z"),
    "Z5": (X_CAMAS, -40107.3, 626.8, "z"),
    "Z6": (X_CAMAS, -37764.3, 626.8, "z"),
    "CruzA": (X_CAMAS, Z_CRUZ_A, 546.6, "cruz"),
}
_T3 = [-4918.0, -3518.0, -2114.0, -714.0, 690.0, 2090.0, 3494.0, 4898.0, 6302.0, 7706.0, 9054.0]
for i, x in enumerate(_T3):
    ZONAS[f"T3_{i + 1}"] = (x, Z_T3, 546.6, "x")
ZONAS["Cruz2"] = (X_T2, -35660.0, 506.6, "cruz")
ZONAS["T2a"] = (X_T2, -34283.6, 531.6, "z")
ZONAS["Env"] = (X_T2, -32879.6, 531.6, "env")
ZONAS["S1"] = (X_T2, -31246.1, 506.6, "z")
ZONAS["S2"] = (X_T2, -29083.1, 506.6, "fin")
TRONCO = ["CruzA"] + [f"T3_{i + 1}" for i in range(len(_T3))] + ["Cruz2", "T2a", "Env", "S1", "S2"]
RUTAS = {"A": ["A_est"] + TRONCO,
         "B": ["B_est", "GirB", "Z4", "Z5", "Z6"] + TRONCO,
         "C": ["C_est", "GirC", "Z1", "Z2", "GirB", "Z4", "Z5", "Z6"] + TRONCO}
# modo que necesita un dispositivo para recibir desde / mandar hacia una zona
MODO_IN = {("GirB", "B_est"): "X", ("GirB", "Z2"): "Z", ("GirC", "C_est"): "X",
           ("CruzA", "A_est"): "cad", ("CruzA", "Z6"): "rod", ("Cruz2", "T3_11"): "cad"}
MODO_OUT = {("GirB", "Z4"): "Z", ("GirC", "Z1"): "Z", ("CruzA", "T3_1"): "cad", ("Cruz2", "T2a"): "rod"}


class Pallet:
    def __init__(self, pid, celda, origen):
        self.id, self.celda = pid, celda
        self.segs = []        # (t0, T, pos, (x0,z0), (x1,z1), D, y0, y1)
        self.giros = []       # (t0, t1, dgrados)
        self.carton = None    # id del cartón que lleva
        self.lugar = origen   # 'pila1_k' / 'aereo' / 'ingreso_X' / zona
        self.t_pila_sale = None
        self.estado = []      # (t, texto)
        self.lleno = None     # instante en que la celda lo terminó
        self.t_fin = None     # retirado por el autoelevador
        self.zona_i = None
        self.ocupado_hasta = 0.0
        self.t_env = None

    def mover(self, t0, p0, p1, y0, y1, v, a):
        D = math.dist(p0, p1)
        T, pos = trapecio(D, v, a)
        self.segs.append((t0, T, pos, p0, p1, D, y0, y1))
        return t0 + T

    def xzy(self, t):
        if not self.segs:
            return None
        s0 = self.segs[0]
        if t < s0[0]:
            return (*s0[3], s0[6])
        last = (*s0[3], s0[6])
        for (t0, T, pos, p0, p1, D, y0, y1) in self.segs:
            if t < t0:
                return last
            if t <= t0 + T:
                u = pos(t - t0) / D if D > 0 else 1.0
                return (p0[0] + (p1[0] - p0[0]) * u, p0[1] + (p1[1] - p0[1]) * u, y0 + (y1 - y0) * ease5(min(1, u / 0.35)))
            last = (*p1, y1)
        return last

    def ang(self, t):
        a = 0.0
        for (t0, t1, d) in self.giros:
            if t >= t1:
                a += d
            elif t > t0:
                a += d * ease5((t - t0) / (t1 - t0))
        return a


class Dispositivo:
    def __init__(self, nombre, modo):
        self.n, self.modo, self.ev, self.libre = nombre, modo, [], 0.0      # ev: (t0, t1, de, a)

    def cambiar(self, t, a, T):
        if a == self.modo:
            return t
        self.ev.append((t, t + T, self.modo, a))
        self.modo = a
        self.libre = t + T
        return t + T

    def frac(self, t, modos):
        """0..1 entre modos[0] y modos[1] (para animar)."""
        f = float(modos.index(self.ev[0][2])) if self.ev else float(modos.index(self.modo))
        for (t0, t1, de, a) in self.ev:
            if t >= t1:
                f = float(modos.index(a))
            elif t >= t0:
                u = ease5((t - t0) / (t1 - t0))
                f = modos.index(de) + (modos.index(a) - modos.index(de)) * u
        return f


class Aereo:
    """Carro en Z y elevación dy; tareas sin interrupción: (pallet a celda) o (cartón a buffer)."""

    def __init__(self, pilas):
        self.pilas = pilas                    # {1: [pallets de abajo a arriba], 2: [...]}, cada uno con .y_base, .z
        self.AER = []                         # (t0, t1, campo, a, b)
        self.z, self.dy, self.libre = Z_PARK, 0.0, 0.0
        self.pedidos = []                     # (t, celda)
        self.carton_n = 0
        self.cartones = []                    # dicts: id, t_toma, t_deja, pallet, y_pila
        self.log = []
        self.n_pila_carton = int(H_PILA_CARTON / E_CARTON)

    def _tr(self, t, dur, campo, a, b):
        if dur > 0:
            self.AER.append((t, t + dur, campo, a, b))
        return t + dur

    def ir_z(self, t, z):
        T, _ = trapecio(z - self.z, P["V_AER"], P["A_AER"])
        T = max(T, 0.8) if abs(z - self.z) > 1 else 0.0
        t = self._tr(t, T, "z", self.z, z)
        self.z = z
        return t

    def ir_dy(self, t, dy):
        d = abs(dy - self.dy)
        T = 0.0 if d < 1 else max(1.0, trapecio(d, P["V_ELEV"], 500.0)[0])
        t = self._tr(t, T, "dy", self.dy, dy)
        self.dy = dy
        return t

    def val(self, campo, t):
        v = Z_PARK if campo == "z" else 0.0
        for (t0, t1, c, a, b) in self.AER:
            if c != campo:
                continue
            if t >= t1:
                v = b
            elif t >= t0:
                v = a + (b - a) * ease5((t - t0) / (t1 - t0))
                break
            else:
                break
        return v

    def tope(self, k):
        return self.pilas[k][-1] if self.pilas[k] else None

    def sin_carton(self):
        for k in (1, 2):
            p = self.tope(k)
            if p is not None and p.carton is None:
                return k
        return None

    def viaje_carton(self, t, k):
        """Toma la hoja de arriba de la pila de cartones y la deja sobre el pallet de arriba del buffer k."""
        p = self.tope(k)
        cid = self.carton_n
        self.carton_n += 1
        y_top = CARTON_PILA[1] + H_PILA_CARTON - (cid % self.n_pila_carton) * E_CARTON
        t0 = t
        t = self.ir_dy(t, 0.0)
        t = self.ir_z(t, CARTON_PILA[2])
        t = self.ir_dy(t, y_top - E_CARTON - Y_PAL_SUJ)
        t_toma = t + P["T_VACIO"]
        t = self.ir_dy(t_toma, 0.0)
        t = self.ir_z(t, p.z)
        y_dep = p.y_base + 152.0
        t = self.ir_dy(t, y_dep - Y_PAL_SUJ)
        t_deja = t + P["T_VACIO"]
        t = self.ir_dy(t_deja, 0.0)
        c = {"id": cid, "t_toma": t_toma, "t_deja": t_deja, "pallet": p.id, "y_pila": y_top - E_CARTON, "buffer": k,
             "y_dep": y_dep, "z_dep": p.z}
        self.cartones.append(c)
        p.carton = cid
        self.log.append((t0, t, f"cartón {cid} → buffer {k}"))
        return t

    def viaje_pallet(self, t, celda, y_ing, z_dep, inicio_log):
        k = EST[celda]["buffer"]
        t0 = t
        if self.tope(k) is not None and self.tope(k).carton is None:
            t = self.viaje_carton(t, k)
        p = self.pilas[k].pop()
        t = self.ir_dy(t, 0.0)
        t = self.ir_z(t, p.z)
        t = self.ir_dy(t, p.y_base - Y_PAL_SUJ)
        t_ag = t + P["T_AGARRE"]
        t = self.ir_dy(t_ag, 0.0)
        t = self.ir_z(t, z_dep)
        t = self.ir_dy(t, y_ing - Y_PAL_SUJ)
        t_su = t + P["T_AGARRE"]
        t = self.ir_dy(t_su, 0.0)
        p.t_agarra, p.t_suelta, p.z_dep = t_ag, t_su, z_dep
        self.log.append((t0, t, f"pallet {p.id} (buffer {k}) → celda {celda}"))
        return p, t


class Planta:
    def __init__(self, semilla=7, t_lleno0=None, ext_A=False):
        """ext_A: la celda A la maneja otro (plan6 llama a lleno_A y lee listo_A)."""
        random.seed(semilla)
        self.ext_A = ext_A
        self.occ = {z: None for z in ZONAS}
        self.res = {z: None for z in ZONAS}
        self.dev = {"GirB": Dispositivo("GirB", "Z"), "GirC": Dispositivo("GirC", "X"),
                    "CruzA": Dispositivo("CruzA", "cad"), "Cruz2": Dispositivo("Cruz2", "cad")}
        self.pallets = []
        pilas = {1: [], 2: []}
        for k, zp in ((1, -32274.0), (2, -33804.0)):
            for j in range(10):
                p = self._nuevo("?", f"pila{k}_{j + 1}")
                p.y_base, p.z, p.k, p.j = j * 152.0, zp, k, j + 1
                p.carton = None
                pilas[k].append(p)
        self.aer = Aereo(pilas)
        # arranque en régimen: buffer 2 arriba con cartón (puesto antes), buffer 1 sin cartón
        c = {"id": -1, "t_toma": -1e9, "t_deja": -1e9, "pallet": pilas[2][-1].id, "buffer": 2,
             "y_dep": pilas[2][-1].y_base + 152.0, "z_dep": pilas[2][-1].z, "y_pila": 0.0}
        self.aer.cartones.append(c)
        pilas[2][-1].carton = -1
        self.ingreso = {}        # celda -> pallet esperando en la cama de ingreso (bajo el riel)
        self.estacion = {}       # celda -> pallet en la estación
        self.t_lleno = {}        # celda -> instante previsto de pallet completo (B, C, y A en flujo6)
        self.av = {"libre": 0.0, "retiros": []}
        self.repo = {}
        self.env_libre = 0.0
        self.envueltos = []      # (t0, t1, pid)
        self.eventos = []        # (t, texto) para rótulos
        self.carton_inicial = -1
        t_ini = t_lleno0 or {"A": None, "B": 240.0, "C": 95.0}
        for cel in ("A", "B", "C"):
            # estación: pallet en proceso (con cartón); ingreso: el siguiente ya esperando
            for lugar in ("est", "ing"):
                p = self._nuevo(cel, f"{lugar}_{cel}")
                p.carton = -100 - len(self.pallets)
                x, y, z = EST[cel]["est"]
                if lugar == "est":
                    p.mover(-1e6, (x, z), (x, z), y, y, 1, 1)
                    self.estacion[cel] = p
                    self.occ[f"{cel}_est"] = p.id
                    p.zona_i = 0
                    p.listo = -1.0
                else:
                    p.mover(-1e6, (X_RIEL, EST[cel]["z_dep"]), (X_RIEL, EST[cel]["z_dep"]), y, y, 1, 1)
                    self.ingreso[cel] = p
            if cel == "A" and not ext_A:
                self.t_lleno["A"] = P["N_A"] * P["T_A_CAJA"] + 6.0
            elif cel != "A":
                self.t_lleno[cel] = t_ini[cel]
        self.cartones_previos = [p for p in self.pallets if p.carton is not None and p.carton <= -100]

    def _nuevo(self, celda, origen):
        p = Pallet(len(self.pallets), celda, origen)
        self.pallets.append(p)
        return p

    # ------------------------------------------------------------------ celdas
    def lleno(self, cel, t):
        p = self.estacion.get(cel)
        if p is None or p.lleno is not None:
            return
        p.lleno = t
        p.celda = cel
        p.ruta = RUTAS[cel]
        p.zona_i = 0
        p.ocupado_hasta = t + 0.5
        self.eventos.append((t, f"Celda {cel}: pallet completo"))

    def listo(self, cel):
        """Instante en que el pallet nuevo de la celda quedó en la estación (None si todavía no)."""
        p = self.estacion.get(cel)
        return None if p is None or p.lleno is not None else p.listo

    def _paso_celdas(self, t):
        for cel in ("A", "B", "C"):
            if cel in self.t_lleno and self.t_lleno[cel] is not None and t >= self.t_lleno[cel]:
                self.lleno(cel, self.t_lleno[cel])
                self.t_lleno[cel] = None
            p = self.estacion.get(cel)
            # la estación quedó libre: entra el pallet del ingreso
            if p is None and cel in self.ingreso and self.ingreso[cel] is not None and self.occ[f"{cel}_est"] is None:
                q = self.ingreso.pop(cel)
                x, y, z = EST[cel]["est"]
                t0 = max(t, q.ocupado_hasta)
                t1 = q.mover(t0, (X_RIEL, EST[cel]["z_dep"]), (x, EST[cel]["z_dep"]), y, y, P["V_MESA"], P["A_MESA"])
                t2 = q.mover(t1 + 0.1, (x, EST[cel]["z_dep"]), (x, z), y, y, 150.0, 300.0)     # centrado
                q.listo = t2 + 0.2
                q.zona_i = 0
                q.celda = cel
                q.lleno = None
                self.estacion[cel] = q
                self.occ[f"{cel}_est"] = q.id
                self.aer.pedidos.append((t, cel))
                if cel == "B":
                    self.t_lleno["B"] = q.listo + P["T_B"] - 25.0 + random.uniform(-P["JIT"], P["JIT"])
                elif cel == "C":
                    self.t_lleno["C"] = q.listo + P["T_C"] - 25.0 + random.uniform(-P["JIT"], P["JIT"])
                elif not self.ext_A:
                    self.t_lleno["A"] = q.listo + P["N_A"] * P["T_A_CAJA"] + 6.0

    def _paso_aereo(self, t):
        a = self.aer
        # reposición de un buffer vacío con autoelevador (ruta roja): una pila nueva de 10
        for k, zp in ((1, -32274.0), (2, -33804.0)):
            if not a.pilas[k]:
                rp = self.repo.setdefault(k, t + P["T_REPO"])
                if t >= rp:
                    for j in range(10):
                        p = self._nuevo("?", f"pila{k}_{j + 1}_r{len(self.pallets)}")
                        p.y_base, p.z, p.k, p.j = j * 152.0, zp, k, j + 1
                        p.t_aparece = t
                        a.pilas[k].append(p)
                    self.repo.pop(k)
                    self.eventos.append((t, f"Autoelevador repone el buffer {k} (10 pallets)"))
        if t < a.libre:
            return
        if a.pedidos and a.pilas[EST[a.pedidos[0][1]]["buffer"]]:
            t_req, cel = a.pedidos.pop(0)
            y_ing = EST[cel]["est"][1]
            p, t_fin = a.viaje_pallet(t, cel, y_ing, EST[cel]["z_dep"], t_req)
            p.celda = cel
            p.ocupado_hasta = p.t_suelta + 0.4
            p.mover(p.t_suelta, (X_RIEL, EST[cel]["z_dep"]), (X_RIEL, EST[cel]["z_dep"]), y_ing, y_ing, 1, 1)
            self.ingreso[cel] = p
            a.libre = t_fin
            self.eventos.append((t, f"Robot aéreo: pallet vacío con cartón para la celda {cel}"))
            return
        k = a.sin_carton()
        if k is not None:
            a.libre = a.viaje_carton(t, k)
            self.eventos.append((t, f"Robot aéreo libre: busca un cartón y lo deja sobre el buffer {k}"))

    # ------------------------------------------------------------------ línea
    def _puede_entrar(self, z, desde, t):
        if self.occ[z] is not None or self.res[z] is not None:
            return False
        if z == "T2a" and (self.occ["Env"] is not None or self.res["Env"] is not None):
            return False                              # barrido del brazo: T2 S-11261 vacía mientras hay pallet en la MP402
        if z == "S1" and self.env_activo(t):
            return False
        if z in self.dev:
            d = self.dev[z]
            if t < d.libre:
                return False
            m = MODO_IN.get((z, desde))
            if m and d.modo != m:
                d.cambiar(t, m, P["T_CRUZ"] if "Cruz" in z else P["T_GIRO"])
                return False
        return True

    def env_activo(self, t):
        return any(a <= t < b for (a, b, _) in self.envueltos)

    def _paso_pallet(self, p, t):
        if p.lleno is None or p.t_fin is not None or t < p.ocupado_hasta:
            return
        z = p.ruta[p.zona_i]
        if z == "S2":
            return
        if z == "Env":
            if p.t_env is None:
                if self.occ["S1"] is not None or self.res["S1"] is not None or self.occ["T2a"] is not None:
                    return
                p.t_env = (t + 0.5, t + 0.5 + P["T_ENV"])
                self.envueltos.append((p.t_env[0], p.t_env[1], p.id))
                p.ocupado_hasta = p.t_env[1] + 0.5
                self.eventos.append((t, f"Envolvedora MP402: pallet de la celda {p.celda}"))
                return
        nz = p.ruta[p.zona_i + 1]
        # salida de un dispositivo: modo de salida (gira con el pallet arriba)
        if z in self.dev:
            d = self.dev[z]
            m = MODO_OUT.get((z, nz))
            if t < d.libre:
                return
            if m and d.modo != m:
                if not self._libre_para(nz):
                    return
                t1 = d.cambiar(t, m, P["T_CRUZ"] if "Cruz" in z else P["T_GIRO"])
                if "Gir" in z:
                    p.giros.append((t, t1, -90.0))
                p.ocupado_hasta = t1 + 0.2
                return
        if not self._puede_entrar(nz, z, t):
            return
        x0, z0, y0, _ = ZONAS[z]
        x1, z1, y1, _ = ZONAS[nz]
        if p.zona_i == 0:                                 # sale de la estación desde donde quedó
            x0, z0, y0 = p.xzy(t)
        self.res[nz] = p.id
        es_mesa = p.zona_i == 0
        t_arr = p.mover(t, (x0, z0), (x1, z1), y0, y1, P["V_MESA"] if es_mesa else P["V_CAD"], P["A_MESA"] if es_mesa else P["A_CAD"])
        D = math.dist((x0, z0), (x1, z1))
        frac_lib = 1.0 if z in self.dev or z.endswith("_est") else min(1.0, 1300.0 / max(D, 1.0))
        p.libera = (z, t + (t_arr - t) * frac_lib)
        p.llega = (nz, t_arr)
        p.ocupado_hasta = t_arr + 0.2
        p.zona_i += 1
        if z.endswith("_est"):
            self.estacion.pop(p.celda, None)

    def _libre_para(self, nz):
        return self.occ[nz] is None and self.res[nz] is None

    def _paso_liberar(self, t):
        for p in self.pallets:
            lb = getattr(p, "libera", None)
            if lb and t >= lb[1]:
                if self.occ[lb[0]] == p.id:
                    self.occ[lb[0]] = None
                p.libera = None
            ll = getattr(p, "llega", None)
            if ll and t >= ll[1]:
                self.occ[ll[0]] = p.id
                self.res[ll[0]] = None
                p.llega = None
                if ll[0] == "S2":
                    p.t_s2 = ll[1]
                    self.eventos.append((ll[1], "Salida: pallet envuelto listo para el autoelevador"))

    def _paso_autoelevador(self, t):
        pid = self.occ["S2"]
        if pid is None:
            return
        p = self.pallets[pid]
        if p.t_fin is not None or getattr(p, "t_s2", None) is None:
            return
        tr = max(p.t_s2 + P["T_AE_LLEGA"], self.av["libre"])
        if t >= tr:
            p.t_fin = t
            self.av["libre"] = t + P["T_AE_CICLO"]
            self.av["retiros"].append((t, pid))
            self.occ["S2"] = None
            self.eventos.append((t, "Autoelevador retira el pallet envuelto"))

    def paso(self, t):
        self._paso_liberar(t)
        self._paso_celdas(t)
        self._paso_aereo(t)
        for p in sorted([q for q in self.pallets if q.lleno is not None and q.t_fin is None], key=lambda q: q.lleno):
            self._paso_pallet(p, t)
        self._paso_autoelevador(t)

    # ------------------------------------------------------------------ estado para dibujar
    def pallet_pose(self, p, t):
        """(x, y_base, z, ángulo, visible, en_aereo)."""
        if p.t_fin is not None and t >= p.t_fin:
            return None
        if p.lugar.startswith("pila"):
            if t < getattr(p, "t_aparece", -1e9):
                return None
            ta = getattr(p, "t_agarra", None)
            if ta is None or t < ta:
                return (X_RIEL, p.y_base, p.z, 0.0, True, False)
            if t < p.t_suelta:
                return (X_RIEL, Y_PAL_SUJ + self.aer.val("dy", t), self.aer.val("z", t), 0.0, True, True)
        r = p.xzy(t)
        if r is None:
            return None
        return (r[0], r[2], r[1], p.ang(t), True, False)

    def carton_pose(self, c, t):
        """(x, y_base, z) de la hoja o None si todavía no salió de la pila (se dibuja la pila aparte)."""
        if t < c["t_toma"]:
            return None
        if t < c["t_deja"]:
            return (X_RIEL, Y_PAL_SUJ + self.aer.val("dy", t), self.aer.val("z", t))
        p = self.pallets[c["pallet"]]
        r = self.pallet_pose(p, t)
        if r is None:
            return None
        return (r[0], r[1] + 152.0, r[2])
