"""Generador de cintas de banda modular DEFYMOTION (HK50, piñón Z10 Ø primitivo 161, eje cuadrado 40).

Arma una cinta recta COMPLETA y paramétrica, partida en secciones transportables:
  <carpeta>\\<nombre>\\<nombre>.iam                 ensamble general (inserta todo en identidad)
      Seccion_1..n.iam   bastidor de cada sección (laterales en C, pistas, travesaños, patas, empalmes);
                         la 1 lleva el eje de cola y la última el eje de cabeza con motorreductor
      Banda.iam          banda continua (ida, retorno y vueltas en los tambores): se envía en rollo
      Barandas.iam       guías laterales de varilla Ø12 con postes
  piezas .ipt generadas por medida (se reutilizan dentro de la carpeta de la cinta)

Sistema local de la cinta (mm): X = sentido de avance (0 = extremo de cola del bastidor), Y = arriba (0 = piso),
Z = transversal (0 = eje de la banda). La banda queda con su cara superior en --alto.
Ancho de banda = n_modulos × A (A = 8,85 mm en PP, incremento de ancho de la serie HK50 de MDC).
Patas: caño 40x40 con base regulable (plato Ø100 + varilla M16 x 100 a media carrera + cubo 40x40).

Uso: python cinta_modular.py --nombre CINTA_X --largo 6000 --modulos 23 [--banda lisa|rodillos] [--alto 800]
        [--producto 156] [--seccion-max 2500] [--carpeta C:\\DEFYMOTION\\L3N\\Celdas_IA\\Cintas] [--rehacer]
"""
import argparse
import json
import math
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
import inventor_mcp as inv  # noqa: E402

S = inv._safe
A_MOD = 8.85                 # incremento de ancho HK50 (PP)
T_BANDA = 15.3               # alto de la banda
PD = 161.0                   # diámetro primitivo del piñón Z10
OD_PINON, E_PINON = 175.0, 38.0
EJE = 40.0                   # eje cuadrado
T_CHAPA = 3.175              # laterales 1/8"
H_LAT, ALA_LAT = 200.0, 30.0
GAP = 12.0                   # luz banda - lateral
TUBO = 40.0
SOBRE_EJE = 100.0            # el bastidor se extiende 100 mm más allá de cada eje
BASE_H = 60.0                # altura de la base regulable visible (plato + varilla a media carrera)


def args():
    a = argparse.ArgumentParser()
    a.add_argument("--nombre", required=True)
    a.add_argument("--largo", type=float, required=True, help="largo total del bastidor (mm)")
    a.add_argument("--modulos", type=int, required=True, help="ancho de banda en módulos A (23 -> 203,5; 48 -> 424,8)")
    a.add_argument("--banda", choices=("lisa", "rodillos"), default="lisa")
    a.add_argument("--alto", type=float, default=800.0)
    a.add_argument("--producto", type=float, default=156.0, help="ancho del producto entre guías (mm)")
    a.add_argument("--seccion-max", type=float, default=2500.0)
    a.add_argument("--carpeta", default=r"C:\DEFYMOTION\L3N\Celdas_IA\Cintas")
    a.add_argument("--sin-barandas", action="store_true")
    a.add_argument("--rehacer", action="store_true")
    return a.parse_args()


