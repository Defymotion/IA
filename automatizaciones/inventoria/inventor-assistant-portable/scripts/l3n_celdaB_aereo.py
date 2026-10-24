"""Celda B (representación de la celda instalada, archivo propio Celda_B_existente.iam; respaldo *_antes_aereo.iam):
cambios para que el robot aéreo pueda llevarle pallets vacíos. Bajo el riel (X -11232..-9932, pallet colgado desde
Y 1528) había: el tablero 11-06 (1750 de alto), el tramo oeste de la reja con la puerta y el panel neumático (chapa
filtro), y la primera bahía de la reja norte.
- tablero 11-06: se corre fuera del recorrido (X -1071, Z +358: al norte del gabinete KR C4);
- reja oeste (X -10078, de Z -42363 a la esquina norte -40163) y primera bahía norte: columnas de 1400 y paneles altos de
  345 (piezas Fademaq recortadas de Rejas_v2), la puerta y el panel neumático se ocultan (A REUBICAR) y su vano se
  cierra con una bahía de 880.
Las piezas originales del cerco (ADECO) no se tocan: se ocultan en el contexto de la celda y se agregan las nuevas.
Uso: python l3n_celdaB_aereo.py
"""
import json
import shutil
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import inventor_mcp as inv  # noqa: E402
from estirar_pieza import estirar  # noqa: E402

S = inv._safe
CEL = Path(r"C:\DEFYMOTION\L3N\Celdas_IA\Celda_B_existente.iam")
RV2 = Path(r"C:\DEFYMOTION\L3N\Celdas_IA\Rejas_v2")
ORG = (-6495.6706, 0.0, -43982.2999)
X_O = -10078.0
app = inv._inventor(start_if_needed=False)
tg = app.TransientGeometry
log = {"avisos": [], "ocultos": [], "agregados": []}


def its(x):
    if x is None or isinstance(x, list):
        return x or []
    try:
        return inv._items(x)
    except Exception:  # noqa: BLE001
        return []


def caja(o):
    b = o.RangeBox
    return [b.MinPoint.X * 10 + ORG[0], b.MinPoint.Y * 10, b.MinPoint.Z * 10 + ORG[2],
            b.MaxPoint.X * 10 + ORG[0], b.MaxPoint.Y * 10, b.MaxPoint.Z * 10 + ORG[2]]


def panel(ancho, alto, base):
    nombre = f"{Path(base).stem}_L{int(ancho)}xH{int(alto)}.ipt"
    ruta = RV2 / nombre
    if ruta.exists():
        return str(ruta)
    origen = base
    if abs(ancho - 1240) > 0.5:
        estirar(app, origen, ruta, 0, 300.0, ancho - 1240)
        origen = str(ruta)
    if abs(alto - 900) > 0.5:
        if origen == str(ruta):
            tmp = RV2 / ("_tmp_" + nombre)
            shutil.copyfile(ruta, tmp)
            estirar(app, str(tmp), ruta, 1, 300.0, alto - 900)
            S(lambda: tmp.unlink())
        else:
            estirar(app, origen, ruta, 1, 300.0, alto - 900)
    return str(ruta)


def colocar(cd, f, Mplant, cx, y0, cz, nombre):
    R = [[Mplant.Cell(r, c) for c in range(1, 4)] for r in range(1, 4)]
    m = tg.CreateMatrix()
    m.SetCoordinateSystem(tg.CreatePoint(0, 0, 0), tg.CreateVector(R[0][0], R[1][0], R[2][0]),
                          tg.CreateVector(R[0][1], R[1][1], R[2][1]), tg.CreateVector(R[0][2], R[1][2], R[2][2]))
    o = cd.Occurrences.Add(f, m)
    c = caja(o)
    dx, dy, dz = cx - (c[0] + c[3]) / 2, y0 - c[1], cz - (c[2] + c[5]) / 2
    m2 = o.Transformation
    v = tg.CreateMatrix()
    v.SetTranslation(tg.CreateVector(dx / 10, dy / 10, dz / 10))
    m2.TransformBy(v)
    S(lambda: setattr(o, "Grounded", False))
    o.Transformation = m2
    S(lambda: setattr(o, "Grounded", True))
    S(lambda: setattr(o, "Name", nombre))
    log["agregados"].append((nombre, [round(v_, 1) for v_ in caja(o)]))
    return o


