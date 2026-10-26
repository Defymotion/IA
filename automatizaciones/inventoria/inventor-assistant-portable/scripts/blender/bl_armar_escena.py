"""(Corre DENTRO de Blender) Arma la escena L3N desde escena_blender.json (l3n_blender_exportar.py):
mallas STL compartidas, objetos fijos con su matriz y color, un Empty "SIM:<nombre>" por cada objeto móvil con sus
piezas como hijas, piso blanco, cielo blanco, sol suave y cámara. Ejes: Inventor Y arriba (mm) -> Blender Z arriba (m).
Uso: blender -b --factory-startup -P bl_armar_escena.py -- <escena_blender.json> <plan.json> <salida.blend>
"""
import json
import math
import os
import sys
import time

import bpy
import bmesh  # noqa: E402  (después de bpy: necesario si bpy es un módulo)
from mathutils import Matrix

T0 = time.time()
argv = sys.argv[sys.argv.index("--") + 1:]
ESCJ, PLANJ, BLEND = argv[0], argv[1], argv[2]
FONDO = float(argv[argv.index("--fondo") + 1]) if "--fondo" in argv else 0.6
SOL = float(argv[argv.index("--sol") + 1]) if "--sol" in argv else 2.5
D = json.load(open(ESCJ, encoding="utf-8"))
PLAN = json.load(open(PLANJ, encoding="utf-8"))
MALLAS_DIR = os.path.join(os.path.dirname(ESCJ), "mallas")
C = Matrix(((1, 0, 0, 0), (0, 0, -1, 0), (0, 1, 0, 0), (0, 0, 0, 1)))
log = {"avisos": []}


def Mm(M):
    return Matrix(((M[0], M[1], M[2], M[3] / 1000.0), (M[4], M[5], M[6], M[7] / 1000.0),
                   (M[8], M[9], M[10], M[11] / 1000.0), (0, 0, 0, 1)))


def lin(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
# ------------------------------------------------------------------ mallas
usadas = {h["m"] for h in D["estaticos"]} | {h["m"] for hs in D["plantillas"].values() for h in hs}
OBJ_DIR = os.path.join(os.path.dirname(ESCJ), "mallas_obj")
MESH, NMAT, MTL = {}, {}, {}


def srgb_a_lineal(v):
    return lin(max(0.0, min(1.0, v)))


def material_mtl(m):
    """Un material por color del .mtl (nombre 'R,G,B' de Inventor), corregido a lineal y con el mismo acabado."""
    base = m.name.split(".")[0]
    if base in MTL:
        return MTL[base]
    rgb = None
    try:
        rgb = [int(v) / 255.0 for v in base.split(",")[:3]]
        assert len(rgb) == 3
    except Exception:  # noqa: BLE001
        try:
            b = m.node_tree.nodes.get("Principled BSDF")
            rgb = list(b.inputs["Base Color"].default_value)[:3]
        except Exception:  # noqa: BLE001
            rgb = list(m.diffuse_color)[:3]
    nuevo = bpy.data.materials.new("mtl_" + base)
    try:
        nuevo.use_nodes = True
    except Exception:  # noqa: BLE001
        pass
    b = nuevo.node_tree.nodes.get("Principled BSDF")
    col = (srgb_a_lineal(rgb[0]), srgb_a_lineal(rgb[1]), srgb_a_lineal(rgb[2]), 1.0)
    b.inputs["Base Color"].default_value = col
    b.inputs["Roughness"].default_value = 0.55
    nuevo.diffuse_color = col
    MTL[base] = nuevo
    return nuevo


for mid in sorted(usadas):
    p_obj = os.path.join(OBJ_DIR, mid + ".obj")
    p_stl = os.path.join(MALLAS_DIR, mid + ".stl")
    antes = set(bpy.data.objects)
    try:
        if os.path.exists(p_obj):
            bpy.ops.wm.obj_import(filepath=p_obj, global_scale=0.001, forward_axis="Y", up_axis="Z",
                                  use_split_objects=False, use_split_groups=False)
        elif os.path.exists(p_stl):
            bpy.ops.wm.stl_import(filepath=p_stl, global_scale=0.001)
        else:
            log["avisos"].append(f"falta {mid}")
            continue
    except Exception as e:  # noqa: BLE001
        log["avisos"].append(f"{mid}: {e!r}"[:200])
        continue
    nuevos = [o for o in bpy.data.objects if o not in antes]
    if not nuevos:
        continue
    if len(nuevos) > 1:                           # por si el importador separó cuerpos: se juntan
        for o in bpy.context.view_layer.objects:
            o.select_set(o in nuevos)
        bpy.context.view_layer.objects.active = nuevos[0]
        bpy.ops.object.join()
        nuevos = [o for o in bpy.data.objects if o not in antes]
    ob = nuevos[0]
    me = ob.data
    me.name = mid
    me.transform(ob.matrix_world)            # la escala/ejes del importador quedan en la malla (m, ejes de la pieza)
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)
    bm.to_mesh(me)
    bm.free()
    me.shade_smooth()
    try:
        me.set_sharp_from_angle(angle=math.radians(35))
    except Exception:  # noqa: BLE001
        pass
    for i, m in enumerate(me.materials):
        if m is not None:
            me.materials[i] = material_mtl(m)
    for o in nuevos:
        bpy.data.objects.remove(o)
    NMAT[mid] = len([m for m in me.materials if m is not None])
    if not me.materials:
        me.materials.append(None)
    MESH[mid] = me
