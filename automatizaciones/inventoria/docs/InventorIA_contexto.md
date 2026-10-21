# InventorIA — memoria y contexto de trabajo

Fecha de preparación: 29 de septiembre de 2026 · última actualización: 5 de octubre de 2026  
Método de trabajo detallado (para otra IA): ver `Receta_IA_Inventor.md` en esta misma carpeta.  
Objetivo: poder retomar este proyecto en la PC del trabajo sin depender del historial de la conversación.

## 1. Objetivo general

Implementar una asistencia de IA integrada con Autodesk Inventor para automatizar tareas de diseño mecánico y preparación de documentación de fabricación en una empresa de robótica.

Hay dos líneas principales:

1. Automatización de planos y archivos para fabricación.
2. Diseño paramétrico y cálculo de grippers para manipulación de cajas.

La prioridad recomendada es comenzar por la automatización de entregables de fabricación, porque tiene menor riesgo técnico y permite obtener valor rápidamente. Luego se puede avanzar hacia el configurador de grippers.

## 2. Prueba realizada

Se comprobó la presencia de Autodesk Inventor 2025 y su registro COM.

Se creó una pieza rectangular de prueba:

- Ancho: 100 mm.
- Profundidad: 60 mm.
- Altura/extrusión: 20 mm.
- Formato: Autodesk Inventor `.ipt`.
- Nombre: `pieza_rectangular_100x60x20.ipt`.
- Dimensiones verificadas leyendo la caja envolvente del sólido: 100 × 60 × 20 mm.

Preferencia para los próximos modelos:

- Agregar cotas paramétricas visibles en el boceto.
- Restringir completamente el boceto.
- Usar nombres claros para bocetos, operaciones y parámetros.
- Exponer también la cota de extrusión como parámetro editable.

La pieza de prueba actual tiene las medidas geométricas correctas, pero no fue creada con cotas visibles en el boceto. Esto debe corregirse en la próxima versión del generador.

## 3. Complemento Inventor Assistant

Se creó/instaló un complemento local llamado `inventor-assistant`, versión 0.1.0.

Su arquitectura es:

- Un servidor MCP local escrito en Python.
- Automatización de Inventor mediante COM y `pywin32`.
- Una habilidad de Codex con instrucciones para usar las herramientas.

Herramientas previstas:

- `inventor_status`: comprobar instalación, versión y documento activo.
- `inventor_create_box`: crear una pieza rectangular paramétrica.
- `inventor_open_document`: abrir archivos compatibles.
- `inventor_export_active_document`: exportar el documento activo.

El ZIP adjunto contiene el código fuente, manifiestos, habilidad, icono y script de instalación. No incluye `.venv`; debe reconstruirse en cada PC mediante `scripts/setup.ps1`.

## 4. Problemas técnicos detectados

### 4.1 Herramientas MCP no visibles

El complemento aparecía instalado y su habilidad estaba disponible, pero los comandos `inventor_*` no se publicaban en la conversación. Se reinstaló la copia local mediante el gestor de complementos de Codex para regenerar la caché.

Si ocurre nuevamente:

1. Verificar que `plugin.json`, `mcp.json`, `server/inventor_mcp.py` y `.venv/Scripts/python.exe` existan.
2. Ejecutar el servidor manualmente y confirmar que inicia sin errores.
3. Reinstalar el complemento local.
4. Cerrar completamente Codex y volver a abrirlo.
5. Comprobar que las herramientas aparezcan en una conversación nueva.

### 4.2 Inventor instalado pero COM no disponible

Errores observados:

- `MK_E_UNAVAILABLE` al buscar una instancia activa.
- `0x80080005 — Error en la ejecución de servidor` al intentar iniciar Inventor desde COM.

La solución que funcionó fue:

1. Iniciar `Inventor.exe /Automation` fuera del aislamiento de Codex.
2. Ejecutar el cliente COM con el mismo nivel de permisos que Inventor.
3. Conectarse a la instancia mediante la Running Object Table.

Conclusión: Inventor y el proceso que llama a COM deben ejecutarse en la misma sesión de Windows y con niveles de integridad compatibles.

### 4.3 Caché de tipos de pywin32 defectuosa

La llamada habitual de `win32com.client.GetActiveObject` produjo errores en los wrappers generados. También se recibió un documento genérico sin la propiedad `ComponentDefinition`.

El método que funcionó fue evitar `gen_py` y obtener `IDispatch` dinámicamente:

```python
import pythoncom
from win32com.client.dynamic import Dispatch

pythoncom.CoInitialize()
unknown = pythoncom.GetActiveObject("Inventor.Application")
app = Dispatch(unknown.QueryInterface(pythoncom.IID_IDispatch))
```

Para Inventor 2025 se usaron estos valores de enumeración:

- `kPartDocumentObject = 12290`
- `kJoinOperation = 20481`
- `kPositiveExtentDirection = 20993`

Conviene incorporar este despacho dinámico en la próxima versión del servidor y agregar una prueba automática de creación de pieza.

## 5. Próximo cambio necesario en el generador

Modificar `inventor_create_box` para que el boceto no dependa solamente de coordenadas fijas.

Flujo deseado:

