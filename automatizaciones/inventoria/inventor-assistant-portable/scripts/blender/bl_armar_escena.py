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
MESH = {}
for mid in sorted(usadas):
    p = os.path.join(MALLAS_DIR, mid + ".stl")
    if not os.path.exists(p):
        log["avisos"].append(f"falta {mid}")
        continue
    antes = set(bpy.data.objects)
    try:
        bpy.ops.wm.stl_import(filepath=p, global_scale=0.001)
    except Exception as e:  # noqa: BLE001
        log["avisos"].append(f"{mid}: {e!r}"[:200])
        continue
    nuevos = [o for o in bpy.data.objects if o not in antes]
    if not nuevos:
        continue
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
    for o in nuevos:
        bpy.data.objects.remove(o)
    me.materials.clear()
    me.materials.append(None)
    MESH[mid] = me
log["mallas"] = len(MESH)
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


def objeto(nombre, h, col):
    me = MESH.get(h["m"])
    if me is None:
        return None
    o = bpy.data.objects.new(nombre, me)
    col.objects.link(o)
    o.material_slots[0].link = "OBJECT"
    o.material_slots[0].material = material(h["c"])
    return o


col_f = bpy.data.collections.new("Fijos")
col_s = bpy.data.collections.new("SIM")
sc.collection.children.link(col_f)
sc.collection.children.link(col_s)
for k, h in enumerate(D["estaticos"]):
    o = objeto(f"F{k:05d}", h, col_f)
    if o is not None:
        o.matrix_world = C @ Mm(h["M"])
        o["ruta"] = h["p"]
print(f"[{time.time() - T0:6.1f} s] fijos {len(D['estaticos'])}", flush=True)
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
bg.inputs["Strength"].default_value = 0.9
sol = bpy.data.lights.new("Sol", "SUN")
sol.energy = 2.2
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