log["mallas"] = len(MESH)
log["mallas_obj"] = sum(1 for mid in MESH if os.path.exists(os.path.join(OBJ_DIR, mid + ".obj")))
print(f"[{time.time() - T0:6.1f} s] mallas {len(MESH)}", flush=True)
# ------------------------------------------------------------------ materiales
MATS = {}


def material(c):
    k = tuple(round(v, 3) for v in c)
    if k not in MATS:
        m = bpy.data.materials.new(f"c_{k[0]:.3f}_{k[1]:.3f}_{k[2]:.3f}")
        try:
            m.use_nodes = True
        except Exception:  # noqa: BLE001
            pass
        b = m.node_tree.nodes.get("Principled BSDF")
        b.inputs["Base Color"].default_value = (lin(k[0]), lin(k[1]), lin(k[2]), 1.0)
        b.inputs["Roughness"].default_value = 0.55
        m.diffuse_color = (lin(k[0]), lin(k[1]), lin(k[2]), 1.0)
        MATS[k] = m
    return MATS[k]


# apariencias con textura (madera, cartón) que el OBJ/la API no traen con su color real, y la bandeja LEAF, blanca
# según la ficha (liner externo blanco)
COLOR_POR_ARCHIVO = {"Caja_LEAF": [0.93, 0.93, 0.91], "European Pallet": [0.80, 0.63, 0.43]}
COLOR_POR_APARIENCIA = {"Abedul": [0.80, 0.63, 0.43], "Cartón": [0.62, 0.47, 0.32]}


def color_forzado(h):
    f = D["mallas"].get(h["m"], {}).get("f", "")
    for k, c in COLOR_POR_ARCHIVO.items():
        if k in f:
            return c
    for k, c in COLOR_POR_APARIENCIA.items():
        if h.get("a", "").startswith(k):
            return c
    return None


def objeto(nombre, h, col):
    me = MESH.get(h["m"])
    if me is None:
        return None
    o = bpy.data.objects.new(nombre, me)
    col.objects.link(o)
    cf = color_forzado(h)
    if cf is not None:
        for sl in o.material_slots:
            sl.link = "OBJECT"
            sl.material = material(cf)
        return o
    # colores por cara del .mtl, salvo pieza de un solo color con apariencia propia de la ocurrencia (pisada en el
    # ensamble) o malla sin materiales
    n = NMAT.get(h["m"], 0)
    if n == 0 or (n == 1 and h.get("a") not in ("Valor por defecto", "?")):
        o.material_slots[0].link = "OBJECT"
        o.material_slots[0].material = material(h["c"])
    return o


OCULT = PLAN.get("ocultar", [])
GB = PLAN["grippers"]["SIM_B_Gripper"]
PREF_B = tuple(GB.get("moviles", []) + GB.get("ocultar_hijos", []))


