"""L3N: fotos "tipo render" para el presupuesto, sobre LayoutL3N_Celdas.iam (3 celdas + paredes + línea de pallets).
Fondo blanco, luz suave, sombras (ambiente + objeto + suelo, sin plano de suelo), perspectiva en las vistas 3D y
ortográfica en las plantas. No toca geometría ni guarda: restituye cámara, luz, sombras y modo de visualización.
Escribe <carpeta>\\camaras.json con la cámara de cada foto (para proyectar las etiquetas después).
Uso: python l3n_fotos_presupuesto.py <carpeta_salida> [--solo nombre1,nombre2] [--res 2400x1500] [--iam ruta]
"""
import json
import math
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
import inventor_mcp as inv  # noqa: E402

S = inv._safe
IAM = Path(sys.argv[sys.argv.index("--iam") + 1]) if "--iam" in sys.argv else Path(r"C:\DEFYMOTION\L3N\Celdas_IA\LayoutL3N_Celdas.iam")
OUT = Path(sys.argv[1])
SOLO = set(sys.argv[sys.argv.index("--solo") + 1].split(",")) if "--solo" in sys.argv else None
RES = sys.argv[sys.argv.index("--res") + 1] if "--res" in sys.argv else "2400x1500"
W_PX, H_PX = (int(v) for v in RES.split("x"))
ANG = 0.52                                   # ángulo de perspectiva (rad), ~30°
ORG_A = (-6503.2, 0.0, -35622.3)

# (nombre, tipo, eye, target, up, extents(w,h) sólo ortográficas) — mm, coordenadas del layout
FOTOS = [
    # (nombre, tipo, eye, target, up, extents (ancho, alto) en mm en el plano del target, pared visible, sombras de suelo)
    # planta completa en perspectiva: 4 candidatas (con paredes)
    ("planta_persp_E", "persp", (34000, 20000, -42000), (-4500, 0, -41000), (0, 1, 0), (46000, 28750), True, True),
    ("planta_persp_SE", "persp", (26000, 18000, -66000), (-4500, 0, -40000), (0, 1, 0), (46000, 28750), True, True),
    ("planta_persp_NE", "persp", (28000, 19000, -16000), (-4500, 0, -40000), (0, 1, 0), (46000, 28750), True, True),
    ("planta_persp_NE_alta", "persp", (22000, 30000, -18000), (-4500, 0, -40500), (0, 1, 0), (44000, 27500), True, True),
    # celda A con su cinta de llegada
    ("celdaA_persp_E", "persp", (17000, 9500, -34500), (-3500, 300, -31500), (0, 1, 0), (26000, 16250), True, True),
    ("celdaA_persp_SE", "persp", (12000, 9000, -47000), (-4000, 300, -31500), (0, 1, 0), (26000, 16250), False, True),
    # celda A sola, de cerca (robot, cinta interna, camas, cerco)
    ("celdaA_cerca", "persp", (6500, 6500, -42500), (-6500, 500, -35800), (0, 1, 0), (13000, 8125), False, True),
    # vista superior ortográfica de la zona de cambios (cinta nueva, rejas, puerta, buffers, celda)
    # orientación del DWG de planta de Adeco: x del plano = -Z del layout (derecha), y del plano = -X (arriba)
    ("cambios_top", "orto", (-500, 30000, -36000), (-500, 0, -36000), (-1, 0, 0), (28000, 28000), True, False),   # cuadrada: --res 2000x2000,
    # vista superior de la celda A sola (misma orientación)
    ("celdaA_top", "orto", (-7500, 30000, -35300), (-7500, 0, -35300), (-1, 0, 0), (17600, 11000), False, False),
    # buffers de pallets, pórticos y puerta de paso
    ("buffers_persp", "persp", (-3500, 5500, -27500), (-10200, 800, -32600), (0, 1, 0), (9000, 5625), False, True),
    # salida de pallets de la celda A: barrera IFM y camas (verificación)
    ("salida_persp", "persp", (-2300, 4300, -31800), (-7300, 500, -36600), (0, 1, 0), (7600, 4750), False, True),
    ("salida_cerca", "persp", (-4800, 2600, -33600), (-7400, 600, -35600), (0, 1, 0), (3600, 2250), False, True),
    ("camas_AB", "persp", (-1500, 4500, -36000), (-6500, 300, -39500), (0, 1, 0), (7000, 4375), False, True),
    # pasillo de mantenimiento y puerta, desde el lado de la pared
    ("pasillo_persp", "persp", (-14500, 4500, -24500), (-8500, 600, -30600), (0, 1, 0), (9000, 5625), False, True),
]

