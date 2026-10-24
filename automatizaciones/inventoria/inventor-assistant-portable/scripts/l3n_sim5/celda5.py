"""Celda de paletizado para el planificador v5: geometría del gripper y de la caja, patrón, ingreso de cajas (cinta de
llegada, pateador, cintas internas con o sin freno contador), programa del robot con tiempos reales y blending."""
import math

from comun import (Seg, apply, box_M, bb_de, dpsi_corto, ease, ease5, inv, lerp, mm, prisma, roty, sat, tr, yaw_of)

T_CIERRE = 0.35          # s que tarda la pala móvil en cerrar (la caja se corre en la segunda mitad)
T_ABRE = 0.25
LIFT = 260.0
LIFT_MIN = 200.0
V_LIN_LENTO = 900.0      # mm/s en las bajadas/subidas junto al producto
V_LIN = 2000.0
V_PTP = 2500.0           # límite cartesiano de los cruces (en la práctica mandan los ejes)


class Pinza:
    """Gripper: n garras, caja apoyada contra la pala fija (LB) o centrada en la luz abierta (LBc, para tomar)."""

    def __init__(self, GL, R_box_g, base_fijo, v_movil, holgura, n_garras, cierre, eje_garras):
        self.GL, self.n, self.v_movil, self.holgura, self.cierre = GL, n_garras, v_movil, holgura, cierre
        self.eje_garras = eje_garras
        R = [list(r) for r in R_box_g]
        self.LB = [box_M(R, base_fijo(i)) for i in range(n_garras)]
        self.LBc = []
        for i in range(n_garras):
            p = base_fijo(i)
            self.LBc.append(box_M(R, [p[k] + v_movil[k] * holgura / 2.0 for k in range(3)]))

    def gripper_para(self, Mb, i, centrada=False):
        return mm(Mb, inv((self.LBc if centrada else self.LB)[i]))