1. Crear un rectángulo centrado en el origen.
2. Aplicar restricciones horizontal, vertical, coincidente y simetría cuando corresponda.
3. Crear una cota horizontal para el ancho.
4. Crear una cota vertical para la profundidad.
5. Confirmar que el boceto quede totalmente restringido.
6. Crear la extrusión con una cota/parámetro nombrado.
7. Nombrar parámetros, por ejemplo `Ancho`, `Profundidad` y `Altura`.
8. Guardar y verificar dimensiones mediante `RangeBox`.

## 6. Primera etapa recomendada: documentación de fabricación

Objetivo del piloto:

> Dado un conjunto terminado en Inventor, generar automáticamente planos, PDF, DXF, STEP, BOM y lista de corte siguiendo el estándar de la empresa.

Entradas necesarias:

- Plantillas `.idw` o `.dwg`.
- Cajetín oficial.
- Convención de nombres y códigos.
- Reglas de revisión.
- Materiales y espesores disponibles.
- Tabla de plegado, radios y factor K.
- Tolerancias generales y específicas.
- Capas y unidades exigidas para los DXF.
- Reglas del software de nesting/corte láser.
- Estándar para perfiles, largos, ingletes y agujeros.
- Ejemplos de entregas terminadas consideradas correctas.

Salidas esperadas:

```text
Proyecto/
├── Modelos/
│   ├── Conjunto.iam
│   └── Piezas.ipt
├── Planos/
│   ├── PDF/
│   └── DWG/
├── Corte_laser/
│   ├── Chapa_3mm/
│   └── Chapa_6mm/
├── Perfiles/
│   └── Lista_de_corte.xlsx
├── STEP/
└── BOM.xlsx
```

Controles automáticos deseados:

- Material y espesor definidos.
- Piezas de chapa con desarrollo válido.
- Bocetos totalmente restringidos.
- Cotas y tolerancias necesarias.
- Geometría DXF cerrada, sin duplicados y en escala 1:1.
- Nombres y revisiones correctos.
- Correspondencia entre BOM, planos y archivos de corte.
- Detección de interferencias y archivos faltantes.

## 7. Segunda etapa: configurador de grippers para cajas

La entrada mínima propuesta es:

- Largo, ancho, alto y peso de una caja.
- Cantidad de cajas a tomar.
- Distribución en filas, columnas y niveles.
- Orientación de cada caja.
- Método de toma: lateral, inferior, superior, vacío o apriete.
- Forma en que el gripper toma individualmente y acumula las cajas.
- Aceleraciones del robot y tiempo de ciclo.
- Presión neumática disponible.
- Coeficiente de fricción estimado.
- Carrera necesaria.
- Espacio máximo disponible.
- Robot utilizado y carga admisible.
- Factor de seguridad requerido.

Cálculos previstos:

- Masa total y centro de gravedad.
- Fuerzas por gravedad y aceleración.
- Momentos sobre la muñeca del robot.
- Fuerza mínima de apriete para evitar deslizamiento.
- Fuerza real de cilindros según presión, diámetro y eficiencia.
- Diámetro y carrera de cilindros.
- Consumo de aire y velocidad.
- Selección de válvulas, tuberías, guías y sensores.
- Flexión y tensiones de perfiles y chapas.
- Envolvente, interferencias y accesibilidad.
- Factores de seguridad.

Resultados deseados:

- Informe de cálculo trazable.
- Selección de componentes comerciales.
- Ensamble paramétrico del gripper.
- Planos y archivos de fabricación.
- BOM y lista de corte.
- Archivos DXF y STEP.
- Esquema neumático preliminar.
- Lista explícita de decisiones que requieren aprobación del ingeniero.

Los cálculos de retención de carga, estructura, neumática y capacidad del robot deben ser revisados y aprobados por un profesional responsable antes de fabricar o poner el equipo en servicio.

## 8. Plan de implementación recomendado

### Fase A — recopilar estándares

Seleccionar un proyecto real ya terminado y reunir:

- Modelos iniciales y finales.
- Planos finales.
- DXF/STEP enviados a producción.
- BOM y listas de corte.
- Plantillas y bibliotecas.
- Correcciones realizadas durante fabricación.

### Fase B — automatizar entregables

Implementar herramientas pequeñas y verificables:

1. Inspección de modelos.
2. Generación de desarrollos.
3. Exportación DXF.
4. Creación de planos.
5. Exportación PDF/DWG/STEP.
6. Generación de BOM y listas de corte.
7. Validador final del paquete.

### Fase C — piloto de gripper

Reunir entre cinco y diez grippers históricos y transformar las decisiones de diseño en reglas explícitas. Empezar con una única familia de cajas y un único método de toma.

### Fase D — validación

Comparar automáticamente la salida generada con una entrega aprobada. Ningún archivo debe liberarse directamente a fabricación hasta superar la revisión técnica definida por la empresa.

## 9. Checklist para retomar en la PC del trabajo

