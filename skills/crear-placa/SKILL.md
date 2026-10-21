---
name: "crear-placa"
description: "Crea una placa PCB (KiCad 7) desde especificaciones: netlist en Python, ruteo sin pistas a 90°, esquemático por hojas, diagramas de conexión y 3 subagentes de verificación."
---

# CrearPlaca

Idioma: español rioplatense. Mensajes de estado cortos. Costo y tokens ajustados. Empezar con una frase de qué se va a hacer y llevar lista de tareas (TaskCreate/TaskUpdate); el último paso es siempre verificar.

**REGLA FIJA DEL USUARIO:** ninguna pista a 90° en ninguna placa. Solo chaflanes de 45°, incluidas las uniones en T (la rama entra al tronco a 45°). No se negocia ni se deja "para después".

## 1. Relevamiento (antes de tocar nada)
Preguntar con AskUserQuestion, de a pocas preguntas y primero lo que cambia el diseño:
- Tensión(es) de entrada, fuente y corriente disponible.
- Cargas y corrientes (típica y máxima) por canal; cuántos canales PWM, ON/OFF, ADC.
- MCU/módulo y pines reservados (strapping, USB, PSRAM, UART de log).
- Comunicaciones: RS485, UART a HMI, USB, CAN sí/no. Si hay dos placas, si se conectan entre sí o no.
- Conectores: paso, polos, corriente por pin, sección de cable; qué bornera lleva el retorno de potencia.
- Tamaño, tornillos de montaje, muescas de antena; capas y cobre; fabricante (JLCPCB/PCBWay).
- Presupuesto.
- Protecciones: fusible/polyfuse, TVS, polaridad, rueda libre en cargas inductivas, clamps en entradas ADC.
- Un solo punto de negativo de entrada (evitar dos caminos de retorno).
- Pads de prueba (12V, 5V, 3V3, GND, TX0, RX0) y rótulos de serigrafía en español.
Cuentas a mostrar: corriente por pin de bornera, ΔI y fsw del buck, divisores y niveles ADC, dimensionado de fusible con 0,8× por temperatura, caída del retorno de GND.

## 2. Diseño como código (fuente de verdad)
- `design.py`: `add(ref, huella, valor, x, y, rot, {pin: red}, mpn)` con huellas de /usr/share/kicad/footprints; redes con nombre; `params.json` (ancho, alto, muesca).
- Bornes con los pines hacia el borde. Nunca editar la placa a mano sin llevar el cambio a design.py (si no se pierde al regenerar).
- Al quitar un bloque, revisar huérfanos: desacoples, pull-ups, redes, designadores reutilizados.
- Usar b.Delete(), nunca b.Remove() en pcbnew (segfault).

## 3. Ruteo
1. `route.py`: design → clases de red (proset.py) → DSN con las reglas insertadas ANTES de `(boundary` (si van dentro de `(structure` freerouting falla con "layers missing") → freerouting 1.9.0 con `xvfb-run -mp 40 -mt 1 -oit 0.1` → SES.
2. Correr freerouting en segundo plano (nohup) y revisar por polling con sleeps ≤ 9 min (≈3–4 min de ruteo + 45 s de optimización). Si no aparece el SES en ~5 min con CPU en 0 %, matar y relanzar.
3. `post.sh`: proset → costura de GND (stitch) → islas de GND → chaflanes → neck-down → relleno de zonas → **corner45.py** → corner45 --check → arreglos manuales (CC2 de USB a 45°, TXD0, etc.) → drc.py. Los límites de vías e islas salen de params.json (contorno y muesca de antena).
4. corner45.py: elimina esquinas simples y uniones en T a 90°, parte tramos cuyo extremo cae a mitad de otro (split_mid), limpia microtramos < 0,06 mm y respeta separaciones. `--check` sale con 1 si queda alguna.
5. Reglas de fabricación (JLCPCB 2 capas): pista ≥ 0,15 mm, separación ≥ 0,15 (clase 0,2), vía 0,6/0,3, agujero ≥ 0,3, borde ≥ 0,3. Potencia con pistas anchas o plano de GND; ir.py calcula la caída del retorno con la corriente máxima.

