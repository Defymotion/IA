"""Ingreso de cajas de una celda: cinta de llegada con acumulación, pateador, cinta interna (A) o cinta 1 + freno contador +
cinta 2 (B). Cada caja guarda claves (t, fase, valor) que el muestreo por cuadro interpola."""
import math

from comun import box_M, lerp, ease5

GAP_ACUM = 8.0


class Caja:
    def __init__(self, idx):
        self.idx = idx
        self.keys = []

    def key(self, t, fase, val):
        if self.keys and self.keys[-1][1] == fase and fase in ("path", "kick", "int", "b2") and abs(self.keys[-1][0] - t) < 1e-9:
            self.keys[-1] = (t, fase, val)
            return
        self.keys.append((t, fase, val))


class Recorrido:
    def __init__(self, segs):
        self.segs = []
        for tipo, d, R in segs:
            if tipo == "r":
                (a, b) = d
                self.segs.append(("r", d, math.dist(a, b), None))
            else:
                c, a0, a1 = d
                self.segs.append(("a", d, abs(math.radians(a1 - a0)) * R, R))
        self.L = sum(s[2] for s in self.segs)

    def punto(self, s):
        s = max(0.0, min(self.L, s))
        for tipo, d, L, R in self.segs:
            if s <= L + 1e-9:
                u = s / L
                if tipo == "r":
                    (a, b) = d
                    return (lerp(a[0], b[0], u), lerp(a[1], b[1], u)), ((b[0] - a[0]) / L, (b[1] - a[1]) / L)
                c, a0, a1 = d
                ang = math.radians(lerp(a0, a1, u))
                p = (c[0] + R * math.cos(ang), c[1] + R * math.sin(ang))
                sg = 1 if a1 > a0 else -1
                return p, (-math.sin(ang) * sg, math.cos(ang) * sg)
            s -= L
        raise ValueError


def preparar(c):
    c.rec = Recorrido(c.path_segs)
    c.cajas = [Caja(i) for i in range(c.N_POOL)]
    c.X_PAT_FIN = c.X_KICK0 + c.CARRERA - c.CONTACTO
    c.PROG = [(len(tm["cajas"]), tm, li) for li, capa in enumerate(c.capas) for tm in capa["tomas"]]
    c.prog_i = 0


def caja_en_recorrido(c, s):
    (x, z), (hx, hz) = c.rec.punto(s)
    R = [[hx, 0, -hz], [0, 1, 0], [hz, 0, hx]]
    return box_M(R, [x, c.Y_LLEGADA, z])


def pat_d(c, t):
    for (a_, b_, d_) in c.pat_events:
        if a_ <= t < b_:
            return c.CARRERA * ease5((t - a_) / c.T_PATEO)
        if b_ <= t < d_:
            return c.CARRERA * (1 - ease5((t - b_) / c.T_RETORNO))
    return 0.0


