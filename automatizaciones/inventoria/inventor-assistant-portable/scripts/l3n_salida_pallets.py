"""L3N: completa la línea de pallets y monta la barrera de salida de la celda A (archivos propios de Celdas_IA).
1) Camas de rolos "a medida" en los tramos sin cama de Linea_Pallets.iam (A->B 610, B->C 882, antes de la giratoria
   final), con la misma sección que las Roller_Conveyor_Straight (ancho 1373, rodillos arriba a 626,8). Bloque gráfico:
   2 largueros 60x160, rodillos Ø60 cada 100, 4 patas, banda amarilla en el larguero.
2) Barrera IFM OY513S (tipo 4, 4 haces, 910 mm protegidos, muting T integrado) en Celda_A_L3N.iam: emisor y receptor
   verticales sobre las caras interiores de las dos columnas de reja que flanquean la salida del pallet hacia la mesa
   giratoria (Reja_Este_col_3 y Reja_Norte_interna_col_5), alineados en X, con brazos de muting en cruz.
Uso: python l3n_salida_pallets.py [--rehacer]
"""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import inventor_mcp as inv  # noqa: E402
from cinta_modular import Gen  # noqa: E402

S = inv._safe
BASE = Path(r"C:\DEFYMOTION\L3N\Celdas_IA")
TOP = BASE / "LayoutL3N_Celdas.iam"
LINEA = BASE / "Linea_Pallets.iam"
CELDA = BASE / "Celda_A_L3N.iam"
PIEZAS = BASE / "Salida_pallets"
REHACER = "--rehacer" in sys.argv

ANCHO, Y_TOP = 1372.9, 626.8
X_LIN = (-7219.7 + -5846.8) / 2           # eje de la línea A-B-C (camas a lo largo de Z)
Z_LIN = (-36293.8 + -34920.9) / 2         # eje de la línea hacia la estrechadora (camas a lo largo de X)
# tramos sin cama (coordenadas del layout, mm): (nombre, eje, desde, hasta)
TRAMOS = [("Cama_amedida_AB", "z", -38478.3, -39088.3),
          ("Cama_amedida_BC", "z", -46812.3, -47694.3),
          ("Cama_amedida_final", "x", 12419.8, 13701.8)]
# barrera
X_BAR = -7400.0
Z_COL3_CARA, Z_COL5_CARA = -36227.3, -34846.3       # caras interiores de las columnas
BAR = (50.0, 1085.0, 55.0)                          # OY513S: 1085 x 50 x 55
Y_BAR = 150.0

app = inv._inventor(start_if_needed=False)
log = {"avisos": [], "camas": [], "barrera": {}}


def abrir(p):
    d = next((d for d in inv._items(app.Documents) if S(lambda: Path(d.FullFileName).resolve() == p.resolve(), False)), None)
    return d or app.Documents.Open(str(p), False)


def caja(o):
    b = o.RangeBox
    return [round(v * 10, 1) for v in (b.MinPoint.X, b.MinPoint.Y, b.MinPoint.Z, b.MaxPoint.X, b.MaxPoint.Y, b.MaxPoint.Z)]


