"""Inventor Assistant — servidor MCP para Autodesk Inventor (COM, Windows).

v0.2.0
- Conexión por IDispatch dinámico (sin caché gen_py de pywin32).
- Constantes de Inventor como valores fijos (no depende de win32com.client.constants).
- Si Inventor no está abierto, se lanza `Inventor.exe /Automation` y se busca en la ROT.
- inventor_create_box: rectángulo centrado en el origen, restringido, con cotas
  visibles y parámetros con nombre (Ancho, Profundidad, Altura). Verifica con RangeBox.
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
import winreg
from pathlib import Path
from typing import Any

import pythoncom
from win32com.client.dynamic import Dispatch

try:
    from mcp.server.fastmcp import FastMCP
except ImportError:  # permite importar el módulo en pruebas sin el paquete mcp
    FastMCP = None


# --- Enumeraciones de Inventor 2025 (valores numéricos) ---------------------
K_PART_DOCUMENT = 12290          # DocumentTypeEnum.kPartDocumentObject
K_JOIN_OPERATION = 20481         # PartFeatureOperationEnum.kJoinOperation
K_POSITIVE_EXTENT = 20993        # PartFeatureExtentDirectionEnum.kPositiveExtentDirection

K_HORIZONTAL_DIM = 19201        # DimensionOrientationEnum.kHorizontalDim
K_VERTICAL_DIM = 19202          # DimensionOrientationEnum.kVerticalDim

# ConstraintStatusEnum
K_FULLY_CONSTRAINED = 51713
CONSTRAINT_STATUS_GUESS = {
    51713: "totalmente restringido",
    51714: "sin restringir del todo",
    51715: "sobre-restringido",
    51716: "desconocido",
}

PROGID = "Inventor.Application"
TOL_MM = 0.001


def _log(msg: str) -> None:
    print(f"[inventor] {msg}", file=sys.stderr, flush=True)


def _result(**values: Any) -> str:
    return json.dumps(values, ensure_ascii=False, default=str)


# --- Conexión ----------------------------------------------------------------
PRIVADO = "InventorIA.Privado"     # nombre con que el vigilante registra SU Inventor oculto en la ROT


def _get_private() -> Any | None:
    """Inventor PRIVADO del vigilante (oculto, prioridad baja), registrado en la ROT como '!InventorIA.Privado'.
    Así los trabajos no usan el Inventor en el que está trabajando el usuario."""
    pythoncom.CoInitialize()
    try:
        rot = pythoncom.GetRunningObjectTable()
        ctx = pythoncom.CreateBindCtx(0)
        for mk in rot.EnumRunning():
            try:
                if PRIVADO in mk.GetDisplayName(ctx, None):
                    unk = rot.GetObject(mk)
                    app = Dispatch(unk.QueryInterface(pythoncom.IID_IDispatch))
                    app.Ready                                  # que esté vivo
                    return app
            except pythoncom.com_error:
                continue
    except pythoncom.com_error:
        return None
    return None


def _usa_privado() -> bool:
    import os
    return os.environ.get("INVENTORIA_INSTANCIA", "privado").lower() != "usuario"


def _get_running() -> Any | None:
    """Devuelve la aplicación Inventor: primero el Inventor privado del vigilante (si existe y no se pidió
    INVENTORIA_INSTANCIA=usuario); si no, la instancia activa del usuario (vía ROT) o None."""
    pythoncom.CoInitialize()
    if _usa_privado():
        app = _get_private()
        if app is not None:
            return app
    try:
        unknown = pythoncom.GetActiveObject(PROGID)
    except pythoncom.com_error:
        return None
    return Dispatch(unknown.QueryInterface(pythoncom.IID_IDispatch))


def es_privado(app) -> bool:
    """True si 'app' es el Inventor oculto del vigilante (no hay que hacerlo visible)."""
    p = _get_private() if _usa_privado() else None
    try:
        return p is not None and int(p.MainFrameHWND) == int(app.MainFrameHWND)
    except pythoncom.com_error:
        return False


def _inventor_exe() -> Path | None:
    """Obtiene la ruta de Inventor.exe desde el registro COM."""
    try:
        with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, rf"{PROGID}\CLSID") as key:
            clsid = winreg.QueryValue(key, None)
        with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, rf"CLSID\{clsid}\LocalServer32") as key:
            raw = winreg.QueryValue(key, None)
    except OSError:
        return None
    raw = raw.strip()
    if raw.startswith('"'):
        exe = raw[1:].split('"', 1)[0]
    else:
        exe = raw.split(" /", 1)[0]
    path = Path(exe)
    return path if path.is_file() else None


def _inventor(start_if_needed: bool = True, timeout_s: float = 180.0, visible: bool = True) -> Any:
    app = _get_running()
    if app is None:
        if not start_if_needed:
            raise RuntimeError("Inventor no está en ejecución")
        exe = _inventor_exe()
        if exe is None:
            raise RuntimeError("No se encontró Inventor.exe en el registro COM")
        _log(f"Iniciando {exe} /Automation")
        subprocess.Popen([str(exe), "/Automation"], close_fds=True)
        deadline = time.monotonic() + timeout_s
        while app is None and time.monotonic() < deadline:
            time.sleep(2)
            app = _get_running()
        if app is None:
            raise RuntimeError(
                "Inventor no apareció en la Running Object Table. Verificá que Inventor y este "
                "proceso corran en la misma sesión de Windows y con el mismo nivel de permisos "
                "(ambos normales o ambos como administrador)."
            )
        # esperar a que termine de inicializar
        while time.monotonic() < deadline:
            try:
                if app.Ready:
                    break
            except pythoncom.com_error:
                pass
            time.sleep(1)
    if visible and not es_privado(app):
        try:
            app.Visible = True
        except pythoncom.com_error:
            pass
    return app


# --- Utilidades --------------------------------------------------------------
def _output_path(raw_path: str, expected_suffix: str | None = None) -> Path:
    path = Path(raw_path).expanduser().resolve()
    if expected_suffix and path.suffix.lower() != expected_suffix:
        raise ValueError(f"La ruta debe terminar en {expected_suffix}")
    if not path.parent.exists():
        raise ValueError(f"La carpeta no existe: {path.parent}")
    return path


def _items(collection: Any) -> list[Any]:
    return [collection.Item(i) for i in range(1, collection.Count + 1)]


def _try(fn, *args) -> bool:
    try:
        fn(*args)
        return True
    except pythoncom.com_error:
        return False  # restricción redundante o ya existente


# --- Herramientas ------------------------------------------------------------
def inventor_status(start_if_needed: bool = False) -> str:
    """Comprueba Autodesk Inventor y devuelve versión y documento activo. Puede iniciarlo."""
    app = _get_running()
    if app is None and not start_if_needed:
        exe = _inventor_exe()
        return _result(
            installed=exe is not None,
            running=False,
            exe=str(exe) if exe else None,
            hint="Usá start_if_needed=true para abrir Inventor en modo /Automation",
        )
    app = app or _inventor(start_if_needed=True)
    active = None
    try:
        doc = app.ActiveDocument
        active = doc.FullFileName or doc.DisplayName
    except (pythoncom.com_error, AttributeError):
        pass
    return _result(installed=True, running=True,
                   version=app.SoftwareVersion.DisplayVersion, active_document=active)


def inventor_create_box(width_mm: float, depth_mm: float, height_mm: float,
                        output_path: str, overwrite: bool = False) -> str:
    """Crea una pieza .ipt rectangular paramétrica (mm): boceto centrado en el origen,
    restringido, con cotas Ancho/Profundidad y extrusión Altura. La guarda y verifica."""
    if min(width_mm, depth_mm, height_mm) <= 0:
        raise ValueError("Todas las dimensiones deben ser mayores que cero")
    path = _output_path(output_path, ".ipt")
    if path.exists() and not overwrite:
        raise FileExistsError(f"El archivo ya existe: {path}")

    app = _inventor()
    template = app.FileManager.GetTemplateFile(K_PART_DOCUMENT)
    document = app.Documents.Add(K_PART_DOCUMENT, template, True)
    definition = document.ComponentDefinition
    tg = app.TransientGeometry

    # 1. Boceto en plano XY y punto del origen proyectado
    sketch = definition.Sketches.Add(definition.WorkPlanes.Item(3))
    sketch.Name = "Base rectangular"
    origin = sketch.AddByProjectingEntity(definition.WorkPoints.Item(1))

    # 2. Rectángulo (las coordenadas iniciales ya son las correctas; luego lo fijan las cotas)
    hw, hd = width_mm / 20.0, depth_mm / 20.0  # cm, mitades
    lines = _items(sketch.SketchLines.AddAsTwoPointRectangle(
        tg.CreatePoint2d(-hw, -hd), tg.CreatePoint2d(hw, hd)))

    def is_horizontal(line) -> bool:
        s, e = line.StartSketchPoint.Geometry, line.EndSketchPoint.Geometry
        return abs(s.Y - e.Y) < 1e-9

    def mid_y(line) -> float:
        return (line.StartSketchPoint.Geometry.Y + line.EndSketchPoint.Geometry.Y) / 2

    def mid_x(line) -> float:
        return (line.StartSketchPoint.Geometry.X + line.EndSketchPoint.Geometry.X) / 2

    horizontals = sorted([l for l in lines if is_horizontal(l)], key=mid_y)
    verticals = sorted([l for l in lines if not is_horizontal(l)], key=mid_x)
    if len(horizontals) != 2 or len(verticals) != 2:
        raise RuntimeError("El rectángulo no tiene 2 líneas horizontales y 2 verticales")
    bottom, top = horizontals
    left, right = verticals

    # 3. Restricciones geométricas (se ignoran las que Inventor ya creó)
    gc = sketch.GeometricConstraints
    added = {"horizontal": 0, "vertical": 0, "coincidente": 0}
    for l in horizontals:
        added["horizontal"] += _try(gc.AddHorizontal, l)
    for l in verticals:
        added["vertical"] += _try(gc.AddVertical, l)
    for a, b in ((bottom, right), (right, top), (top, left), (left, bottom)):
        for pa in (a.StartSketchPoint, a.EndSketchPoint):
            for pb in (b.StartSketchPoint, b.EndSketchPoint):
                ga, gb = pa.Geometry, pb.Geometry
                if abs(ga.X - gb.X) < 1e-9 and abs(ga.Y - gb.Y) < 1e-9:
                    added["coincidente"] += _try(gc.AddCoincident, pa, pb)

    # 4. Centrado: diagonal de construcción con su punto medio en el origen
    corners = {}
    for l in lines:
        for p in (l.StartSketchPoint, l.EndSketchPoint):
            g = p.Geometry
            corners.setdefault((round(g.X, 6), round(g.Y, 6)), p)
    p_min = corners[min(corners)]          # esquina inferior izquierda
    p_max = corners[max(corners)]          # esquina superior derecha
    diagonal = sketch.SketchLines.AddByTwoPoints(p_min, p_max)
    diagonal.Construction = True
    gc.AddMidpoint(origin, diagonal)

    # 5. Cotas visibles con parámetros nombrados
    dims = sketch.DimensionConstraints
    off = 0.15 * max(hw, hd) + 0.5  # cm, separación del texto
    d_ancho = dims.AddTwoPointDistance(bottom.StartSketchPoint, bottom.EndSketchPoint,
                                       K_HORIZONTAL_DIM, tg.CreatePoint2d(0, -hd - off))
    d_prof = dims.AddTwoPointDistance(right.StartSketchPoint, right.EndSketchPoint,
                                      K_VERTICAL_DIM, tg.CreatePoint2d(hw + off, 0))
    d_ancho.Parameter.Name = "Ancho"
    d_ancho.Parameter.Expression = f"{width_mm} mm"
    d_prof.Parameter.Name = "Profundidad"
    d_prof.Parameter.Expression = f"{depth_mm} mm"
    try:
        sketch.DimensionsVisible = True
    except pythoncom.com_error:
        pass

    # 6. Extrusión con parámetro Altura
    profile = sketch.Profiles.AddForSolid()
    extrudes = definition.Features.ExtrudeFeatures
    ext_def = extrudes.CreateExtrudeDefinition(profile, K_JOIN_OPERATION)
    ext_def.SetDistanceExtent(f"{height_mm} mm", K_POSITIVE_EXTENT)
    extrude = extrudes.Add(ext_def)
    extrude.Name = "Extrusión base"
    try:
        height_param = extrude.Extent.Distance
    except (pythoncom.com_error, AttributeError):
        height_param = extrude.Definition.Extent.Distance
    height_param.Name = "Altura"
    height_param.Expression = f"{height_mm} mm"
    document.Update()

    # 7. Verificación por caja envolvente (API en cm)
    box = definition.SurfaceBodies.Item(1).RangeBox
    measured = {
        "ancho_mm": round((box.MaxPoint.X - box.MinPoint.X) * 10, 4),
        "profundidad_mm": round((box.MaxPoint.Y - box.MinPoint.Y) * 10, 4),
        "altura_mm": round((box.MaxPoint.Z - box.MinPoint.Z) * 10, 4),
    }
    expected = {"ancho_mm": width_mm, "profundidad_mm": depth_mm, "altura_mm": height_mm}
    ok = all(abs(measured[k] - expected[k]) <= TOL_MM for k in expected)

    # 8. Guardar
    if path.exists() and overwrite:
        path.unlink()
    document.SaveAs(str(path), False)

    # 9. Estado de restricción: leerlo DESPUÉS de document.Update(), si no da un valor viejo
    constraint_status = None
    try:
        constraint_status = int(sketch.ConstraintStatus)
    except (pythoncom.com_error, AttributeError, TypeError):
        pass
    diagnostics = None if constraint_status == K_FULLY_CONSTRAINED else _sketch_diagnostics(sketch)

    params = {p.Name: p.Expression for p in _items(definition.Parameters.ModelParameters)
              if p.Name in ("Ancho", "Profundidad", "Altura")}
    return _result(
        created=True, path=str(path), verified=ok, expected=expected, measured=measured,
        parameters=params, constraints_added=added,
        sketch_constraint_status=constraint_status,
        sketch_constraint_status_label=CONSTRAINT_STATUS_GUESS.get(constraint_status),
        sketch_diagnostics=diagnostics,
    )


def _sketch_diagnostics(sketch) -> dict:
    """Estado de cada punto/línea y tipos de restricción; se usa cuando el boceto no está totalmente restringido."""
    diag_points = []
    for p in _items(sketch.SketchPoints):
        g = p.Geometry
        try:
            st = int(p.ConstraintStatus)
        except (pythoncom.com_error, AttributeError, TypeError):
            st = None
        try:
            ref = bool(p.Reference)
        except (pythoncom.com_error, AttributeError):
            ref = None
        diag_points.append({"x_mm": round(g.X * 10, 3), "y_mm": round(g.Y * 10, 3),
                            "status": CONSTRAINT_STATUS_GUESS.get(st, st), "referencia": ref})
    diag_constraints = []
    for c in _items(sketch.GeometricConstraints):
        try:
            diag_constraints.append(int(c.Type))
        except (pythoncom.com_error, AttributeError, TypeError):
            diag_constraints.append(None)
    diag_lines = []
    for l in _items(sketch.SketchLines):
        try:
            diag_lines.append({"construccion": bool(l.Construction),
                               "status": CONSTRAINT_STATUS_GUESS.get(int(l.ConstraintStatus))})
        except (pythoncom.com_error, AttributeError, TypeError):
            diag_lines.append(None)
    return {"puntos": diag_points, "lineas": diag_lines,
            "restricciones_geometricas_tipos": diag_constraints,
            "cotas": sketch.DimensionConstraints.Count}


def inventor_open_document(path: str, visible: bool = True) -> str:
    """Abre un documento compatible con Autodesk Inventor."""
    source = Path(path).expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(f"No existe el archivo: {source}")
    app = _inventor()
    document = app.Documents.Open(str(source), visible)
    return _result(opened=True, path=str(source), display_name=document.DisplayName, visible=visible)


def inventor_export_active_document(output_path: str, overwrite: bool = False) -> str:
    """Guarda una copia del documento activo en el formato que indica la extensión de destino."""
    path = _output_path(output_path)
    if path.exists() and not overwrite:
        raise FileExistsError(f"El archivo ya existe: {path}")
    app = _inventor()
    try:
        document = app.ActiveDocument
        name = document.DisplayName
    except (pythoncom.com_error, AttributeError) as exc:
        raise RuntimeError("No hay un documento activo en Inventor") from exc
    if path.exists() and overwrite:
        path.unlink()
    document.SaveAs(str(path), True)
    return _result(exported=True, source=name, path=str(path))


# =============================================================================
# Chapa plegada en C: modelo de chapa + desarrollo + DXF de corte + plano IDW/PDF
# =============================================================================
import math  # noqa: E402

SHEET_METAL_SUBTYPE = "{9C464203-9BAE-11D3-8BAD-0060B0CE6BB4}"
K_DRAWING_DOCUMENT = 12292        # DocumentTypeEnum.kDrawingDocumentObject
K_NEGATIVE_EXTENT = 20994         # PartFeatureExtentDirectionEnum.kNegativeExtentDirection
K_HEIGHT_DATUM_OUTER = 75521      # HeightDatumTypeEnum.kHeightDatumOuter
K_BEND_INSIDE_BASE = 75011        # BendPositionEnum.kBendPositionInsideBendFace
K_VIEW_DEFAULT = 10753            # ViewOrientationTypeEnum
K_VIEW_FRONT = 10764
K_VIEW_TOP = 10754
K_VIEW_RIGHT = 10755
K_STYLE_HLR = 32258               # DrawingViewStyleEnum.kHiddenLineRemovedDrawingViewStyle
K_STYLE_FROM_BASE = 32260
K_FILE_BROWSE_IO = 13059          # IOMechanismEnum.kFileBrowseIOMechanism
MAX_TITLE = 30            # caracteres que entran en la casilla de título del cajetín
MAX_PART_NUMBER = 18      # caracteres que entran en la casilla de código
PDF_ADDIN = "{0AC6FD96-2F4D-42CE-8BE0-8AEA580399E4}"

DXF_HIDDEN_LAYERS = ("IV_TANGENT;IV_BEND;IV_BEND_DOWN;IV_TOOL_CENTER;IV_TOOL_CENTER_DOWN;"
                     "IV_ARC_CENTERS;IV_FEATURE_PROFILES;IV_FEATURE_PROFILES_DOWN;IV_ALTREP_FRONT;"
                     "IV_ALTREP_BACK;IV_ROLL_TANGENT;IV_ROLL;IV_UNCONSUMED_SKETCHES")


def _fmt(v: float, nd: int = 2) -> str:
    return f"{v:.{nd}f}".rstrip("0").rstrip(".").replace(".", ",")


def _iprop(doc, set_name: str, prop: str, value: str) -> None:
    try:
        doc.PropertySets.Item(set_name).Item(prop).Value = value
    except pythoncom.com_error:
        pass


def _set_material(app, doc, candidates: list[str]) -> str | None:
    for name in candidates:
        try:
            asset = app.ActiveMaterialLibrary.MaterialAssets.Item(name)
        except pythoncom.com_error:
            continue
        try:
            try:
                local = doc.MaterialAssets.Item(name)
            except pythoncom.com_error:
                local = asset.CopyTo(doc)
            doc.ActiveMaterial = local
            return doc.ActiveMaterial.DisplayName
        except pythoncom.com_error:
            continue
    try:
        return doc.ActiveMaterial.DisplayName
    except pythoncom.com_error:
        return None


def _extent_mm(definition) -> tuple[float, float, float]:
    box = definition.SurfaceBodies.Item(1).RangeBox
    return (round((box.MaxPoint.X - box.MinPoint.X) * 10, 3),
            round((box.MaxPoint.Y - box.MinPoint.Y) * 10, 3),
            round((box.MaxPoint.Z - box.MinPoint.Z) * 10, 3))


def _centered_rect_sketch(app, definition, plane, a_mm, b_mm, name_a, name_b, sketch_name):
    """Rectángulo centrado en el origen, totalmente restringido, cotas con nombre (a: eje x del boceto)."""
    tg = app.TransientGeometry
    sketch = definition.Sketches.Add(plane)
    sketch.Name = sketch_name
    origin = sketch.AddByProjectingEntity(definition.WorkPoints.Item(1))
    ha, hb = a_mm / 20.0, b_mm / 20.0
    lines = _items(sketch.SketchLines.AddAsTwoPointRectangle(
        tg.CreatePoint2d(-ha, -hb), tg.CreatePoint2d(ha, hb)))
    is_h = [abs(l.StartSketchPoint.Geometry.Y - l.EndSketchPoint.Geometry.Y) < 1e-9 for l in lines]
    horiz = [l for l, hz in zip(lines, is_h) if hz]
    vert = [l for l, hz in zip(lines, is_h) if not hz]
    bottom = min(horiz, key=lambda l: l.StartSketchPoint.Geometry.Y)
    right = max(vert, key=lambda l: l.StartSketchPoint.Geometry.X)
    corners = {}
    for l in lines:
        for p in (l.StartSketchPoint, l.EndSketchPoint):
            g = p.Geometry
            corners.setdefault((round(g.X, 6), round(g.Y, 6)), p)
    diag = sketch.SketchLines.AddByTwoPoints(corners[min(corners)], corners[max(corners)])
    diag.Construction = True
    sketch.GeometricConstraints.AddMidpoint(origin, diag)
    dims = sketch.DimensionConstraints
    off = 0.15 * max(ha, hb) + 0.5
    da = dims.AddTwoPointDistance(bottom.StartSketchPoint, bottom.EndSketchPoint,
                                  K_HORIZONTAL_DIM, tg.CreatePoint2d(0, -hb - off))
    db = dims.AddTwoPointDistance(right.StartSketchPoint, right.EndSketchPoint,
                                  K_VERTICAL_DIM, tg.CreatePoint2d(ha + off, 0))
    da.Parameter.Name, da.Parameter.Expression = name_a, f"{a_mm} mm"
    db.Parameter.Name, db.Parameter.Expression = name_b, f"{b_mm} mm"
    return sketch


# --- vistas del plano ---------------------------------------------------------
def _view_curves(view):
    dc = view.DrawingCurves
    try:
        n = dc.Count
    except (pythoncom.com_error, AttributeError, TypeError):
        dc = view.DrawingCurves()
        n = dc.Count
    lines, arcs = [], []
    for i in range(1, n + 1):
        c = dc.Item(i)
        cp = _safe(lambda: c.CenterPoint)
        sp = _safe(lambda: c.StartPoint)
        ep = _safe(lambda: c.EndPoint)
        if cp is not None:            # arco o círculo (los círculos no tienen punto inicial)
            if sp is not None:
                arcs.append({"c": c, "cx": cp.X, "cy": cp.Y,
                             "r": math.hypot(sp.X - cp.X, sp.Y - cp.Y), "sx": sp.X, "sy": sp.Y})
            continue
        if sp is None or ep is None:  # splines u otras curvas sin extremos
            continue
        d = {"c": c, "x1": sp.X, "y1": sp.Y, "x2": ep.X, "y2": ep.Y}
        d["vert"] = abs(sp.X - ep.X) < 1e-6
        d["horiz"] = abs(sp.Y - ep.Y) < 1e-6
        d["x"] = (sp.X + ep.X) / 2
        d["y"] = (sp.Y + ep.Y) / 2
        lines.append(d)
    return lines, arcs


def _view_box(view):
    cx, cy = view.Center.X, view.Center.Y
    return cx - view.Width / 2, cx + view.Width / 2, cy - view.Height / 2, cy + view.Height / 2


class _Dims:
    def __init__(self, app, sheet):
        self.tg = app.TransientGeometry
        self.sheet = sheet
        self.gd = sheet.DrawingDimensions.GeneralDimensions
        self.ok, self.failed = 0, []

    def pt(self, x, y):
        return self.tg.CreatePoint2d(x, y)

    @staticmethod
    def _precision(dim):
        """Entero sin decimales (100); si no, 2 decimales (4,76)."""
        try:
            mm = dim.ModelValue * 10
            dim.Precision = 0 if abs(mm - round(mm)) < 1e-3 else 2
        except (pythoncom.com_error, AttributeError):
            pass

    def linear(self, label, x, y, c1, c2):
        try:
            d = self.gd.AddLinear(self.pt(x, y), self.sheet.CreateGeometryIntent(c1),
                                  self.sheet.CreateGeometryIntent(c2))
            self._precision(d)
            self.ok += 1
        except pythoncom.com_error as exc:
            self.failed.append(f"{label}: {exc}")

    def radius(self, label, x, y, c):
        try:
            d = self.gd.AddRadius(self.pt(x, y), self.sheet.CreateGeometryIntent(c))
            self._precision(d)
            self.ok += 1
        except pythoncom.com_error as exc:
            self.failed.append(f"{label}: {exc}")


def _dimension_profile(dims: _Dims, view, thickness_cm_sheet: float) -> None:
    """Vista del perfil en C: ancho total, altura de ala, espesor y radio interior."""
    lines, arcs = _view_curves(view)
    left, right, bottom, top = _view_box(view)
    v = sorted([l for l in lines if l["vert"]], key=lambda l: l["x"])
    h = sorted([l for l in lines if l["horiz"]], key=lambda l: l["y"])
    if len(v) >= 2:
        dims.linear("ancho total", (left + right) / 2, bottom - 1.3, v[0]["c"], v[-1]["c"])
    if len(h) >= 2:
        dims.linear("altura ala", left - 0.9, (bottom + top) / 2, h[0]["c"], h[-1]["c"])
    if v:  # espesor medido en el ala derecha
        inner = [l for l in v if abs(v[-1]["x"] - l["x"] - thickness_cm_sheet) < 0.02]
        if inner:
            dims.linear("espesor", right + 0.9, top - 0.1, inner[0]["c"], v[-1]["c"])
    # El radio de plegado no se acota (lo define la plegadora); figura en la nota general.


def _dimension_length(dims: _Dims, view, label: str) -> None:
    lines, _ = _view_curves(view)
    left, right, bottom, top = _view_box(view)
    v = sorted([l for l in lines if l["vert"]], key=lambda l: l["x"])
    if len(v) >= 2:
        dims.linear(label, (left + right) / 2, bottom - 0.8, v[0]["c"], v[-1]["c"])


def _dimension_flat(dims: _Dims, sheet, view) -> dict:
    """Desarrollo: medidas totales, posición de cada pliegue y una nota por pliegue.
    Los tramos colineales de una misma línea de plegado (cortada por una escotadura) cuentan como uno."""
    lines, _ = _view_curves(view)
    left, right, bottom, top = _view_box(view)
    v = sorted([l for l in lines if l["vert"]], key=lambda l: l["x"])
    h = sorted([l for l in lines if l["horiz"]], key=lambda l: l["y"])
    notes = sheet.DrawingNotes.BendNotes
    groups: dict[tuple, dict] = {}
    moved_texts: list[str] = []
    for l in v[1:-1] + h[1:-1]:
        key = ("v", round(l["x"], 3)) if l["vert"] else ("h", round(l["y"], 3))
        try:
            note = notes.Add(l["c"])
        except pythoncom.com_error:
            continue                      # no es línea de plegado
        if key in groups:                 # tramo de un pliegue ya anotado
            _safe(lambda: note.Delete())
            continue
        groups[key] = l
        # la nota se centra en la vista; si Inventor no deja moverla, su texto pasa a las notas generales
        cx, cy = (left + right) / 2, (bottom + top) / 2
        tx, ty = (l["x"], cy) if l["vert"] else (cx, l["y"])
        _safe(lambda: setattr(note, "Position", dims.pt(tx, ty)))
        now = _safe(lambda: note.Position)
        if now is None or abs(now.X - tx) + abs(now.Y - ty) > 0.2:
            text = _safe(lambda: note.Text) or _safe(lambda: note.FormattedText) or ""
            moved_texts.append(re.sub(r"<[^>]+>", "", str(text)).strip())
            _safe(lambda: note.Delete())
    bends = sorted(groups.values(), key=lambda l: (l["x"], l["y"]))
    nv = nh = 0
    for b in bends:
        if b["vert"] and len(v) >= 2:
            dims.linear(f"plegado x={b['x']:.2f}", (v[0]["x"] + b["x"]) / 2, bottom - 0.7 - 0.6 * nv,
                        v[0]["c"], b["c"])
            nv += 1
        elif b["horiz"] and len(h) >= 2:
            dims.linear(f"plegado y={b['y']:.2f}", left - 0.7 - 0.6 * nh, (h[0]["y"] + b["y"]) / 2,
                        h[0]["c"], b["c"])
            nh += 1
    if len(v) >= 2:
        dims.linear("desarrollo largo", (left + right) / 2, bottom - 0.7 - 0.6 * nv, v[0]["c"], v[-1]["c"])
    if len(h) >= 2:
        dims.linear("desarrollo ancho", right + 0.9, (bottom + top) / 2, h[0]["c"], h[-1]["c"])
    return {"lineas_de_plegado": len(bends), "filas_cotas_abajo": nv + 1, "columnas_cotas_izq": nh,
            "notas_plegado_movidas": moved_texts}


def _export_pdf(app, ddoc, pdf_path: Path) -> str:
    try:
        tr = app.ApplicationAddIns.ItemById(PDF_ADDIN)
        ctx = app.TransientObjects.CreateTranslationContext()
        ctx.Type = K_FILE_BROWSE_IO
        opts = app.TransientObjects.CreateNameValueMap()
        for k, val in (("All_Color_AS_Black", 1), ("Vector_Resolution", 400), ("Sheet_Range", 14082)):
            try:
                opts.Add(k, val)
            except pythoncom.com_error:
                pass
        data = app.TransientObjects.CreateDataMedium()
        data.FileName = str(pdf_path)
        tr.SaveCopyAs(ddoc, ctx, opts, data)
        return "translator"
    except pythoncom.com_error:
        ddoc.SaveAs(str(pdf_path), True)
        return "saveas"


def inventor_create_c_channel(
    web_mm: float, flange_mm: float, length_mm: float, thickness: str, output_dir: str,
    name: str = "", part_number: str = "", title: str = "", material: str = "", bend_radius_mm: float | None = None,
    quantity: int = 1, general_tolerance: str = "ISO 2768-m", sheet_size: str = "A4",
    overwrite: bool = False,
) -> str:
    """Crea una chapa plegada en C (medidas EXTERIORES en mm), su desarrollo, el DXF de corte láser
    (1:1, solo contorno de corte) y el plano de fabricación (.idw + .pdf).
    thickness: expresión de Inventor, p. ej. "3/16 in" o "4.76 mm".
    bend_radius_mm: radio interior; si se omite, se usa el del estilo de chapa (por defecto = espesor).
    sheet_size: "A4" o "A3" (apaisada). Estructura: output_dir/Modelos, Planos, Planos/PDF, Corte_laser."""
    if min(web_mm, flange_mm, length_mm) <= 0:
        raise ValueError("Las medidas deben ser mayores que cero")
    base = Path(output_dir).expanduser().resolve()
    if not base.parent.exists():
        raise ValueError(f"La carpeta no existe: {base.parent}")
    app = _inventor()
    tg = app.TransientGeometry
    warnings: list[str] = []

    # --- modelo de chapa ------------------------------------------------------
    try:
        template = app.FileManager.GetTemplateFile(K_PART_DOCUMENT, pythoncom.Missing,
                                                   pythoncom.Missing, SHEET_METAL_SUBTYPE)
    except pythoncom.com_error:
        template = app.FileManager.GetTemplateFile(K_PART_DOCUMENT)
    doc = app.Documents.Add(K_PART_DOCUMENT, template, True)
    if doc.SubType != SHEET_METAL_SUBTYPE:
        doc.SubType = SHEET_METAL_SUBTYPE
    cd = doc.ComponentDefinition
    try:
        cd.UseSheetMetalStyleThickness = False
    except pythoncom.com_error:
        pass
    cd.Thickness.Expression = thickness
    doc.Update()
    t_mm = cd.Thickness.Value * 10
    drawing_template = app.FileManager.GetTemplateFile(K_DRAWING_DOCUMENT)
    drawing_ext = ".dwg" if str(drawing_template).lower().endswith(".dwg") else ".idw"
    thick_label = thickness.replace(" in", '"').replace(" mm", " mm")
    # Textos del cajetín con largo máximo; el nombre de archivo puede ser más largo.
    if not part_number:
        part_number = f"CH-C{_fmt(web_mm)}x{_fmt(flange_mm)}-L{_fmt(length_mm)}"
    if not title:
        title = f"CHAPA C {_fmt(web_mm)}x{_fmt(flange_mm)} L{_fmt(length_mm)} e{thick_label}"
    if len(part_number) > MAX_PART_NUMBER:
        warnings.append(f"Código '{part_number}' recortado a {MAX_PART_NUMBER} caracteres")
        part_number = part_number[:MAX_PART_NUMBER]
    if len(title) > MAX_TITLE:
        warnings.append(f"Título '{title}' recortado a {MAX_TITLE} caracteres")
        title = title[:MAX_TITLE]
    if not name:
        name = f"{part_number}_e{_fmt(t_mm)}"
    paths = {
        "ipt": base / "Modelos" / f"{name}.ipt",
        "plano": base / "Planos" / f"{name}{drawing_ext}",
        "pdf": base / "Planos" / "PDF" / f"{name}.pdf",
        "dxf": base / "Corte_laser" / f"Chapa_{_fmt(t_mm)}mm" / f"{name}.dxf",
    }
    for p in paths.values():
        if p.exists() and not overwrite:
            raise FileExistsError(f"El archivo ya existe: {p}")
        p.parent.mkdir(parents=True, exist_ok=True)

    _centered_rect_sketch(app, cd, cd.WorkPlanes.Item(2), web_mm, length_mm,
                          "Alma", "Largo", "Boceto alma")
    sketch = cd.Sketches.Item(cd.Sketches.Count)
    face = cd.Features.FaceFeatures.Add(
        cd.Features.FaceFeatures.CreateFaceFeatureDefinition(sketch.Profiles.AddForSolid()))
    face.Name = "Alma"

    # --- alas -----------------------------------------------------------------
    # Se buscan las alas con medidas EXTERIORES: se prueban posiciones de pliegue y, si ninguna
    # deja el ancho total igual al pedido, la cara del alma se define como Alma - 2*Thickness.
    flanges = cd.Features.FlangeFeatures
    target = (web_mm, flange_mm, length_mm)          # X, Y, Z
    tried = []

    def matches(ext):
        return all(abs(a - b) <= TOL_MM for a, b in zip(ext, target))

    def add_flange(bend_pos):
        body = cd.SurfaceBodies.Item(1)
        planar = []
        for f in _items(body.Faces):
            ys = [v.Point.Y for v in _items(f.Vertices)]
            if len(ys) >= 4 and max(ys) - min(ys) < 1e-6:
                planar.append((ys[0], f))
        if len(planar) < 2:
            raise RuntimeError("No se encontraron las caras del alma")
        base_face = max(planar, key=lambda t: t[0])[1]
        cand = []
        for e in _items(base_face.Edges):
            p1, p2 = e.StartVertex.Point, e.StopVertex.Point
            if abs(p1.X - p2.X) < 1e-6:
                cand.append((abs(p1.X), e))
        xmax = max(c[0] for c in cand)
        edges = app.TransientObjects.CreateEdgeCollection()
        for x, e in cand:
            if abs(x - xmax) < 1e-6:
                edges.Add(e)
        if edges.Count != 2:
            raise RuntimeError(f"Se esperaban 2 aristas para las alas, hay {edges.Count}")
        fdef = flanges.CreateFlangeDefinition(edges, math.pi / 2, f"{flange_mm} mm")
        info = {"posicion_pliegue": bend_pos}
        try:
            fdef.SetDistanceHeightExtent(f"{flange_mm} mm", K_POSITIVE_EXTENT, K_HEIGHT_DATUM_OUTER)
        except pythoncom.com_error as exc:
            info["error_altura"] = str(exc)
        if bend_pos is not None:
            try:
                fdef.BendPosition = bend_pos
            except pythoncom.com_error as exc:
                info["error_posicion"] = str(exc)
        if bend_radius_mm:
            fdef.BendRadius = f"{bend_radius_mm} mm"
        try:
            fl = flanges.Add(fdef)
        except pythoncom.com_error as exc:
            info["error"] = str(exc)
            tried.append(info)
            return None, None
        doc.Update()
        ext = _extent_mm(cd)
        info["envolvente_mm"] = ext
        tried.append(info)
        return fl, ext

    flange = None
    for bend_pos in (K_BEND_INSIDE_BASE, 75009, 75010, 75012):
        fl, ext = add_flange(bend_pos)
        if fl is None:
            continue
        if matches(ext):
            flange = fl
            break
        fl.Delete()
        doc.Update()
    if flange is None:
        # compensación paramétrica: cara del alma = ancho exterior - 2 * espesor
        fl, ext = add_flange(None)
        if fl is not None:
            excess = (ext[0] - web_mm) / 2
            if abs(excess - t_mm) <= TOL_MM:
                cd.Parameters.Item("Alma").Expression = f"{web_mm} mm - 2 * {cd.Thickness.Name}"
                tried.append({"compensacion": "Alma = ancho - 2*Thickness"})
            else:
                cd.Parameters.Item("Alma").Expression = f"{web_mm - 2 * excess} mm"
                tried.append({"compensacion": f"Alma = {web_mm - 2 * excess} mm"})
            doc.Update()
            ext = _extent_mm(cd)
            tried.append({"envolvente_compensada_mm": ext})
            if matches(ext):
                flange = fl
    if flange is None:
        raise RuntimeError(f"No se logró la envolvente {target}. Intentos: {tried}")
    flange.Name = "Alas"
    try:
        flange.Definition.HeightExtent.Distance.Name = "Ala"
    except (pythoncom.com_error, AttributeError):
        pass
    doc.Update()
    ext = _extent_mm(cd)

    try:
        r_mm = cd.BendRadius.Value * 10
    except (pythoncom.com_error, AttributeError):
        r_mm = bend_radius_mm or t_mm
    if bend_radius_mm:
        r_mm = bend_radius_mm

    # --- desarrollo -----------------------------------------------------------
    if not cd.HasFlatPattern:
        cd.Unfold()
    fp = cd.FlatPattern
    flat_l, flat_w = round(fp.Length * 10, 3), round(fp.Width * 10, 3)
    try:
        fp.ExitEdit()
    except pythoncom.com_error:
        pass
    flat_long = max(flat_l, flat_w)
    straight = (web_mm - 2 * (t_mm + r_mm)) + 2 * (flange_mm - (t_mm + r_mm))
    ba = (flat_long - straight) / 2
    k_eff = (ba / (math.pi / 2) - r_mm) / t_mm
    if flange_mm < 6 * t_mm:
        warnings.append(
            f"Ala de {_fmt(flange_mm)} mm < 6×espesor ({_fmt(6*t_mm)} mm): verificar que la matriz V "
            "de la plegadora permita plegarla.")
    warnings.append("Material no indicado: el plano dice 'A CONFIRMAR'." if not material else "")

    # --- iProperties y material -------------------------------------------------
    descr = f"CHAPA PLEGADA C {_fmt(web_mm)}x{_fmt(flange_mm)} L={_fmt(length_mm)} e={thick_label}"
    _iprop(doc, "Design Tracking Properties", "Part Number", part_number)
    _iprop(doc, "Design Tracking Properties", "Description", descr)
    _iprop(doc, "Inventor Summary Information", "Title", title)
    mat_used = _set_material(app, doc, ["Acero, dulce", "Acero dulce", "Steel, Mild", "Acero"])

    if paths["ipt"].exists():
        paths["ipt"].unlink()
    doc.SaveAs(str(paths["ipt"]), False)

    # --- DXF de corte láser -----------------------------------------------------
    if paths["dxf"].exists():
        paths["dxf"].unlink()
    cd.DataIO.WriteDataToFile(
        "FLAT PATTERN DXF?AcadVersion=2000&OuterProfileLayer=CORTE_EXTERIOR"
        "&InteriorProfilesLayer=CORTE_INTERIOR&MergeProfilesIntoPolyline=True&RebaseGeometry=True"
        f"&InvisibleLayers={DXF_HIDDEN_LAYERS}", str(paths["dxf"]))

    # --- plano ----------------------------------------------------------------
    ddoc = app.Documents.Add(K_DRAWING_DOCUMENT, drawing_template, True)
    sheet = ddoc.ActiveSheet
    try:
        sheet.Size = {"A4": 9997, "A3": 9996}.get(sheet_size.upper(), 9997)
        sheet.Orientation = 10242          # apaisada
    except pythoncom.com_error as exc:
        warnings.append(f"No se pudo cambiar el tamaño de hoja: {exc}")
    W, H = sheet.Width, sheet.Height
    scale = 0.1
    for s_ in (1.0, 0.5, 0.25, 0.2, 0.1):
        if (max(web_mm, length_mm) * s_ <= 0.26 * W * 10 and flat_long * s_ <= 0.33 * W * 10
                and length_mm * s_ <= 0.28 * H * 10):
            scale = s_
            break
    views = sheet.DrawingViews
    P = lambda fx, fy: tg.CreatePoint2d(fx * W, fy * H)  # noqa: E731

    profile_view, orient_used = None, None
    for orient in (K_VIEW_FRONT, K_VIEW_TOP, K_VIEW_RIGHT):
        v = views.AddBaseView(doc, P(0.20, 0.80), scale, orient, K_STYLE_HLR)
        if _view_curves(v)[1]:   # tiene arcos → muestra el perfil en C
            profile_view, orient_used = v, orient
            break
        v.Delete()
    if profile_view is None:
        profile_view = views.AddBaseView(doc, P(0.20, 0.80), scale, K_VIEW_FRONT, K_STYLE_HLR)
        warnings.append("No se identificó la vista del perfil en C; revisar vistas.")
    side_view = views.AddProjectedView(profile_view, P(0.44, 0.80), K_STYLE_FROM_BASE)
    plan_view = views.AddProjectedView(profile_view, P(0.20, 0.47), K_STYLE_FROM_BASE)
    iso_view = views.AddProjectedView(profile_view, P(0.44, 0.47), K_STYLE_FROM_BASE)
    try:
        iso_view.ScaleFromBase = False
        iso_view.Scale = scale / 2
    except pythoncom.com_error:
        pass

    # Vista de desarrollo: sin arcos (el perfil plegado sí los tiene)
    nvm = app.TransientObjects.CreateNameValueMap()
    nvm.Add("SheetMetalFoldedModel", False)
    flat_view = None
    flat_attempts = []
    for mv_name, cam in ((pythoncom.ArgNotFound, pythoncom.ArgNotFound), ("", pythoncom.Empty),
                         ("", pythoncom.ArgNotFound)):
        try:
            v = views.AddBaseView(doc, P(0.76, 0.74), scale, K_VIEW_DEFAULT, K_STYLE_HLR,
                                  mv_name, cam, nvm)
        except pythoncom.com_error as exc:
            flat_attempts.append(str(exc))
            continue
        flat_attempts.append("con arcos" if _view_curves(v)[1] else "plana")
        if not _view_curves(v)[1]:
            flat_view = v
            break
        v.Delete()
    if flat_view is None:
        flat_view = views.AddBaseView(doc, P(0.76, 0.74), scale, K_VIEW_DEFAULT, K_STYLE_HLR,
                                      pythoncom.ArgNotFound, pythoncom.ArgNotFound, nvm)
        warnings.append(f"La vista de desarrollo no parece plana ({flat_attempts}): revisar.")
    for v, label in ((profile_view, "PERFIL"), (side_view, "LATERAL"), (plan_view, "PLANTA"),
                     (iso_view, "ISOMÉTRICA"), (flat_view, "DESARROLLO")):
        try:
            v.Name = label
            v.ShowLabel = True
        except pythoncom.com_error:
            pass

    dims = _Dims(app, sheet)
    _dimension_profile(dims, profile_view, t_mm / 10 * scale)
    _dimension_length(dims, side_view, "largo")
    flat_info = _dimension_flat(dims, sheet, flat_view)

    note_lines = [
        f"MATERIAL: {material or 'A CONFIRMAR'}",
        f"ESPESOR: {thick_label} ({_fmt(t_mm, 3)} mm)",
        f"CANTIDAD: {quantity}",
        "PLEGADO: 2 x 90° MISMO SENTIDO",
        f"RADIO INTERIOR: {_fmt(r_mm)} mm  -  K = {_fmt(k_eff, 2)}",
        f"DESARROLLO: {_fmt(flat_long)} x {_fmt(min(flat_l, flat_w))} mm",
        f"DXF: {paths['dxf'].name}",
        "MEDIDAS EXTERIORES EN mm",
        f"TOLERANCIAS GENERALES: {general_tolerance}",
        "ELIMINAR REBABAS Y ARISTAS VIVAS",
    ]
    try:
        sheet.DrawingNotes.GeneralNotes.AddFitted(P(0.60, 0.50), "<Br/>".join(note_lines))
    except pythoncom.com_error as exc:
        warnings.append(f"No se pudo crear la nota general: {exc}")

    _iprop(ddoc, "Design Tracking Properties", "Part Number", part_number)
    _iprop(ddoc, "Design Tracking Properties", "Description", descr)
    _iprop(ddoc, "Inventor Summary Information", "Title", title)
    if paths["plano"].exists():
        paths["plano"].unlink()
    try:
        ddoc.SaveAs(str(paths["plano"]), False)
    except pythoncom.com_error:
        alt = paths["plano"].with_suffix(".dwg" if paths["plano"].suffix == ".idw" else ".idw")
        warnings.append(f"No se pudo guardar como {paths['plano'].suffix}; se guardó como {alt.suffix}")
        paths["plano"] = alt
        if alt.exists():
            alt.unlink()
        ddoc.SaveAs(str(alt), False)
    if paths["pdf"].exists():
        paths["pdf"].unlink()
    pdf_mode = _export_pdf(app, ddoc, paths["pdf"])

    ok = all(abs(a - b) <= TOL_MM for a, b in zip(sorted(ext), sorted(target)))
    return _result(
        created=True, verified=ok, codigo=part_number, titulo=title,
        files={k: str(p) for k, p in paths.items()},
        files_exist={k: p.exists() for k, p in paths.items()},
        expected_mm={"alma": web_mm, "ala": flange_mm, "largo": length_mm},
        envolvente_mm=ext, espesor_mm=round(t_mm, 4), radio_interior_mm=round(r_mm, 4),
        desarrollo_mm={"largo": flat_long, "ancho": min(flat_l, flat_w)},
        k_efectivo=round(k_eff, 4), material=mat_used,
        plano={"escala": f"1:{int(round(1/scale))}", "orientacion_perfil": orient_used,
               "vista_desarrollo": flat_attempts, "cotas_creadas": dims.ok, "cotas_fallidas": dims.failed, **flat_info,
               "pdf": pdf_mode, "plantilla": str(drawing_template), "hoja_cm": [round(W, 2), round(H, 2)]},
        intentos_alas=tried, warnings=[w for w in warnings if w],
    )


# =============================================================================
# Inspección de ensambles existentes (solo lectura: no modifica ni guarda nada)
# =============================================================================
import re  # noqa: E402

K_ASSEMBLY_DOCUMENT = 12291
K_ISO_TOP_RIGHT = 10759
DEFAULT_PARAM = re.compile(r"^d\d+$")


def _safe(fn, default=None):
    try:
        return fn()
    except (pythoncom.com_error, AttributeError, TypeError, ValueError):
        return default


def _box_mm(box) -> list[float] | None:
    if box is None:
        return None
    return [round((box.MaxPoint.X - box.MinPoint.X) * 10, 2),
            round((box.MaxPoint.Y - box.MinPoint.Y) * 10, 2),
            round((box.MaxPoint.Z - box.MinPoint.Z) * 10, 2)]


def _params(cd) -> dict:
    out = {"usuario": [], "modelo_con_nombre": []}
    params = _safe(lambda: cd.Parameters)
    if params is None:
        return out
    for p in _items(params.UserParameters):
        out["usuario"].append({"nombre": p.Name, "expresion": _safe(lambda: p.Expression),
                               "comentario": _safe(lambda: p.Comment, "")})
    for p in _items(params.ModelParameters):
        if not DEFAULT_PARAM.match(p.Name):
            out["modelo_con_nombre"].append({"nombre": p.Name, "expresion": _safe(lambda: p.Expression)})
    return out


def _doc_info(doc) -> dict:
    cd = doc.ComponentDefinition
    dt = "Design Tracking Properties"
    info = {
        "archivo": doc.FullFileName,
        "tipo": {K_PART_DOCUMENT: "pieza", K_ASSEMBLY_DOCUMENT: "ensamble"}.get(doc.DocumentType, doc.DocumentType),
        "chapa": _safe(lambda: doc.SubType == SHEET_METAL_SUBTYPE, False),
        "codigo": _safe(lambda: doc.PropertySets.Item(dt).Item("Part Number").Value),
        "descripcion": _safe(lambda: doc.PropertySets.Item(dt).Item("Description").Value),
        "proveedor": _safe(lambda: doc.PropertySets.Item(dt).Item("Vendor").Value),
        "stock": _safe(lambda: doc.PropertySets.Item(dt).Item("Stock Number").Value),
        "material": _safe(lambda: doc.ActiveMaterial.DisplayName),
        "masa_kg": _safe(lambda: round(cd.MassProperties.Mass, 4)),
        "envolvente_mm": _safe(lambda: _box_mm(cd.RangeBox)),
        "estructura_bom": _safe(lambda: cd.BOMStructure),
        "centro_de_contenido": _safe(lambda: bool(cd.IsContentMember), False),
        "parametros": _params(cd),
    }
    if info["chapa"]:
        info["espesor_mm"] = _safe(lambda: round(cd.Thickness.Value * 10, 3))
    return info


def _asm_relations(doc) -> dict:
    cd = doc.ComponentDefinition
    cons = []
    for c in _items(cd.Constraints):
        cons.append({"nombre": c.Name, "tipo": _safe(lambda: c.Type),
                     "a": _safe(lambda: c.OccurrenceOne.Name), "b": _safe(lambda: c.OccurrenceTwo.Name),
                     "suprimida": _safe(lambda: c.Suppressed, False)})
    joints = []
    for j in _items(_safe(lambda: cd.Joints) or _EmptyColl()):
        joints.append({"nombre": j.Name, "tipo": _safe(lambda: j.Definition.JointType),
                       "a": _safe(lambda: j.OccurrenceOne.Name), "b": _safe(lambda: j.OccurrenceTwo.Name)})
    reps = cd.RepresentationsManager
    return {
        "restricciones": cons, "uniones": joints,
        "posicionales": [r.Name for r in _items(_safe(lambda: reps.PositionalRepresentations) or _EmptyColl())],
        "vistas_diseno": [r.Name for r in _items(_safe(lambda: reps.DesignViewRepresentations) or _EmptyColl())],
        "estados_modelo": [m.Name for m in _items(_safe(lambda: cd.ModelStates) or _EmptyColl())],
    }


class _EmptyColl:
    Count = 0

    def Item(self, i):  # noqa: N802
        raise IndexError


def _capture(app, doc, folder: Path) -> list[str]:
    """Capturas iso/frente/planta/lateral. Restaura la cámara al terminar."""
    saved = []
    try:
        doc.Activate()
        view = app.ActiveView
        cam = view.Camera
        original = (cam.Eye, cam.Target, cam.UpVector)
    except pythoncom.com_error:
        return saved
    for name, orient in (("iso", K_ISO_TOP_RIGHT), ("frente", K_VIEW_FRONT),
                         ("planta", K_VIEW_TOP), ("lateral", K_VIEW_RIGHT)):
        try:
            cam.ViewOrientationType = orient
            cam.Fit()
            cam.Apply()
            path = folder / f"{name}.png"
            view.SaveAsBitmap(str(path), 1600, 1000)
            saved.append(str(path))
        except pythoncom.com_error:
            pass
    try:
        cam.Eye, cam.Target, cam.UpVector = original
        cam.Apply()
    except pythoncom.com_error:
        pass
    return saved


def inventor_inspect_assembly(path: str, output_dir: str = "", max_depth: int = 6,
                              images: bool = True) -> str:
    """Analiza un ensamble (.iam) SIN modificarlo: árbol de componentes, cantidades, materiales,
    masas, envolventes, parámetros con nombre, restricciones/uniones y capturas.
    Deja estructura.json y resumen.md en output_dir (por defecto Documents/InventorIA/Analisis/<nombre>)."""
    source = Path(path).expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(f"No existe el archivo: {source}")
    app = _inventor()
    doc = None
    for d in _items(app.Documents):
        if _safe(lambda: Path(d.FullFileName).resolve() == source, False):
            doc = d
            break
    opened_here = doc is None
    if doc is None:
        doc = app.Documents.Open(str(source), True)
    out = Path(output_dir).expanduser().resolve() if output_dir else \
        Path.home() / "Documents" / "InventorIA" / "Analisis" / source.stem
    out.mkdir(parents=True, exist_ok=True)

    docs: dict[str, dict] = {}
    counts: dict[str, int] = {}
    assemblies: dict[str, dict] = {}

    def walk(occs, depth):
        nodes = []
        for occ in _items(occs):
            try:
                sub = occ.Definition.Document
                key = sub.FullFileName
            except pythoncom.com_error:
                continue
            suppressed = _safe(lambda: occ.Suppressed, False)
            if not suppressed:
                counts[key] = counts.get(key, 0) + 1
            if key not in docs and not suppressed:
                docs[key] = _doc_info(sub)
                if sub.DocumentType == K_ASSEMBLY_DOCUMENT:
                    assemblies[key] = _asm_relations(sub)
            node = {"nombre": occ.Name, "archivo": Path(key).name, "suprimida": suppressed,
                    "fija": _safe(lambda: occ.Grounded, False),
                    "envolvente_mm": _safe(lambda: _box_mm(occ.RangeBox)),
                    "posicion_mm": _safe(lambda: [round(occ.Transformation.Translation.X * 10, 2),
                                                  round(occ.Transformation.Translation.Y * 10, 2),
                                                  round(occ.Transformation.Translation.Z * 10, 2)])}
            if depth < max_depth and not suppressed and sub.DocumentType == K_ASSEMBLY_DOCUMENT:
                node["hijos"] = walk(occ.SubOccurrences, depth + 1)
            nodes.append(node)
        return nodes

    cd = doc.ComponentDefinition
    tree = walk(cd.Occurrences, 1)
    cog = _safe(lambda: cd.MassProperties.CenterOfMass)
    top = {
        "ensamble": _doc_info(doc),
        "masa_total_kg": _safe(lambda: round(cd.MassProperties.Mass, 3)),
        "centro_de_masa_mm": [round(cog.X * 10, 1), round(cog.Y * 10, 1), round(cog.Z * 10, 1)] if cog else None,
        "relaciones": _asm_relations(doc),
    }
    result = {"origen": str(source), "resumen": top, "arbol": tree,
              "documentos": [{**info, "cantidad": counts.get(k, 0)} for k, info in docs.items()],
              "subensambles": assemblies}
    (out / "estructura.json").write_text(json.dumps(result, ensure_ascii=False, indent=1, default=str),
                                         encoding="utf-8")

    # resumen legible
    lines = [f"# {source.name}", "",
             f"- Masa total: {top['masa_total_kg']} kg — centro de masa (mm): {top['centro_de_masa_mm']}",
             f"- Envolvente (mm): {top['ensamble']['envolvente_mm']}",
             f"- Documentos distintos: {len(docs)} — subensambles: {len(assemblies)}", "",
             "| Cant | Archivo | Código | Descripción | Material | Masa kg | Envolvente mm |",
             "|---|---|---|---|---|---|---|"]
    for k, info in sorted(docs.items(), key=lambda kv: (docs[kv[0]]["tipo"] != "ensamble", Path(kv[0]).name)):
        lines.append(f"| {counts.get(k, 0)} | {Path(k).name} | {info['codigo'] or ''} | "
                     f"{info['descripcion'] or ''} | {info['material'] or ''} | {info['masa_kg']} | "
                     f"{info['envolvente_mm']} |")
    (out / "resumen.md").write_text("\n".join(lines), encoding="utf-8")

    shots = _capture(app, doc, out) if images else []
    return _result(analizado=True, origen=str(source), carpeta=str(out), abierto_por_script=opened_here,
                   documentos=len(docs), subensambles=len(assemblies),
                   masa_total_kg=top["masa_total_kg"], capturas=shots)


# =============================================================================
# Paquete de fabricación de un ensamble: plano + PDF + DXF por pieza de chapa,
# y plano de conjunto con lista de materiales.
# =============================================================================
STD_SCALES = (2.0, 1.0, 0.5, 0.2, 0.1, 0.05, 0.02)   # 2:1 para piezas chicas
SHEETS = (("A4", 9997), ("A3", 9996), ("A2", 9995))


def _scale_label(s: float) -> str:
    if s > 1:
        return f"{s:g}:1"
    return "1:1" if s == 1 else f"1:{round(1 / s):g}"


def _leaf_counts(asm_doc) -> dict[str, int]:
    """Cantidad de cada archivo en el ensamble (incluye subensambles, excluye suprimidos)."""
    counts: dict[str, int] = {}

    def walk(occs):
        for occ in _items(occs):
            if _safe(lambda: occ.Suppressed, False):
                continue
            try:
                d = occ.Definition.Document
            except pythoncom.com_error:
                continue
            counts[d.FullFileName] = counts.get(d.FullFileName, 0) + 1
            if d.DocumentType == K_ASSEMBLY_DOCUMENT:
                walk(occ.SubOccurrences)
    walk(asm_doc.ComponentDefinition.Occurrences)
    return counts


def _title_block_top(sheet, default: float = 5.0) -> float:
    try:
        return sheet.TitleBlock.RangeBox.MaxPoint.Y
    except (pythoncom.com_error, AttributeError):
        return default


def _dimension_overall(dims: _Dims, view, label: str) -> None:
    """Cotas totales (ancho abajo, alto a la izquierda) usando las líneas extremas de la vista."""
    lines, _ = _view_curves(view)
    left, right, bottom, top = _view_box(view)
    v = sorted([l for l in lines if l["vert"]], key=lambda l: l["x"])
    h = sorted([l for l in lines if l["horiz"]], key=lambda l: l["y"])
    if len(v) >= 2 and v[-1]["x"] - v[0]["x"] > 0.05:
        dims.linear(f"{label} ancho", (left + right) / 2, bottom - 0.9, v[0]["c"], v[-1]["c"])
    if len(h) >= 2 and h[-1]["y"] - h[0]["y"] > 0.05:
        dims.linear(f"{label} alto", left - 0.9, (bottom + top) / 2, h[0]["c"], h[-1]["c"])


SHEET_TABLE = (("A4", 9997, (29.7, 21.0), 0.2), ("A3", 9996, (42.0, 29.7), 0.1),
               ("A2", 9995, (59.4, 42.0), 0.0))
DRAWING_SHEET = "A4"      # estándar de la empresa: todas las hojas en A4 (None = elegir A4/A3/A2)


def _choose_layout(unit: dict, n_notes: int, n_bends: int, only_sheet: str | None = DRAWING_SHEET):
    """Hoja y escala normalizadas más legibles para la pieza: A4 si entra a 1:5 o mayor,
    si no A3 hasta 1:10, si no A2. Devuelve (hoja, código, escala, W, H, disposición)."""
    for sname, scode, (W, H), smin in SHEET_TABLE:
        if only_sheet and sname != only_sheet:
            continue
        for sc in STD_SCALES:
            if sc < smin and not only_sheet:
                break
            # prioridad: escala grande; si hace falta se omite PLANTA y luego ISOMÉTRICA
            iso_fs = [x / sc for x in STD_SCALES if x <= sc * 0.5 + 1e-9][:4]   # isométrica a escala normalizada
            for drop in ((), ("p",), ("p", "i")):
                for iso_f in iso_fs:
                    lay = _plan_layout(unit, sc, W, H, n_notes, n_bends, iso_f, drop)
                    if lay:
                        return sname, scode, sc, W, H, lay
    return None


def _estimated_units(ext_mm, flat_l, flat_w) -> dict:
    """Tamaño aproximado de cada vista a escala 1 (cm) a partir de la envolvente de la pieza."""
    X, Y, Z = (v / 10 for v in ext_mm)
    unit = {"b": (X, Y), "s": (Z, Y), "p": (X, Z),
            "i": (0.87 * (X + Z), Y + 0.5 * (X + Z))}
    if flat_l:
        unit["f"] = (max(flat_l, flat_w) / 10, min(flat_l, flat_w) / 10)
    return unit


def _new_sheet(ddoc, first_sheet, scode):
    """Hoja nueva con el mismo borde y cajetín que la primera hoja de la plantilla."""
    sheet = ddoc.Sheets.Add(scode, 10242)
    border = _safe(lambda: first_sheet.Border.Definition)
    if border is None or _safe(lambda: sheet.AddBorder(border)) is None:
        _safe(lambda: sheet.AddDefaultBorder())
    tb = _safe(lambda: first_sheet.TitleBlock.Definition)
    if tb is not None:
        _safe(lambda: sheet.AddTitleBlock(tb))
    return sheet


def _part_sheet(app, ddoc, sheet, doc, qty: int, out: dict, warnings: list) -> dict:
    """Una hoja del plano con la pieza de chapa (vistas, desarrollo, cotas, notas) + su DXF."""
    tg = app.TransientGeometry
    P = tg.CreatePoint2d
    cd = doc.ComponentDefinition
    stem = Path(doc.FullFileName).stem
    info = {"pieza": stem, "cantidad": qty}
    t_mm = _safe(lambda: cd.Thickness.Value * 10)
    if not cd.HasFlatPattern:
        cd.Unfold()
    fp = cd.FlatPattern
    flat_l, flat_w = _safe(lambda: fp.Length * 10, 0), _safe(lambda: fp.Width * 10, 0)
    _safe(lambda: fp.ExitEdit())
    ext = _extent_mm(cd)
    _safe(lambda: doc.Save())

    dxf = out["dxf"] / f"{stem}.dxf"
    if dxf.exists():
        dxf.unlink()
    cd.DataIO.WriteDataToFile(
        "FLAT PATTERN DXF?AcadVersion=2000&OuterProfileLayer=CORTE_EXTERIOR"
        "&InteriorProfilesLayer=CORTE_INTERIOR&MergeProfilesIntoPolyline=True&RebaseGeometry=True"
        f"&InvisibleLayers={DXF_HIDDEN_LAYERS}", str(dxf))

    material = _safe(lambda: doc.ActiveMaterial.DisplayName, "")
    if not material or material.lower().startswith(("genérico", "generico", "generic")):
        material = "A CONFIRMAR"
    real_bends = _safe(lambda: cd.Bends.Count, None)
    n_bends = max(1, real_bends if real_bends is not None else 2)
    # control: en una placa sin plegados, el desarrollo tiene que ser la cara grande y el espesor el canto
    if real_bends == 0 and ext and flat_l:
        e = sorted(ext)
        f = sorted([flat_l, flat_w])
        if abs(f[0] - e[1]) > 1.0 or abs(f[1] - e[2]) > 1.0 or (t_mm and abs(t_mm - e[0]) > 0.1):
            warnings.append(
                f"{stem}: CONVERSIÓN A CHAPA INCORRECTA. Desarrollo {f[1]:.1f} x {f[0]:.1f} y espesor "
                f"{t_mm:.2f} mm, pero la pieza mide {e[2]:.1f} x {e[1]:.1f} x {e[0]:.2f} mm. "
                "Reconvertir eligiendo la cara grande como base y el espesor real. DXF NO VÁLIDO.")
            info["conversion_incorrecta"] = True
    n_notes = 6

    # 1) hoja y escala a partir de las medidas de la pieza (las vistas nacen ya a escala)
    est = _estimated_units(ext, flat_l, flat_w)
    chosen = _choose_layout(est, n_notes, n_bends) or ("A2", 9995, 0.02, 59.4, 42.0, None)
    sname, scode, scale, W, H, lay = chosen
    _safe(lambda: setattr(sheet, "Size", scode))
    _safe(lambda: setattr(sheet, "Orientation", 10242))
    iso_f = lay["iso_f"] if lay else 0.5
    views = sheet.DrawingViews
    base = views.AddBaseView(doc, P(W * 0.2, H * 0.7), scale, K_VIEW_FRONT, K_STYLE_HLR)
    side = views.AddProjectedView(base, P(W * 0.4, H * 0.7), K_STYLE_FROM_BASE)
    plan = views.AddProjectedView(base, P(W * 0.2, H * 0.35), K_STYLE_FROM_BASE)
    iso = views.AddProjectedView(base, P(W * 0.4, H * 0.35), K_STYLE_FROM_BASE)
    _safe(lambda: setattr(iso, "ScaleFromBase", False))
    _safe(lambda: setattr(iso, "Scale", scale * iso_f))
    nvm = app.TransientObjects.CreateNameValueMap()
    nvm.Add("SheetMetalFoldedModel", False)
    flat = _safe(lambda: views.AddBaseView(doc, P(W * 0.75, H * 0.7), scale, K_VIEW_DEFAULT, K_STYLE_HLR,
                                           pythoncom.ArgNotFound, pythoncom.ArgNotFound, nvm))
    if flat is not None and _view_curves(flat)[1] and not flat_l:
        flat = None

    # 2) con los tamaños reales, confirmar (o bajar) la escala dentro de la misma hoja
    def real_units(sc, isf):
        u = {"b": (base.Width / sc, base.Height / sc), "s": (side.Width / sc, side.Height / sc),
             "p": (plan.Width / sc, plan.Height / sc), "i": (iso.Width / (sc * isf), iso.Height / (sc * isf))}
        if flat is not None:
            u["f"] = (flat.Width / sc, flat.Height / sc)
        return u
    unit = real_units(scale, iso_f)
    again = _choose_layout(unit, n_notes, n_bends)
    if again:                                          # decisión final con tamaños reales
        sname, scode, scale, W, H, lay = again
        _safe(lambda: setattr(sheet, "Size", scode))
        _safe(lambda: setattr(sheet, "Orientation", 10242))
    if lay is None:
        warnings.append(f"{stem}: no se encontró una disposición limpia; revisar la hoja.")
    iso_f = lay["iso_f"] if lay else iso_f
    for v, sc in ((base, scale), (flat, scale), (iso, scale * iso_f)):
        if v is not None and not (lay and "i" in lay.get("drop", ()) and v is iso):
            _safe(lambda: setattr(v, "Scale", sc))
    if lay:
        for key in lay.get("drop", ()):
            v = {"p": plan, "i": iso}[key]
            _safe(lambda: v.Delete())
        plan = None if "p" in lay.get("drop", ()) else plan
        iso = None if "i" in lay.get("drop", ()) else iso
        for key, v in (("b", base), ("s", side), ("p", plan), ("i", iso), ("f", flat)):
            if v is not None and key in lay:
                _safe(lambda: setattr(v, "Position", P(*lay[key])))
    for v, label in ((base, "FRENTE"), (side, "LATERAL"), (plan, "PLANTA"), (iso, "ISOMÉTRICA"),
                     (flat, "DESARROLLO")):
        if v is not None:
            _safe(lambda: setattr(v, "ShowLabel", True))
            _safe(lambda: setattr(v.Label, "FormattedText", label))

    dims = _Dims(app, sheet)
    _dimension_overall(dims, base, "frente")
    _dimension_overall(dims, side, "lateral")
    flat_info = {"lineas_de_plegado": 0}
    if flat is not None:
        flat_info = _dimension_flat(dims, sheet, flat)

    moved = flat_info.get("notas_plegado_movidas", [])
    notes = [
        f"PIEZA: {stem[:26]}  (x{qty})",
        f"MATERIAL: {material[:14]}  -  ESP. {_fmt(t_mm, 2) if t_mm else '-'} mm",
        f"DESARROLLO: {_fmt(max(flat_l, flat_w), 1)} x {_fmt(min(flat_l, flat_w), 1)} mm",
        f"PLEGADOS: {flat_info.get('lineas_de_plegado', 0)}  -  ESCALA {_scale_label(scale)}"
        + (f" (ISO {_scale_label(scale * iso_f)})" if iso is not None else ""),
        *[f"PLEGADO: {t} (x{moved.count(t)})" for t in sorted(set(moved)) if t],
        "CORTE DXF 1:1 - ISO 2768-m - SIN REBABAS",
    ]
    nx, ny = (lay["n"] if lay else (1.5, 1.2 + 0.6 * len(notes)))
    _safe(lambda: sheet.DrawingNotes.GeneralNotes.AddFitted(P(nx, ny), "<Br/>".join(notes)))
    _safe(lambda: setattr(sheet, "Name", stem[:30]))
    info.update({"hoja": sname, "escala": _scale_label(scale), "iso": _scale_label(scale * iso_f) if iso is not None else None,
                 "vistas_omitidas": list((lay or {}).get("drop", ())),
                 "diag_vistas_cm_a_escala_1": {k: [round(a, 1), round(b, 1)] for k, (a, b) in unit.items()},
                 "diag_layout": (lay or {}).get("motivo", "ok" if lay else "sin disposición"),
                 "espesor_mm": t_mm, "desarrollo_mm": [round(flat_l, 1), round(flat_w, 1)],
                 "cotas": dims.ok, "cotas_fallidas": len(dims.failed),
                 "plegados": flat_info.get("lineas_de_plegado"), "vista_desarrollo": flat is not None,
                 "dxf": str(dxf)})
    return info


def _plan_layout(unit: dict, sc: float, W: float, H: float, n_notes: int, n_bends: int,
                 iso_f: float = 0.5, drop: tuple = ()):
    """Acomoda las vistas en la hoja (cm) sin superposiciones.
    FRENTE arriba a la izquierda, LATERAL a su derecha y PLANTA debajo (alineadas por proyección).
    DESARROLLO, ISOMÉTRICA y notas van al primer hueco libre donde entren (cajetín incluido como zona ocupada).
    Cada vista reserva espacio para su rótulo y sus cotas. Devuelve {vista: (x, y)} o None."""
    TB_W, TB_H = 17.8, 4.4
    X0, X1, Y0, Y1 = 1.2, W - 1.0, 1.0, H - 1.0         # interior del borde
    LAB = 1.8                                             # rótulo sobre cada vista (sin tocar el borde)
    DIM = 1.5                                             # cota abajo / a la izquierda
    sz = {"b": unit["b"], "s": unit["s"], "p": unit["p"]}
    w = {k: (v[0] * sc, v[1] * sc) for k, v in sz.items()}
    w["i"] = (unit["i"][0] * sc * iso_f, unit["i"][1] * sc * iso_f)
    if "f" in unit:
        w["f"] = (unit["f"][0] * sc, unit["f"][1] * sc)
    # márgenes (izq, der, abajo, arriba) que ocupa cada vista con cotas y rótulo
    marg = {"b": (DIM, 0.4, DIM, LAB), "s": (DIM, 0.4, DIM, LAB), "p": (0.4, 0.4, 0.4, LAB),
            "i": (0.3, 0.3, 0.1, 1.2), "f": (0.2, 1.3, 0.8 + 0.55 * (n_bends + 1), LAB)}
    notes_wh = (0.26 * 38, 0.58 * n_notes + 0.2)
    # el rótulo puede ser más ancho que la vista: reservar su ancho también
    labels = {"b": "FRENTE", "s": "LATERAL", "p": "PLANTA", "i": "ISOMÉTRICA", "f": "DESARROLLO"}
    for k in list(marg):
        if k in w:
            extra = max(0.0, (0.4 * len(labels[k]) + 0.4 - w[k][0]) / 2)
            ml, mr, mb, mt = marg[k]
            marg[k] = (max(ml, extra), max(mr, extra), mb, mt)

    occupied = [(W - TB_W, 0.0, W, TB_H + 0.1)]         # cajetín

    def box(k, cx, cy):
        (vw, vh), (ml, mr, mb, mt) = w[k], marg[k]
        return (cx - vw / 2 - ml, cy - vh / 2 - mb, cx + vw / 2 + mr, cy + vh / 2 + mt)

    def free(r):
        if r[0] < X0 - 1e-6 or r[2] > X1 + 1e-6 or r[1] < Y0 - 1e-6 or r[3] > Y1 + 1e-6:
            return False
        e = 1e-6
        return all(r[2] <= o[0] + e or r[0] >= o[2] - e or r[3] <= o[1] + e or r[1] >= o[3] - e
                   for o in occupied)

    out = {"iso_f": iso_f, "drop": drop}
    # vistas fijas por proyección
    (bw, bh), (ml, mr, mb, mt) = w["b"], marg["b"]
    bx, by = X0 + ml + bw / 2, Y1 - mt - bh / 2
    rb = box("b", bx, by)
    if not free(rb):
        return None
    occupied.append(rb)
    out["b"] = (bx, by)
    sx = rb[2] + marg["s"][0] + w["s"][0] / 2
    rs = box("s", sx, by)
    if not free(rs):
        return None
    occupied.append(rs)
    out["s"] = (sx, by)
    py = rb[1] - marg["p"][3] - w["p"][1] / 2
    if "p" not in drop:
        rp = box("p", bx, py)
        if not free(rp):
            return None
        occupied.append(rp)
        out["p"] = (bx, py)

    def place(k, size, margins, prefer):
        """Busca el primer hueco libre para un rectángulo; prefer ordena los candidatos."""
        vw, vh = size
        ml, mr, mb, mt = margins
        xs = {X0 + ml + vw / 2, X1 - mr - vw / 2} | {o[2] + ml + vw / 2 for o in occupied} \
            | {o[0] - mr - vw / 2 for o in occupied}
        ys = {Y1 - mt - vh / 2, Y0 + mb + vh / 2} | {o[1] - mt - vh / 2 for o in occupied} \
            | {o[3] + mb + vh / 2 for o in occupied}
        cands = sorted(((x, y) for x in xs for y in ys), key=prefer)
        for x, y in cands:
            r = (x - vw / 2 - ml, y - vh / 2 - mb, x + vw / 2 + mr, y + vh / 2 + mt)
            if free(r):
                occupied.append(r)
                return (x, y)
        return None

    if "f" in w:                                # desarrollo: arriba y a la derecha
        pos = place("f", w["f"], marg["f"], lambda c: (-c[1] + 0.001 * -c[0]))
        if pos is None:
            return None
        out["f"] = pos
    nw, nh = notes_wh                           # notas: sobre el cajetín o donde entren
    pos = place("n", (nw, nh), (0.2, 0.2, 0.2, 0.2),
                lambda c: (abs(c[0] - (W - TB_W + nw / 2)) + abs(c[1] - (TB_H + 0.6 + nh / 2))))
    if pos is None:
        return None
    out["n"] = (pos[0] - nw / 2, pos[1] + nh / 2)   # esquina superior izquierda del texto
    if "i" not in drop:                         # la isométrica ocupa el mejor hueco que queda
        pos = place("i", w["i"], marg["i"], lambda c: (abs(c[1] - py) + 0.3 * abs(c[0] - bx)))
        if pos is None:
            return None
        out["i"] = pos
    return out


def _assembly_drawing(app, asm, out: dict, drawing_template, warnings: list) -> dict:
    tg = app.TransientGeometry
    cd = asm.ComponentDefinition
    ext = _extent_mm(cd) if _safe(lambda: cd.SurfaceBodies.Count, 0) else _box_mm(cd.RangeBox)
    ddoc = app.Documents.Add(K_DRAWING_DOCUMENT, drawing_template, True)
    try:
        sheet = ddoc.ActiveSheet
        _safe(lambda: setattr(sheet, "Size", 9996))      # A3
        _safe(lambda: setattr(sheet, "Orientation", 10242))
        W, H = sheet.Width, sheet.Height
        need = max(ext[0] + ext[2], ext[1] + ext[2])
        scale = next((s for s in STD_SCALES if need * s <= 0.45 * W * 10), 0.02)
        views = sheet.DrawingViews
        P = tg.CreatePoint2d
        base = views.AddBaseView(asm, P(W * 0.22, H * 0.70), scale, K_VIEW_FRONT, K_STYLE_HLR)
        plan = views.AddProjectedView(base, P(W * 0.22, H * 0.30), K_STYLE_FROM_BASE)
        iso = views.AddProjectedView(base, P(W * 0.50, H * 0.30), K_STYLE_FROM_BASE)
        pl = _safe(lambda: sheet.PartsLists.Add(base, P(W - 1.0, H - 1.0)))
        if pl is None:
            warnings.append("No se pudo crear la lista de materiales en el plano de conjunto.")
        _iprop(ddoc, "Inventor Summary Information", "Title", Path(asm.FullFileName).stem[:MAX_TITLE].upper())
        ext_dwg = ".dwg" if str(drawing_template).lower().endswith(".dwg") else ".idw"
        stem = Path(asm.FullFileName).stem
        dwg, pdf = out["planos"] / f"{stem}_CONJUNTO{ext_dwg}", out["pdf"] / f"{stem}_CONJUNTO.pdf"
        for f in (dwg, pdf):
            if f.exists():
                f.unlink()
        ddoc.SaveAs(str(dwg), False)
        _export_pdf(app, ddoc, pdf)
        return {"plano": str(dwg), "pdf": str(pdf), "escala": _scale_label(scale),
                "lista_materiales": pl is not None}
    finally:
        _safe(lambda: ddoc.Close(True))


def inventor_fabrication_package(assembly_path: str = "", output_dir: str = "",
                                 only: str = "", include_assembly: bool = True) -> str:
    """Genera el paquete de fabricación del ensamble (activo si no se indica ruta):
    por cada pieza de CHAPA propia (no Centro de Contenido): plano + PDF + DXF de corte, con cantidad
    por gripper; y un plano de conjunto con lista de materiales.
    only: filtra piezas cuyo nombre contenga este texto (para probar con una sola).
    Salida: <carpeta del ensamble>/Fabricacion/{Planos, Planos/PDF, Corte_laser}."""
    app = _inventor()
    if assembly_path:
        asm = None
        for d in _items(app.Documents):
            if _safe(lambda: Path(d.FullFileName).resolve() == Path(assembly_path).resolve(), False):
                asm = d
        if asm is None:
            app.SilentOperation = True
            try:
                asm = app.Documents.Open(str(Path(assembly_path).resolve()), True)
            finally:
                app.SilentOperation = False
    else:
        asm = app.ActiveDocument
    if asm.DocumentType != K_ASSEMBLY_DOCUMENT:
        raise ValueError("El documento no es un ensamble")
    base = Path(output_dir) if output_dir else Path(asm.FullFileName).parent / "Fabricacion"
    out = {"planos": base / "Planos", "pdf": base / "Planos" / "PDF", "dxf": base / "Corte_laser"}
    for p in out.values():
        p.mkdir(parents=True, exist_ok=True)
    drawing_template = app.FileManager.GetTemplateFile(K_DRAWING_DOCUMENT)
    counts = _leaf_counts(asm)
    warnings: list[str] = []
    done, skipped, errors = [], [], []
    parts = []
    for d in _items(asm.AllReferencedDocuments):
        name = Path(d.FullFileName).name
        if d.DocumentType != K_PART_DOCUMENT:
            continue
        if "content center files" in d.FullFileName.lower() or _safe(lambda: d.ComponentDefinition.IsContentMember, False):
            skipped.append({"pieza": name, "motivo": "Centro de Contenido"})
            continue
        if d.SubType != SHEET_METAL_SUBTYPE and Path(d.FullFileName).parent.name.lower() == "estructura":
            if only and only.lower() not in name.lower():
                continue
            qty = counts.get(d.FullFileName, 0)
            if qty:
                parts.append((name, d, qty))
            continue
        if d.SubType != SHEET_METAL_SUBTYPE:
            e = sorted(_safe(lambda: _extent_mm(d.ComponentDefinition), [0, 0, 0]) or [0, 0, 0])
            mat = (_safe(lambda: d.ActiveMaterial.DisplayName, "") or "").lower()
            if 0 < e[0] <= 12.7 and e[1] >= 5 * e[0] and "plást" not in mat and "plast" not in mat:
                motivo = f"placa plana modelada como pieza normal (e={e[0]} mm): no es chapa en Inventor"
            else:
                motivo = "no es chapa (comercial u otra)"
            skipped.append({"pieza": name, "motivo": motivo})
            continue
        if only and only.lower() not in name.lower():
            continue
        qty = counts.get(d.FullFileName, 0)
        if qty == 0:
            skipped.append({"pieza": name, "motivo": "suprimida o sin uso"})
            continue
        parts.append((name, d, qty))
    parts.sort(key=lambda t: t[0].lower())

    # un solo plano con una hoja por pieza
    stem_asm = Path(asm.FullFileName).stem
    ddoc = app.Documents.Add(K_DRAWING_DOCUMENT, drawing_template, True)
    first = ddoc.Sheets.Item(1)
    drawing_path = pdf_path = None
    try:
        for i, (name, d, qty) in enumerate(parts):
            try:
                sheet = first if i == 0 else _new_sheet(ddoc, first, 9997)
                if d.SubType != SHEET_METAL_SUBTYPE:
                    done.append(_solid_sheet(app, ddoc, sheet, d, qty, warnings))
                else:
                    done.append(_part_sheet(app, ddoc, sheet, d, qty, out, warnings))
            except Exception as exc:  # noqa: BLE001
                errors.append({"pieza": name, "error": str(exc)})
        _iprop(ddoc, "Design Tracking Properties", "Part Number", stem_asm[:MAX_PART_NUMBER])
        _iprop(ddoc, "Inventor Summary Information", "Title", f"{stem_asm} - CHAPAS"[:MAX_TITLE].upper())
        ext_dwg = ".dwg" if str(drawing_template).lower().endswith(".dwg") else ".idw"
        suffix = f"_{only}" if only else ""
        drawing_path = out["planos"] / f"{stem_asm}_CHAPAS{suffix}{ext_dwg}"
        pdf_path = out["pdf"] / f"{stem_asm}_CHAPAS{suffix}.pdf"
        def _free_path(f: Path) -> Path:
            """Si el archivo está abierto (bloqueado) en otro programa, usar un nombre nuevo."""
            if f.exists():
                try:
                    f.unlink()
                except PermissionError:
                    f = f.with_name(f"{f.stem}_{time.strftime('%H%M%S')}{f.suffix}")
                    warnings.append(f"Archivo abierto en otro programa; se guardó como {f.name}")
            return f
        for od in _items(app.Documents):     # si el plano anterior está abierto en Inventor, cerrarlo
            if _safe(lambda: Path(od.FullFileName).resolve() == drawing_path.resolve(), False):
                _safe(lambda: od.Close(True))
        drawing_path, pdf_path = _free_path(drawing_path), _free_path(pdf_path)
        if done:
            _safe(lambda: ddoc.Sheets.Item(1).Activate())
            ddoc.SaveAs(str(drawing_path), False)
            _export_pdf(app, ddoc, pdf_path)
    finally:
        _safe(lambda: ddoc.Close(True))
    asm_info = None
    if include_assembly and not only:
        try:
            asm_info = _assembly_drawing(app, asm, out, drawing_template, warnings)
        except Exception as exc:  # noqa: BLE001
            errors.append({"pieza": "CONJUNTO", "error": str(exc)})
    # índice
    idx = ["# Paquete de fabricación — " + Path(asm.FullFileName).stem, "",
           "| Pieza | Cant. | Espesor mm | Desarrollo mm | Plegados | Hoja | Escala |", "|---|---|---|---|---|---|---|"]
    for i in done:
        if i.get("tipo") == "estructura":
            idx.append(f"| {i['pieza']} | {i['cantidad']} | caño | — | — | {i['hoja']} | {i['escala']} |")
            continue
        idx.append(f"| {i['pieza']} | {i['cantidad']} | {i['espesor_mm'] and round(i['espesor_mm'], 2)} | "
                   f"{i['desarrollo_mm'][0]} x {i['desarrollo_mm'][1]} | {i['plegados']} | {i['hoja']} | {i['escala']} |")
    if errors:
        idx += ["", "## Errores", *[f"- {e['pieza']}: {e['error']}" for e in errors]]
    (base / "indice.md").write_text("\n".join(idx), encoding="utf-8")
    return _result(carpeta=str(base), plano=str(drawing_path), pdf=str(pdf_path), hojas=len(done),
                   piezas=done, conjunto=asm_info, omitidas=skipped,
                   errores=errors, avisos=warnings)


# =============================================================================
# Constructor de chapas desde su DESARROLLO (gripper_design.FlatPart): cara + pliegues
# =============================================================================
K_CENTERLINE_OF_BEND = 75777       # BendLocationEnum.kCenterlineOfBend
HEX_FLATS_MM = 10.0                # hexágono: medida entre caras


def _bulge_center(p1, p2, bulge):
    """Centro del arco DXF entre p1 y p2 con bulge (mm)."""
    (x1, y1), (x2, y2) = p1, p2
    theta = 4 * math.atan(bulge)
    c = math.hypot(x2 - x1, y2 - y1)
    r = c / (2 * math.sin(abs(theta) / 2))
    mx, my = (x1 + x2) / 2, (y1 + y2) / 2
    d = math.sqrt(max(r * r - (c / 2) ** 2, 0.0))
    ux, uy = (x2 - x1) / c, (y2 - y1) / c
    nx, ny = -uy, ux                 # normal a la izquierda de la cuerda
    sgn = 1 if (bulge > 0) == (abs(theta) < math.pi) else -1
    return (mx + sgn * nx * d, my + sgn * ny * d)


def _draw_loop(sketch, tg, loop):
    """Dibuja un contorno cerrado [(x, y, bulge)] en mm, con tramos rectos y arcos conectados."""
    pts = [sketch.SketchPoints.Add(tg.CreatePoint2d(x / 10, y / 10)) for x, y, _ in loop]
    n = len(loop)
    for i in range(n):
        b = loop[i][2]
        a, c = pts[i], pts[(i + 1) % n]
        if abs(b) < 1e-9:
            sketch.SketchLines.AddByTwoPoints(a, c)
        else:
            cx, cy = _bulge_center(loop[i][:2], loop[(i + 1) % n][:2], b)
            sketch.SketchArcs.AddByCenterStartEndPoint(tg.CreatePoint2d(cx / 10, cy / 10), a, c, b > 0)


def _new_sheet_metal_doc(app, thickness_mm: float):
    try:
        template = app.FileManager.GetTemplateFile(K_PART_DOCUMENT, pythoncom.Missing,
                                                   pythoncom.Missing, SHEET_METAL_SUBTYPE)
    except pythoncom.com_error:
        template = app.FileManager.GetTemplateFile(K_PART_DOCUMENT)
    doc = app.Documents.Add(K_PART_DOCUMENT, template, True)
    if doc.SubType != SHEET_METAL_SUBTYPE:
        doc.SubType = SHEET_METAL_SUBTYPE
    cd = doc.ComponentDefinition
    _safe(lambda: setattr(cd, "UseSheetMetalStyleThickness", False))
    cd.Thickness.Expression = f"{thickness_mm} mm"
    doc.Update()
    return doc


def _cut_text(app, cd, tx: dict, idx: int) -> dict:
    """Texto calado pasante sobre el desarrollo (plano XY), centrado en (x, y) mm y girado rot_deg."""
    tg = app.TransientGeometry
    try:
        ft = (f"<StyleOverride Font='{tx.get('fuente', 'Arial')}' FontSize='{tx['alto'] / 10:.3f}'>"
              f"{tx['texto']}</StyleOverride>")

        def crear(x_mm, y_mm):
            sk = cd.Sketches.Add(cd.WorkPlanes.Item(3))
            _safe(lambda: setattr(sk, "Name", f"Logo {idx}"))
            tb = sk.TextBoxes.AddFitted(tg.CreatePoint2d(x_mm / 10, y_mm / 10), ft)
            _safe(lambda: setattr(tb, "Rotation", math.radians(tx.get("rot_deg", 0))))
            col = app.TransientObjects.CreateObjectCollection()
            col.Add(tb)
            return sk, tb, sk.Profiles.AddForSolid(False, col)

        sk, tb, prof = crear(tx["x"], tx["y"])
        c = _safe(lambda: prof.RegionProperties.Centroid)
        moved = None
        if c is not None:                                     # centrar el texto en (x, y)
            dx, dy = tx["x"] - c.X * 10, tx["y"] - c.Y * 10
            if abs(dx) > 0.5 or abs(dy) > 0.5:
                sk.Delete()
                sk, tb, prof = crear(tx["x"] + dx, tx["y"] + dy)
                moved = [round(dx, 1), round(dy, 1)]
        cut = cd.Features.ExtrudeFeatures.AddByThroughAllExtent(prof, 20995, 20482)   # simétrico, corte
        _safe(lambda: setattr(cut, "Name", f"Logo calado {idx}"))
        fuente = _safe(lambda: tb.Style.Font)
        return {"texto": tx["texto"], "ok": True, "corregido_mm": moved, "fuente_estilo": fuente,
                "area_mm2": _safe(lambda: round(prof.RegionProperties.Area * 100, 1))}
    except Exception as exc:  # noqa: BLE001
        return {"texto": tx.get("texto"), "ok": False, "error": repr(exc)[:300]}


def build_flat_part(app, spec: dict, out_ipt: Path, out_dxf: Path | None = None) -> dict:
    """Crea una pieza de chapa a partir de su desarrollo: cara con todos los cortes y pliegues sobre
    las líneas de plegado. Verifica la envolvente plegada y exporta el DXF del desarrollo."""
    tg = app.TransientGeometry
    doc = _new_sheet_metal_doc(app, spec["espesor"])
    cd = doc.ComponentDefinition
    t0 = time.time()
    sk = cd.Sketches.Add(cd.WorkPlanes.Item(3))
    sk.Name = "Desarrollo"
    _safe(lambda: setattr(sk, "DeferUpdates", True))
    _draw_loop(sk, tg, spec["contorno"])
    for loop in spec.get("contornos_interiores", []):
        _draw_loop(sk, tg, loop)
    for x, y, d in spec.get("circulos", []):
        sk.SketchCircles.AddByCenterRadius(tg.CreatePoint2d(x / 10, y / 10), d / 20)
    rad = (spec.get("hex_flats") or HEX_FLATS_MM) / math.sqrt(3)
    for x, y in spec.get("hexagonos", []):
        sk.SketchLines.AddAsPolygon(6, tg.CreatePoint2d(x / 10, y / 10),
                                    tg.CreatePoint2d(x / 10, (y + rad) / 10), True)
    _safe(lambda: setattr(sk, "DeferUpdates", False))
    face = cd.Features.FaceFeatures.Add(
        cd.Features.FaceFeatures.CreateFaceFeatureDefinition(sk.Profiles.AddForSolid()))
    _safe(lambda: setattr(face, "Name", "Cara desarrollo"))
    t_sketch = round(time.time() - t0, 1)
    textos_res = [_cut_text(app, cd, tx, i) for i, tx in enumerate(spec.get("textos", []), 1)]

    # pliegues: línea sobre la cara del plano del boceto (z = 0), de borde a borde
    xs = [p[0] for p in spec["contorno"]]
    ys = [p[1] for p in spec["contorno"]]
    folds, tried = [], []
    expected = sorted(spec.get("envolvente_plegada") or [])

    def base_face():
        for f in _items(cd.SurfaceBodies.Item(1).Faces):
            zs = [v.Point.Z for v in _items(f.Vertices)]
            if len(zs) >= 3 and max(zs) - min(zs) < 1e-6 and abs(zs[0]) < 1e-6:
                return f
        raise RuntimeError("No se encontró la cara del desarrollo")

    # 1) todas las líneas de plegado sobre la cara del desarrollo, ANTES de plegar
    bends = spec.get("pliegues", [])
    lines = []
    bf = base_face()
    for i, b in enumerate(bends):
        fsk = cd.Sketches.Add(bf)
        _safe(lambda: setattr(fsk, "Name", f"Linea pliegue {i + 1}"))
        if b["eje"] == "x":
            p1, p2 = (b["pos"], min(ys)), (b["pos"], max(ys))
        else:
            p1, p2 = (min(xs), b["pos"]), (max(xs), b["pos"])
        q1 = fsk.ModelToSketchSpace(tg.CreatePoint(p1[0] / 10, p1[1] / 10, 0))
        q2 = fsk.ModelToSketchSpace(tg.CreatePoint(p2[0] / 10, p2[1] / 10, 0))
        lines.append(fsk.SketchLines.AddByTwoPoints(q1, q2))

    def stationary_holds(pending) -> bool:
        """¿Las líneas de plegado pendientes siguen sobre una cara plana en z = 0?"""
        try:
            f = base_face()
        except RuntimeError:
            return False
        pts = [v.Point for v in _items(f.Vertices)]
        x0, x1 = min(p.X for p in pts) * 10, max(p.X for p in pts) * 10
        y0, y1 = min(p.Y for p in pts) * 10, max(p.Y for p in pts) * 10
        for b in pending:
            if b["eje"] == "x" and not (x0 - 0.01 <= b["pos"] <= x1 + 0.01):
                return False
            if b["eje"] == "y" and not (y0 - 0.01 <= b["pos"] <= y1 + 0.01):
                return False
        return True

    # 2) plegar uno por uno; si el lado que se mueve deja afuera a los pliegues pendientes, invertirlo
    for i, (b, line) in enumerate(zip(bends, lines)):
        pending = bends[i + 1:]
        fold, errs = None, []
        for side in (None, True, False):
            fdef = cd.Features.FoldFeatures.CreateFoldDefinition(line, f"{b.get('angulo', 90)} deg")
            _safe(lambda: setattr(fdef, "BendLocation", K_CENTERLINE_OF_BEND))
            if side is not None:
                _safe(lambda: setattr(fdef, "IsPositiveBendSide", side))
            try:
                cand = cd.Features.FoldFeatures.Add(fdef)
            except pythoncom.com_error as exc:
                errs.append(str(exc))
                continue
            doc.Update()
            if stationary_holds(pending):
                fold = cand
                break
            cand.Delete()
            doc.Update()
        if fold is None:
            raise RuntimeError(f"No se pudo plegar el pliegue {i + 1} ({b}): {errs}")
        _safe(lambda: setattr(fold, "Name", f"Pliegue {i + 1}"))
        folds.append(fold)
    doc.Update()
    ext = _extent_mm(cd)
    ok = bool(expected) and all(abs(a - e) <= 0.05 for a, e in zip(sorted(ext), expected))
    # si algún pliegue fue para el otro lado, probar invertirlos
    if expected and not ok and folds:
        for combo in range(1, 2 ** len(folds)):
            for j, fold in enumerate(folds):
                if combo >> j & 1:
                    _safe(lambda: setattr(fold.Definition, "IsPositiveBendDirection",
                                          not fold.Definition.IsPositiveBendDirection))
            doc.Update()
            ext = _extent_mm(cd)
            tried.append({"combinacion": combo, "envolvente": ext})
            ok = all(abs(a - e) <= 0.05 for a, e in zip(sorted(ext), expected))
            if ok:
                break
            for j, fold in enumerate(folds):          # deshacer
                if combo >> j & 1:
                    _safe(lambda: setattr(fold.Definition, "IsPositiveBendDirection",
                                          not fold.Definition.IsPositiveBendDirection))

    if not cd.HasFlatPattern:
        cd.Unfold()
    fp = cd.FlatPattern
    flat = (round(fp.Length * 10, 2), round(fp.Width * 10, 2))
    _safe(lambda: fp.ExitEdit())
    _iprop(doc, "Design Tracking Properties", "Part Number", spec["nombre"][:MAX_PART_NUMBER])
    _iprop(doc, "Design Tracking Properties", "Description", spec["nombre"].upper())
    _set_material(app, doc, ["Acero, suave", "Acero, dulce", "Acero", "Steel, Mild"])
    out_ipt.parent.mkdir(parents=True, exist_ok=True)
    if out_ipt.exists():
        out_ipt.unlink()
    doc.SaveAs(str(out_ipt), False)
    if out_dxf:
        out_dxf.parent.mkdir(parents=True, exist_ok=True)
        if out_dxf.exists():
            out_dxf.unlink()
        cd.DataIO.WriteDataToFile(
            "FLAT PATTERN DXF?AcadVersion=2000&OuterProfileLayer=CORTE_EXTERIOR"
            "&InteriorProfilesLayer=CORTE_INTERIOR&MergeProfilesIntoPolyline=True&RebaseGeometry=True"
            f"&InvisibleLayers={DXF_HIDDEN_LAYERS}", str(out_dxf))
    return {"pieza": spec["nombre"], "ipt": str(out_ipt), "dxf": str(out_dxf) if out_dxf else None,
            "envolvente_mm": ext, "esperada_mm": expected, "envolvente_ok": ok,
            "desarrollo_inventor_mm": flat, "desarrollo_diseno_mm": spec.get("desarrollo"),
            "segundos_boceto": t_sketch, "segundos_total": round(time.time() - t0, 1),
            "intentos_sentido": tried, "textos": textos_res, "documento": doc}


def build_plate_part(app, nombre: str, largo: float, alto: float, espesor: float, out_ipt: Path,
                     materiales: tuple = ("Caucho", "Goma", "Rubber")) -> dict:
    """Placa maciza (no chapa) largo × alto × espesor: boceto en XY desde el origen y extrusión +Z."""
    tg = app.TransientGeometry
    doc = app.Documents.Add(K_PART_DOCUMENT, app.FileManager.GetTemplateFile(K_PART_DOCUMENT), True)
    cd = doc.ComponentDefinition
    sk = cd.Sketches.Add(cd.WorkPlanes.Item(3))
    sk.SketchLines.AddAsTwoPointRectangle(tg.CreatePoint2d(0, 0), tg.CreatePoint2d(largo / 10, alto / 10))
    ext = cd.Features.ExtrudeFeatures.AddByDistanceExtent(sk.Profiles.AddForSolid(), espesor / 10,
                                                          20993, 20481)   # positiva, unión
    _safe(lambda: setattr(ext, "Name", "Placa"))
    _iprop(doc, "Design Tracking Properties", "Part Number", nombre[:MAX_PART_NUMBER])
    _iprop(doc, "Design Tracking Properties", "Description", nombre.upper())
    mat = _set_material(app, doc, list(materiales))
    doc.Update()
    out_ipt.parent.mkdir(parents=True, exist_ok=True)
    if out_ipt.exists():
        out_ipt.unlink()
    doc.SaveAs(str(out_ipt), False)
    return {"pieza": nombre, "ipt": str(out_ipt), "envolvente_mm": _extent_mm(cd), "material": mat,
            "documento": doc}


# =============================================================================
# Perfiles (caños) y marcos soldados de caño — para rejas y estructuras
# =============================================================================
def _rect_tube_sketch(cd, plane, p_min, p_max, e, tg):
    """Sección de caño en 'plane' dada por dos esquinas opuestas EN COORDENADAS DEL MODELO (mm), que
    difieren en los dos ejes del plano; el interior se achica e en esos ejes. No depende de cómo estén
    orientados los ejes del boceto."""
    sk = cd.Sketches.Add(plane)
    lo, hi = list(p_min), list(p_max)
    ejes = [i for i in range(3) if abs(hi[i] - lo[i]) > 1e-9]
    for k in (0, 1):
        q1, q2 = lo[:], hi[:]
        if k:
            for i in ejes:
                q1[i] += e
                q2[i] -= e
        s1 = sk.ModelToSketchSpace(tg.CreatePoint(*[v / 10 for v in q1]))
        s2 = sk.ModelToSketchSpace(tg.CreatePoint(*[v / 10 for v in q2]))
        sk.SketchLines.AddAsTwoPointRectangle(s1, s2)
    return sk


def _profile_ring(sk):
    """Perfil del anillo (la región entre los dos rectángulos): el de menor área de los perfiles posibles."""
    prof = sk.Profiles.AddForSolid()
    return prof


def build_tube_part(app, nombre: str, a: float, b: float, e: float, largo: float, out_ipt: Path,
                    descripcion: str = "") -> dict:
    """Caño rectangular a × b × e, largo L, sección centrada en el origen y eje +Z (0 .. L)."""
    tg = app.TransientGeometry
    doc = app.Documents.Add(K_PART_DOCUMENT, app.FileManager.GetTemplateFile(K_PART_DOCUMENT), True)
    cd = doc.ComponentDefinition
    sk = _rect_tube_sketch(cd, cd.WorkPlanes.Item(3), (-a / 2, -b / 2, 0), (a / 2, b / 2, 0), e, tg)
    ext = cd.Features.ExtrudeFeatures.AddByDistanceExtent(sk.Profiles.AddForSolid(), largo / 10, 20993, 20481)
    _safe(lambda: setattr(ext, "Name", "Caño"))
    return _finish_struct(app, doc, nombre, descripcion or f"CAÑO {a:g}x{b:g}x{e:g} L={largo:g}", out_ipt)


def build_frame_part(app, nombre: str, W: float, H: float, a: float, b: float, e: float, out_ipt: Path,
                     travesanos: tuple = (), agujeros: list | None = None, descripcion: str = "") -> dict:
    """Marco soldado de caño a (en el plano) × b (espesor) × e: montantes de alto H en x = 0..a y W-a..W,
    largueros de W - 2a arriba, abajo y en las alturas 'travesanos' (centro, mm). Plano XY, espesor
    centrado en z = 0. agujeros: [(x, y, d)] pasantes en Z."""
    tg = app.TransientGeometry
    doc = app.Documents.Add(K_PART_DOCUMENT, app.FileManager.GetTemplateFile(K_PART_DOCUMENT), True)
    cd = doc.ComponentDefinition
    wp = cd.WorkPlanes
    feats = cd.Features.ExtrudeFeatures
    def extruir(sk, dist_mm, eje, hasta_mm):
        """Extruye y verifica que el cuerpo llegue a 'hasta_mm' en el eje (0 x, 1 y); si no, invierte."""
        for direc in (20993, 20994):
            f = feats.AddByDistanceExtent(sk.Profiles.AddForSolid(), dist_mm / 10, direc, 20481)
            doc.Update()
            mx, mn = cd.RangeBox.MaxPoint, cd.RangeBox.MinPoint
            vmax, vmin = (mx.X, mn.X) if eje == 0 else (mx.Y, mn.Y)
            if vmax * 10 >= hasta_mm - 0.01 and vmin * 10 >= -0.01 - (a if eje == 0 else 0):
                return f
            f.Delete()
        raise RuntimeError("No se pudo extruir el caño en el sentido correcto")

    # montantes: sección en el plano XZ (normal Y), extrusión hacia +Y
    for xc in (a / 2, W - a / 2):
        extruir(_rect_tube_sketch(cd, wp.Item(2), (xc - a / 2, 0, -b / 2), (xc + a / 2, 0, b / 2), e, tg), H, 1, H)
    # largueros: sección en un plano paralelo a YZ en x = a, extrusión hacia +X hasta W - a
    pl = wp.AddByPlaneAndOffset(wp.Item(1), a / 10)
    _safe(lambda: setattr(pl, "Visible", False))
    for yc in (a / 2, H - a / 2, *travesanos):
        sk = _rect_tube_sketch(cd, pl, (a, yc - a / 2, -b / 2), (a, yc + a / 2, b / 2), e, tg)
        f = feats.AddByDistanceExtent(sk.Profiles.AddForSolid(), (W - 2 * a) / 10, 20993, 20481)
        doc.Update()
        if cd.RangeBox.MinPoint.X * 10 < -0.01:          # salió hacia -x: invertir
            f.Delete()
            feats.AddByDistanceExtent(sk.Profiles.AddForSolid(), (W - 2 * a) / 10, 20994, 20481)
    if agujeros:
        sk = cd.Sketches.Add(wp.Item(3))
        for x, y, d in agujeros:
            c = sk.ModelToSketchSpace(tg.CreatePoint(x / 10, y / 10, 0))
            sk.SketchCircles.AddByCenterRadius(c, d / 20)
        feats.AddByThroughAllExtent(sk.Profiles.AddForSolid(), 20995, 20482)
    return _finish_struct(app, doc, nombre, descripcion or f"MARCO {W:g}x{H:g} CAÑO {a:g}x{b:g}x{e:g}", out_ipt)


def _finish_struct(app, doc, nombre, descr, out_ipt: Path) -> dict:
    _iprop(doc, "Design Tracking Properties", "Part Number", nombre[:MAX_PART_NUMBER])
    _iprop(doc, "Design Tracking Properties", "Description", descr.upper())
    _set_material(app, doc, ["Acero, suave", "Acero, dulce", "Acero", "Steel, Mild"])
    doc.Update()
    out_ipt.parent.mkdir(parents=True, exist_ok=True)
    if out_ipt.exists():
        out_ipt.unlink()
    doc.SaveAs(str(out_ipt), False)
    cd = doc.ComponentDefinition
    return {"pieza": nombre, "ipt": str(out_ipt), "envolvente_mm": _extent_mm(cd),
            "cuerpos": _safe(lambda: cd.SurfaceBodies.Count), "masa_kg": _safe(lambda: round(cd.MassProperties.Mass, 3)),
            "documento": doc}


def _solid_sheet(app, ddoc, sheet, doc, qty: int, warnings: list) -> dict:
    """Hoja A4 para una pieza que no es chapa (caño, marco soldado): frente, lateral, planta e isométrica,
    cotas totales y nota con la descripción."""
    tg = app.TransientGeometry
    P = tg.CreatePoint2d
    cd = doc.ComponentDefinition
    stem = Path(doc.FullFileName).stem
    ex, ey, ez = _extent_mm(cd)
    _safe(lambda: setattr(sheet, "Size", 9997))
    _safe(lambda: setattr(sheet, "Orientation", 10242))
    W, H = sheet.Width, sheet.Height
    top = H - 1.2
    bottom = _title_block_top(sheet) + 0.6
    # escala: frente (ex × ey) + lateral (ez) en horizontal; frente + planta (ez) en vertical
    scale = 0.01
    for sc in STD_SCALES:
        w_need = (ex + ez) * sc / 10 + 4.5
        h_need = (ey + ez) * sc / 10 + 4.0
        if w_need <= W * 0.62 and h_need <= top - bottom:
            scale = sc
            break
    fw, fh, sw, ph = ex * scale / 10, ey * scale / 10, ez * scale / 10, ez * scale / 10
    fx, fy = 2.2 + fw / 2, top - 1.0 - fh / 2
    views = sheet.DrawingViews
    front = views.AddBaseView(doc, P(fx, fy), scale, K_VIEW_FRONT, K_STYLE_HLR)
    side = views.AddProjectedView(front, P(fx + fw / 2 + 1.8 + sw / 2, fy), K_STYLE_FROM_BASE)
    plan = views.AddProjectedView(front, P(fx, fy - fh / 2 - 1.8 - ph / 2), K_STYLE_FROM_BASE)
    iso_sc = scale
    for sc in STD_SCALES:
        if sc <= scale and max(ex, ey, ez) * sc / 10 <= 7.5:
            iso_sc = sc
            break
    iso = views.AddProjectedView(front, P(W - 5.5, top - 4.5), K_STYLE_FROM_BASE)
    _safe(lambda: setattr(iso, "ScaleFromBase", False))
    _safe(lambda: setattr(iso, "Scale", iso_sc))
    for v, label in ((front, "FRENTE"), (side, "LATERAL"), (plan, "PLANTA"), (iso, "ISOMÉTRICA")):
        _safe(lambda: setattr(v, "ShowLabel", True))
        _safe(lambda: setattr(v.Label, "FormattedText", label))
    sheet.Update()
    dims = _Dims(app, sheet)
    _safe(lambda: _dimension_overall(dims, front, "frente"))
    _safe(lambda: _dimension_overall(dims, side, "lateral"))
    descr = _safe(lambda: doc.PropertySets.Item("Design Tracking Properties").Item("Description").Value, "") or ""
    mat = _safe(lambda: doc.ActiveMaterial.DisplayName, "") or "A CONFIRMAR"
    masa = _safe(lambda: round(cd.MassProperties.Mass, 2))
    notes = [f"PIEZA: {stem}  (x{qty})", f"{descr}", f"MATERIAL: {mat}  -  MASA: {masa} kg",
             f"MEDIDAS: {ex:g} x {ey:g} x {ez:g} mm  -  ESCALA {_scale_label(scale)}",
             "SOLDADURA: filete continuo en uniones de caños, amolar y pintar."]
    _safe(lambda: sheet.DrawingNotes.GeneralNotes.AddFitted(P(W * 0.40, bottom + 3.2), "<Br/>".join(notes)))
    _safe(lambda: setattr(sheet, "Name", stem[:30]))
    return {"pieza": stem, "cantidad": qty, "hoja": "A4", "escala": _scale_label(scale),
            "iso": _scale_label(iso_sc), "cotas": dims.ok, "cotas_fallidas": len(dims.failed), "tipo": "estructura"}


# =============================================================================
# Retoque de un plano existente (sin regenerarlo): listar, escalar, mover, ocultar, reacomodar
# =============================================================================
def _label_text(v) -> str:
    t = _safe(lambda: v.Label.FormattedText) or _safe(lambda: v.Name) or ""
    return re.sub(r"<[^>]+>", "", str(t)).strip().upper()


def _scale_value(txt) -> float:
    """'1:5' -> 0.2, '2:1' -> 2.0, 0.2 -> 0.2"""
    if isinstance(txt, (int, float)):
        return float(txt)
    a, b = str(txt).replace(" ", "").split(":")
    return float(a) / float(b)


def _sheet_listing(sheet, idx: int) -> dict:
    views = []
    for j, v in enumerate(_items(sheet.DrawingViews), 1):
        views.append({"n": j, "vista": _label_text(v), "escala": _scale_label(_safe(lambda: v.Scale, 1) or 1),
                      "x": round(v.Center.X, 2), "y": round(v.Center.Y, 2),
                      "ancho": round(v.Width, 2), "alto": round(v.Height, 2)})
    notes = []
    for j, n in enumerate(_items(sheet.DrawingNotes.GeneralNotes), 1):
        p = _safe(lambda: n.Position)
        notes.append({"n": j, "x": p and round(p.X, 2), "y": p and round(p.Y, 2),
                      "texto": re.sub(r"<[^>]+>", " | ", str(_safe(lambda: n.FormattedText, "")))[:120]})
    return {"hoja": idx, "nombre": sheet.Name, "ancho_cm": round(sheet.Width, 1), "alto_cm": round(sheet.Height, 1),
            "vistas": views, "notas": notes}


def _find_view(sheet, ref):
    vs = _items(sheet.DrawingViews)
    if isinstance(ref, int):
        return vs[ref - 1]
    ref = str(ref).upper().replace("ISOMETRICA", "ISOMÉTRICA")
    for v in vs:
        if _label_text(v).startswith(ref):
            return v
    raise ValueError(f"No encontré la vista '{ref}' en la hoja {sheet.Name}")


def _relayout_sheet(app, sheet, warnings: list) -> str:
    """Reacomoda una hoja con el acomodador, usando el tamaño actual de sus vistas (no cambia escalas)."""
    keymap = {"FRENTE": "b", "LATERAL": "s", "PLANTA": "p", "ISOMÉTRICA": "i", "DESARROLLO": "f"}
    views = {}
    for v in _items(sheet.DrawingViews):
        t = _label_text(v)
        for name, key in keymap.items():
            if t.startswith(name):
                views[key] = v
    if "b" not in views or "s" not in views:
        return "hoja sin FRENTE/LATERAL: no se reacomoda"
    sc = views["b"].Scale
    iso_f = (views["i"].Scale / sc) if "i" in views else 0.5
    unit = {k: (v.Width / (sc * (iso_f if k == "i" else 1)), v.Height / (sc * (iso_f if k == "i" else 1)))
            for k, v in views.items()}
    if "p" not in unit:
        unit["p"] = (0.01, 0.01)
    drop = tuple(k for k in ("p", "i") if k not in views)
    n_notes = 6
    lay = _plan_layout(unit, sc, sheet.Width, sheet.Height, n_notes, 2, iso_f, drop)
    if lay is None:
        return "no entra con las escalas actuales"
    P = app.TransientGeometry.CreatePoint2d
    for k, v in views.items():
        if k in lay:
            _safe(lambda: setattr(v, "Position", P(*lay[k])))
    notes = _items(sheet.DrawingNotes.GeneralNotes)
    if notes and "n" in lay:
        _safe(lambda: setattr(notes[0], "Position", P(*lay["n"])))
    return "reacomodada"


def inventor_edit_drawing(drawing_path: str, ops: list | None = None, export_pdf: bool = True) -> str:
    """Abre un plano existente y aplica retoques sin regenerarlo. Sin ops, solo lista hojas/vistas/notas.
    Cada op es un dict con "hoja" (número o nombre) y una acción:
      {"hoja": 4, "vista": "ISOMÉTRICA", "escala": "1:5"}          cambia la escala de la vista
      {"hoja": 4, "vista": "ISOMÉTRICA", "mover": {"x": 24, "y": 7}}  posición absoluta (cm de hoja)
      {"hoja": 4, "vista": "PLANTA", "mover": {"dx": 1.5, "dy": 0}}   desplazamiento relativo
      {"hoja": 4, "vista": "PLANTA", "borrar": true}                  elimina la vista
      {"hoja": 4, "notas": {"x": 15, "y": 9}}                          mueve las notas generales
      {"hoja": 4, "reacomodar": true}                                  reubica todo con el acomodador
    Guarda el plano y reexporta el PDF (si el PDF está abierto en otro programa, usa otro nombre)."""
    path = Path(drawing_path).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f"No existe el plano: {path}")
    app = _inventor()
    ddoc = None
    for d in _items(app.Documents):
        if _safe(lambda: Path(d.FullFileName).resolve() == path, False):
            ddoc = d
    opened_here = ddoc is None
    if ddoc is None:
        app.SilentOperation = True
        try:
            ddoc = app.Documents.Open(str(path), True)
        finally:
            app.SilentOperation = False
    sheets = _items(ddoc.Sheets)
    P = app.TransientGeometry.CreatePoint2d
    done, errors, warnings = [], [], []

    def get_sheet(ref):
        if isinstance(ref, int):
            return ref, sheets[ref - 1]
        for i, sh in enumerate(sheets, 1):
            if str(ref).lower() in sh.Name.lower():
                return i, sh
        raise ValueError(f"No encontré la hoja '{ref}'")

    for op in ops or []:
        try:
            idx, sheet = get_sheet(op["hoja"])
            if op.get("reacomodar"):
                done.append({"hoja": idx, "resultado": _relayout_sheet(app, sheet, warnings)})
                continue
            if "notas" in op:
                note = _items(sheet.DrawingNotes.GeneralNotes)[0]
                m = op["notas"]
                cur = note.Position
                x = m.get("x", cur.X + m.get("dx", 0))
                y = m.get("y", cur.Y + m.get("dy", 0))
                note.Position = P(x, y)
                done.append({"hoja": idx, "notas": [x, y]})
                continue
            v = _find_view(sheet, op["vista"])
            name = _label_text(v)
            if op.get("borrar"):
                v.Delete()
                done.append({"hoja": idx, "vista": name, "borrada": True})
                continue
            if "escala" in op:
                sc = _scale_value(op["escala"])
                _safe(lambda: setattr(v, "ScaleFromBase", False))
                v.Scale = sc
                if name.startswith("ISOM"):   # actualizar "(ISO 1:x)" en las notas
                    for n in _items(sheet.DrawingNotes.GeneralNotes):
                        t = _safe(lambda: n.FormattedText, "")
                        if t and "(ISO " in t:
                            _safe(lambda: setattr(n, "FormattedText",
                                                  re.sub(r"\(ISO [0-9:]+\)", f"(ISO {_scale_label(sc)})", t)))
                done.append({"hoja": idx, "vista": name, "escala": _scale_label(sc)})
            if "mover" in op:
                m = op["mover"]
                cur = v.Center
                x = m.get("x", cur.X + m.get("dx", 0))
                y = m.get("y", cur.Y + m.get("dy", 0))
                keep_scale = _safe(lambda: v.Scale)
                own_scale = _safe(lambda: not v.ScaleFromBase, True)
                v.Position = P(x, y)
                if keep_scale and own_scale:      # mover solo puede alterar la escala: volver a fijarla
                    _safe(lambda: setattr(v, "ScaleFromBase", False))
                    _safe(lambda: setattr(v, "Scale", keep_scale))
                    v.Position = P(x, y)
                done.append({"hoja": idx, "vista": name, "posicion": [round(x, 2), round(y, 2)]})
        except Exception as exc:  # noqa: BLE001
            errors.append({"op": op, "error": str(exc)})

    pdf = None
    if ops:
        _safe(lambda: ddoc.Update2(True))
        _safe(lambda: ddoc.Update())
        for sh in _items(ddoc.Sheets):          # que cada hoja se regenere antes de exportar
            _safe(lambda: sh.Activate())
            _safe(lambda: sh.Update())
        _safe(lambda: _items(ddoc.Sheets)[0].Activate())
        ddoc.Save()
        if export_pdf:
            pdf = path.parent / "PDF" / f"{path.stem}.pdf"
            pdf.parent.mkdir(exist_ok=True)
            if pdf.exists():
                try:
                    pdf.unlink()
                except PermissionError:
                    pdf = pdf.with_name(f"{pdf.stem}_{time.strftime('%H%M%S')}.pdf")
                    warnings.append(f"PDF abierto en otro programa; se exportó como {pdf.name}")
            _export_pdf(app, ddoc, pdf)
    listing = [_sheet_listing(sh, i) for i, sh in enumerate(_items(ddoc.Sheets), 1)]
    if opened_here:
        _safe(lambda: ddoc.Close(True))
    return _result(plano=str(path), pdf=str(pdf) if pdf else None, cambios=done, errores=errors,
                   avisos=warnings, hojas=listing)


# =============================================================================
# Ejecución de scripts del complemento en un proceso nuevo (toma siempre el código actualizado)
# =============================================================================
PLUGIN_ROOT = Path(__file__).resolve().parents[1]


def inventor_run_script(script: str, args: list[str] | None = None, timeout_s: int = 900) -> str:
    """Ejecuta un script de la carpeta scripts/ del complemento con el Python del .venv, en un proceso
    nuevo (así usa el código recién modificado) y devuelve su salida. Solo acepta archivos .py de scripts/."""
    name = Path(script).name
    target = (PLUGIN_ROOT / "scripts" / name).resolve()
    if target.parent != (PLUGIN_ROOT / "scripts").resolve() or target.suffix != ".py" or not target.is_file():
        raise ValueError(f"Script no permitido o inexistente: {script}")
    py = PLUGIN_ROOT / ".venv" / "Scripts" / "python.exe"
    if not py.is_file():
        py = Path(sys.executable)
    proc = subprocess.run([str(py), str(target), *(args or [])], cwd=str(PLUGIN_ROOT),
                          capture_output=True, text=True, encoding="utf-8", errors="replace",
                          timeout=timeout_s)
    out = proc.stdout[-20000:]
    err = proc.stderr[-8000:]
    return _result(script=name, args=args or [], codigo_salida=proc.returncode, salida=out, errores=err)


# --- Registro MCP ------------------------------------------------------------
if FastMCP is not None:
    mcp = FastMCP("Autodesk Inventor")
    for _fn in (inventor_status, inventor_create_box, inventor_open_document,
                inventor_export_active_document, inventor_create_c_channel,
                inventor_inspect_assembly, inventor_fabrication_package, inventor_run_script,
                inventor_edit_drawing):
        mcp.tool(name=_fn.__name__)(_fn)


if __name__ == "__main__":
    if FastMCP is None:
        sys.exit("Falta el paquete 'mcp'. Ejecutá scripts/setup.ps1")
    _log("Inventor Assistant MCP 0.2.0 iniciado")
    mcp.run(transport="stdio")
