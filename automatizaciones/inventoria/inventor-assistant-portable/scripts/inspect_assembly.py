"""Analiza un ensamble de Inventor sin modificarlo.

Uso (desde la carpeta del complemento):
    .\\.venv\\Scripts\\python.exe .\\scripts\\inspect_assembly.py              -> ensamble activo en Inventor
    .\\.venv\\Scripts\\python.exe .\\scripts\\inspect_assembly.py "C:\\...\\X.iam"
Resultado: Documents\\InventorIA\\Analisis\\<nombre>\\ (estructura.json, resumen.md, capturas .png)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
import inventor_mcp as inv  # noqa: E402

if len(sys.argv) > 1:
    target = sys.argv[1]
else:
    app = inv._inventor(start_if_needed=False)
    try:
        doc = app.ActiveDocument
        target = doc.FullFileName
    except Exception:
        sys.exit("No hay documento activo en Inventor")
    if doc.DocumentType != inv.K_ASSEMBLY_DOCUMENT:
        sys.exit(f"El documento activo no es un ensamble: {target}")
    if not target:
        sys.exit("El ensamble activo no está guardado todavía")
    print("Analizando ensamble activo:", target)
print(inv.inventor_inspect_assembly(target))
