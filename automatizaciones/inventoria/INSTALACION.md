# Instalación en una PC nueva (paso a paso)

Tiempo estimado: unos 30 minutos, sin contar la instalación de Inventor.

## 1. Requisitos

| Qué | Detalle |
|---|---|
| Windows 10/11 | Con una cuenta de usuario normal; no hace falta ejecutar nada como administrador |
| Autodesk Inventor 2025 | Con licencia activa. Probado en 2025.4 |
| Python 3.10 o superior (recomendado 3.13) | `winget install -e --id Python.Python.3.13`. **No usar** el alias de la Microsoft Store |
| App de escritorio de Claude | Con la cuenta de la empresa. Es la que vincula la PC con Claude |
| Espacio en disco | Unos 5 GB libres para cuadros de video (1300 cuadros Full HD ≈ 1,2 GB) |

> Inventor y Python tienen que correr en **la misma sesión de Windows y con el mismo nivel de permisos**. No
> abrir Inventor "como administrador", porque si no la conexión COM falla (`MK_E_UNAVAILABLE` / `0x80080005`).

## 2. Descargar el repositorio

- Descargarlo (clonar `https://github.com/Defymotion/IA` o bajar el ZIP desde **Code → Download ZIP**) en
  cualquier carpeta, por ejemplo `Descargas\IA`.
- Entrar a la carpeta **`automatizaciones\inventoria\`**: ahí están `instalar.bat` y todo lo de InventorIA.
- No hace falta ponerlo en un lugar especial: el instalador lo copia a su lugar.

## 3. Ejecutar el instalador

Doble clic en **`instalar.bat`** (o `powershell -ExecutionPolicy Bypass -File .\instalar.ps1`). Hace lo siguiente:

1. Crea `Documents\InventorIA\` con `_pedidos`, `Generados`, `Analisis`, `Comerciales`, `Plantillas` y `Calculos`.
2. Copia el complemento a `Documents\InventorIA\inventor-assistant-portable\`, que es donde lo buscan los scripts.
3. Copia la documentación a `Documents\InventorIA\` (sin pisar una memoria local ya existente) y a
   `inventor-assistant-portable\docs\`.
4. Copia `CLAUDE.md` a `Documents\InventorIA\`.
5. Crea el entorno Python `.venv` e instala `pywin32`, `mcp` y `pillow`.
6. Crea en el escritorio el acceso directo **"Vigilante InventorIA"**.
7. Corre la verificación (punto 4).

## 4. Verificar

1. Abrir **Inventor** y esperar a que termine de cargar.
2. Ejecutar `Documents\InventorIA\inventor-assistant-portable\scripts\verificar_instalacion.bat`.
3. Todo tiene que salir en `[OK ]`. Lo que salga `[FALTA]` trae al lado cómo resolverlo.

El resultado queda también en `_pedidos\verificacion.txt`, para que la IA lo lea.

## 5. Conectar Claude con la PC

1. Abrir la **app de escritorio de Claude** en esta PC, con la cuenta de la empresa.
2. Empezar una **tarea nueva desde la app de escritorio, con esta computadora seleccionada**.
   - Si es una conversación que ya existía, abrirla en la app de escritorio y elegir **"Vincular a esta
     computadora"**.
   - Así Claude puede leer y copiar archivos en las carpetas que autorices.
3. Cuando Claude pida acceso a una carpeta, autorizar **`Documents\InventorIA`**. Si un proyecto está en otra
   carpeta, autorizarla también; para los originales alcanza con lectura.
4. Abrir **Inventor** y el **Vigilante InventorIA**: dejar la ventana negra abierta mientras se trabaja. La app de
   Claude también tiene que quedar abierta (puede estar minimizada).

> Mientras la IA renderiza un video, podés seguir usando la PC, pero **no toques el Inventor** ni cierres el
> vigilante. Si lo cerrás en medio de un trabajo, al reabrirlo ese trabajo vuelve a empezar: avisale a la IA
> antes de reabrirlo.

## 6. Primer mensaje a Claude

Pegar esto en la tarea vinculada:

```text
Vas a trabajar con Autodesk Inventor 2025 en esta PC con el método InventorIA.
Primero leé Documents\InventorIA\CLAUDE.md y después docs\Guia_IA_Inventor.md (y docs\SIMULACIONES.md si vamos a simular).
El vigilante está abierto. Leé Documents\InventorIA\_pedidos\verificacion.txt y hacé una prueba de conexión
(pedido p001 con test_create_box.py). Después te cuento el proyecto.
Proyecto: <nombre>  ·  Originales (no tocar): <ruta>  ·  Entregables: <video / gripper / planos ...>
```

Si la IA no ve archivos de la PC, la tarea no quedó vinculada: repetir el punto 5.

## 7. Modelos CAD necesarios

El repositorio trae sólo código y documentación. Los modelos se copian desde el servidor de proyectos de DEFYMOTION
a `Documents\InventorIA\` respetando estas carpetas:

| Para qué | Carpeta esperada | Notas |
|---|---|---|
| Robot KUKA KR 140 R3200-2 PA (simulaciones de celdas) | `Documents\InventorIA\12_ADECO2\KUKA\KUKA-KR_140_R3200_2_PA-ASM.iam` (+ eslabones V01…V05) | Cinemática en `scripts\celda_kin.py`. Para otro robot, la IA releva sus ejes (ver la guía §12.3) |
| Comerciales reutilizados (ADN-25/32, HIWIN, tuercas) | `Documents\InventorIA\Comerciales\` y `12_ADECO2\...` | Los usa `construir_gripper.py` |
| Layout del cliente a simular | Una **copia** en `Documents\InventorIA\<Proyecto>\` | Nunca trabajar sobre el original |
| Plantillas de dibujo de la empresa | La que use Inventor por defecto (`.dwg`) | Para planos A4 |

Si un modelo no está, la IA tiene `buscar_archivos.py` para encontrarlo en la PC.

## 8. Uso diario (resumen)

1. Abrir Inventor y después el Vigilante InventorIA.
2. Abrir la app de Claude, en una tarea vinculada a la PC.
3. Pedir el trabajo, con datos concretos: medidas, pesos, patrón, robot, qué se quiere ver en el video.
4. La IA primero releva y muestra fotos de prueba; después construye o renderiza y entrega los archivos
   (MP4, PDF, DXF, XLSX). También quedan en `Documents\InventorIA\Generados\<proyecto>\`.

## 9. Problemas comunes

| Síntoma | Solución |
|---|---|
| `[FALTA] Inventor abierto y accesible por COM` | Abrir Inventor normal (no como administrador) y en la misma sesión de Windows. Esperar a que cargue |
| El vigilante no ejecuta nada | ¿Está abierta la ventana "Vigilante InventorIA"? ¿Hay un diálogo abierto en Inventor? Cerrarlo |
| La IA dice que no ve la PC | Abrir la app de escritorio de Claude y revisar que la tarea esté vinculada a esta computadora |
| Se cerró Inventor en medio de un trabajo | Reabrir Inventor (sin abrir ensambles) y avisarle a la IA |
| Un trabajo arrancó "solo" dos veces | Se cerró el vigilante a mitad de un pedido. La IA debe neutralizarlo (ver `CLAUDE.md`) |
| Python no encontrado | `winget install -e --id Python.Python.3.13`, cerrar y volver a abrir la consola y repetir `instalar.bat` |