app = inv._inventor(start_if_needed=False)
tg = app.TransientGeometry
OUT.mkdir(parents=True, exist_ok=True)
log = {"fotos": [], "avisos": []}


def abrir(p):
    d = next((d for d in inv._items(app.Documents) if S(lambda: Path(d.FullFileName).resolve() == p.resolve(), False)), None)
    if d is None or not S(lambda: d.Views.Count, 0):
        d = app.Documents.Open(str(p), True)
    return d


app.SilentOperation = True
doc = abrir(IAM)
doc.Activate()
time.sleep(2)
v = app.ActiveView
cam = v.Camera
estado = {
    "eye": (cam.Eye.X, cam.Eye.Y, cam.Eye.Z), "target": (cam.Target.X, cam.Target.Y, cam.Target.Z),
    "up": (cam.UpVector.X, cam.UpVector.Y, cam.UpVector.Z), "persp": S(lambda: cam.Perspective, False),
    "modo": S(lambda: v.DisplayMode, None), "luz": S(lambda: doc.ActiveLightingStyle.Name, None),
    "sombras": {p: S(lambda: getattr(v, p), None) for p in ("ShowAmbientShadows", "ShowObjectShadows", "ShowGroundShadows",
                                                             "ShowGroundPlane", "ShowGroundReflections")},
}
ov = doc.ObjectVisibility
vis0 = {p: S(lambda: getattr(ov, p), None) for p in ("Sketches", "Sketches3D", "SketchDimensions", "Annotations3D",
                                                     "AllWorkFeatures", "ConstructionSurfaces", "UCSTriads", "UCSPlanes",
                                                     "UCSAxes", "UCSPoints")}
