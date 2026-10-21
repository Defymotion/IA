---
name: inventor-design
description: Diseñar piezas o automatizar Autodesk Inventor en Windows mediante las herramientas locales del complemento. Usar para comprobar Inventor, crear una caja paramétrica, abrir modelos o exportar documentos CAD.
---

# Diseño con Autodesk Inventor

Usa las herramientas MCP `inventor_*` de este complemento para operar Inventor en el equipo local.

1. Llama primero a `inventor_status` para comprobar instalación, versión y documento activo.
2. Antes de escribir un archivo, confirma dimensiones, unidades, formato y ruta si el pedido no las especifica.
3. Para una pieza rectangular simple, usa `inventor_create_box`. Las dimensiones se expresan en milímetros.
4. Para trabajar con un archivo existente, usa `inventor_open_document`.
5. Para entregar otro formato, usa `inventor_export_active_document` y una extensión compatible con Inventor.
6. Informa la ruta absoluta de cada archivo creado.

No sobrescribas archivos salvo petición explícita. No cierres documentos ni Inventor automáticamente. Este MVP crea cajas paramétricas; para geometría más compleja, amplía el servidor con una herramienta específica.
