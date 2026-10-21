# Receta: cómo una IA maneja Autodesk Inventor (DEFYMOTION)

Guía para que otra IA trabaje con Inventor de la misma forma que se hizo en el proyecto InventorIA:
piezas paramétricas (grippers, rejas), ensambles con restricciones, planos A4, DXF de corte láser, listas de
materiales y simulaciones animadas de robots.

Está escrita para una IA que **no está sentada frente a la PC**: corre en otra máquina (Linux en la nube),
y la PC con Inventor está en Windows. Si tu IA corre directamente en la PC, saltá la parte del "vigilante" y
ejecutá los scripts directo.

---

## 0. Reglas de trabajo (lo más importante)

1. **Nunca tocar originales.** Los proyectos reales están en `Documents\Del C\DEFYMOTION`. Se trabaja sobre
   copias (`Documents\InventorIA\12_ADECO2`) o se generan archivos nuevos en `Documents\InventorIA\Generados\`.
   Abrir originales sólo en modo lectura para relevar medidas.
2. **No rehacer desde cero lo que ya existe.** Si el usuario pide corregir algo:
   - planos → abrir el `.dwg/.idw` existente y editar (mover vistas, cambiar escala, agregar cotas); si una hoja
     está muy mal, borrar sólo esa hoja y rehacerla;
   - piezas/ensambles → modificar los existentes (parámetros, posiciones); no crear piezas nuevas.
   - Esto ahorra muchísimo tiempo y tokens.
3. **Todo por script, nada a mano.** Cada tarea es un script Python reutilizable con argumentos.
   La segunda vez que se pide algo parecido, se corre el mismo script con otros parámetros.
4. **Medir antes de suponer.** Antes de construir sobre un modelo ajeno: relevarlo (cajas envolventes,
   matrices, caras, cilindros, restricciones) y guardar el relevamiento en JSON.
5. **Verificar después de construir.** Interferencias, cotas que fallaron, imagen ISO del resultado; mirar la
   imagen antes de entregar.
6. **No guardar cambios de prueba.** Las animaciones y pruebas modifican el modelo en memoria y al final restituyen
   los valores. No se llama a `Save()` salvo en archivos propios recién generados.
7. Español rioplatense con el usuario, medidas en mm, hojas A4, sin cotas de radio de plegado.

---

## 1. Arquitectura

```
IA (nube, Linux)                         PC del usuario (Windows + Inventor 2025)
──────────────────                       ────────────────────────────────────────
escribe script .py  ── copia archivo ──▶ inventor-assistant-portable\scripts\xxx.py
escribe pedido pNNN.json ── copia ────▶ Documents\InventorIA\_pedidos\pNNN.json
                                          vigilante.py lo ejecuta con el python del .venv