def oculto(ruta):
    return any(ruta == r or ruta.startswith(r + "/") for r in OCULT)


def oculto_en_gripper_B(ruta):
    return any(seg.startswith(PREF_B) for seg in ruta.split("/")[1:]) if PREF_B else False


col_f = bpy.data.collections.new("Fijos")
col_s = bpy.data.collections.new("SIM")
sc.collection.children.link(col_f)
sc.collection.children.link(col_s)
n_oc = 0
for k, h in enumerate(D["estaticos"]):
    if oculto(h["p"]):
        n_oc += 1
        continue
    o = objeto(f"F{k:05d}", h, col_f)
    if o is not None:
        o.matrix_world = C @ Mm(h["M"])
        o["ruta"] = h["p"]
log["fijos_ocultos"] = n_oc
print(f"[{time.time() - T0:6.1f} s] fijos {len(D['estaticos']) - n_oc} (ocultos {n_oc})", flush=True)
VIS0 = {n: ob["vis"] for n, ob in PLAN["objetos"].items()}
M0 = {n: ob["M"] for n, ob in PLAN["objetos"].items()}
for nm, clave in D["sim"].items():
    e = bpy.data.objects.new("SIM:" + nm, None)
    e.empty_display_size = 0.1
    col_s.objects.link(e)
    if nm in M0:
        e.matrix_world = C @ Mm(M0[nm])
    vis = VIS0.get(nm, True)
    e.hide_render = not vis
    for j, h in enumerate(D["plantillas"][clave]):
        if nm == "SIM_B_Gripper" and oculto_en_gripper_B(h["p"]):
            continue
        o = objeto(f"{nm}#{j}", h, col_s)
        if o is None:
            continue
        o.parent = e
        o.matrix_parent_inverse = Matrix.Identity(4)
        o.matrix_basis = Mm(h["M"])
        o.hide_render = not vis
print(f"[{time.time() - T0:6.1f} s] SIM {len(D['sim'])}", flush=True)
# ------------------------------------------------------------------ piso, cielo, luz, cámara
bpy.ops.mesh.primitive_plane_add(size=400.0, location=(0.0, 40.0, 0.0))
piso = bpy.context.active_object
piso.name = "Piso"
piso.data.materials.append(material([0.96, 0.96, 0.96]))
w = bpy.data.worlds.new("Cielo")
sc.world = w
try:
    w.use_nodes = True
except Exception:  # noqa: BLE001
    pass
bg = w.node_tree.nodes.get("Background")
bg.inputs["Color"].default_value = (1.0, 1.0, 1.0, 1.0)
bg.inputs["Strength"].default_value = FONDO
sol = bpy.data.lights.new("Sol", "SUN")
sol.energy = SOL
sol.angle = math.radians(12)
so = bpy.data.objects.new("Sol", sol)
sc.collection.objects.link(so)
so.rotation_euler = (math.radians(38), math.radians(8), math.radians(35))
cam = bpy.data.cameras.new("Camara")
cam.sensor_fit = "HORIZONTAL"
cam.clip_start = 0.1
cam.clip_end = 500.0
co = bpy.data.objects.new("Camara", cam)
sc.collection.objects.link(co)
sc.camera = co
# ------------------------------------------------------------------ render
for eng in ("BLENDER_EEVEE", "BLENDER_EEVEE_NEXT"):
    try:
        sc.render.engine = eng
        break
    except Exception:  # noqa: BLE001
        continue
log["motor"] = sc.render.engine
sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = 1920, 1080, 100
sc.render.image_settings.file_format = "PNG"
sc.view_settings.view_transform = "Standard"
try:
    sc.eevee.taa_render_samples = 32
except Exception:  # noqa: BLE001
    pass
bpy.ops.wm.save_as_mainfile(filepath=BLEND, compress=False)
log["objetos"] = len(bpy.data.objects)
log["materiales"] = len(MATS)
log["tiempo_s"] = round(time.time() - T0, 1)
print("RESULTADO " + json.dumps(log, ensure_ascii=False), flush=True)