app.SilentOperation = True
try:
    cel = next((d for d in its(app.Documents) if S(lambda: Path(d.FullFileName).resolve() == CEL.resolve(), False)), None)
    cel = cel or app.Documents.Open(str(CEL), False)
    cd = cel.ComponentDefinition
    occ = {o.Name: o for o in its(cd.Occurrences)}
    if "IA_B_aereo_col_1" in occ:
        log["avisos"].append("ya estaba hecho")
    else:
        resp = CEL.with_name("Celda_B_existente_antes_aereo.iam")
        if not resp.exists():
            cel.SaveAs(str(resp), True)
        lay = occ["ADECOAGRO2_Layout[Fademaq]:1"]
        sub = {o.Name: o for o in its(lay.SubOccurrences)}
        cerco = next(o for n, o in sub.items() if n.startswith("Cerco Perimetral"))
        cer = {o.Name: o for o in its(cerco.SubOccurrences)}

        def busca(pref, cx, cz, tol=200.0):
            for n, o in cer.items():
                if n.startswith(pref):
                    c = caja(o)
                    if abs((c[0] + c[3]) / 2 - cx) < tol and abs((c[2] + c[5]) / 2 - cz) < tol:
                        return n, o
            return None, None

        ocultar = []
        for pref, cx, cz in (("Ensamblaje Columna_", -10063.2, -42363.9), ("Ensamblaje Columna_", -9988.2, -40163.9),
                             ("Ensamblaje Columna Puerta", -10123.2, -41043.9), ("Ensamblaje Puerta", -9989.8, -40853.6)):
            n, o = busca(pref, cx, cz, 700.0 if pref == "Ensamblaje Puerta" else 200.0)
            if o is None:
                log["avisos"].append(f"no encontré {pref} en ({cx}, {cz})")
            else:
                ocultar.append(o)
        tmpl = {}
        for n, o in cer.items():
            if not n.startswith("Panel 03"):
                continue
            c = caja(o)
            cxx, czz = (c[0] + c[3]) / 2, (c[2] + c[5]) / 2
            if abs(cxx - X_O) < 40 and abs(czz - (-41704)) < 100:          # tramo oeste
                (tmpl.setdefault("Z_alto" if c[1] > 600 else "Z_bajo", o))
                if c[1] > 600:
                    ocultar.append(o)
            if abs(czz - (-40149)) < 40 and abs(cxx - (-9328)) < 100:     # primera bahía norte
                tmpl.setdefault("X_alto" if c[1] > 600 else "X_bajo", o)
                ocultar.append(o)
        for n, o in cer.items():                                           # ménsulas altas de esas columnas
            if n.startswith("Chapa 02"):
                c = caja(o)
                if c[1] > 1350 and (abs((c[0] + c[3]) / 2 - X_O) < 120 or abs((c[2] + c[5]) / 2 - (-40149)) < 120):
                    ocultar.append(o)
        for n, o in sub.items():
            if n.startswith(("Chapa filtro", "carcasas arriba")):
                ocultar.append(o)
        for o in ocultar:
            S(lambda: setattr(o, "Visible", False))
            log["ocultos"].append(S(lambda: o.Name))
        falt = [k for k in ("Z_bajo", "X_bajo") if k not in tmpl]
        if falt:
            log["avisos"].append(f"faltan plantillas {falt}")
        col_f = str(RV2 / "Ensamblaje Columna_[CP1512]_ADECO_H1400.iam")
        colM = next(o for n, o in cer.items() if n.startswith("Ensamblaje Columna_")).Transformation
        pan_base = tmpl["Z_bajo"].Definition.Document.FullFileName
        Mz, Mx = tmpl["Z_bajo"].Transformation, tmpl["X_bajo"].Transformation
        for k, (cx, cz) in enumerate(((X_O, -42363.9), (X_O, -41043.9), (X_O, -40163.9)), start=1):
            colocar(cd, col_f, colM, cx, 0.0, cz, f"IA_B_aereo_col_{k}")
        # tramo oeste (1320 entre columnas): panel bajo original queda; alto recortado
        colocar(cd, panel(1240, 345, pan_base), Mz, X_O, 1055.0, (-42363.9 + -41043.9) / 2, "IA_B_aereo_panel_oeste_alto")
        # vano de la puerta (880): bahía nueva
        L = (-40163.9) - (-41043.9) - 80.0
        colocar(cd, panel(L, 900, pan_base), Mz, X_O, 145.0, (-41043.9 + -40163.9) / 2, "IA_B_aereo_panel_vano_bajo")
        colocar(cd, panel(L, 345, pan_base), Mz, X_O, 1055.0, (-41043.9 + -40163.9) / 2, "IA_B_aereo_panel_vano_alto")
        # primera bahía norte (de X -10078 a la columna existente en -8668)
        L2 = (-8668.2 - X_O) - 80.0
        colocar(cd, panel(L2, 900, pan_base), Mx, (X_O + -8668.2) / 2, 145.0, -40148.9, "IA_B_aereo_panel_norte_bajo")
        colocar(cd, panel(L2, 345, pan_base), Mx, (X_O + -8668.2) / 2, 1055.0, -40148.9, "IA_B_aereo_panel_norte_alto")
        # tablero 11-06 fuera del recorrido
        t11 = occ["11-06:1"]
        m = t11.Transformation
        v = tg.CreateMatrix()
        v.SetTranslation(tg.CreateVector(-107.1, 0, 35.8))
        m.TransformBy(v)
        S(lambda: setattr(t11, "Grounded", False))
        t11.Transformation = m
        log["tablero_11-06"] = [round(v_, 1) for v_ in caja(t11)]
        cel.Update()
        cel.Save()
finally:
    S(lambda: setattr(app, "SilentOperation", False))
print(json.dumps(log, ensure_ascii=False, indent=1))
