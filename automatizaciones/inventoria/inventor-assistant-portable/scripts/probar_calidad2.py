"""Segunda prueba de calidad (no guarda): sombras de la vista, estilo de iluminación y modos de visualización."""
import json
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
import inventor_mcp as inv  # noqa: E402

S = inv._safe
DOCS = Path.home() / "Documents" / "InventorIA"
ESC = DOCS / "Generados" / "ADECO_SIM" / "ADECO_simulacion.iam"
OUT = DOCS / "Generados" / "ADECO_SIM" / "Calidad"
app = inv._inventor(start_if_needed=False)
doc = next((d for d in inv._items(app.Documents)
            if S(lambda: Path(d.FullFileName).resolve() == ESC.resolve(), False)), None) or app.Documents.Open(str(ESC), True)
doc.Activate()
v = app.ActiveView
cam = v.Camera
S(lambda: setattr(cam, "Perspective", False))
cam.Apply()
res = {"modos": {}}
for k in ("ShowAmbientShadows", "ShowObjectShadows", "ShowGroundShadows"):
    res[k] = str(S(lambda: setattr(v, k, True) or getattr(v, k), "error"))
res["ShowGroundPlane"] = str(S(lambda: setattr(v, "ShowGroundPlane", False) or v.ShowGroundPlane, "error"))
v.Update()
v.SaveAsBitmap(str(OUT / "D_sombras.png"), 2560, 1440)
for nombre in ("Luz suave", "Habitación gris", "Dos luces"):
    try:
        doc.ActiveLightingStyle = doc.LightingStyles.Item(nombre)
        v.Update()
        v.SaveAsBitmap(str(OUT / f"E_{nombre.replace(' ', '_')}.png"), 1600, 900)
        res.setdefault("luces", []).append(nombre)
    except Exception as exc:  # noqa: BLE001
        res.setdefault("luces_error", []).append(f"{nombre}: {exc}"[:100])
for modo in (8708, 8709, 8710, 8711, 8712, 8713, 8714, 8715):
    try:
        v.DisplayMode = modo
        v.Update()
        t = time.time()
        v.SaveAsBitmap(str(OUT / f"F_modo_{modo}.png"), 1600, 900)
        res["modos"][modo] = {"leido": S(lambda: v.DisplayMode), "s": round(time.time() - t, 2)}
    except Exception as exc:  # noqa: BLE001
        res["modos"][modo] = str(exc)[:80]
S(lambda: setattr(v, "DisplayMode", 8708))
(OUT / "calidad2.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps(res, ensure_ascii=False))