1. Instalar o comprobar Autodesk Inventor.
2. Abrir Inventor normalmente y comprobar licencia.
3. Extraer `inventor-assistant-portable.zip`.
4. Ejecutar `scripts/setup.ps1` para construir `.venv` e instalar dependencias.
5. Instalar el complemento local en Codex y reiniciar Codex.
6. Comprobar `inventor_status`.
7. Actualizar el servidor para usar `IDispatch` dinámico.
8. Crear una pieza de prueba con cotas visibles y boceto totalmente restringido.
9. Probar apertura, guardado y exportación.
10. Seleccionar un proyecto real terminado para iniciar el piloto de planos y corte.

## 10. Archivos adjuntos a esta memoria

- `InventorIA_contexto.md`: este documento.
- `pieza_rectangular_100x60x20.ipt`: pieza de prueba verificada.
- `inventor-assistant-portable.zip`: código fuente portable del complemento, sin `.venv`.


## 11. Avance del 30 de septiembre de 2026 — complemento v0.2.0

Probado en la PC `Equipo` con Inventor 2025.4 y Python 3.13 (pywin32 312, mcp 1.30).

Resuelto (puntos 7 y 8 del checklist):

- Conexión por `IDispatch` dinámico; constantes como valores fijos. Ya no se usa `gen_py` ni `win32com.client.constants`.
- Si Inventor no está abierto, el servidor lanza `Inventor.exe /Automation` (ruta tomada del registro COM) y lo busca en la ROT.
- `inventor_create_box` crea: boceto `Base rectangular` centrado en el origen (diagonal de construcción con punto medio en el origen), cotas visibles `Ancho` y `Profundidad`, extrusión `Extrusión base` con parámetro `Altura`. Verificado: 100 × 60 × 20 mm por `RangeBox` y boceto **totalmente restringido**.
- `scripts/test_create_box.py`: prueba automática (medidas, parámetros y estado de restricción).
- `scripts/setup.ps1`: detecta Python real (evita el alias de Microsoft Store) y avisa si falta.

Valores de enumeración confirmados en la documentación de la API:

- `kHorizontalDim = 19201`, `kVerticalDim = 19202`, `kAlignedDim = 19203`.
- `kFullyConstrainedConstraintStatus = 51713`, `kUnderConstrained = 51714`, `kOverConstrained = 51715`, `kUnknown = 51716`.

Lecciones:

