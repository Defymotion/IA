# Inventor Assistant

Complemento local de Codex para controlar Autodesk Inventor mediante su API COM en Windows.

## Requisitos

- Windows con Autodesk Inventor instalado.
- Python 3.10 o posterior en `PATH`.
- Dependencias de `requirements.txt`.

Ejecuta `powershell -ExecutionPolicy Bypass -File scripts/setup.ps1` una vez para crear el entorno local e instalar las dependencias.

Incluye herramientas para comprobar la conexión, crear una pieza rectangular, abrir un documento y exportar el documento activo. El servidor usa MCP por `stdio`; sus diagnósticos van a `stderr`.