app.SilentOperation = True
try:
    g = Gen(app, PIEZAS)
    top = abrir(TOP)
    off = {}
    for o in inv._items(top.ComponentDefinition.Occurrences):
        t = o.Transformation.Translation
        off[o.Name.split(":")[0]] = (t.X * 10, t.Y * 10, t.Z * 10)
    log["origenes"] = {k: [round(v, 1) for v in off[k]] for k in ("Linea_Pallets", "Celda_A_L3N")}

    # -------------------------------------------------------------- 1) camas a medida
    def cama(L):
        L = round(L)
        nombre = f"Cama_rolos_amedida_v2_L{L}"
        ruta = PIEZAS / f"{nombre}.iam"
        if ruta.exists() and not REHACER:
            return ruta
        larg = g.caja(f"Larguero_cama_60x160_L{L}", L, 160.0, 60.0, f"Larguero de cama de rolos 60x160 L={L}", ["negro", "gris oscuro"])
        banda = g.caja(f"Banda_cama_5x60_L{L}", L, 60.0, 5.0, "Banda amarilla del larguero", ["amarillo", "naranja"])
        rod = g.cilindro(f"Rodillo_D60_galv_L{round(ANCHO - 120)}", 60.0, ANCHO - 120.0, "z", "Rodillo Ø60 galvanizado", ["aluminio", "acero"])
        pata = g.caja("Pata_cama_60x60_H467_negra", 60.0, Y_TOP - 160.0, 60.0, "Pata de cama de rolos 60x60", ["negro"])
        ens = app.Documents.Add(inv.K_ASSEMBLY_DOCUMENT, app.FileManager.GetTemplateFile(inv.K_ASSEMBLY_DOCUMENT), False)
        cd = ens.ComponentDefinition

        def poner(r, x, y, z, n):
            o = cd.Occurrences.Add(str(r), g.mm([[1, 0, 0, x], [0, 1, 0, y], [0, 0, 1, z]]))
            S(lambda: setattr(o, "Name", n))
            S(lambda: setattr(o, "Grounded", True))

        zl = ANCHO / 2 - 30.0
        for s, lado in ((-1, "a"), (1, "b")):
            poner(larg, L / 2, Y_TOP - 160.0, s * zl, f"Larguero_{lado}")
            poner(banda, L / 2, Y_TOP - 140.0, s * (ANCHO / 2 + 2.5), f"Banda_{lado}")
            for k, x in enumerate((60.0, L - 60.0)):
                poner(pata, x, 0.0, s * zl, f"Pata_{lado}{k + 1}")
        n = max(1, int((L - 60.0) // 100.0) + 1)
        paso = (L - 60.0) / max(1, n - 1) if n > 1 else 0.0
        for k in range(n):
            poner(rod, 30.0 + k * paso if n > 1 else L / 2, Y_TOP - 30.0, 0.0, f"Rodillo_{k + 1}")
        inv._iprop(ens, "Design Tracking Properties", "Description", f"CAMA DE ROLOS A MEDIDA L={L} (GRAFICA)")
        ens.SaveAs(str(ruta), False)
        ens.Close(True)
        return ruta

    lin = abrir(LINEA)
    lcd = lin.ComponentDefinition
    for o in list(inv._items(lcd.Occurrences)):
        if o.Name.startswith("IA_Cama_amedida"):
            o.Delete()
    ox, _, oz = off["Linea_Pallets"]
    for nombre, eje, a, b in TRAMOS:
        L = abs(b - a)
        r = cama(L)
        if eje == "z":
            s = 1.0 if b > a else -1.0                     # el largo local +X va hacia 'b'
            M = [[0, 0, -s, X_LIN - ox], [0, 1, 0, 0], [s, 0, 0, a - oz]]
        else:
            M = [[1, 0, 0, a - ox], [0, 1, 0, 0], [0, 0, 1, Z_LIN - oz]]
        o = lcd.Occurrences.Add(str(r), g.mm(M))
        S(lambda: setattr(o, "Name", f"IA_{nombre}"))
        S(lambda: setattr(o, "Grounded", True))
        c = caja(o)
        log["camas"].append({"nombre": nombre, "largo": round(L), "caja_layout": [round(c[0] + ox, 1), c[1], round(c[2] + oz, 1),
                                                                                 round(c[3] + ox, 1), c[4], round(c[5] + oz, 1)]})
    lin.Update()
    lin.Save()

    # -------------------------------------------------------------- 2) barrera IFM en la salida de la celda A
    cuerpo = g.caja("IFM_OY513S_cuerpo", *BAR, "IFM OY513S rejilla de seguridad tipo 4, 4 haces, 910 mm, muting T integrado",
                    ["gris", "aluminio"])
    tapa = g.caja("IFM_OY513S_tapa", BAR[0] + 6, 40.0, BAR[2] + 6, "Tapa / conector de la rejilla OY513S", ["negro"])
    brazo = g.caja("IFM_brazo_muting_L600", 600.0, 40.0, 40.0, "Brazo de muting con sensores premontados (IFM)",
                   ["amarillo", "naranja"])
    sensor = g.caja("IFM_sensor_muting", 60.0, 50.0, 70.0, "Sensor de muting (barrera fotoeléctrica)", ["negro"])
    cel = abrir(CELDA)
    ccd = cel.ComponentDefinition
    for o in list(inv._items(ccd.Occurrences)):
        if o.Name.startswith(("Barrera_IFM", "Barrera_brazo", "Barrera_sensor")):
            o.Delete()
    cx, _, cz = off["Celda_A_L3N"]

    def add(r, x, y, z, n):
        o = ccd.Occurrences.Add(str(r), g.mm([[1, 0, 0, x - cx], [0, 1, 0, y], [0, 0, 1, z - cz]]))
        S(lambda: setattr(o, "Name", n))
        S(lambda: setattr(o, "Grounded", True))
        return o

    z_em = Z_COL3_CARA + BAR[2] / 2
    z_re = Z_COL5_CARA - BAR[2] / 2
    for nombre, z, zs in (("emisor", z_em, 1), ("receptor", z_re, -1)):
        add(cuerpo, X_BAR, Y_BAR, z, f"Barrera_IFM_{nombre}")
        add(tapa, X_BAR, Y_BAR - 40.0, z, f"Barrera_IFM_{nombre}_tapa_inf")
        add(tapa, X_BAR, Y_BAR + BAR[1], z, f"Barrera_IFM_{nombre}_tapa_sup")
        # brazo de muting a 700 mm (ve la carga, por encima de los rodillos), sólo hacia adentro de la celda: del lado
        # de la mesa giratoria quedaría dentro del barrido del pallet al girar
        add(brazo, X_BAR - 320.0, 700.0, z, f"Barrera_brazo_{nombre}")
        for k, dx in enumerate((-570.0, -130.0)):
            add(sensor, X_BAR + dx, 695.0, z, f"Barrera_sensor_{nombre}_{k + 1}")
    cel.Update()
    cel.Save()
    luz = abs(z_re - z_em) - BAR[2]
    pal = next((caja(o) for o in inv._items(ccd.Occurrences) if o.Name.startswith("IA_Pallet_TBA250")), None)
    log["barrera"] = {"modelo": "IFM OY513S + brazos de muting", "X": X_BAR, "Z_emisor": round(z_em, 1), "Z_receptor": round(z_re, 1),
                      "luz_entre_cuerpos": round(luz, 1), "altura_protegida": [Y_BAR + 80, Y_BAR + 990]}
    if pal:
        pz0, pz1 = pal[2] + cz, pal[5] + cz
        log["barrera"]["libre_pallet"] = [round(pz0 - (z_em + 35.0), 1), round((z_re - 35.0) - pz1, 1)]
        if min(log["barrera"]["libre_pallet"]) < 30:
            log["avisos"].append("los brazos/sensores de muting quedan a menos de 30 mm del pallet")
    top.Update()
finally:
    S(lambda: setattr(app, "SilentOperation", False))
print(json.dumps(log, ensure_ascii=False, indent=1))