class Gen:
    def __init__(self, app, carpeta: Path):
        self.app, self.tg = app, app.TransientGeometry
        self.dir = carpeta
        self.dir.mkdir(parents=True, exist_ok=True)
        self._ap = {}
        self.piezas = {}

    # ------------------------------------------------------------------ utilidades
    def mm(self, M):
        tg = self.tg
        m = tg.CreateMatrix()
        m.SetCoordinateSystem(tg.CreatePoint(M[0][3] / 10, M[1][3] / 10, M[2][3] / 10),
                              tg.CreateVector(M[0][0], M[1][0], M[2][0]), tg.CreateVector(M[0][1], M[1][1], M[2][1]),
                              tg.CreateVector(M[0][2], M[1][2], M[2][2]))
        return m

    def apariencia(self, doc, prefijos):
        for pref in prefijos:
            if pref not in self._ap:
                ap = None
                for lib in inv._items(self.app.AssetLibraries):
                    for a in inv._items(S(lambda: lib.AppearanceAssets, []) or []):
                        if (S(lambda: a.DisplayName, "") or "").lower().startswith(pref):
                            ap = a
                            break
                    if ap:
                        break
                self._ap[pref] = ap
            if self._ap[pref] is not None:
                if S(lambda: setattr(doc, "ActiveAppearance", self._ap[pref].CopyTo(doc)), "x") is None:
                    return pref
        return None

    def _nueva_pieza(self):
        return self.app.Documents.Add(inv.K_PART_DOCUMENT, self.app.FileManager.GetTemplateFile(inv.K_PART_DOCUMENT), False)

    def _poligono(self, sk, pts3d):
        """Polilínea cerrada a partir de puntos 3D del modelo (mm) que caen en el plano del boceto."""
        tg = self.tg
        p2 = [sk.ModelToSketchSpace(tg.CreatePoint(*[v / 10 for v in p])) for p in pts3d]
        lineas, prim = [], None
        for i in range(len(p2)):
            a = lineas[-1].EndSketchPoint if lineas else p2[0]
            b = prim.StartSketchPoint if (i == len(p2) - 1 and prim is not None) else p2[(i + 1) % len(p2)]
            ln = sk.SketchLines.AddByTwoPoints(a, b)
            if prim is None:
                prim = ln
            lineas.append(ln)
        return sk.Profiles.AddForSolid()

    def _extruir(self, doc, prof, dist, eje, hasta, op=20481):
        """Extruye 'dist' y verifica que el cuerpo llegue a 'hasta' (mm) en el eje (0 x, 1 y, 2 z); si no, invierte."""
        cd = doc.ComponentDefinition
        f = None
        for direc in (20993, 20994):
            f = cd.Features.ExtrudeFeatures.AddByDistanceExtent(prof, dist / 10, direc, op)
            doc.Update()
            mx = (cd.RangeBox.MaxPoint.X, cd.RangeBox.MaxPoint.Y, cd.RangeBox.MaxPoint.Z)[eje] * 10
            if mx >= hasta - 0.05:
                return f
            f.Delete()
            doc.Update()
        raise RuntimeError("no pude extruir en el sentido pedido")

    def _guardar(self, doc, nombre, descr, ap):
        inv._iprop(doc, "Design Tracking Properties", "Part Number", nombre[:60])
        inv._iprop(doc, "Design Tracking Properties", "Description", descr.upper())
        if ap:
            self.apariencia(doc, ap)
        ruta = self.dir / f"{nombre}.ipt"
        if ruta.exists():
            ruta.unlink()
        doc.SaveAs(str(ruta), False)
        doc.Close(True)
        self.piezas[nombre] = str(ruta)
        return ruta

    def ya(self, nombre):
        r = self.dir / f"{nombre}.ipt"
        return r if r.exists() else None

    # ------------------------------------------------------------------ piezas
    def perfil_x(self, nombre, pts_yz, largo, descr, ap):
        """Perfil dado en el plano YZ (lista de (y, z) en mm) extruido a lo largo de +X (0..largo)."""
        r = self.ya(nombre)
        if r:
            return r
        doc = self._nueva_pieza()
        cd = doc.ComponentDefinition
        sk = cd.Sketches.Add(cd.WorkPlanes.Item(1))
        prof = self._poligono(sk, [(0.0, y, z) for y, z in pts_yz])
        self._extruir(doc, prof, largo, 0, largo)
        return self._guardar(doc, nombre, descr, ap)

    def perfil_z(self, nombre, pts_xy, largo, descr, ap, simetrico=True):
        """Perfil en el plano XY extruido a lo largo de Z (simétrico: -largo/2..largo/2)."""
        r = self.ya(nombre)
        if r:
            return r
        doc = self._nueva_pieza()
        cd = doc.ComponentDefinition
        sk = cd.Sketches.Add(cd.WorkPlanes.Item(3))
        prof = self._poligono(sk, [(x, y, 0.0) for x, y in pts_xy])
        if simetrico:
            cd.Features.ExtrudeFeatures.AddByDistanceExtent(prof, largo / 10, 20995, 20481)
            doc.Update()
        else:
            self._extruir(doc, prof, largo, 2, largo)
        return self._guardar(doc, nombre, descr, ap)

    def caja(self, nombre, sx, sy, sz, descr, ap):
        """Prisma con origen en el centro de la base (x, z centrados; y 0..sy)."""
        return self.perfil_z(nombre, [(-sx / 2, 0), (sx / 2, 0), (sx / 2, sy), (-sx / 2, sy)], sz, descr, ap)

    def cilindro(self, nombre, d, largo, eje, descr, ap, d_int=0.0, centrado=True):
        """Cilindro (o tubo si d_int > 0) de eje X, Y o Z; centrado en el largo o desde 0."""
        r = self.ya(nombre)
        if r:
            return r
        doc = self._nueva_pieza()
        cd = doc.ComponentDefinition
        plano = {"x": 1, "y": 2, "z": 3}[eje]
        sk = cd.Sketches.Add(cd.WorkPlanes.Item(plano))
        c = sk.ModelToSketchSpace(self.tg.CreatePoint(0, 0, 0))
        sk.SketchCircles.AddByCenterRadius(c, d / 20)
        if d_int:
            sk.SketchCircles.AddByCenterRadius(c, d_int / 20)
        prof = sk.Profiles.AddForSolid()
        if centrado:
            cd.Features.ExtrudeFeatures.AddByDistanceExtent(prof, largo / 10, 20995, 20481)
            doc.Update()
        else:
            self._extruir(doc, prof, largo, "xyz".index(eje), largo)
        if d_int and cd.SurfaceBodies.Count:
            # si quedó macizo (tomó el perfil exterior), cortar el interior
            if abs(S(lambda: cd.MassProperties.Volume, 0) - math.pi * d * d / 4 * largo / 1000) < 1e-3 * d * d * largo / 1000:
                sk2 = cd.Sketches.Add(cd.WorkPlanes.Item(plano))
                sk2.SketchCircles.AddByCenterRadius(sk2.ModelToSketchSpace(self.tg.CreatePoint(0, 0, 0)), d_int / 20)
                cd.Features.ExtrudeFeatures.AddByThroughAllExtent(sk2.Profiles.AddForSolid(), 20995, 20482)
                doc.Update()
        return self._guardar(doc, nombre, descr, ap)

    def pinon(self):
        nombre = "Pinon_Z10_D161_eje40"
        r = self.ya(nombre)
        if r:
            return r
        doc = self._nueva_pieza()
        cd = doc.ComponentDefinition
        sk = cd.Sketches.Add(cd.WorkPlanes.Item(3))                 # plano XY, eje del piñón = Z
        c = sk.ModelToSketchSpace(self.tg.CreatePoint(0, 0, 0))
        sk.SketchCircles.AddByCenterRadius(c, OD_PINON / 20)
        cd.Features.ExtrudeFeatures.AddByDistanceExtent(sk.Profiles.AddForSolid(), E_PINON / 10, 20995, 20481)
        doc.Update()
        sk2 = cd.Sketches.Add(cd.WorkPlanes.Item(3))
        p1 = sk2.ModelToSketchSpace(self.tg.CreatePoint(-EJE / 20, -EJE / 20, 0))
        p2 = sk2.ModelToSketchSpace(self.tg.CreatePoint(EJE / 20, EJE / 20, 0))
        sk2.SketchLines.AddAsTwoPointRectangle(p1, p2)
        cd.Features.ExtrudeFeatures.AddByThroughAllExtent(sk2.Profiles.AddForSolid(), 20995, 20482)
        doc.Update()
        return self._guardar(doc, nombre, "Piñón Z10 HK50 Ø primitivo 161, agujero cuadrado 40 (MDC)", ["gris", "blanco"])

    def base_regulable(self):
        nombre = "Base_regulable_D100_M16"
        r = self.ya(nombre)
        if r:
            return r
        doc = self._nueva_pieza()
        cd = doc.ComponentDefinition
        tg = self.tg
        for (d, y0, h) in ((100.0, 0.0, 10.0), (16.0, 10.0, BASE_H - 10.0)):
            pl = cd.WorkPlanes.AddByPlaneAndOffset(cd.WorkPlanes.Item(2), y0 / 10)
            S(lambda: setattr(pl, "Visible", False))
            sk = cd.Sketches.Add(pl)
            sk.SketchCircles.AddByCenterRadius(sk.ModelToSketchSpace(tg.CreatePoint(0, y0 / 10, 0)), d / 20)
            self._extruir(doc, sk.Profiles.AddForSolid(), h, 1, y0 + h)
        # cubo plástico 40x40 (va dentro del caño) de BASE_H a BASE_H + 30
        pl = cd.WorkPlanes.AddByPlaneAndOffset(cd.WorkPlanes.Item(2), BASE_H / 10)
        S(lambda: setattr(pl, "Visible", False))
        sk = cd.Sketches.Add(pl)
        sk.SketchLines.AddAsTwoPointRectangle(sk.ModelToSketchSpace(tg.CreatePoint(-2, BASE_H / 10, -2)),
                                              sk.ModelToSketchSpace(tg.CreatePoint(2, BASE_H / 10, 2)))
        self._extruir(doc, sk.Profiles.AddForSolid(), 30.0, 1, BASE_H + 30.0)
        return self._guardar(doc, nombre, "Base regulable: plato plástico Ø100, varilla AISI 304 M16x100, cubo 40x40 (MDC)",
                             ["negro", "gris oscuro"])


