"""Diagnóstico: por qué falla Occurrences.Add de un archivo. Lista documentos cargados con nombres parecidos, abre el
archivo invisible, informa referencias faltantes y prueba insertarlo en un ensamble temporal que no se guarda.
Uso: python diag_insertar.py <archivo.iam> "filtro1;filtro2"
"""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
import inventor_mcp as inv  # noqa: E402

S = inv._safe
ruta = Path(sys.argv[1])
filtros = [s.lower() for s in sys.argv[2].split(";") if s]
app = inv._inventor(start_if_needed=False)
app.SilentOperation = True
res = {"cargados": [], "faltantes": [], "add": None}
try:
    for d in inv._items(app.Documents):
        f = str(S(lambda: d.FullFileName, ""))
        if any(k in f.lower() for k in filtros):
            res["cargados"].append(f)
    res["n_documentos"] = app.Documents.Count
    try:
        doc = app.Documents.Open(str(ruta), False)
        for fd in inv._items(doc.File.AllReferencedFiles):
            pass
        for d in inv._items(doc.AllReferencedDocuments):
            pass
        for fd in inv._items(doc.ReferencedFileDescriptors):
            if S(lambda: fd.ReferenceMissing, False):
                res["faltantes"].append(S(lambda: fd.FullFileName))
        res["abre"] = True
        nombres = {}
        for d in inv._items(app.Documents):
            f = str(S(lambda: d.FullFileName, ""))
            nombres.setdefault(Path(f).name.lower(), set()).add(f)
        propios = [str(S(lambda: d.FullFileName, "")) for d in inv._items(doc.AllReferencedDocuments)]
        res["conflictos"] = {Path(f).name: sorted(nombres[Path(f).name.lower()]) for f in propios
                             if len(nombres.get(Path(f).name.lower(), ())) > 1}
        res["n_refs"] = len(propios)
    except Exception as e:  # noqa: BLE001
        res["abre"] = repr(e)
    tmp = app.Documents.Add(inv.K_ASSEMBLY_DOCUMENT, app.FileManager.GetTemplateFile(inv.K_ASSEMBLY_DOCUMENT), False)
    res["add"] = {}
    m = app.TransientGeometry.CreateMatrix()
    res["model_states"] = S(lambda: [x.Name for x in inv._items(doc.ComponentDefinition.ModelStates)])
    res["full_doc_name"] = S(lambda: doc.FullDocumentName)
    res["es_iassembly"] = S(lambda: doc.ComponentDefinition.IsiAssemblyFactory)
    res["es_substituto"] = S(lambda: doc.ComponentDefinition.IsModelStateFactory)
    for nombre, fn in (("ruta", lambda: tmp.ComponentDefinition.Occurrences.Add(str(ruta), m)),
                       ("full_doc_name", lambda: tmp.ComponentDefinition.Occurrences.Add(doc.FullDocumentName, m)),
                       ("por_definicion", lambda: tmp.ComponentDefinition.Occurrences.AddByComponentDefinition(doc.ComponentDefinition, m)),
                       ("otra_pieza", lambda: tmp.ComponentDefinition.Occurrences.Add(sys.argv[3], m) if len(sys.argv) > 3 else None)):
        try:
            fn()
            res["add"][nombre] = "OK"
        except Exception as e:  # noqa: BLE001
            res["add"][nombre] = repr(e)
    tmp.Close(True)
    res["proyecto"] = S(lambda: app.DesignProjectManager.ActiveDesignProject.FullFileName)
    res["workspace"] = S(lambda: app.DesignProjectManager.ActiveDesignProject.WorkspacePath)
    res["libs"] = S(lambda: [p.Path for p in inv._items(app.DesignProjectManager.ActiveDesignProject.LibraryPaths)])
finally:
    S(lambda: setattr(app, "SilentOperation", False))
print(json.dumps(res, ensure_ascii=False, indent=1))