class Celda:
    def __init__(self, nombre, cfg):
        self.n = nombre
        for k, v in cfg.items():
            setattr(self, k, v)
        self.ciclos = []
        self.robot_last = None
        self.q_last = [0.0, -40.0, 90.0, 0.0]
        self.AJUSTES = []
        self.PALA_LOG = []
        self.TRAS = {"directo": 0, "desvio": 0, "sin_solucion": 0}
        self.PSI_U = [0.0, None]
        # cajas del ingreso
        self.path_q, self.int_q, self.b2_q = [], [], []
        self.pos, self.vel = {}, {}
        self.src_next = self.src_t0
        self.src_i = 0
        self.kick = None
        self.pat_events = []
        self.freno_events = []          # (t_abre, t_cierra)
        self.freno_abierto = None
        self.liberar = 0
        self.prog_i = 0
        self.cyc = None
        self.placed_pal = {}
        self.T_FIN_PAL = {}
        self.libres = []
        self.max_q = 0

    # ------------------------------------------------------------------ geometría del pick
    def caja_en_cinta(self, x):
        return box_M(self.R_BOX_INT, [x, self.Y_BANDA, self.Z_INT])

    def slot_x(self, j):
        return self.X_STOP - self.W / 2.0 - j * self.W

    # ------------------------------------------------------------------ choques fijos
    def choca_estatico(self, Mg, garras, holgura=15.0):
        GL = self.pinza.GL
        objs = [prisma(Mg, (GL[0], GL[3]), (GL[1], GL[4]), (GL[2], GL[5]))]
        hx, hz = self.L / 2.0, self.W / 2.0
        objs += [prisma(mm(Mg, self.pinza.LB[g_]), (-hx, hx), (0, self.H), (-hz, hz)) for g_ in garras]
        for pl, y0, y1, bb in objs:
            for n_, c in self.ESTATICOS:
                if y0 < c[4] + 5.0 and c[1] - 5.0 < y1 and sat(pl, c, holgura):
                    return n_
        return None

    # ------------------------------------------------------------------ movimientos con tiempos del robot
    def _paso(self, a, b, tipo="ptp", giro=None, nota="", dwell=0.0, blend=True, evento=None):
        return {"a": a, "b": b, "tipo": tipo, "giro": dpsi_corto(a[0], b[0]) if giro is None else giro, "nota": nota,
                "dwell": dwell, "blend": blend, "evento": evento}

    def temporizar(self, t0, pasos):
        """Tiempos de cada paso con el modelo del robot y superposición entre pasos encadenados con blend."""
        segs, eventos = [], []
        t = t0
        q = self.q_last
        prev = None
        for p in pasos:
            vlin = {"lento": V_LIN_LENTO, "lin": V_LIN, "ptp": V_PTP}[p["tipo"]]
            T, q = self.robot.duracion(p["a"], p["b"], p["giro"], q, v_lin=vlin)
            start = t
            if prev is not None and prev["blend"] and p["blend"] and prev["dwell"] == 0.0:
                ov = min(0.3, 0.3 * prev["_T"], 0.3 * T)
                start = t - ov
            p["_T"] = T
            s = Seg(start, T, p["a"], p["b"], nota=p["nota"], giro=p["giro"])
            segs.append(s)
            if p["evento"]:
                eventos.append((p["evento"], s.t1))
            t = s.t1 + p["dwell"]
            prev = p
        self.q_last = q
        return segs, eventos, t

    # ------------------------------------------------------------------ traslados que no barren lo fijo
    def _tramo_ok(self, a, b, giro, garras):
        d = math.dist(a[1], b[1])
        n = max(4, int(d / 50.0), int(abs(giro) / 5.0))
        for i in range(n + 1):
            u = i / n
            p = [lerp(a[1][k], b[1][k], u) for k in range(3)]
            if self.choca_estatico(self.robot.gripper_pose(a[0] + giro * u, p), garras, holgura=20.0) is not None:
                return False
        # que el robot llegue en todo el tramo con codo arriba y dentro de los límites de los ejes
        m = max(3, int(d / 250.0))
        for i in range(m + 1):
            u = i / m
            p = (a[0] + giro * u, [lerp(a[1][k], b[1][k], u) for k in range(3)])
            if not self.robot.alcanza(p, self.q_last):
                return False
        return True

    def cruce(self, A, B, garras, nota):
        dc = dpsi_corto(A[0], B[0])
        giros = [dc] + ([dc - 360.0 if dc > 0 else dc + 360.0] if abs(dc) > 150.0 else [])
        if self.PSI_U[1] is None:
            self.PSI_U[0], self.PSI_U[1] = A[0], A[0]
        giros.sort(key=lambda g_: abs(self.PSI_U[0] + g_ - self.PSI_U[1]))
        for g_ in giros:
            if self._tramo_ok(A, B, g_, garras):
                self.TRAS["directo"] += 1
                self.PSI_U[0] += g_
                return [self._paso(A, B, "ptp", g_, nota)]
        y = A[1][1]
        cands = [[self.PAL_O[0], y, self.PAL_O[2]], [self.PAL_O[0], y, (self.PAL_O[2] + self.Z_INT) / 2]]
        # puntos de paso alejados de la base (el tramo recto puede pasar demasiado cerca del robot)
        bx, bz = self.robot.base_xz
        for u in (0.3, 0.5, 0.7):
            px, pz = lerp(A[1][0], B[1][0], u), lerp(A[1][2], B[1][2], u)
            r = math.hypot(px - bx, pz - bz) or 1.0
            for R_ in (1500.0, 1800.0, 2100.0):
                if r < R_:
                    cands.append([bx + (px - bx) / r * R_, y, bz + (pz - bz) / r * R_])
        cands += [[lerp(A[1][0], B[1][0], u), y, lerp(A[1][2], B[1][2], u)] for u in (0.25, 0.5, 0.75)]
        cands += [[self.PAL_O[0] + dx, y, self.PAL_O[2] + dz] for dx in (-400.0, 0.0, 400.0) for dz in (-500.0, 0.0, 500.0)]
        cands.sort(key=lambda V: math.dist(A[1], V) + math.dist(V, B[1]))
        for V in cands:
            for g_ in giros:
                pa_, pr_ = (A[0], V), (A[0] + g_, V)
                if self._tramo_ok(A, pa_, g_, garras) and self._tramo_ok(pr_, B, 0.0, garras):
                    self.TRAS["desvio"] += 1
                    self.PSI_U[0] += g_
                    return [self._paso(A, pr_, "ptp", g_, nota), self._paso(pr_, B, "ptp", 0.0, nota)]
                if self._tramo_ok(A, pa_, 0.0, garras) and self._tramo_ok(pa_, B, g_, garras):
                    self.TRAS["desvio"] += 1
                    self.PSI_U[0] += g_
                    return [self._paso(A, pa_, "ptp", 0.0, nota), self._paso(pa_, B, "ptp", g_, nota)]
                if self._tramo_ok(A, pa_, 0.0, garras) and self._tramo_ok(pa_, pr_, g_, garras) and self._tramo_ok(pr_, B, 0.0, garras):
                    self.TRAS["desvio"] += 1
                    self.PSI_U[0] += g_
                    return [self._paso(A, pa_, "ptp", 0.0, nota), self._paso(pa_, pr_, "ptp", g_, "gira"),
                            self._paso(pr_, B, "ptp", 0.0, nota)]
        self.TRAS["sin_solucion"] += 1
        self.AJUSTES.append(("traslado_choca", nota))
        self.PSI_U[0] += giros[0]
        return [self._paso(A, B, "ptp", giros[0], nota)]

    def traslado(self, a, b, nota="traslado", garras=()):
        yv = max(a[1][1], b[1][1])
        out = []
        if yv - a[1][1] > 5:
            p = (a[0], [a[1][0], yv, a[1][2]])
            out.append(self._paso(a, p, "lin", 0.0, "sube"))
            a = p
        p = (b[0], [b[1][0], yv, b[1][2]])
        out += self.cruce(a, p, list(garras), nota)
        if yv - b[1][1] > 5:
            out.append(self._paso(p, b, "lin", 0.0, "baja"))
        return out

    # ------------------------------------------------------------------ alcance
    def arriba(self, p, dy):
        sub = lambda pp, d: (pp[0], [pp[1][0], pp[1][1] + d, pp[1][2]])
        for d in [dy] + [v for v in range(int(dy) - 20, int(min(dy, LIFT_MIN)) - 1, -20)]:
            c = sub(p, d)
            if self.robot.alcanza(c):
                if d != dy:
                    self.AJUSTES.append(("baja", round(dy - d)))
                return c
        bx, bz = self.robot.base_xz
        for r in range(50, 1001, 50):
            o = p[1]
            L = math.hypot(o[0] - bx, o[2] - bz)
            c = (p[0], [o[0] - (o[0] - bx) / L * r, o[1] + LIFT_MIN, o[2] - (o[2] - bz) / L * r])
            if self.robot.alcanza(c):
                self.AJUSTES.append(("retira", r))
                return c
        self.AJUSTES.append(("sin_solucion", 0))
        return sub(p, LIFT_MIN)

    @staticmethod
    def org_de(Mg):
        return yaw_of(Mg), [Mg[0][3], Mg[1][3], Mg[2][3]]

    # ------------------------------------------------------------------ un ciclo del robot
    def plan_ciclo(self, t, toma):
        """toma: {"tipo": "una"|"grupo", "cajas": [(R, p) relativas al pallet], "dir": vector mundo (libre/colgar)}."""
        P = self.pinza
        n = len(toma["cajas"])
        garras = list(range(P.n - n, P.n))
        Mpick = P.gripper_para(self.caja_en_cinta(self.slot_x(0)), P.n - 1, centrada=True)
        p_pick = self.org_de(Mpick)
        sub = lambda pp, d: (pp[0], [pp[1][0], pp[1][1] + d, pp[1][2]])
        above_pick = sub(p_pick, LIFT)
        cur = self.robot_last if self.robot_last else above_pick
        pasos = self.traslado(cur, above_pick, nota="a_toma")
        pasos.append(self._paso(above_pick, p_pick, "lento", 0.0, "baja_toma", dwell=T_CIERRE + 0.05, blend=False, evento="cierra"))
        pasos.append(self._paso(p_pick, sub(p_pick, LIFT), "lento", 0.0, "sube_toma"))
        drops = []          # (k paso, garra, M)
        if toma["tipo"] == "grupo":
            dirv = toma["dir"]
            opciones = []
            for flip in (0, 1):
                Mbs = [self.pat_world(R, p, flip) for (R, p) in toma["cajas"]]
                Mg0 = P.gripper_para(Mbs[0], 0)
                eg = apply([r[:3] + [0] for r in Mg0[:3]] + [[0, 0, 0, 1]], P.eje_garras)
                Mbs.sort(key=lambda M: M[0][3] * eg[0] + M[2][3] * eg[2])
                Mg = P.gripper_para(Mbs[0], P.n - n)       # garras de la toma: las últimas n
                vm = apply([r[:3] + [0] for r in Mg[:3]] + [[0, 0, 0, 1]], P.v_movil)
                pala_ok = vm[0] * dirv[0] + vm[2] * dirv[2] > 0.5
                ok = (self.robot.alcanza(self.org_de(Mg)) and self.robot.alcanza(sub(self.org_de(Mg), LIFT_MIN))
                      and self.choca_estatico(Mg, []) is None)
                opciones.append((ok, pala_ok, Mg, Mbs))
            opciones.sort(key=lambda o: (not o[0], not o[1]))
            ok, pala_ok, Mg, tgt = opciones[0]
            if not (ok and pala_ok):
                self.AJUSTES.append(("grupo_pala", ok, pala_ok))
            self.PALA_LOG.append(("grupo", ok, pala_ok))
            pl = self.org_de(Mg)
            ab = self.arriba(pl, LIFT)
            pasos += self.traslado(pasos[-1]["b"], ab, garras=garras)
            pasos.append(self._paso(ab, pl, "lento", 0.0, "baja_deja", dwell=T_ABRE + 0.05, blend=False, evento="deja0"))
            for g_, M in zip(garras, tgt):
                drops.append(("deja0", g_, M))
            pasos.append(self._paso(pl, self.arriba(pl, LIFT), "lento", 0.0, "sube_deja"))
        else:
            dcol = toma["dir"]                 # hacia donde pueden colgar las que quedan (zona vacía)
            prev = pasos[-1]["b"]
            opciones = []
            for flip in (0, 1):
                for orden_g in (tuple(reversed(garras)), tuple(garras)):
                    Mg_a = P.gripper_para(self.pat_world(*toma["cajas"][0], flip), orden_g[0])
                    vm = apply([r[:3] + [0] for r in Mg_a[:3]] + [[0, 0, 0, 1]], P.v_movil)
                    orden = sorted(toma["cajas"], key=lambda c: c[1][0] * vm[0] + c[1][2] * vm[2])
                    planes, ok, pref = [], True, 0.0
                    for k, (c, g_) in enumerate(zip(orden, orden_g)):
                        Mb2 = self.pat_world(*c, flip)
                        Mg_c = P.gripper_para(Mb2, g_)
                        rest = list(orden_g[k + 1:])
                        if rest:
                            Mr = mm(Mg_c, P.LB[rest[0]])
                            d = [Mr[0][3] - Mb2[0][3], Mr[2][3] - Mb2[2][3]]
                            pref += 1.0 if d[0] * dcol[0] + d[1] * dcol[2] > 0 else -1.0
                        if not (self.robot.alcanza(self.org_de(Mg_c)) and self.robot.alcanza(sub(self.org_de(Mg_c), LIFT_MIN))) \
                                or self.choca_estatico(Mg_c, rest):
                            ok = False
                        planes.append((Mg_c, Mb2))
                    cuerpo_adentro = orden_g == tuple(reversed(garras))
                    opciones.append((ok, pref, cuerpo_adentro, planes, orden_g))
            opciones.sort(key=lambda o: (not o[0], -o[1], not o[2]))
            ok, pref, _, planes, orden_g = opciones[0]
            if not ok:
                self.AJUSTES.append(("una_sin_opcion",))
            self.PALA_LOG.append(("una", ok, pref, orden_g))
            for k, (g_, (Mg, Mb2)) in enumerate(zip(orden_g, planes)):
                pl = self.org_de(Mg)
                ab = self.arriba(pl, LIFT if k == 0 else LIFT_MIN)
                if k == 0:
                    pasos += self.traslado(prev, ab, garras=orden_g)
                else:
                    pasos.append(self._paso(prev, ab, "lin", 0.0, "corre"))
                pasos.append(self._paso(ab, pl, "lento", 0.0, "baja_deja", dwell=T_ABRE + 0.02, blend=False, evento=f"deja{k}"))
                drops.append((f"deja{k}", g_, Mb2))
                nxt = self.arriba(pl, LIFT_MIN if k < len(planes) - 1 else LIFT)
                pasos.append(self._paso(pl, nxt, "lento", 0.0, "sube_deja"))
                prev = nxt
        segs, eventos, t_fin = self.temporizar(t, pasos)
        ev = dict(eventos)
        self.robot_last = segs[-1].b
        cyc = {"t0": t, "t1": segs[-1].t1, "segs": segs, "t_cierra": ev["cierra"] + T_CIERRE, "t_contacto": ev["cierra"],
               "garras": garras, "drops": [(ev[k] + 0.0, g_, M) for (k, g_, M) in drops], "n": n, "tipo": toma["tipo"],
               "Mpick": Mpick}
        self.ciclos.append(cyc)
        return cyc

    def pat_world(self, R, p, flip=0):
        M = box_M(R, [self.PAL_O[0] + p[0], self.PAL_O[1] + p[1], self.PAL_O[2] + p[2]])
        return mm(M, roty(180.0)) if flip else M

    def ir_a_casa(self, t):
        Mpick = self.pinza.gripper_para(self.caja_en_cinta(self.slot_x(0)), self.pinza.n - 1, centrada=True)
        home = (self.org_de(Mpick)[0], [Mpick[0][3], Mpick[1][3] + LIFT, Mpick[2][3]])
        pasos = self.traslado(self.robot_last, home, nota="espera")
        segs, _, _ = self.temporizar(t, pasos)
        self.robot_last = home
        cyc = {"t0": t, "t1": segs[-1].t1, "segs": segs, "t_cierra": None, "garras": [], "drops": [], "n": 0, "tipo": "casa"}
        self.ciclos.append(cyc)
        return cyc
