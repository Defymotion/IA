"""(Dentro de Blender) Imprime estado de objetos en cuadros dados. Uso: ... -P bl_debug.py -- <nombres,coma> <cuadros,coma>"""
import json
import sys

import bpy

argv = sys.argv[sys.argv.index("--") + 1:]
nombres, cuadros = argv[0].split(","), [int(v) for v in argv[1].split(",")]
sc = bpy.context.scene
res = {}
for f in cuadros:
    sc.frame_set(f)
    for n in nombres:
        o = bpy.data.objects.get(n)
        if o is None:
            res[f"{f}:{n}"] = "no existe"
            continue
        hs = list(o.children)
        res[f"{f}:{n}"] = {"pos": [round(v, 3) for v in o.matrix_world.translation], "escala": [round(v, 2) for v in o.scale],
                           "hide_render": o.hide_render, "hijos": len(hs),
                           "hijo0": ([round(v, 3) for v in hs[0].matrix_world.translation], hs[0].hide_render) if hs else None,
                           "acciones": bool(o.animation_data and o.animation_data.action)}
print("RESULTADO " + json.dumps(res, ensure_ascii=False))
