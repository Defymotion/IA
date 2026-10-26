"""(Corre DENTRO de Blender) Aspecto del render sobre la escena animada: cielo (HDRI de estudio de Blender para luz y
reflejos, fondo blanco para la cámara), sol, piso de cemento claro, metales con brillo, Eevee con trazado de rayos,
desenfoque de movimiento y gestión de color. Guarda el .blend (o una copia) listo para renderizar.
Uso: blender -b anim.blend -P bl_ambiente.py -- <salida.blend> [--variante real|base] [--hdri studio] [--muestras 48]
     [--vista Standard|AgX] [--look ...] [--sol 3.0] [--hdri-fuerza 0.6] [--sin-blur]
"""
import glob
import json
import math
import os
import sys

import bpy

argv = sys.argv[sys.argv.index("--") + 1:]
SALIDA = argv[0]


def arg(k, d):
    return argv[argv.index(k) + 1] if k in argv else d


VAR = arg("--variante", "real")
HDRI = arg("--hdri", "studio")
MUESTRAS = int(arg("--muestras", "48"))
VISTA = arg("--vista", "Standard")
LOOK = arg("--look", "")
SOL = float(arg("--sol", "3.0"))
F_HDRI = float(arg("--hdri-fuerza", "0.6"))
sc = bpy.context.scene
log = {"avisos": []}
METALES = ("Acero", "Cromo", "Aluminio", "inoxidable", "Inox", "Semipulido", "Galvan", "Metal", "Cobre", "Placa")


def bsdf(m):
    return m.node_tree.nodes.get("Principled BSDF") if m and m.node_tree else None


# ------------------------------------------------------------------ materiales
mat_metal = {}
for o in bpy.data.objects:
    if o.type != "MESH":
        continue
    a = str(o.get("a", ""))
    es_metal = VAR == "real" and any(k in a for k in METALES)
    for sl in o.material_slots:
        m = sl.material
        b = bsdf(m)
        if b is None:
            continue
        if es_metal and sl.link == "OBJECT":
            if m.name not in mat_metal:
                mm_ = m.copy()
                mm_.name = m.name + "_metal"
                bb = bsdf(mm_)
                bb.inputs["Metallic"].default_value = 0.75
                bb.inputs["Roughness"].default_value = 0.36
                mat_metal[m.name] = mm_
            sl.material = mat_metal[m.name]
for m in bpy.data.materials:
    b = bsdf(m)
    if b is None or m.name.endswith("_metal") or m.name.startswith("Piso"):
        continue
    b.inputs["Roughness"].default_value = 0.42 if VAR == "real" else 0.55
log["materiales_metal"] = len(mat_metal)
# ------------------------------------------------------------------ piso
piso = bpy.data.objects.get("Piso")
if piso is not None:
    m = bpy.data.materials.new("Piso_cemento")
    try:
        m.use_nodes = True
    except Exception:  # noqa: BLE001
        pass
    nt = m.node_tree
    b = nt.nodes.get("Principled BSDF")
    if VAR == "real":
        tex = nt.nodes.new("ShaderNodeTexNoise")
        tex.inputs["Scale"].default_value = 0.35
        tex.inputs["Detail"].default_value = 6.0
        ramp = nt.nodes.new("ShaderNodeValToRGB")
        ramp.color_ramp.elements[0].color = (0.70, 0.70, 0.69, 1.0)
        ramp.color_ramp.elements[1].color = (0.80, 0.80, 0.79, 1.0)
        nt.links.new(tex.outputs["Fac"], ramp.inputs["Fac"])
        nt.links.new(ramp.outputs["Color"], b.inputs["Base Color"])
        b.inputs["Roughness"].default_value = 0.55
    else:
        b.inputs["Base Color"].default_value = (0.91, 0.91, 0.91, 1.0)
        b.inputs["Roughness"].default_value = 0.8
    piso.data.materials.clear()
    piso.data.materials.append(m)
# ------------------------------------------------------------------ cielo
w = sc.world
nt = w.node_tree
for n in list(nt.nodes):
    nt.nodes.remove(n)
out = nt.nodes.new("ShaderNodeOutputWorld")
blanco = nt.nodes.new("ShaderNodeBackground")
blanco.inputs["Color"].default_value = (1.0, 1.0, 1.0, 1.0)
blanco.inputs["Strength"].default_value = 1.0
hdri_ok = False
if VAR == "real":
    rutas = []
    for base in (bpy.utils.system_resource("DATAFILES", path="studiolights/world"),):
        if base:
            rutas += glob.glob(os.path.join(base, "*.exr"))
    log["hdri_disponibles"] = [os.path.basename(r) for r in rutas]
    elegido = next((r for r in rutas if HDRI in os.path.basename(r).lower()), rutas[0] if rutas else None)
    if elegido:
        env = nt.nodes.new("ShaderNodeTexEnvironment")
        env.image = bpy.data.images.load(elegido, check_existing=True)
        luz = nt.nodes.new("ShaderNodeBackground")
        luz.inputs["Strength"].default_value = F_HDRI
        nt.links.new(env.outputs["Color"], luz.inputs["Color"])
        lp = nt.nodes.new("ShaderNodeLightPath")
        mix = nt.nodes.new("ShaderNodeMixShader")
        nt.links.new(lp.outputs["Is Camera Ray"], mix.inputs["Fac"])
        nt.links.new(luz.outputs["Background"], mix.inputs[1])
        nt.links.new(blanco.outputs["Background"], mix.inputs[2])
        nt.links.new(mix.outputs["Shader"], out.inputs["Surface"])
        hdri_ok = True
        log["hdri"] = os.path.basename(elegido)
if not hdri_ok:
    blanco.inputs["Strength"].default_value = 0.6
    nt.links.new(blanco.outputs["Background"], out.inputs["Surface"])
# ------------------------------------------------------------------ sol
so = bpy.data.objects.get("Sol")
if so is not None:
    so.data.energy = SOL
    so.data.angle = math.radians(4.0 if VAR == "real" else 12.0)
    so.rotation_euler = (math.radians(40), math.radians(10), math.radians(32))
# ------------------------------------------------------------------ render
ee = sc.eevee
for attr, val in (("taa_render_samples", MUESTRAS), ("use_raytracing", VAR == "real"), ("use_shadows", True),
                  ("shadow_ray_count", 2), ("shadow_step_count", 8), ("use_fast_gi", VAR == "real")):
    try:
        setattr(ee, attr, val)
    except Exception as e:  # noqa: BLE001
        log["avisos"].append(f"eevee.{attr}: {e!r}"[:120])
try:
    ee.ray_tracing_options.resolution_scale = "2"
except Exception:  # noqa: BLE001
    pass
if "--sin-blur" in argv:
    sc.render.use_motion_blur = False
try:
    sc.view_settings.view_transform = VISTA
    if LOOK:
        sc.view_settings.look = LOOK
except Exception as e:  # noqa: BLE001
    log["avisos"].append(f"vista: {e!r}"[:160])
sc.render.image_settings.file_format = "PNG"
sc.render.image_settings.color_mode = "RGB"
bpy.ops.wm.save_as_mainfile(filepath=SALIDA, compress=False)
log["variante"], log["vista"], log["blur"] = VAR, sc.view_settings.view_transform, sc.render.use_motion_blur
print("RESULTADO " + json.dumps(log, ensure_ascii=False), flush=True)
