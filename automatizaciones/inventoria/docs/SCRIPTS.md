# Índice de scripts

Todos están en `inventor-assistant-portable/scripts/` (y la librería en `server/`).
Se ejecutan con `.venv\Scripts\python.exe scripts\<script>.py [args]`, o por pedido al vigilante.
Los `relevar_*`, `analizar_*`, `diag_*` y `fotos_*` son **sólo lectura**.

## Simulación y animación

| Script | Qué hace |
|---|---|
| `scripts/animar_celda.py` | Anima la celda (robot + gripper) moviendo los eslabones por cinemática (celda_kin) y abriendo/cerrando el gripper con la restricción "Apertura" del módulo. Captura un cuadro por paso. No guarda cambios en el modelo. |
| `scripts/animar_gripper.py` | Animación de apertura/cierre de un gripper YA GENERADO (no crea ni guarda piezas). |
| `scripts/armar_celda.py` | Arma la celda robot + base + gripper como ensamble NUEVO que sólo referencia archivos existentes: - base_principal_circular.iam (ya trae el pie del robot, V01) |
| `scripts/armar_newpack.py` | Escena de simulación NewPack2 (COPIA; los originales no se tocan). |
| `scripts/celda_kin.py` | Cinemática simple del KUKA KR 140 R3200-2 PA (modelo del proyecto ADECO2) para ubicar eslabones y gripper. |
| `scripts/paletizar_adeco.py` | Simulación de paletizado en el layout ADECO2 (2 pisos del patrón de Pallet_Completo). |
| `scripts/paletizar_celda.py` | Prueba de paletizado en la celda KR 140 + gripper 4x12 kg. |
| `scripts/partir_zip.py` | Divide los cuadros de una carpeta en varios zip de menos de ~350 MB cada uno. Uso: python partir_zip.py <carpeta_cuadros> <prefijo_salida> |
| `scripts/partir_zip_existente.py` | Parte un zip de cuadros existente en varios zip de menos de ~350 MB (sin descomprimir a disco). Uso: python partir_zip_existente.py <zip_origen> <prefijo_salida> |
| `scripts/simular_newpack.py` | Simulación NewPack2 sobre la escena COPIA (Generados\NEWPACK2_SIM\NewPack2_simulacion.iam; ver armar_newpack.py). |

## Diseño y construcción

| Script | Qué hace |
|---|---|
| `scripts/calc_gripper.py` | Dimensiona un gripper de apriete y escribe la memoria de cálculo. |
| `scripts/construir_chapas.py` | Genera las chapas de un gripper nuevo en Inventor a partir del diseñador (gripper_design). |
| `scripts/construir_ensamble.py` | Arma el ensamble de un gripper generado tomando como referencia el ensamble de ADECO2 (copia). |
| `scripts/construir_gripper.py` | Gripper de apriete de N cajas DESDE CERO: diseño → chapas y gomas → módulo de pala móvil → ensamble con restricciones (sin neumática; con cilindros ADN, guías HIWIN y tuercas del vástago). |
| `scripts/construir_gripper6.py` | Gripper de 6 paquetes (DosHermanos): apriete a lo largo del eje de los paquetes, pala fija central y 2 palas móviles exteriores con Festo DSNU-10-25 y guías miniatura MGW (las del proyecto). Cilindros POR DENTRO, bajo el |
| `scripts/construir_reja.py` | Reja perimetral cuadrada con portón corredizo (prueba del generador de rejas). |
| `scripts/copiar_comerciales.py` | Copia piezas comerciales (sin modificarlas) a Documents\InventorIA\Comerciales\<destino>. Uso: python copiar_comerciales.py <carpeta_origen> <destino> <archivo1> [archivo2 ...] |
| `scripts/copiar_plantilla.py` | Copia un gripper existente a una carpeta de trabajo y verifica sus referencias. |
| `scripts/empaquetar_ensamble.py` | Deja un ensamble AUTOCONTENIDO: copia a <carpeta base>\Comerciales todos los archivos que referencia (en cualquier nivel) que estén fuera de la carpeta base, y repunta las referencias a esas copias. Los originales no |
| `scripts/make_chapa_c.py` | Genera la chapa plegada en C, su DXF de corte y el plano de fabricación. |
| `server/gripper_calc.py` | Dimensionamiento de grippers por apriete lateral (DEFYMOTION). |
| `server/gripper_design.py` | Diseñador de grippers de apriete (DEFYMOTION): de la caja al desarrollo de cada chapa. |