Si los scripts de una placa anterior existen (p. ej. /home/claude/pcb_revC/), reutilizarlos; si no, reescribirlos con esta misma lógica.

## 4. Verificaciones propias (antes de llamar a los subagentes)
- DRC con pcbnew (`WriteDRCReport`, KiCad 7 CLI no tiene DRC): 0 en clearance, shorting, unconnected, track_width, hole, annular, copper_edge, dangling. Silk/courtyard aceptables solo si no hay choque físico.
- `corner45.py --check` = 0 esquinas.
- ir.py con la corriente máxima: caída del retorno en mV y W.
- Esquemático ↔ placa con sch_check.py = PASS (comparación de pads por red, refs, valores y huellas).

## 5. Esquemático jerárquico (nunca "una caja por componente")
Generado desde design.py (misma netlist que la placa), con símbolos reales de las librerías de KiCad y cables dentro de cada bloque; etiquetas solo entre hojas; notas de cálculo en español. Hojas: raíz (bloques), entrada y protección, buck, LDO y desacople, MCU, USB, salidas (una hoja por borne de 4 canales), mando/MARCHA/SSR, comunicación (RS485 y UART HMI). KiCad 7 no tiene ERC: la validación es sch_check.py. Exportar `io_board.pdf` y PNG por hoja y revisarlos visualmente.

## 6. Diagramas de conexión (como la última vez)
Generar con scripts SVG → PNG/PDF:
- (a) Diagrama de conexionado eléctrico de la placa: alimentación, cadena de maniobra, buck/LDO, transceptores, ESP, MOSFET y retorno, con leyenda y notas.
- (b) Vista superior con los bornes reales, en orden físico, de izquierda a derecha como se mira la placa.
- (c) Conexionado de la HMI (UART, alimentación, nivel de TX 3,3 V).
- (d) Tablas de conectores y de señales (GPIO ↔ función).
- (e) Lista de pendientes por verificar.
Publicar como artefacto HTML claro (misma URL si ya existe) y PDF A3 apaisado con Playwright; entregar con SendUserFile. Los diagramas deben reflejar la revisión vigente de la placa.

## 7. Subagentes de verificación (tres, independientes)
Cada uno lee el proyecto y corre sus propios scripts; NO edita nada. Reportan ERROR / MEJORA / OK, máximo 500 palabras. Se lanzan en paralelo.
1. **Eléctrico:** huérfanos y terminaciones, corriente por borne, strapping pins, divisores/ADC, protecciones (orden fusible → TVS), polaridad, un solo camino de retorno, coordinación de fusibles, niveles lógicos 3,3/5 V.
2. **Ruteo:** busca ángulos de 90° con script propio (incluye T a mitad de tramo y microtramos), corre el DRC, plano de GND y cuellos de cobre, ancho de pistas de potencia, vías fuera del contorno, muesca o keepout de antena, pistas de alta frecuencia/USB.
3. **Disposición de la placa y fabricación:** ubicación de componentes (conectores en bordes, desacoples junto a pines, bucles de corriente cortos, separación potencia/señal, antena libre), tornillos de montaje, serigrafía legible y sin superposiciones, Gerber/BOM/CPL coherentes (todas las refs, rotaciones, LCSC faltantes, excluir H* y TP*), esquemático ↔ placa (sch_check) y prueba negativa del chequeo.
Aplicar las correcciones y pedir re-verificación al mismo subagente con SendMessage hasta que diga OK.

## 8. Entrega
Zip con kicad/ (pcb, pro, sch), fab/ (Gerber, BOM, CPL), esquemático PDF, vista PNG, NOTAS de armado y cambios, scripts. Decir con claridad qué quedó sin verificar (códigos LCSC, rotaciones del CPL, pines de la HMI, etc.) y qué depende del usuario fuera de la placa.