def paso_ingreso(c, t, DT, necesita):
    """Avanza un DT el ingreso. necesita: cajas de las próximas tomas (para dosificar)."""
    # fuente
    if t >= c.src_next and (c.src_i < c.N_POOL or c.libres):
        if (not c.path_q) or c.pos[c.path_q[-1]] >= c.L + GAP_ACUM:
            if c.src_i < c.N_POOL:
                b = c.src_i
                c.src_i += 1
            else:
                b = c.libres.pop(0)
            c.path_q.append(b)
            c.pos[b] = 0.0
            c.vel[b] = None
            c.cajas[b].key(t, "path", 0.0)
            c.src_next = t + c.PASO_FUENTE
    # cinta de llegada con acumulación
    lim = c.rec.L
    for b in c.path_q:
        s0 = c.pos[b]
        s1 = min(s0 + c.V_BANDA * DT, lim)
        mov = (s1 - s0) > 1e-9
        if c.vel.get(b) is None or (c.vel[b] > 1e-9) != mov:
            c.cajas[b].key(t, "path", s0)
            c.vel[b] = (s1 - s0) / DT
        c.pos[b] = s1
        lim = s1 - (c.L + GAP_ACUM)
    # pateador
    if c.kick is None and c.path_q and c.pos[c.path_q[0]] >= c.rec.L - 0.01:
        tail_ok = (not c.int_q) or c.pos[c.int_q[-1]] >= c.X_PAT_FIN + c.W + 2.0
        if c.freno is None:
            cupo = necesita
            ok = tail_ok and len(c.int_q) < cupo
        else:
            capacidad = int((c.freno["x"] - c.X_PAT_FIN) / c.W) - 1
            ok = tail_ok and len(c.int_q) < capacidad
        if ok:
            b = c.path_q.pop(0)
            c.cajas[b].key(t, "path", c.rec.L)
            c.cajas[b].key(t, "kick", t)
            c.kick = (b, t)
            c.pat_events.append((t, t + c.T_PATEO, t + c.T_PATEO + c.T_RETORNO))
    if c.kick is not None and c.kick[0] is not None and t >= c.kick[1] + c.T_PATEO:
        b = c.kick[0]
        c.cajas[b].key(t, "int", c.X_PAT_FIN)
        c.int_q.append(b)
        c.pos[b] = c.X_PAT_FIN
        c.vel[b] = None
        c.kick = (None, c.kick[1])
    if c.kick is not None and t >= c.kick[1] + c.T_PATEO + c.T_RETORNO:
        c.kick = None
    # cinta interna (A) / cinta 1 contra el freno (B)
    if c.freno is None:
        lim = c.slot_x(0)
        for b in c.int_q:
            lim = _mover(c, b, t, DT, lim, "int", c.V_BANDA)
    else:
        fx = c.freno["x"] - c.W / 2.0
        # liberación: las primeras 'liberar' cajas pasan el freno hacia la cinta 2
        if c.liberar > 0 and c.freno_abierto is None and len(c.int_q) >= c.liberar \
                and all(abs(c.pos[c.int_q[j]] - (fx - j * c.W)) < 0.5 for j in range(c.liberar)):
            c.freno_abierto = t
            n = c.liberar
            for j in range(n):
                b = c.int_q.pop(0)
                c.cajas[b].key(t, "int", c.pos[b])
                c.cajas[b].key(t, "b2", c.pos[b])
                c.b2_q.append(b)
                c.vel[b] = None
            c.liberar = 0
            c._ult_liberada = c.b2_q[-1]
        if c.freno_abierto is not None:
            ult = c._ult_liberada
            if c.pos.get(ult, 0) > c.freno["x"] + c.W / 2.0 + 30.0 or ult not in c.b2_q:
                c.freno_events.append((c.freno_abierto, t))
                c.freno_abierto = None
        lim = fx
        for b in c.int_q:
            lim = _mover(c, b, t, DT, lim, "int", c.V_BANDA)
        lim = c.slot_x(0)
        for b in c.b2_q:
            lim = _mover(c, b, t, DT, lim, "b2", c.freno["v2"])
        if c.freno_abierto is None and c.liberar == 0 and not c.b2_q and necesita > 0:
            c.liberar = necesita_primera(c)
    c.max_q = max(c.max_q, len(c.int_q))


def necesita_primera(c):
    return c.PROG[c.prog_i][0] if c.prog_i < len(c.PROG) else 0


def _mover(c, b, t, DT, lim, fase, v):
    x0 = c.pos[b]
    x1 = min(x0 + v * DT, lim)
    mov = (x1 - x0) > 1e-9
    if c.vel.get(b) is None or (c.vel[b] > 1e-9) != mov:
        c.cajas[b].key(t, fase, x0)
        c.vel[b] = (x1 - x0) / DT
    c.pos[b] = x1
    return x1 - c.W


def cola_toma(c):
    """Cajas de la toma (frente primero) y si están en posición."""
    q = c.int_q if c.freno is None else c.b2_q
    return q


def lista_para_tomar(c, n):
    q = cola_toma(c)
    return len(q) >= n and all(abs(c.pos[q[j]] - c.slot_x(j)) < 0.05 for j in range(n))