## Planos

| Script | Qué hace |
|---|---|
| `scripts/planos_gripper.py` | Genera planos (PDF), DXF de corte y plano de conjunto del ensamble ACTIVO en Inventor. |
| `scripts/planos_reja.py` | Planos de fabricación de una reja generada con construir_reja.py. |
| `scripts/probar_cotas.py` |  |
| `scripts/retocar_plano.py` | Retoca un plano existente sin regenerarlo (o solo lista su contenido). |

## Relevamiento y diagnóstico

| Script | Qué hace |
|---|---|
| `scripts/analizar_brida.py` | Sólo lectura: cara de montaje de la brida del robot (eslabón V05) y de la brida del gripper. Salida: Documents\InventorIA\Analisis\bridas.json |
| `scripts/analizar_brida_kr.py` | Sólo lectura: busca el patrón de la brida de montaje (ISO 9409) en un modelo de robot (.ipt/.iam de STEP). Agrupa los agujeros circulares coplanares y equidistantes de un centro (círculo de agujeros) y lista los |
| `scripts/analizar_robot.py` | Relevamiento (sólo lectura) del robot KUKA, la base del robot y su ubicación en el ensamble general ADECO2. |
| `scripts/buscar_archivos.py` | Busca archivos CAD por patrón (sólo lectura) en Documentos y Escritorio/Descargas. Uso: python buscar_archivos.py "ADN-32" ["HNA-32" ...] |
| `scripts/diag_calidad.py` | Diagnóstico (sólo lectura): opciones de calidad de imagen de Inventor y si hay Pillow en el .venv (--instalar: lo instala con pip). |
| `scripts/diag_centrador.py` | Diagnóstico (sin guardar) del centrador de la escena NewPack2: cajas en el MUNDO de las piezas de los pistones con la chapa en su lugar y corrida, y de los hijos de los cilindros (para mover vástagos). |
| `scripts/diag_chapa.py` | Diagnóstico (sin guardar): por qué la chapa de los pistones no se mueve en la escena NewPack2. |
| `scripts/diag_chapa2.py` | Diagnóstico (sin guardar): mover la chapa de los pistones a través del PROXY (Tope_pistones es flexible). Primero cierra sin guardar la escena NewPack2 (quedó con 'flexible' apagado en memoria) y la vuelve a abrir. |
| `scripts/diag_modulo.py` | Sólo lectura: cajas de las ocurrencias de un módulo y círculos verticales de bloques / empuja pala / pala. |
| `scripts/fotos_ensamble.py` | Fotos (sólo lectura) de un ensamble: ISO, frente, lateral, superior e ISO desde abajo. Restituye la cámara. Uso: python fotos_ensamble.py "<iam>" <carpeta_salida> [prefijo] |
| `scripts/geometria_ref.py` | Relevamiento geométrico de piezas de referencia (sólo lectura). |
| `scripts/inspect_assembly.py` | Analiza un ensamble de Inventor sin modificarlo. |
| `scripts/listar.py` | Lista archivos de una carpeta (sólo lectura). Uso: python listar.py <carpeta> [profundidad=3] |
| `scripts/probar_apertura.py` | Prueba el mecanismo del módulo: cambia la restricción "Apertura" (carrera del cilindro) y mide cuánto se mueven la pala, la goma, los bloques, la placa de empuje y el vástago. Deja todo como estaba (no guarda). |
| `scripts/probar_calidad.py` | Prueba de calidad de imagen sobre la escena de simulación ADECO (no guarda nada). Lista las opciones de visualización disponibles en la API y renderiza el mismo cuadro con distintas |
| `scripts/probar_calidad2.py` | Segunda prueba de calidad (no guarda): sombras de la vista, estilo de iluminación y modos de visualización. |
| `scripts/probar_palas_adeco.py` | Sólo en memoria (no guarda): cómo se mueven las palas móviles del gripper ADECO2. - componentes de pala_movil_apriete (caja en coordenadas del gripper) |
| `scripts/probar_presentacion.py` | Sondeo de la API de presentaciones (.ipn) de Inventor: qué objetos y métodos expone esta versión. Crea una presentación temporal de la escena de paletizado (no la guarda) y lista los miembros de cada objeto |
| `scripts/probar_privado.py` | Prueba del Inventor privado: a qué Inventor se conecta, si está oculto y si puede sacar imágenes sin ventana (vista activa y cámara transitoria). Sólo lectura: no guarda nada. |
| `scripts/radiografia_piezas.py` | Radiografía de piezas del ensamble ACTIVO: bocetos con sus cotas (nombre, expresión, valor), parámetros, operaciones y patrones. No modifica nada. |
| `scripts/relevar_activo.py` | Relevamiento (SÓLO LECTURA) del ensamble ACTIVO en Inventor: ruta, proyecto, componentes de primer y segundo nivel (archivo, matriz, caja, visibilidad, fijo), restricciones con su valor, parámetros, representaciones y |
| `scripts/relevar_adeco.py` | Sólo lectura: componentes de nivel superior del ensamble general ADECO2 (archivo, matriz, caja) + cajas envolventes de piezas sueltas útiles (caja, pallet) + PDFs que parezcan patrones de paletizado. |
| `scripts/relevar_comercial.py` | Relevamiento SOLO LECTURA de piezas/ensambles comerciales (cilindros, guías, robots): caja de cada pieza, agujeros (círculos de aristas) con centro, normal y diámetro, caras cilíndricas grandes (ejes) y masa. |
| `scripts/relevar_doshermanos.py` | Relevamiento SOLO LECTURA del layout DosHermanos (no guarda nada). - Layout: componentes de 1er nivel (archivo, caja, color), dónde está el/los gripper y los paquetes. |
| `scripts/relevar_gripper_adeco.py` | Sólo lectura: gripper de bandejas de ADECO2 y patrón del pallet completo. - Gripper_ADECO2_V1.iam: componentes (archivo, caja, fijo), restricciones (tipo, valor), parámetros, caras planas |
| `scripts/relevar_newpack.py` | Relevamiento detallado (sin guardar) de la celda NewPack2 abierta en Inventor: - gripper: componentes (cajas en el MUNDO), restricciones con valores y PRUEBA de cada restricción con desfase o |
| `scripts/transformaciones.py` | Extrae la posición y orientación (matriz 4×4) y la caja envolvente de cada componente del ensamble ACTIVO y de sus subensambles (2 niveles). No modifica nada. |
| `scripts/vistas_ensamble.py` | Imágenes de un ensamble con cámara libre (sin modificar el ensamble). Uso: python vistas_ensamble.py "<ensamble.iam>" --arriba 0 0 -1 --dirs="1,-1,-0.8;-1,1,-0.8" [--ancho 1600 --alto 1000] |

## Infraestructura

| Script | Qué hace |
|---|---|
| `scripts/proyecto_copia.py` | Activa el proyecto (.ipj) de una copia de trabajo y verifica que el gripper use solo la copia. |
| `scripts/reiniciar_vigilante.py` | Reinicia el vigilante (para que tome una versión nueva de vigilante.py) sin intervención del usuario. Lo lanza el propio vigilante como pedido: deja el resultado, marca el pedido como hecho, abre un vigilante nuevo |
| `scripts/test_create_box.py` | Prueba de humo del servidor: conecta con Inventor y crea una caja paramétrica. |
| `scripts/vigilante.py` | Vigilante: ejecuta pedidos que Claude deja en Documents\InventorIA\_pedidos. |
| `server/inventor_mcp.py` | Inventor Assistant — servidor MCP para Autodesk Inventor (COM, Windows). |
| `scripts/verificar_instalacion.py` | Verifica que esta PC esté lista (Python, paquetes, carpetas, vigilante, COM con Inventor, modelos base). |