cs = app.ColorSchemes
esquema0 = next((c.Name for c in inv._items(cs) if S(lambda: c.Active, False)), None)
fondo0 = S(lambda: cs.BackgroundType, None)
try:
    # fondo blanco: esquema "Presentation" (fondo blanco) y fondo de un solo color
    for nombre in ("Presentation", "Presentación"):
        c = S(lambda: cs.Item(nombre), None)
        if c is not None:
            S(lambda: c.Activate())
            break
    else:
        log["avisos"].append("no encontré el esquema de colores Presentation")
    S(lambda: setattr(cs, "BackgroundType", 52737))     # kOneColorBackgroundType
    for p in vis0:
        S(lambda: setattr(ov, p, False))
    for p, val in (("ShowAmbientShadows", True), ("ShowObjectShadows", True), ("ShowGroundShadows", True),
                   ("ShowGroundPlane", False), ("ShowGroundReflections", False)):
        S(lambda: setattr(v, p, val))
    luz = None
    for nombre in ("Luz suave", "Soft Light", "Luz suave 1"):
        luz = S(lambda: doc.LightingStyles.Item(nombre), None)
        if luz is not None:
            break
    if luz is not None:
        S(lambda: setattr(doc, "ActiveLightingStyle", luz))
    else:
        log["avisos"].append("no encontré el estilo de luz 'Luz suave'; se usa el activo")
    S(lambda: setattr(v, "DisplayMode", 8452))        # sombreado con aristas (contraste sobre fondo blanco)
    # paredes (blancas) en gris claro sólo para la foto: apariencia en la ocurrencia, sin guardar
    gris = None
    for lib in inv._items(app.AssetLibraries):
        for a in inv._items(S(lambda: lib.AppearanceAssets, []) or []):
            nm = (S(lambda: a.DisplayName, "") or "").lower()
            if nm.startswith(("hormigón", "hormigon", "concrete")) or nm in ("gris claro", "light gray", "gris"):
                gris = a
                break
        if gris is not None:
            break
    paredes = [o for o in inv._items(doc.ComponentDefinition.Occurrences) if o.Name.lower().startswith("pared")]
    log["paredes"] = [o.Name for o in paredes]
    vis_pared = {o.Name: S(lambda: o.Visible, True) for o in paredes}
    log["apariencia_pared"] = S(lambda: gris.DisplayName, None)
    if gris is not None and paredes:
        gcopy = S(lambda: gris.CopyTo(doc), None) or gris
        for o in paredes:
            S(lambda: setattr(o, "Appearance", gcopy))
    else:
        log["avisos"].append("no pude pintar las paredes de gris (apariencia o paredes no encontradas)")

    def foto(nombre, tipo, eye, target, up, ext, pared, suelo):
        for o in paredes:                               # en el layout están ocultas: visibles sólo donde se pide
            S(lambda: setattr(o, "Visible", bool(pared)))
        S(lambda: setattr(v, "ShowGroundShadows", bool(suelo)))
        S(lambda: setattr(v, "ShowAmbientShadows", bool(suelo)))     # en las plantas, sin halos
        cam.Target = tg.CreatePoint(target[0] / 10, target[1] / 10, target[2] / 10)
        cam.Eye = tg.CreatePoint(eye[0] / 10, eye[1] / 10, eye[2] / 10)
        cam.UpVector = tg.CreateUnitVector(*up)
        if tipo == "persp":
            cam.Perspective = True
            S(lambda: setattr(cam, "PerspectiveAngle", ANG))
        else:
            cam.Perspective = False
        w, h = ext[0] / 10, ext[1] / 10
        r = W_PX / H_PX
        if w / h > r:
            cam.SetExtents(w, w / r)
        else:
            cam.SetExtents(h * r, h)
        cam.Apply()
        ruta = OUT / f"{nombre}.png"
        for _ in range(2):                           # calentamiento: sombras calculadas
            v.Update()
            v.SaveAsBitmap(str(ruta), W_PX, H_PX)
        info = {"nombre": nombre, "tipo": tipo, "png": str(ruta), "res": [W_PX, H_PX],
                "eye": [cam.Eye.X * 10, cam.Eye.Y * 10, cam.Eye.Z * 10],
                "target": [cam.Target.X * 10, cam.Target.Y * 10, cam.Target.Z * 10],
                "up": [cam.UpVector.X, cam.UpVector.Y, cam.UpVector.Z],
                "angulo": S(lambda: cam.PerspectiveAngle, ANG) if tipo == "persp" else None}
        w, h = ext
        info["extents"] = [w, w / r] if w / h > r else [h * r, h]
        return info

    for f in FOTOS:
        if SOLO and f[0] not in SOLO:
            continue
        try:
            log["fotos"].append(foto(*f))
            print(f[0], flush=True)
        except Exception as exc:  # noqa: BLE001
            log["avisos"].append(f"{f[0]}: {exc!r}")
finally:
    # restituir todo
    for o in (paredes if "paredes" in dir() else []):
        S(lambda: o.SetRenderStyle(53249))               # kPartRenderStyle: vuelve a la apariencia de la pieza
        S(lambda: setattr(o, "Visible", vis_pared.get(o.Name, False)))
    S(lambda: setattr(cam, "Perspective", estado["persp"]))
    S(lambda: setattr(cam, "Target", tg.CreatePoint(*estado["target"])))
    S(lambda: setattr(cam, "Eye", tg.CreatePoint(*estado["eye"])))
    S(lambda: setattr(cam, "UpVector", tg.CreateUnitVector(*estado["up"])))
    S(lambda: cam.Apply())
    if estado["modo"] is not None:
        S(lambda: setattr(v, "DisplayMode", estado["modo"]))
    for p, val in estado["sombras"].items():
        if val is not None:
            S(lambda: setattr(v, p, val))
    if estado["luz"]:
        S(lambda: setattr(doc, "ActiveLightingStyle", doc.LightingStyles.Item(estado["luz"])))
    for p, val in vis0.items():
        if val is not None:
            S(lambda: setattr(ov, p, val))
    if fondo0 is not None:
        S(lambda: setattr(cs, "BackgroundType", fondo0))
    if esquema0:
        S(lambda: cs.Item(esquema0).Activate())
    S(lambda: setattr(app, "SilentOperation", False))
(OUT / "camaras.json").write_text(json.dumps(log, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps(log, ensure_ascii=False, indent=1))
