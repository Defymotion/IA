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

## L3N Paletizado L3 2027 (Adecoagro Chivilcoy) — instalación y relevamiento, 21/10/2026

- PC de Nahuel (nm). Documentos de Windows está en OneDrive: el instalador creó InventorIA en
  `OneDrive\Documentos\InventorIA`, pero los scripts usan `Path.home()/Documents`. Se movió todo a
  `C:\Users\nm\Documents\InventorIA` (la copia vieja quedó como `OneDrive\Documentos\InventorIA_viejo_para_borrar`).
  Pendiente en el repo: que el instalador y los scripts usen la misma ruta.
- Pedidos: p001 `test_create_box.py` OK; p002 falló (el activo era la pieza de prueba); p003 `activar_doc.py`
  (nuevo: activa un documento abierto y cierra sólo los de una carpeta propia); p004 `relevar_activo.py --nombre L3N` OK.
- Original (no tocar): `C:\DEFYMOTION\L3N\LayoutL3N_Principal.iam`, proyecto `L3N_AdecoagroChivilcoy.ipj`.
  Relevamiento en `Analisis\L3N\` (35 componentes de primer nivel, 523 referencias): 3 celdas
  (`ADECOAGRO_Chivilcoy:1` y dos `ADECOAGRO_Chivilcoy - L3N_Linea3`, la `:3` fija, 4268 x 3951 mm),
  pallets europeos 1200 x 1000 apilados, transportes `Roller_Conveyor_Straight_400V_FlatBelt` y
  `roller conveyor - rotating`, envolvedora `MP402:1`.
- Robot de la celda nueva según la oferta: KUKA KR 180 R3200-2 PA (el modelo del layout viene de ADECO, KR 140).
- Faltan del cliente: caja (medidas y peso), cajas por toma, patrón y pisos del pallet.
- Último pedido: p004.

### L3N — copia de estudio ajustada al DWG de planta (22/10/2026)

- Copia (no toca originales): `C:\DEFYMOTION\L3N\Estudio_IA\LayoutL3N_Estudio_DWG.iam` + subensamble copia
  `ADECOAGRO_Chivilcoy_Estudio_DWG.iam` (dentro del proyecto L3N para que resuelvan las referencias).
  Script `l3n_estudio_dwg.py [--rehacer]`. Restricciones del principal suprimidas, todo fijo en posiciones absolutas.
- Mapeo DWG (m) -> Inventor (mm): ancla giratoria A DWG (3843.973, 1293.966) = Inventor (X -6503.2, Z -35622.3);
  X = -6503.2 + (1293.966 - y)*1000 ; Z = -35622.3 - (x - 3843.973)*1000.
- Celda A = `L3N_Linea3:2`; celda B = `ADECOAGRO_Chivilcoy:1` (incluía la giratoria de C y sus camas; en la copia
  quedan suprimidas y se pusieron nuevas en el principal); celda C = `L3N_Linea3:3`.
  Movidos: B -668 mm en Z (A->B 8,36 m), C +432 mm en Z (B->C 6,59 m) y bajada a nivel de piso (y -24,4).
- Línea de pallets: envolvedora a 16,27 m y giratoria final a 21,09 m de A, +3 camas de rodillos de 2 m.
  Sin la giratoria intermedia (pedido del usuario). Tramos sin cama (a medida): A->B 610, B->C 882, antes de la
  giratoria final 1292 mm.
- Cinta de llegada A (alcance Defy, viene de la embandejadora CBP34): 31,2 m con 13 módulos BM2000 de
  `Cintas Transportadoras` (una sola familia: las carpetas BM comparten nombres de archivo y Inventor no abre dos
  iguales -> error E_INVALIDARG en Occurrences.Add). Banda a 800 mm (las patas 40x40 quedan ~280 mm en el aire).
  La cinta vieja dibujada en A (correas + curvas, en `L3N_Linea3:2`) se ocultó en el principal con
  `ocultar_subocc.py` (Visible=False, no toca el subensamble).
- Freno de cajas de C agregado en la misma posición relativa que A. Línea 4 (Tetra) en el DWG llega ~1,3 m al este:
  falta definir el empalme. B: su cinta Tetra modelada cruza la línea de pallets B->C (revisar con el usuario).
- Tetra Pak: no hay CAD de máquinas; sólo `Medidas cinta tetra.ipt` (tramo 3 m, 205 x 110) y `Tope cinta tetra.iam`.
- Fotos: `Analisis\L3N\estudio_dwg\` (general2_*, celdaA_*, celdas_*). Scripts nuevos: medir_ensambles,
  relevar_internos, relevar_estados, abrir_layout, fotos_zona, ocultar_subocc, l3n_estudio_dwg.
- Lección: escribir el pedido como .tmp y renombrar a .json (un .json vacío se ejecutó y falló, p008).
- Último pedido: p020.

### L3N — ensambles por celda (22/10/2026, tarde)

- Nueva estructura en `C:\DEFYMOTION\L3N\Celdas_IA\` (archivos nuevos; nada existente tocado), script `l3n_celdas.py [--rehacer]`:
  `LayoutL3N_Celdas.iam` (paredes + 4 piezas, cada una con 3 restricciones de nivelación X/Y/Z contra los planos de
  origen, valor = posición DWG), `Celda_A_L3N.iam` (nueva, alcance Defy, incluye `Cinta_Llegada_A.iam`),
  `Celda_B_existente.iam` (como en planta), `Celda_C_existente.iam` (representación: sin cintas, freno, pateador ni
  empujador), `Linea_Pallets.iam` (camas entre celdas + línea + MP402 + giratoria final + guía + pasarela).
  Origen de cada celda = centro de su mesa giratoria a nivel de piso: A (-6503, 0, -35622), B (-6496, 0, -43982),
  C (-6483, 0, -50572). Las piezas internas están fijas en coordenadas relativas a ese origen (sin restricciones).
- Celda nueva = A (KUKA KR 180 R3200-2 PA; el modelo sigue siendo el KR 140 de ADECO). B y C existen y son sólo gráfica.
- Error E_INVALIDARG (-2147024809) en `Occurrences.Add` de un ensamble: ocurre cuando ya hay cargado en sesión otro
  archivo con el mismo nombre desde otra carpeta (aunque sin ventana). Diagnóstico: `diag_insertar.py` (lista
  conflictos de nombre). Solución: NO copiar una sola carpeta BM (comparten piezas entre BM1800/2000/2260/2400);
  usar la biblioteca original de Documents y hacer `Documents.CloseAll(True)` (sólo no referenciados) antes de insertar.
  Quedó una copia descartable en `Estudio_IA\_descartar_copia_BM2000` (borrar).
- Datos del cliente para la celda A (PDF 2PADOK 7703-UK-4, 27/05/2026): caja WASF open ends TBA 250 Edge Helicap
  3x8, 386 x 156 x 149 mm, 6,1 kg; pallet 1200x1000 (150 mm, 25 kg); 17 cajas/capa, 8 capas, 136 cajas/pallet;
  carga 1158 x 928 x 1192; total 854,6 kg, 1342 mm de alto; cartón 3 mm; sin saliente. Copia en
  `Analisis\L3N\TBA_250_Edge_Helicap_3x8_WASF_open_ends.pdf`.
- Video de la celda B en funcionamiento (IMG_7322.MOV, 86 s): banda modular blanca con guías laterales de caño,
  tope/pateador neumático, el robot toma 1 caja por vez con gripper de apriete lateral y apila sobre pallet;
  mesa giratoria de pallets y cortina/barrera a la salida. Cuadros en `Analisis\L3N\video_B\`.
- Fotos: `Analisis\L3N\celdas_ia\`. Último pedido: p037.

### L3N — celdas v2, caja real y pallet (22/10/2026, 13:30)

- `l3n_celdas.py` v2: quita las paredes blancas (factory assets `Pared`, `Pared (puerta)`) de las tres celdas y
  reemplaza el `Ensamble freno de cajas` (sólo estructura) por 2 módulos BM2000 (4,45 m) alineados al extremo del
  robot, banda a 800 mm. C también lleva cinta interna (representación). La copia descartable de BM2000 se borró.
- `l3n_caja_pallet.py`: `Celdas_IA\Producto\Caja_TBA250_3x8.ipt` (386x156x149, 6,1 kg, apariencia Cartón -
  Ondulado, origen centro de la base) y `Pallet_TBA250_17x8.iam` (pallet 1200x1000x152 + 136 cajas: 2 filas de 7
  giradas + 1 fila de 3, capas impares a 180°; envolvente 1200 x 1344 x 1000, 861 kg). Reemplazó `Pallet_Completo`
  en `Celda_A_L3N.iam` (`IA_Pallet_TBA250`) y puso `IA_Caja_en_cinta` en el extremo del robot.
- Robot aéreo de pallets (pedido del usuario): en el DWG de planta está como "TRANSPORTE AÉREO PALLETS VACÍOS":
  dos rieles de 100 mm a y=1297,26 y 1298,83 (Inventor X -9797 y -11367), x 3839,7-3861,9 (Z -31350 a -53550,
  22,2 m), riel central a y=1298,16 (X -10697) de 20 m; pórticos (pares de patas a 0,72 m) en x 3844,75/3845,47,
  3849,7/3850,4 y 3860,83/3861,56 con travesaños de 2 m en y 1297,08-1299,08; estaciones de pallets (1,07 x 2,4 m)
  en x 3843,45-3844,52, 3851,8-3852,87 y 3858,39-3859,46 (sobre cada celda), y 1296,35-1298,75.
  En Inventor sólo hay `guia_robot_dispensador_de_pallets` (perfil 80, X -9858, Z -56256..-31056, alto 2080).
  Faltan alturas y perfiles (preguntados al usuario). Foto real en el chat del 22/10 (pórtico con columna, carro
  naranja con mástil y horquillas, pila de pallets en el piso).
- Fotos: `Analisis\L3N\celdas_ia\v2_*, v3_*`. Último pedido: p042.
- Robot aéreo modelado como volúmenes (`l3n_robot_aereo.py`, `Celdas_IA\Robot_Aereo\Robot_Aereo_Pallets.iam`,
  insertado en el layout con cotas al origen de A): 2 rieles 100x200 de 22,2 m colgados a 3250-3450, 3 pórticos
  150x150 hasta 3600 en Z -36759/-41699/-52844 (patas en X -9617 y -11617), carro 1900x450x1200 bajo los rieles,
  mástil 220 desde 2080 (donde empieza el robot) hasta el carro, 2 horquillas con un pallet, y 2 pilas de 10
  pallets al inicio del riel (las "European Pallet" que estaban sueltas; se quitaron de Celda_A y la guía vieja de
  Linea_Pallets). Todas las alturas y perfiles son estimados: ajustar con datos reales. `cambiar_apariencia.py`
  (apariencia por nombre que EMPIEZA con el texto; "naranja" contenía "ladrillo naranja"). Último pedido: p047.
- Robot aéreo v2 (corrección del usuario): rieles 100x200 con cara superior en 2080 (perfil blanco); carro
  1900x400x1200 y torre 400x1500x600 POR ENCIMA de los rieles (tope 3980); por debajo sólo barra de elevación 150,
  bastidor de sujeción 1300x200x1100 (cara inferior a 1680 en transporte) y el pallet; columnas 150x150 hasta la
  cara inferior del riel (1880) con travesaño debajo, no cruzan por arriba. `--rehacer` quita primero el robot del
  layout abierto. Fotos v6_aereoA. Último pedido: p049.
- Rejas (22/10 13:55): `l3n_rejas_A.py [A|C]` arma el cerco con las piezas Fademaq de la celda B (columna
  `Ensamblaje Columna_[CP1512]_ADECO.iam` 180x180x1955 y `Panel 03_[CP1512]` 1240x900 en dos alturas) sobre las
  líneas del cercamiento original de A (relativas a la giratoria: sur z -2905, este x -935, norte interna z +866,
  norte lejana z +4518; oeste abierto). Paso ≤1320 (4+2+4+6 bahías). Igual en C. Riel bajado a 100x100 (cara
  inferior 1980): `l3n_chequeo_rejas.py` no da choques en A ni C. Pendiente: puerta de acceso (B tiene
  `Ensamblaje Puerta 01` + `Columna Puerta`) — falta que el usuario diga dónde va.
  B: el pórtico 2 del robot aéreo (Z -41699, del DWG) cruza un panel transversal del cerco de B en X≈-10078: o el
  pórtico real está en otro lado o el panel; a verificar en planta. Último pedido: p063.
- Referencias rotas (22/10 14:00): el cartel "requiere datos del documento ..._descartar_copia_BM2000\Piñon BM.ipt"
  salió porque Inventor había resuelto los BM2000 de Celdas_IA a la copia borrada (mismo nombre de archivo ya
  cargado en sesión). Arreglo: biblioteca de bandas DENTRO del proyecto en `C:\DEFYMOTION\L3N\Cintas
  Transportadoras\Banda Modular 2000` (+ `Banda Modular 1800\UCT205`, que BM2000 referencia) copiada desde
  Documents (sin OldVersions); referencias de Cinta_Llegada_A, Celda_A/B/C re-apuntadas con `reapuntar_refs.py`
  (--solo-raiz) y layout recargado con `l3n_recargar.py` (cierra sólo documentos de Celdas_IA/Estudio_IA).
  Lección: NO borrar carpetas de las que Inventor tenga documentos cargados; antes cerrar y `CloseAll(True)`.
  La biblioteca maestra sigue en Documents\InventorIA\Cintas Transportadoras; la del proyecto es copia de trabajo.
- Gripper celda A: igual criterio que B (1 caja por toma, apriete sobre las caras de 386, palas sobre 156).
  `calc_gripper.py --fila 156 --apriete 386 --alto 149 --masa 6.1 --cajas 1`: F = 225,9 N, ADN-20-80 (FS 2,23)
  o ADN-25-80 (FS 3,5); gripper estimado 18,4 kg. Copia de referencia para `construir_gripper.py` armada en
  `Documents\InventorIA\12_ADECO2\{Gripper, Neumatica, Guias Lineales}` (desde L3N\ADECO 12-12-25, sin OldVersions).
  Pedido p079: `construir_gripper.py --nombre GRIPPER_1xTBA250 ...` (salida Generados\GRIPPER_1xTBA250).
- Gripper GRIPPER_1xTBA250 construido (p084, 142 s): `Generados\GRIPPER_1xTBA250\Ensamble\Gripper_GRIPPER_1xTBA250.iam`
  con `--paso 300` (con paso 156 el frame no entra la brida de 250 ni el logo: falla el pliegue 1). Un módulo de pala
  móvil ADN-25-80 + HGH15, pala fija con goma. Masa 25,1 kg (estimación 18,4), envolvente 453 x 300 x 432, luz
  abierta 431 (caja 386 + 45). Interferencias sólo las normales (rosca/tuerca, soporte). Avisos de proceso: si un
  run falla a mitad, quedan "PiezaNN/EnsamblajeNN" sin guardar abiertos y el siguiente SaveAs da E_INVALIDARG:
  `cerrar_propios.py` los cierra. `listar_abiertos.py` para ver ventanas/sin guardar. Pendiente: versión --liviano,
  insertar en Celda_A_L3N reemplazando Gripper_ADECO2_V1, planos (planos_gripper.py). Último pedido: p084.
- Gripper definitivo celda A: toma de 3 a 7 cajas con garras individuales (como B: toma 3 y deja de a 1, toma 7 y
  deja de a 7). `GRIPPER_7xTBA250` (p088, 248 s, `--cajas 7 --paso 156 --alas-rectas`; las alas curvas de ADECO2
  sólo entran hasta ~L/2-hz ≤ span: con 1092 de largo da AssertionError en _contorno_frame_curvo). 7 módulos
  ADN-25-80 + HGH15, pala fija corrida. Masa 70,3 kg (+42,7 de cajas = 113 kg, KR 180 OK), envolvente
  453 x 1092 x 432, luz abierta 431. Interferencias sólo las normales (×7). GRIPPER_1xTBA250 queda como descarte.
  Pendiente: versión --liviano, insertar en Celda_A_L3N, planos. Último pedido: p088.
- GRIPPER_7xTBA250 v2 (p091/p094): alas curvas también en frames largos (`_contorno_frame_curvo`: si L/2-hz > span,
  hz = L/2-span: tramo recto a alto completo y la curva de ADECO2 en las puntas) y pintado como ADECO2 con
  `pintar_como.py` (frame Blanco, brida/palas Turquesa, gomas Gris; apariencias por nombre, con CopyTo y fallback
  a la biblioteca). Foto `..._iso_pintado.png`. Pendiente: "estrías" en la estructura media (preguntado: ¿franjas de
  perforaciones de la pala fija o nervaduras en el alma?). Último pedido: p094.
- Gripper montado en la celda A (`l3n_montar_gripper.py --en-brida`, p115): `IA_Gripper_7xTBA250` colgado del
  círculo de agujeros del eslabón V05 del KR 140 (local del .ipt (1850, 0, 1745), normal -Z; relevado con
  `analizar_brida_kr.py`), largo a lo largo de X. El `Gripper_ADECO2_V1:1` quedó SUPRIMIDO y renombrado
  `..._reemplazado` (Delete falla con el layout abierto; también `Transformation =` y `Grounded`: usar
  `SetTransformWithoutConstraints`). Sistema local del gripper generado: largo +Y, brida en z mín (normal -Z),
  palas +Z; ADECO2: largo +X, brida +Y, palas -Y; RN2O = [[0,1,0],[0,0,-1],[-1,0,0]].
  Brida vs robot: STEP KR120/180/240 R3200 PA: 12 x Ø12 en PCD 160, 3 grupos de 4 a 20° (centros 90/210/330);
  brida ADECO2/gripper: PCD 160, Ø12, 3 grupos de 4 (centros 0/120/240) -> mismo patrón girado 30°. El modelo
  KR140 V05 del layout tiene PCD 125 x 12 Ø10 (no es la brida real). Foto v13_gripperA. Último pedido: p116.
- Simulación celda A (22/10 15:10): `armar_l3n.py [--rearmar]` (plantilla de armar_newpack) arma
  `Generados\L3N_SIM\CeldaA_simulacion.iam` + `Gripper_sim.iam` + `escena.json`: oculta el KUKA armado, agrega
  SIM_V01..V05 (matrices del ADECO en `12_ADECO2\KUKA`, copiado), phi0 calculado de la normal de la brida de V05
  (=-90-atan2(-0.6889,0.7249)), gripper colgado de la brida (BRIDA_G=(387,546,-245.2) local; R_WD largo a lo largo
  de X), registra los 7 módulos con su restricción "Apertura", oculta el pallet lleno y agrega pallet vacío +
  136 cajas ocultas. El robot es de 4 ejes: la brida queda siempre horizontal (celda_kin). Primera corrida (p117)
  guardó la escena pero la celda tenía un gripper duplicado (`Gripper_GRIPPER_7xTBA250:2`, resto de p106/p108)
  y el gripper de 7 quedó "sin resolver" por piezas del GRIPPER_1x (mismos nombres) cargadas en sesión:
  Delete/Suppress/Definition.Document fallan. Pendiente: reiniciar Inventor, `l3n_limpiar_celdaA.py`, `armar_l3n.py
  --rearmar`, foto. Lección: no construir dos grippers con piezas del mismo nombre en la misma sesión (o cerrar todo
  entre uno y otro). Último pedido: p124.

### L3N — 23/10/2026 (mañana)

- Cartel "Resolver vínculo" (Celda_A -> Gripper en Documents\InventorIA\Generados): `l3n_fijar_refs.py` (p136) abrió
  los 5 ensambles con el proyecto L3N activo: NINGUNA referencia fuera del proyecto ni faltante. El cartel aparece
  si Inventor se abre con OTRO proyecto activo (usa la ruta absoluta vieja). Regla: abrir siempre con
  `L3N_AdecoagroChivilcoy.ipj` activo (abrir_layout.py lo activa). Las copias viejas de Documents quedaron
  renombradas: `Generados\GRIPPER_7xTBA250_origen` y `Generados\L3N_SIM_viejo` (borrables). La escena de
  simulación (p131, 22/10 18:44) está en `C:\DEFYMOTION\L3N\InventorIA\Generados\L3N_SIM` (foto sim_v1_iso).
- Cinta de llegada v2 (`l3n_cinta_llegada_v2.py`, p143): dos curvas de 90° con el activo de la celda B
  (`L3N\Factory Assets\Horizontal Curve Belt Conveyor (For Asset Chains)_4E75E090...ipt`: origen = centro del arco a
  la altura de la banda, arco en el cuadrante local +x,+y, local z = arriba; R eje 475, banda 370; usar la ruta YA
  CARGADA en sesión del mismo nombre, si no Occurrences.Add da E_INVALIDARG). Recorrido (layout): T1 X=4363 de
  Z=-20922 a -30054 (4 BM2000 + a medida 229), Curva_1, T2 Z=-30529 de X=3888 a -11659 (6 BM2000 + a medida
  2193), Curva_2, T3 X=-12134 de Z=-31004 a -37021 (2 BM2000 + a medida 1566): 32,2 m. Módulos a medida =
  `Celdas_IA\Producto\BM_a_medida_L<mm>.ipt` (volumen: bastidor 270x120 + patas). T3 pasa entre el pateador
  (x máx -12370) y el inicio de la cinta interna (x mín -11898), banda a 800. Pateador de A centrado al eje de la
  cinta interna (Z -36697, dz +165). Fotos v16_*. Pendiente: subir scripts nuevos al repo (desde p130 en adelante).
  Último pedido: p146.
- Módulos BM a medida (23/10 09:45): `bm_modulo.py --largo L --tag T` copia la familia BM2000 del proyecto a
  `C:\DEFYMOTION\L3N\Cintas Transportadoras\BM_<tag>` renombrando todos los archivos (sufijo _<tag>) y re-apunta
  las referencias (83 archivos, 47 refs). Parámetros de largo relevados (`relevar_params_carpeta.py`, Analisis\Cintas
  \params_BM2000.json): Lateral der/izq d2=2000 (largo), d19=1395 (falla al editar: conducido); Deslizante Z d10=1960,
  L d10=1555, Pi d6=1735; Estructura base 40x40-2000.ipt (esqueleto del Frame Generator) d8=1395 (largo), d6=440 es
  HORIZONTAL (no es altura de patas: no tocar), patas = d1 250 + d5 150 vertical. Valores con p.Value (cm): Expression
  con "." falla en locale es. Primera prueba BM_L2193: laterales crecen en sentidos opuestos (der hacia +X/motor,
  izq hacia -X/cola), el esqueleto creció hacia -X, la banda (patrón) no se alarga y quedan bocetos visibles. Falta:
  fijar el extremo de cola en ambos laterales, patrón de la banda por largo, altura de patas (d1/d5) + base regulable
  (plato Ø100 + M16x100 + cubo 40x40). Hay carpetas que se llaman "*.ipt" (Ensamble Estructura base 40x40-2000.ipt):
  filtrar con is_file(). Último pedido: p153.
- Motorización de cintas (23/10 10:00, preliminar): cálculo tipo Intralox/Habasit BP=[(M+2W)·fw + M·fp·acum]·L·g con
  M=15,8 kg/m (cajas 6,1 kg a lo largo, pegadas), W=1,7 kg/m (PP 6,83 kg/m² x 249), fw=0,13 (PP/UHMW), fp=0,30
  (cartón/PP), SF 1,4, Rp 68,8 mm, v=25 m/min, η 0,8. Tramo de 15,5 m acumulado 100 %: BP 1100 N, ABP 1,54 kN
  (6,2 kN/m contra ~14,6 kN/m nominal de un PP flat top 1"), 106 N·m en el eje, 0,57 kW. 9,1 m: 0,9 kN, 62 N·m,
  0,34 kW. 6 m: 0,6 kN, 41 N·m, 0,22 kW. Propuesta: una banda continua por tramo recto (1 motor por tramo, en
  cabeza), bastidor en secciones de 2,5 m abulonadas (transporte), banda enviada en rollos y unida con varillas
  en obra; curvas con motor propio. Alternativa pedida por el usuario: módulos de 2,5 m con banda propia y
  transmisión a cadena 1 motor cada 2 (más transferencias y motores). Falta: decisión del usuario.
- Fichas MDC (leídas en el navegador integrado, 23/10): las fichas por serie son sólo geometría, sin resistencia,
  peso, rozamientos ni radios. HK50 serie 1000: M1000 (HK50-M-01000, 22 % apertura, paso 50, varilla Ø6,3, alto
  15,3, PP+PE o acetal) y M1300 (HK50-M-01300, misma banda con ruedas para acumulación -> combinable con la lisa,
  mismos piñones); empujadores P1100/1200/1400/1250, aletas A170/A172. Piñones: Z6 Ø primitivo 100, Z10 Ø 161,
  Z16 Ø 225 (agujero cuadrado 38,1 / 40). M2000 = con transferencia; M3000/M3300 0 % y 12 %; M4000/M4300 HS50;
  M5000 (HC22, paso 42, agujeros colisos) y M8000 (HC2.2, paso 25,4) parecen bandas de curva (side-flex): radio
  no indicado; M6000/M7000/M9000 paso 25,4. Con Z10 Ø161 el par del tramo de 15,5 m acumulado sube a ~124 N·m.
  El catálogo general (94 p.) tiene texto pero no datos de bandas plásticas.
- Cálculo propio de MDC (cotización DC 02-1224, banda con rodillos 381 x L 4,4 m, Z10, PP): peso banda 8,31 kg/m²,
  resistencia 1332 kg (ancho 381 -> ~3500 kgf/m), μ banda-pista 0,31, μ banda-producto 0,21; F = (P+B)·0,31 +
  (P+B)·0,21, SF 50 %. DC 02-1367: lisa 249 (desarrollos 4,8/5,3 m) y con rodillos 398 (5,6/4,4 m), "el mismo
  piñón aplica para ambas mallas" (Z10, eje cuadrado 40). Con el método MDC, tramo de 15,5 m en 249 lisa sin
  acumulación: ~86 kgf (129 con SF) contra ~870 kgf (1332 x 249/381): 15 %; con acumulación total ~170/254 kgf: 29 %.
- Anchos de banda (23/10 10:30, usuario): la misma caja viaja a lo largo (156 de ancho) en la llegada y el pateador
  la gira al entrar a la celda (386 de ancho): banda 200 en la llegada y 420 en la celda. Incremento de ancho HK50 =
  medida A de la ficha (8,85 PP / 8,82 acetal): 381 = 43·A, 398 = 45·A, 249 ≈ 28·A. Anchos reales: 23·A = 203,5
  (llegada) y 48·A = 424,8 (celda). A confirmar con MDC (incremento, ancho mínimo, piñones por ancho).
- Orientación de la caja (usuario, 23/10 10:31): en B y en A la caja llega a lo largo (156 de ancho) y el pateador
  la gira A PROPÓSITO al entrar a la celda: sobre la cinta interna va con 386 cruzado (Z) y 156 en el avance (X),
  que es como la toman las 7 garras del gripper (paso 156 a lo largo de X) y como lo pide el patrón de paletizado.
  `IA_Caja_en_cinta` de Celda_A estaba con 386 a lo largo de X: girada 90° (`l3n_girar_caja.py`, p154).
  Pendiente: re-armar la escena de simulación (toma `caja_toma` de la celda). Último pedido: p154.
- Cintas nuevas como BLOQUES DE LAYOUT (23/10, `cinta_modular.py`, p155-p170). El usuario aclara: son bloques
  usables (layout, simulación, cotización), NO modelo de fabricación. La versión de fabricación sale de las
  BM2000/BM1800 ya fabricadas: sólo cambia el ancho de módulos (travesaños, ejes, piñones, pistas, cruz de patas);
  laterales y plegados se reutilizan y se encastran módulos para largar. PENDIENTE (etapa posterior): modelo 100 %
  paramétrico que con las medidas de caja recalcule todas las cintas y largue planos.
  `cinta_modular.py --nombre --largo --modulos n (A=8,85) --banda lisa|rodillos --producto --seccion-max 2500
  --motor-lado der|izq --motor-adelante --baranda-hasta x --rehacer`: secciones <=2,5 m (laterales C 200 alas
  afuera, pistas UHMW ida/retorno, travesaños, empalmes, patas 40x40 + base regulable Ø100 M16 a media carrera,
  banda a 800), Banda.iam continua, Barandas.iam, eje cuadrado 40 + piñones Z10, UCFL, motorreductor (volumen).
  Generadas en C:\DEFYMOTION\L3N\Celdas_IA\Cintas\: Cinta_Llegada_T1 (9132, 4 secc.), _T2 (15547, 7), _T3 (6017; la
  usada es _T3b: motor del lado del pateador apuntando hacia afuera de la cabeza, barandas hasta 5317 para la
  zona de empuje), Cinta_Interna_CeldaA_L4447 (48 mód. = 424,8, ruedas, 2 secc.; la de 4861 quedó sin uso).
  `l3n_cintas_bloques.py <interna> [T3=...]` reemplazó en Cinta_Llegada_A los BM2000/a medida (curvas intactas) y
  en Celda_A_L3N los BM2000_CeldaA_1/_2 por la interna única (mismo x0, eje Z -36697); caja de muestra centrada en
  el eje. Pendiente: chapa puente T3 -> interna (~230 mm entre bandas, la caja mide 156 en ese sentido), verificar
  reductor de T3 contra el pateador, re-armar la simulación. Último pedido: p170.
- Celda A, correcciones del usuario (23/10 11:38-11:52, p171-p190):
  - Piezas sueltas (relevadas con `relevar_puntos.py`, Analisis\celdaA_volando.json): `chapa tope derecha:1`,
    `soporte bandejas:14/15` y `Empujador 01:1` OCULTOS (visibilidad_occ, reversible); `Gripper_ADECO2_V1_reemplazado`
    (suprimido, del ADECO) BORRADO con `borrar_occ.py`.
  - T3 alargado 100 mm aguas abajo (`Cinta_Llegada_T3d`, 6117, extra3=100): reductor a ~100 mm del pateador
    (pedido: 100 mm alcanzan), motor del lado del pateador apuntando hacia afuera, barandas hasta 5317.
  - Robot "torcido": el KUKA armado de ADECO tiene la muñeca a 46° (normal brida (0,-0.69,0.72)) y el gripper
    estaba suelto sobre el pallet con el largo vertical. `l3n_robot_pose.py`: oculta el armado, pone IA_Robot_V01..V05
    sueltos con phi0 = -46,457 (como la simulación, celda_kin) en pose de TOMA sobre las últimas 7 cajas de la
    cinta interna (IK Gauss-Newton: q = 5,83 / -20,0 / -26,67, q6 = -q1), brida mirando abajo y gripper colgado
    con el largo a lo largo de X (palas 15 mm sobre la banda). OJO armar_l3n.py --rearmar: ahora la celda tiene
    IA_Robot_V0x y el armado oculto (adaptar para no duplicar eslabones).
  - Cinta interna definitiva `Cinta_Interna_CeldaA_L4447c`: barandas hasta 3150 (zona de toma libre) y motor del
    lado del robot (del lado del pallet chocaba con una columna de la reja).
  - Pendiente: chapa puente / tope en la transferencia T3 -> interna, re-armar simulación. Último pedido: p190.
- Llegada A, ajustes del usuario (23/10 12:23, p191-p196): la cinta Tetra termina a mitad del tramo previo a la
  Curva_1 (marca naranja en el DWG): T1 arranca en Z -25562 (DWG x≈3833,91, estimado con la escala de la captura
  ~10,6 mm/px; A RELEVAR) -> `Cinta_Llegada_T1b` 4492 mm (antes 9132). T2 (15547) partido en dos con motor cada
  uno: `Cinta_Llegada_T2a` y `_T2b` de 7773,5 (motor del lado +Z del layout, afuera de la Curva_2; la unión en
  X -3885,5 queda cabeza con cola, falta chapa de transferencia). `l3n_cintas_bloques.py` acepta `z1ini=`,
  `t2div=`, `T1=/T2a=/T2b=/T3=` y `extra3=`. Pedido usado: `Cinta_Interna_CeldaA_L4447c T1=Cinta_Llegada_T1b
  T2a=Cinta_Llegada_T2a T2b=Cinta_Llegada_T2b T3=Cinta_Llegada_T3d extra3=100 z1ini=-25562 t2div=2`.
  Motores de la llegada: T1, T2a, T2b, T3 + 2 curvas = 6. Último pedido: p196.
- Rejas, pasillo, puerta y buffers (23/10 12:42-13:10, p197-p211). LAYOUT EN PAUSA (el usuario pasa al cotizador).
  - Pared (Paredes.ipt, medido con `medir_distancia.py`): L con cara interior a lo largo de T2 en Z -29790,2 (de
    X -11664 a ~-2364, ahí dobla +Z) y tramo transversal X -11814,2..-11664,2 (150) que T2/Curva_2 atraviesan.
  - Pasillo de mantenimiento (lado pared, pedido): 800 libres entre motor y pared (EN ISO 14122: mín. 600,
    recomendado 800, 1000 si pasan varios). T2 corrido 365 mm hacia -Z: eje Z -30894 (`zt2=-30894`; las curvas se
    corren con él). Nuevos bloques `Cinta_Llegada_T1c` 4857 y `Cinta_Llegada_T3e` 5752 (barandas hasta 4950).
  - Reja de la cinta (`l3n_rejas_A.py A --zt2 -30894`): eje de columnas a 350 del eje de T2 (~100 mm del bastidor)
    desde la pared hasta afuera de la Curva_1 (X 4855) y por +X de T1 hasta Z -29419 (13 + 2 bahías). Corregido:
    los paneles "alto" estaban apoyados en el piso (ahora conservan la altura de la plantilla de B).
  - Puerta de paso P1 (`l3n_buffers.py`): vano 900x2100 en la pared transversal (Z -30740..-29840), hoja 800 que
    abre hacia afuera (lado T3); el motor de T2b queda adentro, a 802 de la pared. Requiere obra civil (vano).
  - Buffers: 2 pilas de 15 pallets (2280 mm) en X -10635, Z -32274 / -33804, 4 guías 80x80 blancas H1900 por pila
    (luz 60, por fuera del bastidor 1300x1100 del robot), placas de anclaje, 2 pórticos de soporte del riel
    (Z -31425 y -33039). Libres: 300 a la reja de la cinta, 250 entre pilas, 222 a la reja norte interna.
    AVISO: 15 pallets superan la altura de transporte del robot aéreo del modelo (pallet a 1528-1680): no puede
    pasar sobre una pila llena (o el riel es más alto en la realidad, o 10 por pila). Último pedido: p211.
- Buffers en 10 pallets por pila (23/10 13:43, p212, `l3n_buffers.py --zt2 -30894 --pallets 10`): pila de 1520 mm,
  pasa por debajo del pallet en transporte del robot aéreo (cara inferior 1528). Para 12 haría falta el riel con
  cara superior a ~2430 (15: ~2880). Cotizador ADECO actualizado (hoja Cintas por componentes con costos reales de
  CITRIC, hoja Comparación CITRIC, Pendientes 14-19). Último pedido: p212.
- Presupuesto 051-23102026.01 (23/10 14:00-18:00, sin pedidos al vigilante; p213-p215 de fotos NO llegaron al
  caerse el puente). Google Slides 1C8zIwDERYVSsqD87rVeI1OpwMgsgsNxbYJU6Rg_1GP0 (copia de la plantilla
  050-05062025.03 hecha por el usuario, editada con el conector de Slides): portada, objetivo, alcance,
  características, funcionamiento, documentación, propuesta, planificación, supuestos, layout (imágenes del 3D:
  planta y celda A, subidas al repo público como URLs raw y después borradas del branch; quedan en el historial,
  commit bbb18a3), incluye / no incluye, "Inversión por etapas" (hoja nueva `l3n_s_etapas`, tabla `l3n_et_table`),
  comercial, plazo y garantía, pasos, historial.
  - Etapas (desglose informativo, NO se ofrece contratar por etapa): 1 cinta de llegada 41.610, 2 rejado 7.860,
    3 buffers 3.680, 4 pateador 2.950, 5 celda robótica 169.816, 6 estrechadora 7.940, 7 programación 12.350 =
    246.206 USD + IVA (cotizador: costo 167.487, Parámetros B10 = 1,40 ganancia y B11 = 0,07 impuestos directos;
    precio = costo x 1,47 redondeado a 10, la celda absorbe el redondeo). Pago 50 % anticipo / 30 % montaje (acta)
    / 20 % SAT (acta). Plazo 20 semanas (robot KUKA 15 desde la OC; oferta válida hasta 18/11/2026).
  - Cotizador 1wa8Vzp9Gx3GPHY2jyp9Ojye9QTDE2LcqAq9y9oW22pE: filas nuevas 36 relé de seguridad 250 y 37 barrera
    tipo 4 con muting 1.800 (reemplazan 2 x 1.200; antes la barrera la ponía Adecoagro, ahora la compra DEFY);
    Pendientes 6 y 20 actualizados; Comparación CITRIC con referencias corridas bien.
  - Decisiones del usuario sobre la propuesta: sin criterios de aceptación por ahora; matriz de responsabilidades
    como tabla editable (`l3n_resp_table`, 14 filas) + "Supuestos del proyecto piloto" (`l3n_sup_text`: anteproyecto
    para reservar CAPEX 2027, curvas estándar, altura del riel -> 10 pallets por buffer, inicio de T1 del plano,
    ventana de parada se define después y no está en el plazo, cadencia a confirmar); sin ROI (no hay datos de
    Adeco); se entregan programas fuente PLC/HMI/robot, backups, licencias y lista de repuestos; "ajustes menores"
    90 días = reprogramación, puntos de paletizado, programa del PLC y mecanismos sin cambio físico grande
    (soporte de sensor, detalle del gripper).
  - Truco Slides: deleteText ALL + insertText hereda el estilo del último párrafo -> re-estilar (fontSize, DARK1,
    bold, deleteParagraphBullets); las formas creadas quedan con size 3000000 EMU y escala -> para moverlas usar
    scaleX/Y = tamaño/3000000, no 1. Verificar con export PDF de Drive (base64) + pdftoppm.
  - Pendientes L3N: relevar fin de cinta Tetra, altura del riel y cadencia; cotización MDC (anchos 23 y 48
    módulos) y curvas; precio local de la barrera; chapa puente T3->interna y T2a->T2b; re-armar simulación
    (`armar_l3n.py --rearmar` con IA_Robot_V0x); versión de fabricación de las cintas (familia BM2000, sólo cambia
    el ancho) y modelo 100 % paramétrico; fotos de la celda (repetir p213-p215). Último pedido: p212.
- Presupuesto, tarde (23/10 18:00-19:30, p213-p240): fotos tipo render del layout (`l3n_fotos_presupuesto.py`:
  fondo blanco con esquema "Presentation" + BackgroundType 52737, luz suave, sombras, perspectiva 0,52 rad,
  SetExtents también en perspectiva, paredes visibles sólo en las fotos que lo piden) y flechas/etiquetas con
  Pillow (naranja = nuevo, gris = existente). Imágenes en `C:\DEFYMOTION\L3N\Presupuesto_img\` (01..04 anotadas
  + sin_anotar\), puestas en el deck (`l3n_img_cambios`, `l3n2_img_celda`, `l3n2_img_buffers`,
  `l3n_img_propuesta2`; createImage sólo con URL pública: se reusa el contentUrl de una imagen ya pegada).
  Cruce con el cotizador de Córdoba (16kAUHOTIDUW8b3__QsCFINVdxTKA0YMyvS6MLQOx5rw): se agregaron estructuras de
  pateadores/centrador/fijación, sensores reed, EtherCAT, protecciones y baliza. Barrera de salida IFM OY513S
  (tipo 4, 4 haces, muting) en las dos columnas de reja del borde de la cama (X -7400, emisor Z -36199,8,
  receptor Z -34873,8, Y 150..1235) con brazos de muting L600 a Y 700 sólo hacia adentro (del lado de la
  giratoria barrerían el pallet al girar). Cotizador: COSTO 178.421 / PRECIO 262.279 USD.
- Camas de rolos a medida (p236-p238, `l3n_camas_medida.py --ver _v2`): copia del STEP original
  `RM8x10_800020-5500-429-19-0_B_IAD_000.step.ipt` estirada (corte en Z -1214: MoveFeature de cuerpos enteros +
  MoveFace de las caras lejanas + rodillos Ø89 cada 150) y ensambles `Cama_rolos_400V_L{L}_v2.iam` con las patas
  originales en `Celdas_IA\Camas_medida`; reemplazan IA_Cama_L2648_5, IA_Cama_L2920_3 e IA_Cama_L3320 en
  Linea_Pallets (sin huecos entre camas). API: MoveFaceFeatures.CreateDefinition(caras).SetFreeMoveType(matriz);
  MoveFeatures.CreateMoveDefinition(cuerpos).AddFreeDrag(x,y,z).

### L3N — simulación completa de planta (23/10/2026 noche, p240-p252)

- Relevamiento (`l3n_sim_relevar.py`, p240, ~11 min): `Analisis\L3N\sim_relevamiento.json` con matrices de layout
  de celda A (2 niveles), línea, robot aéreo, cinta de llegada, KUKA (eslabones), gripper (módulos con su
  restricción "Apertura" -484,73), patrón del pallet lleno (17x8, 136 cajas), giratoria A y MP402.
- Planificador del lado de la IA (`scripts/l3n_plan_sim.py rel.json plan.json`, Python puro + celda_kin): simulación
  por eventos (DT 5 ms) de cintas con acumulación (500 mm/s, una caja cada 1,15 s), pateador (0,55 s + 0,4 s de
  retorno), cinta interna contra el tope, robot (ciclos: fila de 3 dejada de a una con el gripper a 90° y las
  cajas colgadas hacia la zona libre, y 2 tomas de 7; traslados "sube-cruza-baja" a la altura mayor para no barrer
  cajas; alturas sobre la capa ≥200 y ajuste por alcance), robot aéreo (pila 1 -> cama de ingreso, camas a 420
  mm/s, centrador), salida (giratoria 90° en 3 s, pallet por la línea a 450 mm/s con aceleración 300, envuelto
  MP402 6 vueltas en 30 s con el carro subiendo y bajando y 8 bandas de film, salida a X 12600), pallet 2 y
  reciclado de las cajas del pallet 1 para seguir paletizando. Verificaciones: IK < 3 mm en todo el video, cajas
  colgadas y gripper contra cajas apoyadas (AABB) sin choques. Tiempo de paletizado de 136 cajas ≈ 162 s de ciclos
  (velocidades de video, no optimizadas). Guion de 9 tramos (general, pateador, aéreo ×2, capa 1 ×1, capas 2-8 ×7,
  salida ×1,5, traslado ×8, envuelto ×3, final): 2870 cuadros a 30 fps.
- Hallazgos para el usuario: (1) pateador a 164 mm de la caja: con 300 de carrera la caja no llega a la interna
  (se simuló 450); (2) palas de 33,5 mm y patrón sin luz entre filas: se simularon 35 mm entre bandas y entre las 3
  transversales (carga 998 x 1228); (3) alturas del modelo: cama celda/giratoria ~507 (rodillos), línea 626,8,
  MP402 501,3.
- Escena (`armar_l3n_sim.py plan.json`, p242, 8,5 min): `Documents\InventorIA\Generados\L3N_SIM2\`:
  `L3N_SIM_Planta.iam` = SaveAs COPIA del layout + proxies móviles ocultos + 265 objetos SIM_* de primer nivel
  (eslabones, gripper, 232 cajas, pallets, pateador, aéreo con barra telescópica de 3 tramos, deck de la
  giratoria, rotor y carro de la MP402, film); `Gripper_SIM\` = copia del gripper con un archivo por módulo de
  pala (cada garra abre sola; +Apertura CIERRA: signo_abre -1, abre 25 mm); `Piezas\` = film A/B y
  `Pallet_lleno_sim.iam` (patrón con luz). Matrices del plan redondeadas a 4 decimales -> Inventor exige
  ortonormalizar (Gram-Schmidt) o Occurrences.Add da E_INVALIDARG. La búsqueda de apariencias en las bibliotecas
  tarda ~6 min (y no encontró "vidrio": el film quedó blanco opaco, se ve bien).
- Render (`simular_l3n_planta.py plan --desde --hasta --paso 2 --carpeta Cuadros --sin-pantalla`; pruebas con
  `--cuadros a,b,c` y `--prueba-giratoria th1,th2`): aplica sólo cambios; las cajas ocultas o fuera de cuadro no se
  mueven hasta que hace falta (de 17,7 a ~6 s por cuadro: cada Transformation de una ocurrencia visible en la
  escena de planta cuesta ~0,18 s). Giratoria: th 0 = transporta en Z (hacia B), 90 = hacia la celda/MP402
  (verificado con fotos en planta). Primero cuadros pares (video a 15 fps) y después impares. plan_l3n_v2.json =
  cámara nueva del pateador (desde el SO). Pedidos: p249 (0-999), p250 (1000-1999), p251 (2000-2869), p252
  (180-359 con v2), todos paso 2. Leyendas y reloj se agregan en la nube (`l3n_rotular_cuadros.py`).
- Correcciones pedidas por el usuario sobre el primer video (24/10 00:54) y resueltas (p256-p270):
  1. El pateador empujaba las cajas contra la columna 1b del pórtico 1 del robot aéreo (estaba sobre la cinta
     interna). `l3n_ajustes_sim.py` (p260, respaldos *_antes_ajustes_sim.iam): pórtico 1 a Z -37500 (columna 1b en X
     -11700, travesaño nuevo L2233 en Celdas_IA\Ajustes_sim), y además lo que mostraron los chequeos de choques:
     travesaño del pórtico de buffer 2 -> 2 ménsulas (la sujeción del pallet pasaba por él), buffers +53 mm en X
     (centrados con los rieles, X -10582), reja norte interna + receptor IFM +150 en Z (la fila de 3 del lado norte
     necesita ~312 mm), brazos/sensores de muting a Y 560, y el tramo de reja norte bajo el robot aéreo bajado a
     1400 (columna 2 y paneles altos 1-2 ocultos; poste y paneles nuevos): el pallet colgado (1528) cruzaba la reja
     de 1955. ALTURA 1400 A VALIDAR CON SEGURIDAD.
  2. El robot esperaba la cinta interna llena: ahora el pateador dosifica (sólo pasan las cajas de la toma
     pendiente y la siguiente: 3+7, 7+7, 7+3) y la llegada acumula.
  3. Robot duplicado: el KUKA armado (KUKA-KR_140_R3200_2_PA-ASM:1) que el layout tenía oculto volvía a verse en la
     copia (la visibilidad de proxies no persiste al reabrir); se oculta desde el plan (`ocultar`), igual que
     chapa tope, soportes de bandejas y Empujador 01.
  4. Codo abajo: el IK caía en la solución de codo abajo al borde del alcance (capa 7, filas lejanas). Ahora
     `q_for_gripper` exige codo arriba con margen (seno ≥ 0,12) y `alcanza()` también; fila de 3 con orientación
     única para las 3 dejadas (sin giros de 180° que barrían las rejas), deja primero la garra 6 (las que quedan
     cuelgan hacia adentro) y se elige la orientación que alcanza y no toca obstáculos fijos (relevamiento).
  Chequeos (en la nube, sin Inventor): codo mínimo 0,49, IK < 0,05 mm, sin choques gripper/cajas contra cajas
  apoyadas ni contra obstáculos fijos, robot aéreo sin choques. Paletizado del pallet 1: ~167 s (184 en el reloj).
  Plan `Generados\L3N_SIM2\plan_l3n_v3.json` (2860 cuadros), render en `Cuadros_v3` (p265-p267 pares, p268-p270
  impares). Con Inventor recién abierto el render baja a ~2,7 s por cuadro (antes 6-12: Inventor cargado de
  horas). Si el usuario cierra todo: abrir vigilante.bat (Explorador, scripts\vigilante.bat) y pedir
  `abrir_layout.py <ipj> <layout>` para levantar Inventor con el proyecto L3N. Último pedido: p270.
- Video v3 entregado: `Generados\L3N_SIM2\Animacion\L3N_simulacion_v3_30fps.mp4` (95,5 s) y `_960.mp4`.

### L3N — simulación v4 (24/10/2026 tarde, p271-p279)

Pedidos del usuario sobre el v3: (a) 1 caja cada 2,5 s (velocidad normal de una encajonadora; más luz entre cajas
en la cinta); (b) la columna 1b tapaba la puerta de los tableros -> correr tableros y rejas; (c) la reja sur casi
tocaba el robot: hacen falta ≥600 mm detrás por la caída de cables -> correr todo hacia -Z; (d) orden de dejada:
fila de 3 "derecha, medio, izquierda" (mirando desde el robot) y filas de 7 "primero la del medio y después la del
borde", porque la pala MÓVIL tiene que abrir siempre hacia donde hay lugar; así entre cajas sólo baja la pala fija y
la luz puede ser chica (pallet más cuadrado).
- `l3n_relevar_palas.py` (p271, sólo lectura): pala fija x 161,7-166,5 + goma hasta 169,0 (7,3 mm en total); pala
  móvil abierta con la goma en x 600,5 (cilindro ADN-25-80 retraído, 80 mm de carrera); la caja de 386 apoya contra
  la goma fija (centro x local 362) y la móvil cierra 45,3 mm (en v3 la caja flotaba ~20 mm de cada pala).
- `l3n_reja_sur.py 700` (p272, respaldo `Celda_A_L3N_antes_reja_sur.iam`): Reja_Sur_* (15 ocurrencias) y tableros
  (Kr c4 Technologieschrank:1, 11-06:1) -700 en Z; reja este alargada con poste `Reja_Este_col_0` y paneles de 797
  (`Celdas_IA\Ajustes_sim\Panel_reja_797x900.ipt`). Luz base del robot -> reja: 642,6 mm. Tablero 11-06 queda
  188 mm al sur de la columna 1b (ya no le tapa la puerta). Nuevo relevamiento p273.
- Planificador v4 (`scripts/l3n_plan_sim.py`): PASO_FUENTE 2,5 s; LUZ_PALA 10 mm (carga 1178 x 948 x 1344, dentro
  del pallet 1200 x 1000; antes 1228 x 998); fila de 3: se elige la orientación con la garra 6 primero y las cajas
  colgadas hacia adentro, y el sentido de avance sale de la pala móvil (+X local): extremo opuesto, medio, otro
  extremo (capa 1: X- -> X+, que es derecha -> izquierda vista desde el robot; alterna por capa); filas de 7: banda
  del medio primero con la pala móvil hacia el borde. Choques contra lo fijo con cajas giradas en planta (SAT, no
  AABB); los cruces que barren rejas al girar (giros de 180° en capas alternas) giran sobre el centro del pallet o
  en un punto libre (`cruce()`), y en los giros de ~180° se elige el sentido que mantiene el eje 6 en ±180°.
  Chequeos: sin choques (gripper/cajas contra cajas apoyadas y contra lo fijo; luz mínima pala fija-caja vecina 2,7
  mm), codo ≥0,42, IK <0,05 mm. Pallet 1 completo a los 347,7 s (5,5 min; el robot trabaja ~17-21 s por capa:
  sobra capacidad). Guion: fila de 3 en primer plano ×1, resto de la capa 1 ×2, capas 2-8 ×10; 3137 cuadros.
- Render: `simular_l3n_planta.py` usa `cierre_mm` del plan (abierta = valor del modelo -484,73 de escena.json;
  cerrada = +45,3 mm). `l3n_sim_pallet_lleno.py plan` (p274) movió las 136 cajas de `Pallet_lleno_sim.iam` a la luz
  nueva. Fotos de prueba en `Prueba7` (p275) y mosaicos en `L3N_SIM2\Revision_v4`. Render completo en
  `Cuadros_v4` (p276-p279, 800 cuadros cada uno, 1,9-3,7 s por cuadro, ~2 h en total).
- Video: rótulos y armado en la VM del puente (rotular.py desde los PNG del montaje a `~/work/rot4`, partes de 400
  cuadros con ffmpeg crf 19 medium de <55 s cada una, concat -c copy). OJO: no cortar rotular.py con `timeout`
  (deja un JPG truncado que después se saltea): verificar los JPG con PIL antes de codificar.
  Entregado `Generados\L3N_SIM2\Animacion\L3N_simulacion_v4_30fps.mp4` (104,6 s, 162 MB) y `_960.mp4`.
  Último pedido: p279.
- Velocidad de encajonadoras Tetra (para el usuario): A3/Flex 5000-8000 envases/h; A3/Speed hasta 26 500 envases
  porción/h. Con 24 envases por caja: 1 caja cada 3,3-10,8 s; 2,5 s es exigente para una sola línea.
- Limpieza (24/10 17:45, pedido del usuario): todo lo de versiones anteriores de la simulación (Cuadros v1/v3, jpg,
  zips, Prueba1-6, planes v1-v3, videos previa y v3, OldVersions de la escena, `Generados\L3N_SIM_viejo`) se movió a
  `Generados\_PARA_BORRAR_versiones_viejas_L3N` (7,7 GB) para que el usuario lo borre (la IA no borra en firme).
  Queda en `L3N_SIM2`: escena, Gripper_SIM, Piezas, plan_l3n_v4 (+meta), Cuadros_v4, Prueba7, Revision_v4 y
  Animacion\L3N_simulacion_v4_30fps.mp4 / _960.mp4.

### L3N — simulación v5: celdas A y B juntas (24/10/2026 noche, p280-p318)

Pedido del usuario: reciclar cuadros y aplicar las mejoras 1-5 (tiempos reales KUKA y capacidad máxima; choques de
los eslabones del brazo, no sólo del gripper; celdas A y B juntas compartiendo robot aéreo, giratoria A/línea y MP402;
pateador real en el CAD con carrera 300 hasta la cinta interna; toma realista: el gripper baja centrado y la pala móvil
empuja la caja contra la fija), armar bien las rejas (los paneles se montaban sobre las columnas) y simular la celda B
(instalada y funcionando) con la ficha "Bandeja 24x200 ml LEAF sin sorbete": exterior 313 x 161 x 130, blanca
(liner externo blanco), 21 por capa (franja de 3 + 3 columnas de 6), 9 capas, 189 por pallet 1200 x 1000, 1320 de
alto. B tiene dos cintas después del pateador con un freno con contador en el medio.
Supuestos (avisados): B 1 caja cada 2,5 s; A = KR 180 R3200-2 PA (137/111/119/321 °/s), B = KR 180 R3200 PA de la
generación anterior (105/107/114/242 °/s), aceleraciones estimadas.
- CAD (archivos propios, con respaldo `*_antes_*.iam`):
  - `l3n_rejas_v2.py A|C` (p289/p290) + `l3n_rejas_v2_fix_cano.py` (p295): rejas rehechas con paso 1320, paneles de
    1240 entre columnas (luz 40) y bahías finales recortadas; tramos bajo el robot aéreo a 1400 con piezas Fademaq
    recortadas por `estirar_pieza.py` (MoveFeature/MoveFace sobre copias; las piezas Fademaq no tienen parámetros).
    Piezas en `Celdas_IA\Rejas_v2\`.
  - `l3n_infeed_v5.py` (p291): pateador A +120 (con su carrera de 300 la caja entra 20 mm en la cinta interna);
    B: pateador +150, BM2000_CeldaB_1 -339 y freno con contador (marco, cuchilla 12x160x240 que sube 40 / baja 70, y
    sensor) en el hueco entre las dos cintas.
  - `l3n_pateador_A_cubierta.py` (p301): la cubierta "chapa nueva 2" del pateador A tocaba 27,5 mm el lateral de T3;
    la copia recortada no se pudo insertar (Occurrences.Add E_INVALIDARG con la copia hecha por archivo), así que se
    oculta y se pone la pieza original corrida 32 mm hacia -X (`IA_Pateador_A_chapa_nueva_2_corrida_32`). En la
    realidad: recortarla 32 mm.
  - `l3n_celdaB_aereo.py` (p297): para que el robot aéreo llegue a B: tablero 11-06 corrido (-1071 X, +358 Z), reja
    oeste y primera bahía norte de B a 1400 (columnas H1400 y paneles altos de 345), la puerta y el panel neumático
    (chapa filtro, carcasas arriba) ocultos: HAY QUE REUBICARLOS en la planta real.
  - OJO: lo que se oculta DENTRO de un ensamble de celda no se ve oculto en el layout (cada ensamble guarda su
    visibilidad). `l3n_listar_ocultos.py` (p302) escribe `Analisis\L3N\ocultos_celdas.json` y el plan los repite.
- Relevamiento: `l3n_sim_relevar.py` (p298, celda B incluida) -> `Analisis\L3N\sim_relevamiento.json`; eslabones
  KUKA a STL (`exportar_stl.py`) -> nube de puntos `kuka_puntos.json`.
- Planificador v5: `scripts\l3n_sim5\` (Python puro; ver su README). Capacidad máxima con cajas y pallet siempre
  disponibles (`--capacidad-robot`): A 42,9 cajas/min (1,40 s/caja; toma de a una 9,6 s, grupo 7,1 s); B 35,8
  cajas/min (1,67 s/caja; 11,4 / 7,9 s). Con 1 caja cada 2,5 s (24/min) manda la alimentación: pallet A en 350 s, B
  en 452 s. Chequeos `chk5.py`: sin choques de gripper, cajas, eslabones (nube de puntos) ni robot aéreo; luz mínima
  pala fija-caja vecina 2,7 mm (A) y 2,4 mm (B); codo ≥0,42; IK <0,05 mm.
- Escena `armar_l3n_sim5.py` (p303) -> `Generados\L3N_SIM5\L3N_SIM5_Planta.iam`: gripper A con módulos propios
  (restricción Apertura); gripper B = el original con sus 30 piezas móviles (pala, goma, empujes) ocultas y copiadas
  al primer nivel (`SIM_B_PM_g_k`, se trasladan +Z local del gripper al cerrar 65,2 mm); caja B
  `Piezas\Caja_LEAF_24x200_sin_sorbete_313x161x130.ipt`; pallets llenos A (136) y B (189).
- Render `simular_l3n_v5.py` (garras por gripper, varias giratorias con th [0, 90] verificado con fotos para B).
  4266 cuadros; el tramo "envuelto" A (cuadros 2677-2991) es idéntico al v4 (misma cámara, pallet, rotor, carro y
  film; para eso la línea en X usa la Z de la estación A, -35617,06) y se copiaron los cuadros c02475-c02789 de
  `L3N_SIM2\Cuadros_v4`. Render en `L3N_SIM5\Cuadros` (p313-p318).
- Velocidad del render: con `SetCoordinateSystem` por cada matriz (como en v4) cada movimiento costaba ~0,11 s y los
  tramos con las dos celdas iban a 5-8 s por cuadro (p313-p315). Desde p320 el renderizador reutiliza una Matrix con
  `PutMatrixData` (~0,02-0,03 s por movimiento, mismo resultado píxel a píxel, p324). Ver Guía §12.1.
- Render completo p313-p322 (las partes 4-6 renumeradas p320-p322 después de los benchs p319/p323 y la prueba p324):
  3,2 / 4,9 / 8,0 s por cuadro con la matriz vieja; 2,4 / 3,2 / 2,6 s con PutMatrixData.
- Video: rótulos en la VM del puente (`L3N_SIM5\_herramientas\rotular.py`, marca "Celdas A y B" con caja al ancho
  del texto; si un PNG se lee a medio sincronizar se saltea y se toma en otra pasada) a `~/work/rot5`, partes de 400
  cuadros con `parte5.sh` (concat demuxer sin repetir el último cuadro; crf 19 medium) y concat -c copy. Copias en
  el repo: `scripts\l3n_sim5\video\`.
  Entregado `Generados\L3N_SIM5\Animacion\L3N_simulacion_v5_30fps.mp4` (142,2 s, 210 MB) y `_960.mp4` (27 MB).
  Último pedido: p324.
- Pendiente / a confirmar con el usuario: reubicar puerta y panel neumático de B (tramo oeste bajo el robot aéreo),
  tablero 11-06 corrido, recorte real de 32 mm de la cubierta del pateador A, chapa del pateador B apenas por debajo
  de la superficie de la cinta Tetra en el CAD original; tiempos de los KUKA estimados (confirmar modelo de B).
- Limpieza (25/10 21:20, pedido del usuario: "todo lo no utilizado a una carpeta que diga borrar"):
  - `Documents\InventorIA\Generados\_BORRAR` (8,6 GB): `L3N_SIM2_simulacion_v4` (escena, cuadros y videos v4),
    `L3N_SIM5_cuadros_PNG` (los 4266 PNG del v5), `L3N_SIM5_pruebas` (fotos de prueba y OldVersions), `PRUEBA`,
    `_staging` (archivos de traspaso).
  - `C:\DEFYMOTION\L3N\_BORRAR` (144 MB): respaldos `*_antes_*.iam` de las celdas, OldVersions de `Celdas_IA`, la
    copia sin usar `chapa nueva 2_recortada_32.ipt` y `InventorIA\Generados\L3N_SIM` (simulación v1).
  - Queda en uso `Generados\L3N_SIM5` (escena, Gripper_SIM, Piezas, plan + meta, escena.json, _herramientas,
    Animacion). No se tocó `ADECO 12-12-25` (originales del cliente) ni `Estudio_IA`.
  - Para retocar un tramo del video v5 sin los PNG: re-renderizar ese tramo (~2,5 s/cuadro) y re-armar (las partes
    rotuladas en la VM del puente pueden no estar más).

### L3N — prueba de render en Blender (25-26/10/2026, p325-p336)

PC del usuario (`info_pc.py`): Lenovo, Intel Core Ultra 7 155H (16 núcleos, 22 hilos), 32 GB DDR5-5600 en un solo
módulo, video integrado "Intel Graphics", SSD 1 TB, Windows 11. Blender 5.2.3 LTS en
`C:\Program Files\Blender Foundation\Blender 5.2` (`buscar_blender.py`).
- Inventor no exporta FBX de fábrica; el OBJ (ATF, desde 2017) trae un .mtl con un material por color de cara
  ("R,G,B"), en mm y en coordenadas de la pieza. El STL no trae color y la apariencia de la ocurrencia muchas veces
  es "Valor por defecto" (el color real está en cuerpos/caras: KUKA naranja, franjas del piso).
- `l3n_blender_exportar.py plan` (p327, 24 min; casi todo es recorrer las 7000 hojas por COM): escena v5 reabierta
  limpia -> `Blender\escena_blender.json` (5887 ocurrencias fijas con matriz, color y ruta; 30 plantillas de objetos
  SIM; 497 piezas, sin tornillería <20 mm). OJO: lo oculto por el armador de la escena no queda guardado al reabrir:
  se filtra con `plan["ocultar"]` y, en el gripper B, con los prefijos de piezas móviles/bandejas.
- `l3n_blender_mallas_obj.py` (p332, 1 min): las 497 piezas a `Blender\mallas_obj\mNNNN.obj/.mtl`.
- Blender (`scripts\blender\`, lanzados por `bl_correr.py` desde el vigilante):
  `bl_armar_escena.py` (p335, 6 s) -> `Blender\L3N_SIM5.blend` (mallas compartidas, Empty "SIM:<nombre>" por objeto
  móvil, colores del .mtl pasados de sRGB a lineal, madera y bandeja LEAF forzadas, piso y cielo blancos, sol);
  `bl_render_tramo.py` aplica el plan igual que `simular_l3n_v5.py`. Cámara: Inventor corre el ojo a ~1,1032·ancho
  del objetivo (`camara_inventor.py`), así el encuadre coincide.
- Resultado: tramo celda B (cuadros 1133-1412) con Eevee 32 muestras a 2,9 s por cuadro (Inventor ~2,5-3 s): mismo
  tiempo en esta PC, aspecto más limpio y Inventor libre. Videos en `L3N_SIM5\Blender\Videos`
  (`L3N_comparacion_Inventor_Blender.mp4`, `L3N_prueba_Blender_celdaB.mp4`). Falta en Blender: palas del gripper A
  (en Inventor van por restricción; hay que exportar sus piezas móviles como las de B).

### L3N — simulación completa en Blender (26/10/2026 madrugada, p337-p354)

Pedido del usuario: render completo en Blender, con libertad para el realismo, y corregir que el pallet B no giraba
con la mesa giratoria.
- Planificador (`l3n_sim5/linea5.py`, `plan5.py`): `giro_pallet()`: el pallet gira con la mesa cuando ésta gira con
  él arriba (giratoria B -90° al salir a la línea en Z; giratoria A +90° al pasar a la línea en X). Plan
  `plan_l3n_v5b.json` (sólo cambian `SIM_B_Lleno` y sus films).
- `gripper_A_moviles.py` (p337): con +1 cm de "Apertura" se mueven -10 mm en X del gripper: pala, goma, placa de
  empuje, empuja pala ×2, vástago ADN (KS), tuercas DIN-439 y las placas 0485 (cierre = -45,3 mm·f en X).
- Blender (`scripts\blender\`): `bl_armar_escena.py` -> `bl_animar.py` (plan a claves: 229 148 claves de matriz,
  visibilidad por escala 0/1 constante, palas A/B hijas de su gripper, cámara como Inventor con cortes sin
  interpolar, obturador del desenfoque = min(0,5; 0,5/velocidad del tramo), `use_overwrite=False` + placeholders) ->
  `bl_ambiente.py --variante real --muestras 40` (HDRI studio.exr de Blender para luz/reflejos con fondo blanco para
  la cámara, sol de 4°, piso de cemento claro, metales por apariencia, Eevee con trazado de rayos) ->
  `bl_correr.py --render <blend> <Cuadros\c#####> --rango a b` (p349-p354, ~3,7 s por cuadro, 4,4 h).
  OJO: los objetos que empiezan ocultos tienen `hide_render` del armado; `bl_animar` lo limpia (visibilidad por escala).
- Video: rótulos en la VM (`rotular.py` saltea PNG a medio sincronizar con cualquier excepción; segunda pasada) en
  `~/work/rot_bl5`, partes de 400 con `parte_bl5.sh`, concat. Entregado
  `Generados\L3N_SIM5\Animacion\L3N_simulacion_v5_Blender_30fps.mp4` (142,2 s, 140 MB) y `_960.mp4` (28 MB).
  Cuadros PNG en `L3N_SIM5\Blender\Cuadros` (para retocar tramos: `bl_correr.py --render ... --rango`). Último
  pedido: p354.
