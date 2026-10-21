# CLAUDE.md — Instrucciones para la IA (léelas antes de hacer cualquier cosa)

Trabajás para DEFYMOTION (Argentina, robótica y paletizado) operando **Autodesk Inventor 2025** en la PC del usuario.
- Idioma: español rioplatense.
- Unidades: mm.
- Planos: A4, todas las hojas en un mismo archivo de dibujo.

**Antes de la primera tarea**, leé en este orden:
1. `docs/Guia_IA_Inventor.md`: el método completo, con errores conocidos y sus soluciones.
2. `docs/SIMULACIONES.md`, si la tarea es una animación o simulación.
3. `docs/InventorIA_contexto.md`: qué se hizo en cada proyecto y qué quedó pendiente.

Estos archivos están en `Documents\InventorIA\` (o en `inventor-assistant-portable\docs\`) de la PC del usuario.
Traelos con las herramientas del puente si no están adjuntos.

## 1. Cómo llegás a Inventor

Hay dos situaciones posibles.

**A) Corrés en la nube y la PC del usuario está vinculada** (herramientas `device_*` del puente: listar, traer y
copiar archivos). Es el caso normal. No podés ejecutar nada en la PC directamente: lo hace el **vigilante**.
1. Escribí el script en tu espacio de trabajo. Debe tener argumentos, escribir un `resultado.json` y restituir todo
   en un `finally`.
2. Copialo a `~/Documents/InventorIA/inventor-assistant-portable/scripts/<script>.py`.
3. **Verificá la copia**: traela de vuelta y compará con `diff <(tr -d '\r' < traído) local`. Si difiere, copiá
   desde una carpeta de staging nueva.
4. Después copiá el pedido `~/Documents/InventorIA/_pedidos/pNNN.json`:
   `{"script": "x.py", "args": [...], "timeout_s": 1800}`.
5. Esperá y traé `pNNN.resultado.json`. Tiene `codigo_salida`, `salida` (stdout, recortada a 60.000 caracteres) y
   `errores`. Si la salida es larga, traé el `resultado.json` que el propio script escribe en `Generados\...`.

Reglas del vigilante:
- **Ids nuevos siempre.** Mirá cuál fue el último en `_pedidos` (`*.hecho`) o en el contexto y seguí con el
  siguiente.
- **Todo `*.json` en `_pedidos` se ejecuta.** Los datos auxiliares van como `.txt`.
- Para **cancelar** un pedido ya copiado, sobrescribilo con
  `{"script":"buscar_archivos.py","args":["zz_no_existe_zz"],"timeout_s":60}`.
- Si el usuario **cierra el vigilante en medio de un pedido**, ese `.json` vuelve a correr al reabrirlo.
  Neutralizalo antes.
- `vigilante.activo` late **entre** pedidos. Durante un render largo no cambia: no es una caída.
- **Límites del puente:** 400 MB por archivo y 500 MB por llamada. Los cuadros van en zips de menos de 350 MB
  (`partir_zip.py` / `partir_zip_existente.py`).
- Si no responde, casi siempre hay un **diálogo abierto en Inventor**: pedile al usuario que lo cierre.

**B) Corrés en la propia PC** (Claude Code con terminal en Windows): ejecutá directamente
`.venv\Scripts\python.exe scripts\<script>.py` desde `Documents\InventorIA\inventor-assistant-portable`.
No hace falta el vigilante.

## 2. Reglas de trabajo (obligatorias)

1. **Nunca modificar originales.**
   - Leer en sólo lectura y trabajar en copias (`SaveAs`, primero los subensambles y después el general) o en
     `Documents\InventorIA\Generados\<PROYECTO>\`.
   - Las pruebas que mueven restricciones, sólo en copias.
2. **Editar, no regenerar:** planos → retocar la hoja; piezas → `--reusar-piezas` / `--rehacer`; videos →
   re-renderizar el tramo y empalmarlo.
3. `app.SilentOperation = True` mientras corre un script (sin diálogos) y volver a `False` al final.
4. Antes de construir, **relevá** el modelo (cajas, matrices, restricciones, subensambles **flexibles**, topes)
   y guardalo en JSON en `Analisis\`.
5. Después de construir, **verificá y mirá**: interferencias (sólo en ensambles estáticos), masa, envolvente,
   imagen. No digas que algo funciona sin haberlo visto.
6. **Primero en chico:** fotos de prueba (`--prueba-planos`, `--test-agarre`), después `--max-cuadros 1`, después el
   render completo. Preguntá antes de lo caro si hay dudas del mecanismo; mostrale una foto al usuario.
7. **No usar `AnalyzeInterference` en una escena animada:** cerró Inventor. Usá `RangeBox` y fotos de cerca.
8. **No cerrar documentos del usuario** ni usar `Documents.CloseAll`: puede tener trabajo sin guardar.
   Cerrá sólo los de tus carpetas.
9. Al terminar cada tema importante, **actualizá `InventorIA_contexto.md`** con qué se hizo, dónde quedó, qué
   falta y el último pedido. Copiá el archivo también a `inventor-assistant-portable\docs\`.

## 3. Convenciones DEFYMOTION

- **Grippers de apriete lateral:**
  - una pala fija (**sin hexágonos**) y una pala móvil por caja;
  - cilindros Festo y guías HIWIN **por dentro** del chasis;
  - chasis en C (alas arriba) y brida en U invertida;
  - todo en chapa de acero plegada con soldadura mínima;
  - logo DEFYMOTION calado en las alas, cuando entra.
- **Cálculo:** `F = m·(g + a)·FS / (2·μ)` con 8 bar, μ = 0,4, FS = 2, a = 5 m/s².
  - Verificar la carga del robot con gripper + producto.
- **Planos:** A4, un solo dibujo y un solo PDF, escala normalizada máxima, sin cotas de radio de plegado y DXF 1:1
  por chapa.
- **Videos:**
  - 1920×1080 horizontal (o 1080×1920 vertical si lo piden);
  - "Luz suave", las 3 sombras, sin plano de suelo, cámara ortográfica y planos de trabajo ocultos;
  - cámara re-aplicada en cada cuadro y renders de calentamiento.

## 4. Al empezar una tarea con el usuario

- Una frase con lo que vas a hacer y cuánto tarda.
- Si faltan datos que cambian el resultado (medidas, peso, patrón, robot, cómo agarra), preguntá con opciones.
  La lista de preguntas típicas está en la guía, §0.
- Al entregar: qué salió, dónde quedó en la PC y qué falta, en pocas líneas.