lee pNNN.resultado.json  ◀── trae ──── _pedidos\pNNN.resultado.json  (stdout, stderr, código)
trae imágenes/zip/pdf    ◀── trae ──── Generados\...\*.png / *.zip / *.pdf
```

- `server/inventor_mcp.py`: librería con todas las funciones de Inventor (COM con pywin32).
- `server/gripper_design.py`: diseño paramétrico del gripper (cálculos y desarrollos de chapa).
- `scripts/*.py`: un script por tarea (construir, planos, animar, relevar…).
- `scripts/vigilante.py` + `vigilante.bat`: el "ejecutor" en la PC.

### 1.1 El vigilante (cola de pedidos)

- Carpeta: `Documents\InventorIA\_pedidos\`.
- Pedido: `pNNN.json` → `{"script": "construir_reja.py", "args": ["--nombre", "X"], "timeout_s": 2400}`.
- Sólo ejecuta `.py` de la carpeta `scripts\` del complemento (seguridad).
- Resultado: `pNNN.resultado.json` con `codigo_salida`, `segundos`, `salida` (stdout), `errores` (stderr).
- Al terminar renombra el pedido a `pNNN.hecho`.
- Late `vigilante.activo` (fecha) **entre** pedidos; mientras corre un trabajo largo no se actualiza. No
  interpretar eso como caída: esperar el `resultado.json`.
- **Usar siempre un id nuevo** (p001, p002…). Un id ya usado no se vuelve a ejecutar.
- **Cualquier archivo `*.json` que caiga en `_pedidos` se toma como pedido.** Los datos auxiliares (listas,
  plantas, operaciones) se dejan como `.txt` (`p048_planta.txt`) y se pasan por argumento.
- Primero se copia el script y los datos; **después** el `.json` del pedido (si no, puede ejecutar la versión vieja).
- Si el puente de archivos cachea, copiar desde una carpeta de staging nueva y verificar el contenido trayendo
  el archivo de vuelta antes de lanzar el pedido.
- Si deja de responder: casi siempre hay un cuadro de diálogo de Inventor abierto. Pedirle al usuario que lo
  cierre y vuelva a abrir `vigilante.bat`.
- Límites del puente: archivos de hasta 400 MB y 500 MB por llamada. Para muchos cuadros de animación, el
  script de la PC los comprime en `.zip` (sin compresión, PNG ya está comprimido) y, si pasan 350 MB, se
  parten con `partir_zip.py`.

---

## 2. Conexión a Inventor (pywin32)

```python
import inventor_mcp as inv
app = inv._inventor(start_if_needed=False)   # GetActiveObject("Inventor.Application")
app.SilentOperation = True                   # sin cuadros de diálogo (¡clave para que no se cuelgue!)
tg = app.TransientGeometry
S = inv._safe                                # S(lambda: expr, default) -> evita que un COM error corte todo
for o in inv._items(coleccion): ...          # colecciones COM 1..Count
```

Reglas de la API que costaron aprender:

- **Unidades internas en cm.** Todo lo que viene de la API (RangeBox, Matrix.Cell(r,4), Offset.Value) está en
  cm; multiplicar por 10. Al crear puntos, dividir mm/10. Ángulos en radianes.
- Volver a poner `SilentOperation = False` al terminar (con `atexit`).
- `Documents.Open(path, visible)`: abrir invisible para leer; visible si hace falta una vista para imágenes.
- Antes de abrir, buscar si ya está abierto (`app.Documents` por `FullFileName`), para no duplicar.
- Enums: guardar las constantes numéricas con su nombre en comentario
  (`K_PART_DOCUMENT=12290`, `K_ASSEMBLY_DOCUMENT=12291`, `K_DRAWING_DOCUMENT=12292`, presentación 12293,
  vista frente 10764, superior 10754, derecha 10755, ISO 10759, estilo HLR 32258, "desde base" 32260,
  extrusión positiva 20993 / negativa 20994, unión 20481, corte 20482).
- Cuando no se conoce un miembro: **introspección de la typelib**:
  ```python
  ti = obj._oleobj_.GetTypeInfo(); ta = ti.GetTypeAttr()
  nombres = {ti.GetNames(ti.GetFuncDesc(i).memid)[0] for i in range(ta.cFuncs)}
  ```
- Las piezas no tienen `ComponentDefinition.Constraints`; preguntar `DocumentType` antes de iterar.
- Un `hasattr()` sobre objetos COM puede lanzar `com_error`; usar `S(lambda: obj.Prop)`.

### 2.1 Matrices (la base de todo lo de ensambles)

```python
def mread(m):  # Matrix de Inventor -> lista 4x4 en mm
    return [[m.Cell(r, c) * (10 if (c == 4 and r < 4) else 1) for c in range(1, 5)] for r in range(1, 5)]

def mmake(M):  # 4x4 en mm -> Matrix de Inventor
    m = tg.CreateMatrix()
    m.SetCoordinateSystem(tg.CreatePoint(M[0][3]/10, M[1][3]/10, M[2][3]/10),
                          tg.CreateVector(M[0][0], M[1][0], M[2][0]),
                          tg.CreateVector(M[0][1], M[1][1], M[2][1]),
                          tg.CreateVector(M[0][2], M[1][2], M[2][2]))
    return m
```
Se trabaja con listas Python (multiplicar, invertir rot+traslación) y sólo al final se convierte. Componer:
`mundo = T_padre · T_local`. Un componente se ubica con `Occurrences.Add(ruta, mmake(M))` y se mueve con
`occ.Transformation = mmake(M)`.

- Inventor usa **Y arriba** por defecto; si diseñás con Z arriba, aplicá al final
  `G = [[1,0,0,0],[0,0,1,0],[0,-1,0,0],[0,0,0,1]]`. El layout de ADECO usa **Z arriba**: siempre mirar las
  matrices reales en vez de suponer.

---

## 3. Flujo típico de un pedido

1. **Entender y relevar.** Abrir referencias en sólo lectura y volcar a JSON: componentes, archivo, matriz,
   caja envolvente, restricciones (tipo, valor), caras planas grandes y cilindros (candidatos a ejes/agujeros).
   Guardar imagen ISO. (`geometria_ref.py`, `relevar_adeco.py`, `analizar_robot.py`).
2. **Diseñar en Python** (sin Inventor): medidas, desarrollos de chapa, posiciones. Probar la cuenta localmente
   con los JSON relevados (se puede ejecutar la parte de cálculo de un script fuera de Inventor con datos stub).
3. **Construir** en Inventor con un script que reciba parámetros y escriba `resultado.json` (piezas creadas,
   masas, avisos, errores con traza).
4. **Verificar**: interferencias (`AnalyzeInterference`), envolvente, imagen ISO; mirarla.
5. **Entregar** PDF/DXF/XLSX/MP4 y dejar copia en la PC en `Generados\<nombre>\...`.
6. **Correcciones**: editar sobre lo generado (ver regla 2).

---

## 4. Piezas

### 4.1 Chapas (sheet metal) desde su desarrollo — `build_flat_part(app, spec, ipt, dxf)`
- El diseño se describe como `FlatPart`: contorno exterior (polilínea con *bulges* para arcos), contornos
  interiores (calados, logo), círculos, ranuras, líneas de plegado, espesor, material.
- Se dibuja la cara, se extruye con el espesor de la chapa y se pliega sobre las líneas de plegado.
- DXF de corte: desarrollo 1:1, sólo contorno de corte (capas de plegado/tangencia ocultas).
- Logos calados: no usar TextBox (fuente con islas que se caen); usar glifos tipo esténcil propios
  (polígonos con puentes) como contornos interiores.

### 4.2 Estructura (caños)
- `build_tube_part`: caño rectangular a×b×e, sección centrada, eje +Z.
- `build_frame_part`: marco soldado (montantes, largueros, travesaños, agujeros pasantes).
- Después de cada extrusión **verificar el sentido** con `RangeBox`; si salió para el otro lado, borrar
  la operación y extruir en sentido contrario.
- iProperties: `Part Number` (≤18 caracteres, entra en el cajetín), `Description`, material
  ("Acero, suave"…).

### 4.3 Piezas comerciales
- Se copian de proyectos existentes (cilindros Festo ADN, guías HIWIN) a `InventorIA\Comerciales` y se
  insertan desde ahí. Nunca se modelan.

---

## 5. Ensambles

### 5.1 Ubicación
- Calcular la matriz de cada componente en Python y `Occurrences.Add(ruta, matriz)`.
- Fijar (`Grounded=True`) lo que no se mueve.

### 5.2 Restricciones (cuando se piden)
- Inserción en agujeros coaxiales en contacto; coincidencia/nivelación de planos.
- El signo/convención de las restricciones de plano no es confiable: **calibrar**: crear con offset 0,
  medir el desplazamiento, probar candidatos y aceptar el que deja la pieza en la pose planificada.
- Restricción de mando con nombre (ej. "Apertura") para el mecanismo; probarla con todo el grupo móvil libre
  (moverla ±carrera y medir qué se mueve).

### 5.3 Copias de ensambles grandes
- Para simular sobre un layout de cliente: `Open(general)` → `SaveAs(copia)` → trabajar en la copia
  (ocultar lo que se reemplaza con `Visible=False`, agregar lo nuevo). El original queda igual.
- Un ensamble nuevo puede referenciar archivos existentes sin copiarlos (celda robot+base+gripper).

---

## 6. Planos (A4, una hoja por pieza)

Base: plantilla de dibujo del usuario (`GetTemplateFile(12292)`), hojas A4 apaisadas (`Size=9997`,
`Orientation=10242`), cajetín de la primera hoja copiado a las nuevas (`_new_sheet`).

### 6.1 Disposición
- Calcular el área útil: bordes + rectángulo del cajetín (`sheet.TitleBlock.RangeBox`). El cajetín está abajo
  a la derecha: la columna izquierda está libre hasta abajo.
- Elegir la escala normalizada más grande que entre (1:1, 1:2, 1:5, 1:10, 1:20, 1:25, 1:30, 1:40, 1:50).
- Piezas largas (caños): vista lateral con el eje horizontal (`kRightView` si el largo está en Z) + vista de
  punta ampliada (vista proyectada con `ScaleFromBase=False`).
- Marcos: frente + **vista de detalle** (`AddDetailView`, circular) de la esquina con el agujero.
- Isométrica como **vista base ISO** (`AddBaseView(..., 10759, ...)`); una proyectada en diagonal no siempre
  da ISO.
- Rótulos: ocultar el rótulo automático (`ShowLabel=False`) y poner una nota propia en negrita, donde no pise.
- Notas de pieza: renglones cortos (≈0,26 cm por carácter); bloque apoyado sobre el cajetín.

### 6.2 Cotas automáticas (lo que funcionó)
- Para encontrar la curva a acotar: `view.ModelToSheetSpace(punto_modelo)` da la posición en la hoja; buscar
  en `view.DrawingCurves` la línea vertical/horizontal en esa coordenada (tolerancia ~0,006 cm) que se superpone
  con el rango esperado.
- `GeneralDimensions.AddLinear(punto_texto, sheet.CreateGeometryIntent(curva1), ...curva2)`.
- **Verificar cada cota**: leer `dim.ModelValue*10` y compararlo con el valor esperado; si no coincide,
  borrarla y registrar el fallo.
- **Centro de un agujero**: `sheet.CreateGeometryIntent(circulo)` **sin** argumento de intención apunta al
  centro (los valores de `PointIntentEnum` fallan en 2025).
- Entre centros de dos agujeros: dos intents de círculo.
- Diámetros: `AddDiameter(punto, intent_circulo)`.
- Precisión: 0 decimales si es entero, 1 si no.
- Llamadas de soldadura: `LeaderNotes.Add(colección de 2 puntos, "FILETE a3<Br/>TODO ALREDEDOR")`.
- Conjuntos soldados (columna + base): subensamble con las mismas matrices que en el general; hoja con
  elevación, detalle del pie (unión soldada) y planta.

### 6.3 Plano de conjunto
- Planta acotada entre **ejes**: acotar entre las caras del mismo lado de dos columnas da la distancia
  entre ejes.
- Elevación con alturas; isométrica; lista de piezas (`PartsLists.Add`) en su propia hoja si no entra.

### 6.4 Exportar
- PDF con el add-in de PDF (`_export_pdf`), todas las hojas, todo en negro.
- Si el PDF/DWG está abierto en otro programa, guardar con otro nombre en vez de fallar.
- Mirar el PDF (rasterizar a PNG) antes de entregar.

---

## 7. Listas de materiales (Excel con openpyxl, del lado de la IA)
- Datos desde `resultado.json` del constructor (cantidades, masas, perfiles).
- Hojas: Resumen, Corte de caños (perfil, largo, cantidad, metros, barras de 6 m con fórmulas), Piezas
  (masa unitaria × cantidad con fórmulas), Herrajes, Bulonería.
- Fórmulas de Excel, no valores calculados, para que el usuario pueda editar.

---

## 8. Animaciones y simulación de robots

### 8.1 Método: un cuadro por paso
No se usan presentaciones (`.ipn`): en Inventor 2025 la API no permite crear escenas ni acciones del
storyboard, sólo leerlas.

En cambio:
1. Mover el modelo por API: valor de una restricción (`constraint.Offset.Value = v`) o
   `occurrence.Transformation = matriz`.
2. `doc.Update()` y `app.ActiveView.SaveAsBitmap(png, ancho, alto)`.
3. Repetir por cada cuadro (interpolación con curva coseno para que arranque y frene suave).
4. En la PC se comprimen los PNG en zip; la IA los trae y arma MP4 (ffmpeg, `-crf 18 -preset slow`) y GIF.
5. Al final restituir todos los valores (sin `Save`).

### 8.2 Calidad de imagen (configuración que quedó)
- 1920×1080.
- Vista: `ShowAmbientShadows`, `ShowObjectShadows`, `ShowGroundShadows` en True; `ShowGroundPlane` False.
- Iluminación: `doc.ActiveLightingStyle = doc.LightingStyles.Item("Luz suave")`.
- Ocultar planos de trabajo y bocetos (`doc.ObjectVisibility.AllWorkFeatures/UserWorkPlanes/OriginWorkPlanes/
  Sketches = False` y `WorkPlanes[i].Visible=False`), y rejas/paredes que tapen la vista (sólo durante el render).
- Cámara: `Target`, `Eye`, `UpVector` (Z arriba en ADECO), `Perspective=False`,
  `SetExtents(ancho_cm, alto_cm)`, `Apply()`. Probar con **1 cuadro** (`--max-cuadros 1`) antes del render
  completo.
- El modo "realista" (DisplayMode 8714) es un estilo tipo boceto: no sirve. El trazado de rayos tarda minutos por
  cuadro: inviable.

### 8.3 Gripper abriendo/cerrando
- Restricción de mando del módulo ("Apertura"): todas las cajas usan el mismo módulo → se mueven juntas.
- Averiguar sentido y carrera **midiendo**: cambiar el valor ±5 mm, medir el desplazamiento de la pala y la
  luz entre gomas, volver al valor original. Cerrar hasta el contacto con la caja, no hasta el fin de carrera.
- En un gripper ajeno sin restricción de mando: recorrer todas sus restricciones con offset, cambiar cada una
  5 mm y medir qué pieza se mueve y hacia dónde (`probar_palas_adeco.py`). Así se encontró la restricción interna
  del cilindro (cierra todas las palas) y las de cada pala (abren de a una).

### 8.4 Robot KUKA (KR 140 R3200-2 PA)
- El modelo son 5 sólidos (V01 base, V02 carrusel, V03 brazo, V04 antebrazo, V05 muñeca/brida), sin uniones.
- Ejes sacados de la geometría (cilindros grandes y coaxiales de cada eslabón), en coordenadas del ensamble
  del robot (Y arriba):
  - A1: eje Y por el origen;
  - A2: eje Z por (330, 645);
  - A3: eje Z por (338,02, 1994,98);
  - muñeca: eje Z por (1291,82, 1179,32). La brida se mantiene horizontal hacia abajo (paralelogramo):
    a V05 se le aplica −(q2+q3) y una corrección fija φ0 = −46,46° para que mire hacia abajo;
  - A6: giro del gripper sobre el eje vertical de la brida.
- Cinemática directa (`celda_kin.poses`): cada eslabón = T_robot · R1 · R2(@A2) · R3(@A3) · … · M_original.
- **Cinemática inversa**: de la pose deseada del gripper se calcula la brida; q1 = atan2 en planta; la
  muñeca = brida − offset fijo; q2 y q3 por el triángulo de dos eslabones (codo como en el modelo); q6 por la
  dirección del eje X del gripper. Verificar con la directa (error < 5–7 mm).
- Montaje del gripper: centro de la cara de la brida del gripper sobre el centro de la brida del robot; su eje
  "arriba" hacia el robot; PCD 160 coincide.
- Ubicación del robot: usar la matriz del robot en el layout del cliente (si la base trae otro pie del robot,
  avisar de la diferencia).

### 8.5 Paletizado
- Patrón: sacado del ensamble del pallet completo (posiciones de cada bandeja). Normalizar cada bandeja a un
  marco canónico (centro del cuerpo, Y local hacia arriba), porque algunas están dadas vueltas.
- Pick: posiciones de las bandejas detenidas contra el tope en el layout.
- Al tomar: `B_rel = inv(G_toma) · B_bandeja`; mientras se lleva, `B = G_actual · B_rel`.
- Al dejar: `G = B_destino · inv(B_rel)`, probando también la bandeja girada 180° y anclando por la primera o la
  última de la fila; elegir la que mejor ubica toda la fila.
- **Evitar choques**: orden por piso = primero las bandejas giradas, después columnas alejándose de ellas; elegir
  la orientación del gripper con las **palas móviles hacia el lado libre** y la pala fija contra lo apilado.
- Dejar de a una (bandejas sueltas): tomar con palas independientes y abrir sólo la de esa bandeja.
- Entrada de bandejas: deslizar a lo largo de la cinta hasta el tope mientras el robot deja.

---

## 8.6 Grippers livianos y bridas de otros robots
- Cuando el robot es chico (KR 30, carga 30 kg), sumar gripper + caja y comparar con la carga admisible
  **antes** de construir. Estimar la masa de las chapas en Python (área del desarrollo − agujeros − hexágonos ×
  espesor × 7,85 g/cm³) y probar variantes: alas más cortas, alivianar alma y brida, brida más fina, palas más bajas.
- La pala fija **no se aliviana** y no baja de 3/16" si la caja es alta (flexión).
- Patrón de la brida del robot: buscar un modelo del robot o de su familia en la PC (`buscar_archivos.py`) y relevar
  los agujeros con `analizar_brida_kr.py` (grupos de círculos iguales y coplanares a igual distancia de un centro).
  Registrar el patrón en `ROBOT_BRIDAS` con una nota de qué modelo se usó; decir al usuario qué hay que confirmar.
- Si un módulo de referencia se usó para animaciones, puede haber quedado "movido": normalizarlo midiendo una
  referencia fija (agujeros de los bloques) antes de copiar posiciones. Síntoma: `agujeros_ok = 0` en el registro de
  la pala y piezas cruzadas en la imagen.

## 9. Comunicación con el usuario
- Al empezar: una frase con lo que se va a hacer. Si el trabajo es largo, avisar el tiempo estimado.
- Mostrar primero una prueba chica (un cuadro, una hoja) si el resultado es caro de rehacer.
- Al entregar: qué se hizo, dónde quedó en la PC, y supuestos/pendientes en pocas líneas (ej. interferencias del
  modelo de muestra, medidas supuestas, choques que no se controlan).
- No decir que algo funciona sin haber mirado la imagen/PDF.

---

## 10. Lista de scripts (carpeta `scripts\`)

| Script | Qué hace |
|---|---|
| `vigilante.py` / `.bat` | Ejecuta los pedidos de `_pedidos` |
| `construir_gripper.py` | Gripper paramétrico completo (chapas, módulos, restricciones, ensamble) |
| `planos_gripper.py` | Paquete de fabricación de chapas (planos A4, DXF, conjunto) |
| `retocar_plano.py` | Edita un plano existente (escala, mover vistas, notas, reacomodar) |
| `construir_reja.py` | Reja desde planta (poligonales, aberturas, portón corredizo) |
| `planos_reja.py` | Planos de reja: piezas, conjuntos soldados, planta acotada, elevación, lista |
| `animar_gripper.py` | Video de apertura/cierre del gripper |
| `analizar_robot.py`, `analizar_brida.py` | Relevamiento del robot y bridas |
| `celda_kin.py` | Cinemática del KUKA |
| `armar_celda.py`, `animar_celda.py` | Celda robot+base+gripper y su animación |
| `paletizar_celda.py` | Paletizado de prueba en la celda |
| `relevar_adeco.py`, `relevar_gripper_adeco.py`, `probar_palas_adeco.py` | Relevamiento del layout ADECO |
| `paletizar_adeco.py` | Simulación de paletizado en el layout ADECO |
| `probar_calidad*.py` | Pruebas de calidad de imagen |
| `partir_zip.py` | Divide los cuadros en zips < 350 MB |
| `geometria_ref.py`, `buscar_archivos.py`, `listar.py`, `copiar_comerciales.py` | Utilidades |
| `analizar_brida_kr.py` | Patrón ISO 9409 de la brida de un robot a partir de su modelo (STEP importado) |
| `vistas_ensamble.py` | Imágenes de un ensamble con cámara libre (`--arriba`, `--dirs="x,y,z;..."`) |
| `diag_modulo.py` | Diagnóstico de posiciones y agujeros de un módulo de pala móvil |

---

## 11. Errores típicos y su solución

| Síntoma | Causa | Solución |
|---|---|---|
| El vigilante "no responde" | Trabajo largo (el latido se actualiza entre pedidos) o un diálogo de Inventor | Esperar el resultado; si no aparece, cerrar el diálogo y reabrir `vigilante.bat` |
| Un `.json` de datos se ejecutó como pedido | El vigilante toma todo `*.json` | Datos como `.txt` |
| Se ejecutó la versión vieja del script | El pedido llegó antes que el script, o caché del puente | Copiar script primero, verificar, después el pedido |
| Pieza extruida al revés | Sentido de extrusión según el boceto | Verificar con `RangeBox` y reextruir |
| Restricción deja la pieza dada vuelta | Convención de signo | Calibrar con offset 0 y medir |
| Cota a un centro falla | `PointIntentEnum` no anda | Intent del círculo sin argumento |
| Isométrica sale de canto | Proyectada en lugar de ISO | Vista base ISO (10759) |
| Textos y vistas superpuestos | Disposición fija | Calcular área útil, notas sobre el cajetín, rótulos propios |
| Bandejas/cajas dadas vuelta al dejar | Origen de la pieza en una cara, ejes invertidos | Marco canónico (centro, Y arriba) |
| Gripper choca al dejar | Lado de las palas móviles | Palas móviles hacia el lado libre; orden de dejada |
| Video vertical | Orientación del modelo | Rotar cuadros o fijar `UpVector` de la cámara |
| Zip > 400 MB | Full HD con sombras | `partir_zip.py` |