def armar(x):
    T0 = time.time()
    app = inv._inventor(start_if_needed=False)
    app.SilentOperation = True
    tg = app.TransientGeometry
    W = x.modulos * A_MOD
    L = x.largo
    out = Path(x.carpeta) / x.nombre
    top_path = out / f"{x.nombre}.iam"
    log = {"nombre": x.nombre, "W_banda": round(W, 1), "largo": L, "banda": x.banda, "avisos": []}
    try:
        if top_path.exists() and not x.rehacer:
            raise SystemExit(f"Ya existe {top_path}: usá --rehacer")
        for d in list(inv._items(app.Documents)):                       # cerrar sólo lo propio de esta cinta
            if str(S(lambda: d.FullFileName, "")).lower().startswith(str(out).lower() + "\\"):
                S(lambda: d.Close(True))
        if x.rehacer and out.exists():
            for p in out.glob("*.i??"):
                S(lambda: p.unlink())
        g = Gen(app, out)
        # ---------------------------------------------------------------- geometría
        y_top = x.alto                                  # cara superior de la banda
        y_eje = y_top - T_BANDA / 2 - PD / 2            # centro de los ejes
        x_cola, x_cab = SOBRE_EJE, L - SOBRE_EJE        # ejes
        z_lat = W / 2 + GAP                             # cara interior del lateral
        y_lat_top = y_top - 8.0                         # el lateral asoma 8 mm por debajo de la cara de la banda
        y_lat_bot = y_lat_top - H_LAT
        n_sec = max(1, math.ceil(L / x.seccion_max))
        Ls = L / n_sec
        log.update({"secciones": n_sec, "largo_seccion": round(Ls, 1), "y_eje": round(y_eje, 1)})

        # ---------------------------------------------------------------- piezas
        Lr = round(Ls, 1)
        lat = g.perfil_x(f"Lateral_C_{round(H_LAT)}_L{Lr:g}",
                         [(0, 0), (H_LAT, 0), (H_LAT, ALA_LAT), (H_LAT - T_CHAPA, ALA_LAT), (H_LAT - T_CHAPA, T_CHAPA),
                          (T_CHAPA, T_CHAPA), (T_CHAPA, ALA_LAT), (0, ALA_LAT)],
                         Lr, f"Lateral en C chapa 1/8\" {H_LAT:g}x{ALA_LAT:g} L={Lr:g} (plegado)", ["acero inoxidable", "aluminio", "acero"])
        pista = g.perfil_x(f"Pista_UHMW_25x12_L{Lr:g}", [(0, -12.5), (12, -12.5), (12, 12.5), (0, 12.5)], Lr,
                           f"Pista de deslizamiento UHMW 25x12 L={Lr:g}", ["verde", "blanco"])
        trav = g.caja(f"Travesano_40x20_W{round(2 * z_lat):g}", TUBO, 20.0, 2 * z_lat, f"Travesaño caño 40x20 L={2 * z_lat:.0f}",
                      ["acero inoxidable", "acero"])
        h_pata = y_lat_bot - BASE_H
        pata = g.caja(f"Pata_40x40_H{round(h_pata):g}", TUBO, h_pata, TUBO, f"Pata caño 40x40 H={h_pata:.0f}",
                                 ["acero inoxidable", "acero"])
        z_pata = z_lat + T_CHAPA + TUBO / 2
        cruz = g.caja(f"Cruz_patas_40x40_W{round(2 * z_pata - TUBO):g}", TUBO, TUBO, 2 * z_pata - TUBO,
                      f"Travesaño de patas 40x40 L={2 * z_pata - TUBO:.0f}", ["acero inoxidable", "acero"])
        base = g.base_regulable()
        empalme = g.caja("Empalme_seccion_150x120x4.76", 150.0, 120.0, 4.76, "Planchuela de empalme entre secciones 3/16\"",
                         ["acero inoxidable", "acero"])
        L_eje = 2 * (z_lat + T_CHAPA) + 2 * 60.0
        eje_cola = g.caja(f"Eje_cuadrado_40_L{round(L_eje):g}", EJE, EJE, L_eje, f"Eje cuadrado 40 AISI 304 L={L_eje:.0f}",
                          ["acero inoxidable", "acero"])
        eje_cab = g.caja(f"Eje_cuadrado_40_L{round(L_eje + 60):g}", EJE, EJE, L_eje + 60, f"Eje cuadrado 40 AISI 304 L={L_eje + 60:.0f} (motriz)",
                         ["acero inoxidable", "acero"])
        pinon = g.pinon()
        rodam = g.caja("Rodamiento_UCFL_100x100x35", 100.0, 100.0, 35.0, "Rodamiento con soporte de brida UCFL (eje Ø40 con buje)",
                       ["gris oscuro", "negro"])
        reductor = g.caja("Motorreductor_SEW_reductor", 130.0, 130.0, 150.0, "Motorreductor SEW (reductor, volumen)", ["azul"])
        motor = g.cilindro("Motorreductor_SEW_motor", 120.0, 220.0, "x", "Motorreductor SEW (motor, volumen)", ["azul"], centrado=False)
        espesor_b = T_BANDA
        banda_ap = ["blanco"] if x.banda == "lisa" else ["gris oscuro", "gris"]
        largo_ida = x_cab - x_cola
        b_ida = g.caja(f"Banda_{x.banda}_W{round(W, 1):g}_L{round(largo_ida):g}", largo_ida, espesor_b, W,
                       f"Banda modular HK50 {'M1000 lisa' if x.banda == 'lisa' else 'M1300 con ruedas'} {x.modulos} módulos = {W:.1f} mm, tramo",
                       banda_ap)
        b_tambor = g.cilindro(f"Banda_{x.banda}_tambor_W{round(W, 1):g}", PD + espesor_b, W, "z",
                              "Banda modular, vuelta sobre los piñones", banda_ap, d_int=PD - espesor_b)
        rod = None
        if x.banda == "rodillos":
            rod = g.cilindro("Rueda_acumulacion_D21_L13", 21.0, 13.0, "z", "Rueda de acumulación M1300 (representativa)", ["gris oscuro", "negro"])
        log["piezas"] = len(g.piezas)

        # ---------------------------------------------------------------- secciones
        def nuevo_ens():
            return app.Documents.Add(inv.K_ASSEMBLY_DOCUMENT, app.FileManager.GetTemplateFile(inv.K_ASSEMBLY_DOCUMENT), False)

        def poner(ens, ruta, M, nombre):
            o = ens.ComponentDefinition.Occurrences.Add(str(ruta), g.mm(M))
            S(lambda: setattr(o, "Name", nombre))
            S(lambda: setattr(o, "Grounded", True))
            return o

        I = [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0]]

        def T(xx, yy, zz):
            return [[1, 0, 0, xx], [0, 1, 0, yy], [0, 0, 1, zz]]

        def Ry180(xx, yy, zz):             # giro 180° sobre Y (espeja X y Z)
            return [[-1, 0, 0, xx], [0, 1, 0, yy], [0, 0, -1, zz]]

        n_pistas = max(2, math.ceil(W / 150.0) + 1)
        z_pistas = [-W / 2 + 25 + i * (W - 50) / (n_pistas - 1) for i in range(n_pistas)]
        n_pin = max(2, round(W / 110.0))
        z_pines = [-W / 2 + 40 + i * (W - 80) / (n_pin - 1) for i in range(n_pin)]
        secciones = []
        for s in range(n_sec):
            ens = nuevo_ens()
            x0, x1 = s * Ls, (s + 1) * Ls
            # laterales en C con las alas hacia afuera (alma en z_lat..z_lat+T); el izquierdo girado 180° sobre Y
            poner(ens, lat, T(x0, y_lat_bot, z_lat), "Lateral_der")
            poner(ens, lat, Ry180(x1, y_lat_bot, -z_lat), "Lateral_izq")
            # pistas de ida (bajo la banda) y de retorno
            for i, zp in enumerate(z_pistas):
                poner(ens, pista, T(x0, y_top - T_BANDA - 12, zp), f"Pista_ida_{i + 1}")
            y_ret = y_eje - PD / 2 - T_BANDA / 2 - 12            # base de las pistas de retorno
            for i, zp in enumerate((z_pistas[0], z_pistas[-1])):
                poner(ens, pista, T(x0, y_ret, zp), f"Pista_retorno_{i + 1}")
            # travesaños bajo las pistas cada <= 800
            n_t = max(2, math.ceil(Ls / 800.0) + 1)
            for i in range(n_t):
                xt = x0 + 60 + i * (Ls - 120) / (n_t - 1)
                poner(ens, trav, T(xt, y_top - T_BANDA - 12 - 20, 0), f"Travesano_{i + 1}")
            for i in range(n_t - 1):
                xt = x0 + 60 + (i + 0.5) * (Ls - 120) / (n_t - 1)
                poner(ens, trav, T(xt, y_ret - 20, 0), f"Travesano_retorno_{i + 1}")
            # patas en el arranque de la sección (y al final, en la última)
            xs_pata = [x0 + 80] + ([x1 - 80] if s == n_sec - 1 else [])
            for k, xp in enumerate(xs_pata):
                for lado, zs in (("izq", -z_pata), ("der", z_pata)):
                    poner(ens, pata, T(xp, BASE_H, zs), f"Pata_{k + 1}_{lado}")
                    poner(ens, base, T(xp, 0, zs), f"Base_regulable_{k + 1}_{lado}")
                poner(ens, cruz, T(xp, BASE_H + 200, 0), f"Cruz_patas_{k + 1}")
            # empalme con la sección siguiente
            if s < n_sec - 1:
                for lado, zs in (("izq", -(z_lat + T_CHAPA + 2.38)), ("der", z_lat + T_CHAPA + 2.38)):
                    poner(ens, empalme, T(x1, y_lat_bot + 25, zs), f"Empalme_{lado}")
            # eje de cola (sección 1) / eje de cabeza con motor (última)
            for es_cab, xe, ruta_eje in (((False, x_cola, eje_cola),) if s == 0 else ()) + \
                                         (((True, x_cab, eje_cab),) if s == n_sec - 1 else ()):
                ze = 30.0 if es_cab else 0.0                    # el eje motriz asoma del lado del motor (+z)
                poner(ens, ruta_eje, T(xe, y_eje - EJE / 2, ze), "Eje_cabeza" if es_cab else "Eje_cola")
                for i, zp in enumerate(z_pines):
                    poner(ens, pinon, T(xe, y_eje, zp), f"Pinon_{'cab' if es_cab else 'cola'}_{i + 1}")
                for lado, zs in (("izq", -(z_lat + T_CHAPA + 17.5)), ("der", z_lat + T_CHAPA + 17.5)):
                    poner(ens, rodam, T(xe, y_eje - 50, zs), f"Rodamiento_{'cab' if es_cab else 'cola'}_{lado}")
                if es_cab:
                    zr = z_lat + T_CHAPA + 35 + 75
                    poner(ens, reductor, T(xe, y_eje - 65, zr), "Reductor")
                    poner(ens, motor, T(xe - 65 - 220, y_eje, zr), "Motor")
            ruta = out / f"Seccion_{s + 1}.iam"
            inv._iprop(ens, "Design Tracking Properties", "Part Number", f"{x.nombre} - sección {s + 1}/{n_sec}")
            if ruta.exists():
                ruta.unlink()
            ens.SaveAs(str(ruta), False)
            ens.Close(True)
            secciones.append(ruta)
        # ---------------------------------------------------------------- banda
        ens = nuevo_ens()
        poner(ens, b_ida, T((x_cola + x_cab) / 2, y_top - T_BANDA, 0), "Banda_ida")
        poner(ens, b_ida, T((x_cola + x_cab) / 2, y_eje - PD / 2 - T_BANDA / 2, 0), "Banda_retorno")
        poner(ens, b_tambor, T(x_cola, y_eje, 0), "Banda_vuelta_cola")
        poner(ens, b_tambor, T(x_cab, y_eje, 0), "Banda_vuelta_cabeza")
        if rod is not None:                              # ruedas de acumulación: cada 50 mm x cada 4 módulos
            n_x = int(largo_ida // 100)
            zs_r = [-W / 2 + 4 * A_MOD * (k + 0.5) for k in range(int(W // (4 * A_MOD)))]
            for i in range(n_x):
                for j, zr_ in enumerate(zs_r):
                    poner(ens, rod, T(x_cola + 50 + i * 100, y_top - 5.5, zr_), f"Rueda_{i + 1}_{j + 1}")
            log["ruedas"] = n_x * len(zs_r)
        ruta_banda = out / "Banda.iam"
        inv._iprop(ens, "Design Tracking Properties", "Part Number",
                   f"Banda HK50 {'M1000' if x.banda == 'lisa' else 'M1300'} {x.modulos} mód. desarrollo {2 * largo_ida + math.pi * PD:.0f} mm")
        if ruta_banda.exists():
            ruta_banda.unlink()
        ens.SaveAs(str(ruta_banda), False)
        ens.Close(True)
        log["desarrollo_banda_mm"] = round(2 * largo_ida + math.pi * PD)
        # ---------------------------------------------------------------- barandas
        ruta_bar = None
        if not x.sin_barandas:
            ens = nuevo_ens()
            varilla = g.cilindro(f"Varilla_D12_L{round(L - 100):g}", 12.0, L - 100, "x", "Varilla AISI 304 Ø12 (baranda)",
                                 ["acero inoxidable", "acero"], centrado=False)
            poste = g.cilindro("Poste_baranda_D12_L120", 12.0, 120.0, "y", "Vástago de baranda con mordaza", ["negro", "gris oscuro"],
                               centrado=False)
            zg = x.producto / 2 + 7 + 6
            z_post = z_lat + T_CHAPA + 10
            Lb = round(z_post - zg + 6)
            brazo = g.cilindro(f"Brazo_baranda_D12_L{Lb}", 12.0, Lb, "z", "Brazo de soporte de baranda", ["negro", "gris oscuro"])
            n_p = max(2, math.ceil((L - 100) / 1200.0) + 1)
            for lado, zs in (("izq", -zg), ("der", zg)):
                sg = 1 if zs > 0 else -1
                for k, yy in enumerate((y_top + 35, y_top + 95)):
                    poner(ens, varilla, T(50, yy, zs), f"Varilla_{lado}_{k + 1}")
                    for i in range(n_p):
                        xp = 80 + i * (L - 160) / (n_p - 1)
                        poner(ens, brazo, T(xp, yy, sg * (zg - 6 + Lb / 2)), f"Brazo_{lado}_{k + 1}_{i + 1}")
                for i in range(n_p):
                    xp = 80 + i * (L - 160) / (n_p - 1)
                    poner(ens, poste, T(xp, y_lat_top - 10, sg * z_post), f"Poste_{lado}_{i + 1}")
            ruta_bar = out / "Barandas.iam"
            if ruta_bar.exists():
                ruta_bar.unlink()
            ens.SaveAs(str(ruta_bar), False)
            ens.Close(True)
        # ---------------------------------------------------------------- general
        top = nuevo_ens()
        for i, r in enumerate(secciones):
            poner(top, r, I, f"Seccion_{i + 1}")
        poner(top, ruta_banda, I, "Banda")
        if ruta_bar:
            poner(top, ruta_bar, I, "Barandas")
        inv._iprop(top, "Design Tracking Properties", "Part Number", x.nombre)
        inv._iprop(top, "Design Tracking Properties", "Description",
                   f"Cinta banda modular HK50 {W:.1f} x {L:.0f} mm, banda {x.banda}, {n_sec} secciones de {Ls:.0f} mm, banda a {x.alto:.0f}")
        if top_path.exists():
            top_path.unlink()
        top.SaveAs(str(top_path), False)
        cd = top.ComponentDefinition
        b = cd.RangeBox
        log["envolvente_mm"] = [round(v * 10, 1) for v in (b.MinPoint.X, b.MinPoint.Y, b.MinPoint.Z, b.MaxPoint.X, b.MaxPoint.Y, b.MaxPoint.Z)]
        log["masa_kg"] = S(lambda: round(cd.MassProperties.Mass, 1))
        top.Close(True)
        log["archivo"] = str(top_path)
        log["segundos"] = round(time.time() - T0, 1)
        (out / "resultado.json").write_text(json.dumps(log, ensure_ascii=False, indent=1), encoding="utf-8")
        return log
    finally:
        S(lambda: setattr(app, "SilentOperation", False))


if __name__ == "__main__":
    r = armar(args())
    print(json.dumps(r, ensure_ascii=False, indent=1))
