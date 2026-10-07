# InventorIA

**Qué hace:** Claude maneja Autodesk Inventor por script para diseñar piezas y ensambles paramétricos (grippers, rejas, estructuras), sacar planos A4, DXF de corte y listas de materiales, y renderizar animaciones de celdas robotizadas KUKA cuadro a cuadro.
**Para quién:** Ingeniería y diseño mecánico.
**Estado:** ✅ En uso
**Responsable:** <nombre>
**Versión:** 1.0 · 7 de octubre de 2026

## Requisitos

- Windows con **Autodesk Inventor 2025** (licencia activa)
- **Python 3.13** real (no el alias de la Microsoft Store)
- `.venv` con `pywin32` (312); opcionales `mcp`, `openpyxl`
- `ffmpeg` del lado de la IA para armar los videos
- Carpeta de trabajo `Documents\InventorIA\` con `_pedidos\`, `Generados\`, `Analisis\`, `Comerciales\`

## Cómo arrancar

1. Instalar el complemento en `Documents\InventorIA\inventor-assistant-portable\` y correr `scripts\setup.ps1`.
2. Si Claude trabaja desde la nube, abrir `scripts\vigilante.bat` en la PC (ejecuta los pedidos que deja la IA).
3. Pasarle a Claude `GUIA.md` completa y completar el texto de arranque de la **sección 0**.
4. Antes de cualquier trabajo caro: relevamiento + una imagen de prueba aprobada.

## Entregables

- Piezas de chapa y ensambles con restricciones (`Generados\<PROYECTO>\`)
- Planos A4 de chapas y conjunto (`.dwg` + `.pdf`) y DXF de corte 1:1
- BOM en `.xlsx` con fórmulas (piezas, corte de caños, herrajes, bulonería)
- Videos MP4 Full HD (horizontal o vertical) de la celda funcionando

## Contenido de la carpeta

| Archivo | Para qué |
|---|---|
| `GUIA.md` | Guía maestra: reglas, método, listas de control, errores típicos |
| `scripts/vigilante.py` / `.bat` | Ejecutor de pedidos en la PC |
| `scripts/` | Un script por tarea (relevar, construir gripper, planos, simular) |
| `server/inventor_mcp.py` | Funciones base de Inventor por COM |
| `server/gripper_design.py`, `gripper_calc.py` | Diseño paramétrico y cálculo de apriete |
| `ejemplos/` | Casos de referencia anonimizados (gripper KR30, celda de palletizado) |

## Reglas de oro (resumen)

1. Nunca tocar originales: se trabaja sobre copias.
2. Editar, no regenerar.
3. Todo por script con argumentos y `resultado.json`.
4. Medir antes de suponer; mirar la imagen antes de decir que funciona.
5. Probar en chico (1 imagen → 1 cuadro → tramo) antes del render completo.

## Limitaciones y avisos

- La API de Inventor 2025 no permite crear presentaciones (`.ipn`): las animaciones se hacen cuadro a cuadro.
- No usar `AnalyzeInterference` durante una simulación (cierra Inventor).
- Los cálculos son preliminares; los aprueba un ingeniero antes de fabricar.

## Historial

| Versión | Fecha | Cambio |
|---|---|---|
| 1.0 | 2026-10-07 | Primera versión de la guía maestra |
