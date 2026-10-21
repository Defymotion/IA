import sys, json, traceback
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
import inventor_mcp as inv
S = inv._safe
app = inv._inventor(start_if_needed=False)
tg = app.TransientGeometry; P = tg.CreatePoint2d
app.SilentOperation = True
OUT = Path.home() / "Documents" / "InventorIA" / "Generados" / "REJA_CROQUIS"
doc = app.Documents.Open(str(OUT / "Chapas" / "Base columna.ipt"), False)
dd = app.Documents.Add(inv.K_DRAWING_DOCUMENT, app.FileManager.GetTemplateFile(inv.K_DRAWING_DOCUMENT), True)
sh = dd.Sheets.Item(1)
v = sh.DrawingViews.AddBaseView(doc, P(10, 12), 0.5, inv.K_VIEW_FRONT, inv.K_STYLE_HLR)
sh.Update()
r = {"circ": [], "lines": 0, "pruebas": []}
dc = v.DrawingCurves
circ, lines = [], []
for i in range(1, dc.Count + 1):
    c = dc.Item(i)
    cp = S(lambda: c.CenterPoint); sp = S(lambda: c.StartPoint)
    r["circ"].append([S(lambda: c.CurveType), cp and round(cp.X, 3), cp and round(cp.Y, 3), sp is None])
    if cp is not None and sp is None: circ.append(c)
    elif sp is not None and cp is None: lines.append(c)
k0 = min(circ, key=lambda c: (c.CenterPoint.X, c.CenterPoint.Y))
lv = min([l for l in lines if abs(l.StartPoint.X - l.EndPoint.X) < 1e-5], key=lambda l: l.StartPoint.X)
gd = sh.DrawingDimensions.GeneralDimensions
li = sh.CreateGeometryIntent(lv)
def prueba(nom, f):
    try:
        gi = f()
        d = gd.AddLinear(P(k0.CenterPoint.X - 1, k0.CenterPoint.Y + 2), gi, li)
        r["pruebas"].append([nom, round(d.ModelValue * 10, 2)]); d.Delete()
    except Exception as e:
        r["pruebas"].append([nom, repr(e)[:120]])
for k in list(range(45569, 45592)) + list(range(46081, 46090)):
    prueba(f"enum {k}", lambda k=k: sh.CreateGeometryIntent(k0, k))
prueba("punto centro", lambda: sh.CreateGeometryIntent(k0, k0.CenterPoint))
prueba("sin intent", lambda: sh.CreateGeometryIntent(k0))
try:
    cm = sh.Centermarks.Add(sh.CreateGeometryIntent(k0))
    prueba("centermark", lambda: sh.CreateGeometryIntent(cm))
    prueba("centermark kCenter?", lambda: sh.CreateGeometryIntent(cm, 45572))
except Exception as e:
    r["pruebas"].append(["centermark add", repr(e)[:150]])
try:
    from win32com.client import constants as C
    r["const"] = {n: getattr(C, n, None) for n in ("kCenterPointIntent", "kStartPointIntent", "kEndPointIntent", "kMidPointIntent")}
except Exception as e:
    r["const"] = repr(e)
S(lambda: dd.Close(True))
app.SilentOperation = False
print(json.dumps(r, indent=0, default=str))
