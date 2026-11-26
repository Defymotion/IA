# -*- coding: utf-8 -*-
# Script para el motor Python de EcoStruxure Machine Expert / CODESYS (BETA, sin probar en planta).
# Compatible con Python 2.7 (IronPython) y 3.x. Lo lanza el adaptador schneider_me.ps1.
# Variables globales del motor: projects, system (las inyecta Machine Expert).
from __future__ import print_function
import io, json, os, traceback

P = json.load(io.open(os.environ['PLC_BRIDGE_PARAMS'], encoding='utf-8-sig'))
R = {'ok': False, 'msgs': []}

def log(m):
    R['msgs'].append(m)
    try: print(m)
    except Exception: pass

def guardar():
    with io.open(P['resultado'], 'w', encoding='utf-8') as f:
        s = json.dumps(R, ensure_ascii=False, indent=2)
        f.write(s if isinstance(s, type(u'')) else s.decode('utf-8'))

try:
    if projects.primary:
        projects.primary.close()
    proj = projects.open(P['proyecto'])
    act = P['action']
    if act == 'export':
        out = os.path.join(P['salida_dir'], 'export')
        if not os.path.isdir(out): os.makedirs(out)
        # 1) todo el proyecto en un solo PLCopenXML
        proj.export_xml(proj.get_children(False), os.path.join(out, 'proyecto_plcopenxml.xml'), recursive=True)
        # 2) un archivo por POU / GVL / DUT para poder leerlos sueltos
        obj_dir = os.path.join(out, 'objetos')
        if not os.path.isdir(obj_dir): os.makedirs(obj_dir)
        n = 0
        for o in proj.get_children(True):
            try:
                if o.is_folder: continue
                nom = o.get_name()
                if not nom: continue
                seguro = ''.join(c if c.isalnum() or c in '_-.' else '_' for c in nom)
                proj.export_xml([o], os.path.join(obj_dir, seguro + '.xml'), recursive=True)
                n += 1
            except Exception as e:
                log('no exportado: %s (%s)' % (getattr(o, 'get_name', lambda: '?')(), e))
        log('Exportados %d objetos sueltos' % n)
    elif act == 'import':
        for a in P['archivos']:
            f = os.path.join(P['job_dir'], a)
            proj.import_xml(f)   # importa en la raiz del proyecto; si el objeto existe, CODESYS pregunta/reemplaza segun version
            log('importado: ' + a)
        if P.get('guardar'): proj.save(); log('proyecto guardado')
    elif act == 'compile':
        app = proj.active_application
        app.build()
        log('build ejecutado (ver mensajes en Machine Expert)')
    else:
        raise Exception('accion no soportada: ' + act)
    R['ok'] = True
except Exception as e:
    log('ERROR: %s' % e); log(traceback.format_exc())
finally:
    guardar()
    try:
        if projects.primary: projects.primary.close()
    except Exception: pass