- `DimensionConstraints.AddTwoLineDistance` no existe; usar `AddTwoPointDistance(p1, p2, orientación, punto_texto)`.
- `sketch.ConstraintStatus` debe leerse después de `document.Update()`; antes devuelve un valor desactualizado (51714).
- `AddAsTwoPointRectangle` ya crea las restricciones horizontal, vertical y coincidente.
- En PowerShell, ejecutar desde la carpeta del complemento y con `.\` delante (`.\.venv\Scripts\python.exe`).

Pendiente:

- Registrar el complemento en Codex (o en Claude) y probar las herramientas desde el chat.
- Probar `inventor_open_document` e `inventor_export_active_document` (STEP, PDF, DXF).
- Iniciar la Fase A con un proyecto real terminado.

## 12. Grippers DEFYMOTION — cómo están conformados (30/09/2026)

Fuente: análisis de `DEFYMOTION\17_Newpack2\Gripper\Gripper.iam` con `scripts/inspect_assembly.py` (resultado en `Analisis\Gripper\`) y explicación del diseñador.

### Reglas de diseño de la empresa

- Toma por **apriete lateral**: pala fija + pala móvil.
- La pala móvil se mueve con **cilindros neumáticos** y corre sobre **guías lineales**.
- **Una pala móvil individual por caja** (cada caja con su pala, su cilindro y sus guías).
- Todo se construye en **chapa de acero plegada**. La soldadura es mínima; casi siempre es solo la **unión entre el cilindro y la pala móvil**.
- Entre proyectos cambia:
  - tipo de caja (medidas, peso);
  - cantidad de cajas por toma;
  - cantidad de tipos de caja distintos que toma el mismo gripper;
  - funciones: solo cajas, o cajas + pallet + cartón (hoja separadora).

### Ejemplo Newpack2 (cajas + pallet)

- Chasis: `Chapa principal` 3/16" (400 × 920 × 150). `Brida` 3/8" para la muñeca del robot.
- Apriete: `Pala fija` 3/16" (400 × 283) y `Pala movil` 3/16" (400 × 250) sobre 2 guías HIWIN HGW20 de 400 mm, con cilindro Festo DSBC-32-300 y `Ensamble empuje` (placa de empuje + 2 chapas de transmisión). Fuerza teórica a 6 bar: unos 480 N al avanzar y 415 N al retroceder.
- Pallet: 2 `Ensamble eje` con 4 `Garra` 1/4" sobre ejes en 4 rodamientos UCFL204. Cada eje lo gira un Festo DSBC-50-100 basculante con leva.
- Sensores inductivos Pepperl+Fuchs NBB4 en soportes de chapa de 2 mm. 4 `Cilindro tope`.
- Datos a corregir en los modelos:
  - La mayoría de las piezas tienen material "Genérico", así que la masa y el centro de masa no son confiables (la chapa principal figura con 2,9 kg; en acero serían unos 22 kg).
  - El ensamble incluye el pallet (32 kg).
  - No hay parámetros de usuario: solo "Grosor".

### Modelo de generador propuesto (a validar)

Módulos:

1. Chasis y brida.
2. Pala fija por fila.
3. Módulo pala móvil: pala, guías, cilindro y unión soldada. Uno por caja.
4. Garras de pallet (opcional).
5. Toma de cartón (opcional; método a definir).
6. Sensores y válvulas.

Entradas:

- Cajas: tipos (L × A × H, peso) y cantidad por toma.
- Disposición de las cajas.
- Funciones del gripper.
- Robot: modelo y carga admisible.
- Presión de aire disponible.
- Coeficiente de fricción.
- Factor de seguridad.

### Ejemplo ADECO2 (solo cajas, el caso tipo) — `12_ADECO2\Gripper\Gripper_ADECO2_V1.iam`

- 6 bandejas TBA200 (24 × 200 ml; 333 × 130 × 161 mm; unos 7 kg en el modelo) en **una fila**, con paso de 160–161 mm.
- `frame_principal_v1`: chapa 3/16" de 960 × 400 × 170, 21 kg. `Brida nueva` 3/8", 10,6 kg.
- `Pala fija`: una sola, corrida, chapa 3/16" (940 × 160 × 60), con `Goma pala fija` de 2,5 mm.
- `pala_movil_apriete.iam` ×6, **módulo estándar repetido**:
  - `Pala movil 2 cajas` 3/16" (140 × 132 × 70) con goma de 2,5 mm;
  - 2 guías HIWIN HGH15CA con riel de 150 mm;
  - 1 Festo ADN-25-80 (carrera de 80);
  - `part_empuje` 3/16" y 2 `empuja pala` de 1/8".
- Neumática Festo: isla VTUG de 6 válvulas (una por cilindro), reguladores de caudal GR-QS-6, 2 reguladores de presión MS4-LR y una VUVG.
- En la pala fija y la pala móvil hay cargas de análisis de tensiones (500 N y 5000 N con gravedad): validan las palas con Stress Analysis de Inventor.
- Masa del ensamble: 101,8 kg, incluidas las 7 bandejas (unos 48 kg). El gripper solo pesa unos 53 kg.

### Criterios de cálculo estándar (acordados el 30/09/2026)

- Presión de cálculo: **8 bar**.
- Siempre **una pala fija**; una pala móvil por caja, adaptada a la caja, sin morder la vecina.
- La elección se hace por el peso de la caja y la fricción de la goma de las palas: **2·μ·F ≥ m·(g + a)·FS**.
- Valores estándar:
  - **μ = 0,4** (goma / cartón);
  - **FS = 2**;
  - **a = 5 m/s²**;
  - margen de pala: 10 mm por lado;
  - apertura: 70 mm + 10 mm de tolerancia.
- Herramienta: `server/gripper_calc.py` y `scripts/calc_gripper.py`. Validada contra ADECO2: elige ADN-25-80, con pala de 141 mm, riel de 150 mm y chasis de 966 mm.

## 13. Avance del 30/09/2026 (tarde): planos de fabricación automáticos y trabajo remoto

### Cómo se trabaja ahora (Claude ejecuta sin PowerShell)

- **Vigilante:** doble clic en `inventor-assistant-portable\scripts\vigilante.bat` y dejar la ventana abierta.
  - Claude deja pedidos en `Documents\InventorIA\_pedidos\pNNN.json` con el formato `{"script": "...py", "args": [...]}`.
  - El vigilante los ejecuta con el `.venv` y deja `pNNN.resultado.json` con la salida, los errores y el código de salida.
  - Solo ejecuta archivos `.py` de `scripts\`.
  - Las operaciones de retoque van en archivos `.txt` (por ejemplo `p010_ops.txt`), para que el vigilante no los tome como pedidos.
  - Usar siempre un nombre de pedido nuevo: reusar el mismo nombre puede dejar en la PC el contenido anterior.
- **Copia de trabajo de ADECO2:** `Documents\InventorIA\12_ADECO2` (proyecto completo).
  - Proyecto de Inventor: `ADECOAGRO_Chivilcoy.ipj`, con espacio de trabajo `.` (relativo).
  - `scripts\proyecto_copia.py` activa ese `.ipj` y verifica que el gripper use solo archivos de la copia. `--restaurar` vuelve al proyecto anterior.
- **Por qué este esquema:** con control del equipo, las terminales solo admiten clics, no escritura. Inventor no figura entre las apps que se pueden controlar. Los servidores MCP locales no llegaron a la sesión en la nube.

### Herramientas del servidor (`server/inventor_mcp.py`) y scripts

| Herramienta / script | Qué hace |
|---|---|
| `inspect_assembly.py` | Analiza un `.iam` (o el activo) sin modificarlo: árbol, cantidades, masas, parámetros, restricciones, capturas. Deja el resultado en `Analisis\<nombre>\` |
| `calc_gripper.py` / `gripper_calc.py` | Dimensionamiento (cilindro ADN, carrera, guías, paso, chasis, masa) y memoria en `Calculos\` |
| `planos_gripper.py` | **Regenera** el plano de todas las piezas de CHAPA del ensamble activo (2–3 min) |
| `retocar_plano.py` | **Retoca** el plano existente en segundos: listar, escala, mover, borrar vista, notas, reacomodar hoja |
| `make_chapa_c.py`, `test_create_box.py` | Pruebas / ejemplos |

### Reglas de los planos de fabricación (acordadas)

- **Un solo archivo de dibujo** con **una hoja por pieza de chapa**, y **un solo PDF** con todas las hojas.
  - Salida: `Gripper\Fabricacion\Planos\<ens>_CHAPAS.dwg` y `Planos\PDF\<ens>_CHAPAS.pdf`.
  - Además, un **DXF por pieza** en `Corte_laser\`: 1:1, capas `CORTE_EXTERIOR` / `CORTE_INTERIOR`, sin líneas de plegado.
- **Todas las hojas en A4 apaisada.** La plantilla de dibujo de la PC es `.dwg`.
- **Solo piezas de chapa propias.** Se excluyen las del Centro de Contenido, los comerciales (Festo, HIWIN) y las gomas/plásticos.
- Las placas planas **deben estar hechas como chapa** en Inventor (convertidas), con:
  - el **espesor real**;
  - el **desarrollo creado sobre la cara grande**.

  Si no, el DXF sale mal. Hay un control automático que avisa "CONVERSIÓN A CHAPA INCORRECTA".
- **Escalas normalizadas** 2:1, 1:1, 1:2, 1:5, 1:10, 1:20. Se elige la más grande que entre.
- **Vistas:** FRENTE (arriba a la izquierda), LATERAL a su derecha y PLANTA debajo, alineadas por proyección. El DESARROLLO, la ISOMÉTRICA (a escala menor) y las notas van en el primer hueco libre.
  - Para ganar escala se puede omitir PLANTA y después ISOMÉTRICA.
  - Cada vista reserva el lugar de su rótulo y de sus cotas. El cajetín cuenta como zona ocupada.
- **Cotas:** totales en FRENTE y LATERAL. En el desarrollo: totales y posición de cada pliegue desde el borde, una sola cota por pliegue aunque esté cortado por una escotadura.
  - Las medidas enteras van sin decimales.
  - El radio de plegado **no** se acota: figura en las notas y en la nota de plegado.
- **Notas de cada hoja (5 líneas):**
  - `PIEZA (xCantidad por gripper)`;
  - material y espesor;
  - desarrollo;
  - plegados y escala;
  - `CORTE DXF 1:1 - ISO 2768-m - SIN REBABAS`.
- **Cajetín:** título "<ENS> - CHAPAS" y código = nombre del ensamble (máx. 30 / 18 caracteres).
- **Criterio de trabajo:** regenerar solo si cambia el modelo. Los ajustes finos se hacen con el retoque, que conserva los cambios manuales.

### Lecciones técnicas (API de Inventor desde Python)

- Vista de desarrollo: `AddBaseView(doc, pt, escala, kDefaultViewOrientation, estilo, pythoncom.ArgNotFound, pythoncom.ArgNotFound, nvm)` con `nvm["SheetMetalFoldedModel"]=False`. Si los opcionales van como `""`/`Missing`, Inventor ignora la opción y dibuja la pieza plegada.
- Crear las vistas **ya a la escala elegida**. Crearlas a 1:1 y achicarlas después falla en piezas grandes.
- Mover una vista con escala propia solo con `Position` la desarma. Hay que volver a fijar `Scale` (y `ScaleFromBase=False`) después de moverla.
- Los círculos no tienen `StartPoint`: filtrarlos al recorrer las `DrawingCurves`.
- Los pliegues cortados por una escotadura son varios tramos colineales: agruparlos por coordenada.
- `sketch.ConstraintStatus` debe leerse después de `document.Update()`.
- Una hoja nueva no trae borde ni cajetín: usar `AddBorder(defBorde)` y `AddTitleBlock(defCajetín)` de la hoja 1.
- Antes de sobrescribir un plano abierto en Inventor, cerrarlo. Si el PDF está abierto en un visor, se guarda con otro nombre.

### Estado al cierre de la sesión

- Plano `Gripper_ADECO2_V1_CHAPAS` con 7 hojas en A4:
  1. Brida 1:5
  2. empuja pala
  3. frame 1:10
  4. pala fija 1:5 (sin planta)
  5. pala móvil 1:2 (iso retocada a 1:5)
  6. part_empuje
  7. soporte pistón 2:1
- **Pendiente:** reconvertir `empuja pala` (1/8") y `part_empuje` (3/16"). Hoy su desarrollo salió del canto, con espesor 3,05 por defecto, así que sus DXF no son válidos. Después, regenerar y reaplicar el retoque de la isométrica de la pala móvil.
- **Siguiente etapa del proyecto:** parametrizar el módulo `pala_movil_apriete` sobre la copia y conectarlo con `gripper_calc` para generar grippers nuevos por tipo y cantidad de cajas.

---

## 14. Resumen del 1 al 5 de octubre de 2026 (estado actual)

Desde la sección 13, el trabajo pasó de "retocar planos de ADECO2" a **diseñar y fabricar desde cero** grippers, rejas
y simulaciones de celdas con robot, siempre con Claude trabajando por el vigilante. La receta completa de cómo se hace
cada cosa está en `Receta_IA_Inventor.md`. Acá queda **qué se hizo, dónde está y qué falta**.

### 14.1 Reglas acordadas con DEFYMOTION (vigentes)

- **No tocar originales** (`Documents\Del C\DEFYMOTION\...`). Se trabaja en copias (`InventorIA\12_ADECO2`) o en
  archivos nuevos en `InventorIA\Generados\<nombre>\`.
- **Editar, no regenerar.** Cuando se pide mejorar algo ya hecho:
  - planos → abrir el dibujo existente y editarlo (escala, mover vistas, cotas). Si una hoja está muy mal, se borra
    solo esa hoja y se rehace;
  - piezas y ensambles → modificar los existentes (`--reusar-piezas` / `--rehacer <pieza>`), no hacer piezas nuevas.
- **Planos:** todas las hojas en **A4**, todas en el **mismo archivo de dibujo**, y un único PDF. La escala se elige
  según el tamaño de la pieza.
- **Pala fija sin hexágonos.** Los hexágonos son estéticos/alivianado y van solo en las palas móviles (y en la
  versión liviana, también en el alma del frame y la brida).
- **Frame:**
  - alas curvas como el de ADECO2;
  - si el frame es corto, curva en S fuera de la zona de la brida;
  - logo **DEFYMOTION calado** en las alas, con letras esténcil sin islas.
- **Animaciones:**
  - video horizontal, Full HD;
  - "Luz suave" con sombras;
  - planos de trabajo ocultos;
  - primero se prueba 1 cuadro.
- **Cálculo de apriete:** 8 bar, μ 0,4, FS 2, a 5 m/s² → `F = m·(g+a)·FS / (2·μ)`.

### 14.2 Motor de diseño de grippers (`server/gripper_design.py` + `scripts/construir_gripper.py`)

- **De la caja al gripper completo.** A partir de la caja (fila × apriete × alto, masa) y la cantidad de cajas genera:
  - las chapas desde su desarrollo: frame, pala fija, pala móvil, brida, soportes del cilindro, empuja pala y placa
    de empuje;
  - las gomas;
  - el **módulo de pala móvil** (cilindro ADN + 2 guías HGH15 + chapas) con restricciones;
  - el **ensamble general** con restricciones.
- **Restricción "Apertura".** Cada módulo la lleva: cambiando su valor la pala abre y cierra.
- **Cilindros con módulo validado:**
  - **ADN-25-80**: relevado de ADECO2;
  - **ADN-32-80**: modelo Festo copiado del gripper Tucumán 2026 a `InventorIA\Comerciales\ADN-32-80`.

  Si el cálculo pide un ADN-20, se usa el ADN-25 y se avisa.
- **Comerciales tomados de la copia de ADECO2:** ADN-25, HIWIN y tuerca DIN 439. Antes de usarlos, el script
  normaliza la referencia a "abierto" con los agujeros de los bloques: la copia quedó con la pala corrida 4,4 mm por
  las animaciones.
- **Argumentos principales:**
  - `--nombre --fila --apriete --alto --masa --cajas --paso --ancho-pala`;
  - `--reusar-piezas`, `--rehacer`, `--alas-rectas`, `--sin-logo`;
  - **nuevos** (5/10): `--liviano`, `--alto-palas`, `--robot KR_IONTEC`, `--ala-frame`.
- **Verificación automática** (queda en `resultado.json`): masa real, envolvente, luz entre gomas abierto
  (apriete + 45,5), interferencias e imagen ISO.
  - Interferencias normales que se pueden ignorar: rosca del vástago con la tuerca; soporte con frame o cilindro
    (≈0,1–1 mm³).
- **Planos y DXF:**
  - `planos_gripper.py --ensamble <iam> --con-conjunto` → `Ensamble\Fabricacion\` (`Planos\..._CHAPAS.dwg/pdf`,
    `..._CONJUNTO`, `Corte_laser\*.dxf`);
  - la lista de materiales y la de bulones se arman en Excel del lado de Claude (openpyxl, con fórmulas).

### 14.3 Grippers generados (`InventorIA\Generados\`)

| Carpeta | Caja | Robot | Cilindro | Masa gripper | Entregables |
|---|---|---|---|---|---|
| `GRIPPER_3xTBA200` | 3 × TBA200 (161×333×130, 7 kg) | — | ADN-25-80 | — | piezas, ensamble con restricciones, planos |
| `GRIPPER_4x12kg_C250` | 4 × 200×250×250, 12 kg | KR 140 (celda) | ADN-32-80 | — | chapas, DXF, planos A4 (chapas + conjunto), lista de materiales y bulones (xlsx), video de apertura |
| `GRIPPER_1xC300_KR30` | 1 × 300×300×300, 6 kg | **KR 30** | ADN-25-80 (393 N, FS 3,5) | **14,98 kg** (Inventor) | chapas, DXF, ensamble con restricciones, vistas PNG; **autocontenido** (comerciales en `Comerciales\\`) y `GRIPPER_1xC300_KR30.zip` para enviar. **Faltan planos, lista de materiales y bulones** |

**Gripper liviano para KR30 (5/10)** — `--liviano --alto-palas 200 --robot KR_IONTEC`:

- **Frame:** 3/16" con alas de 110 en vez de 170, curva en S en los extremos, logo calado y alma alivianada con
  hexágonos de 20 entre caras.
- **Brida:** 1/4" (en lugar de 3/8"), de 150 de largo con patas de 70, alivianada.
  - Patrón **KUKA KR IONTEC: 9 × M8 en Ø100**, con centrado Ø63 (el agujero central lleva Ø40).
  - Relevado del modelo `05_Kit Armador de Palets\KR_70_R2100_V01` con `analizar_brida_kr.py`.
  - **Falta confirmar** que el robot sea un KR 30 R2100 (IONTEC) y no un KR 30-3.
  - **Falta** el agujero del pasador de posición.
- **Palas:**
  - de 200 de alto, toman los 2/3 de arriba de la caja;
  - pala fija en 3/16" (en 1/8" flexaba unos 4 mm) y sin hexágonos.
- **Peso:** gripper 14,98 kg + caja 6 kg ≈ 21 kg, de 30 kg admisibles. El centro de gravedad queda unos 200 mm bajo
  la brida: verificar con el diagrama de carga del KR30.
- **Resultado:** envolvente 367 × 300 × 371 mm; luz abierta 345,5 mm (45,5 sobre la caja).

### 14.4 Rejas (`construir_reja.py`, `planos_reja.py`)

- **Construcción:** reja desde una planta en `.txt` (poligonal, aberturas, puerta o portón corredizo).
  - Columnas de perfil con chapas base soldadas.
  - Dos paneles por columna, sin malla por ahora.
- **Generadas:** `REJA_PRUEBA` (cuadrada con puerta) y `REJA_CROQUIS` (desde la foto del croquis del usuario).
- **Planos:**
  - piezas;
  - **conjunto soldado de la columna** (perfil + chapa, con llamadas de soldadura);
  - planta acotada entre ejes;
  - elevación, isométrica y lista de piezas;
  - lista de materiales con corte de caños en barras de 6 m.
- **Pendiente menor:** quedan un par de superposiciones de textos en los planos de reja (el usuario las aceptó).

### 14.5 Celdas con robot y paletizado

- **`CELDA_KR140`** (`Celda_KR140_Gripper4x12.iam`, `Celda_KR140_paletizado.iam`, `celda.json`):
  - KUKA KR 140 R3200-2 PA de la copia de ADECO2, con la base y el gripper de 4 cajas;
  - cinemática directa e inversa en `celda_kin.py` (ejes relevados de la geometría; brida PCD 160);
  - videos de pick & place y paletizado de prueba.
- **`ADECO_SIM`** (copia `ADECO_simulacion.iam`): paletizado de **2 pisos** sobre el layout real de ADECO con el
  gripper ADECO2.
  - Video `Animacion\ADECO_paletizado_HD.mp4` en Full HD, con "Luz suave" y sombras, planos ocultos y más zoom.
  - Correcciones aplicadas:
    - primero deja las 3 bandejas giradas y después las 6;
    - las palas móviles abren hacia el lado libre;
    - bandejas normalizadas para que no queden dadas vuelta.
  - Notas abiertas:
    - el robot queda 345 mm más alto en el layout que en su base;
    - las palas bajan 30 mm por debajo de la bandeja (tocarían el piso de abajo);
    - en el modelo de ADECO las palas 1 y 2 están vinculadas.
- **Presentaciones `.ipn`:** la API de Inventor 2025 no deja crear escenas, así que las animaciones se hacen cuadro a
  cuadro.

### 14.6 Scripts nuevos o cambiados el 5/10

| Script | Qué hace |
|---|---|
| `analizar_brida_kr.py "<modelo>"` | Busca el patrón de agujeros ISO 9409 de la brida de un robot (círculos coplanares en un PCD) → `Analisis\brida_<modelo>.json` |
| `vistas_ensamble.py "<iam>" --arriba 0 0 -1 --dirs="x,y,z;x,y,z"` | Imágenes del ensamble con cámara libre (en los grippers z va hacia abajo) |
| `empaquetar_ensamble.py "<iam>" [--zip]` | Deja el ensamble autocontenido: copia a `<carpeta>\\Comerciales` todo lo que está fuera (cilindro, guías, tuercas), repunta las referencias, guarda, vuelve a abrir desde el disco para verificar y arma un `.zip` para enviar |
| `diag_modulo.py <iam> ...` | Diagnóstico: cajas de cada componente y agujeros de bloques, empuja pala y pala |
| `construir_gripper.py` | Opciones `--liviano --alto-palas --robot --ala-frame`; normaliza la referencia ADECO2 a "abierto" |
| `gripper_design.py` | `LIVIANO`, `ROBOT_BRIDAS` (`KR140_ADECO`, `KR_IONTEC`), `HEX_FRAME`, frame con curva en S, brida parametrizable, `hex_flats` por pieza |
| `inventor_mcp.build_flat_part` | Respeta `hex_flats` de cada pieza (antes los hexágonos eran siempre de 10) |

El diseño por defecto de los grippers de 3 y 4 cajas da **idéntico** que antes (prueba de regresión hecha).

### 14.7 Pedidos del vigilante

- El último usado es **p093**; el próximo es **p094**.
- Siempre se copia primero el script y se verifica trayéndolo de vuelta. Después va el `.json` del pedido.

### 14.8 Pendientes

1. **Gripper KR30:**
   - planos A4 (chapas + conjunto);
   - lista de materiales y de bulones (xlsx);
   - confirmar el modelo exacto del robot y el pasador de la brida;
   - verificar el centro de gravedad contra el diagrama de carga.
2. Agregar al motor de grippers un módulo **ADN-20** (sería más liviano para cajas de menos de 7 kg).
3. **ADECO:** resolver la diferencia de 345 mm de altura del robot y el largo de las palas (30 mm bajo la bandeja).
4. Accesorios del frame (válvulas, reguladores, sensores): todavía sin agujeros en los grippers generados.


---

## 15. 6–7 de octubre de 2026: NewPack2 vertical y nuevo proyecto DosHermanos (EN PAUSA)

### 15.1 NewPack2: videos entregados
- `Generados\NEWPACK2_SIM\Animacion\`:
  - `NewPack2_paletizado_vertical.mp4`: 1080×1920, versión "editada" con cortes de cámara (`--montaje`).
  - `NewPack2_paletizado_vertical_dron.mp4`: sin cortes, la cámara viaja suave mientras el robot se mueve (`--dron`).
- Ambos llevan zoom a la toma del pallet, al centrador y a la primera caja, con la misma calidad de imagen que ADECO ("Luz suave", sombras).
- Comando del dron:
  `simular_newpack.py --ancho 1080 --alto 1920 --centro-vista=-500,-900,1000 --alto-vista 850 --vista=0.6,-1,1.3 --zoom-escala 1.6 --dron --velocidad 1.5`
- Centrador corregido. El subensamble de pistones era FLEXIBLE: la chapa se mueve por su proxy en el centrador. Los vástagos se mueven y el pallet ya no se superpone.
- El usuario prefiere seguir con el método actual (foto por cuadro), sin acelerar el render.
- **Lección:** si se cierra el vigilante en medio de un pedido, ese `.json` queda sin marcar como hecho y se vuelve a ejecutar al reabrirlo. Neutralizarlo antes, sobrescribiéndolo con un pedido inocuo.
- Guía general para proyectos nuevos: `Guia_IA_Inventor.md` (también en `docs\`).

### 15.2 DosHermanos: gripper de 6 paquetes (EN PAUSA)
- **Proyecto:** `Documents\InventorIA\DosHermanos IA\Dos Hermanos Tadeo\`, con el layout `DosHermanosCompleto_V5.iam`.
  - Robot: Borunte `BRTIRUS0805A:1`, de 5 kg de carga.
  - Gripper conceptual original: `Gripper 6 Piezas.iam`, que es una sola pieza.
- **Paquetes:** galletas de arroz Dos Hermanos, cilindros de Ø90 (a confirmar) × 160 mm.
  - Para el cálculo se toman 200 g cada uno (el envase dice 100 g netos).
  - Van en 3 × 2: 3 a lo ancho y 2 a lo largo del eje.
- **Diseño acordado:** apriete A LO LARGO del eje.
  - Pala fija central, entre las 2 filas, sin hexágonos.
  - 2 palas móviles exteriores, en U invertida con orejeta para el vástago.
  - Festo DSNU-10-25 (`DosHermanos IA\Piston 10x25`), POR DENTRO bajo el chasis. Aprieta al retraer: unos 53 N a 8 bar, contra 22 N necesarios. Carrera 25 mm.
  - Guías miniatura `MGW2C1R50Z0CM` (riel 50 mm), 2 por pala.
  - Chasis en C, con alas hacia arriba que bajan hacia las puntas. Brida en U invertida como los demás grippers.
  - Todo en acero de 2 mm.
- **Generado** con `scripts\construir_gripper6.py` en `Generados\GRIPPER6_DOSHERMANOS\` (Chapas, Corte_laser con los DXF, `Ensamble\Gripper6_DosHermanos.iam`).
  - Masa en Inventor: 3,1 kg el gripper y 4,3 kg con paquetes (86 % de la carga del robot).
  - Envolvente 390 × 260 × 153.
  - Sin interferencias, salvo las internas de los comerciales.
- **Pendientes:**
  1. Confirmar el patrón de la brida del Borunte. Se dibujó con 4 × Ø6,6 en Ø44, tomado del modelo.
  2. Confirmar el diámetro del paquete.
  3. Agregar restricciones (apertura) para animar.
  4. Planos A4 de chapas y conjunto, y lista de materiales y bulones.
  5. Ubicarlo en el layout y simular.
- **Relevamientos** en `Analisis\DOSHERMANOS\`: relevamiento.json, comerciales.json, fotos.
  - Scripts nuevos: `relevar_doshermanos.py`, `relevar_comercial.py`, `fotos_ensamble.py`, `diag_calidad.py`, `partir_zip_existente.py`.
- El último pedido usado es el **p155**; el próximo, **p156**.
