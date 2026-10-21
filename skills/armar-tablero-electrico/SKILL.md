---
name: "armar-tablero-electrico"
description: "Arma el tablero eléctrico de un equipo/biorreactor: preguntas, presupuesto de potencia, protecciones, lista de materiales en Drive, diagramas, notas de armado y subagentes de revisión."
---

# ArmarTableroElectrico

Idioma: español rioplatense. Mensajes cortos, costo ajustado. Un tablero por equipo salvo que se pida lo contrario (los tableros no se conectan entre sí). Empezar con una frase de qué se hará y usar lista de tareas; el último paso es verificar.

## 1. Preguntas (AskUserQuestion; primero lo que cambia el diseño)
- Cuántos equipos/tableros y cuántos hay que cotizar.
- Red: 220 V, térmica y diferencial existentes en el laboratorio.
- Cargas por equipo: potencia, tensión y corriente (tiras LED, electroválvula, baliza, HMI, sensores).
- Una fuente o varias; tensión de lógica (preferir una sola de 12 V si alcanza).
- Qué va por transistor/MOSFET (PWM) y qué por relé de interfaz (solo ON/OFF de válvula o baliza).
- Sensor de corriente sí/no; comunicación (UTP/RS485, CAN sí/no, Wi-Fi); HMI por equipo.
- Encendido ON/OFF con enclavamiento (relé KA0, pulsadores ON NA / OFF NC) y parada de emergencia sí/no.
- Tamaño de gabinete y si ya hay cotización; presupuesto y tope (USD y tipo de cambio).

## 2. Arquitectura de referencia (rev C, un tablero por biorreactor, ~300×300×150 mm)
Térmica 2P 6 A → fuente Mean Well LRS-150-12 (12 V, 12,5 A) para lógica y tiras → rama de lógica con fusible 5×20 T3,15 A lento → relé KA0 MY2N-J 12 VDC (retiene el ON y da MARCHA 12 V) → placa de E/S propia → HMI Waveshare ESP32-S3-Touch-LCD-7 en la puerta. Tiras por fusible 25 A + SSR de CC 25 A (MOSFET, Ron ≤ 10 mΩ; lo cierran MARCHA y SSR_EN). Sin CAN, sin switches DIP, sin sensor de corriente Hall, sin M12, sin fuente de 24 V. UTP solo hacia el sensor RS485.
Usar esto como punto de partida y justificar cada desvío.

## 3. Cálculos (mostrarlos)
- Presupuesto de potencia por tablero (ej.: luminaria de 1,3 m ≈ 18 W = 1,5 A a 12 V; 5–6 luminarias + válvula 1 A + lógica 0,7 A ≈ 9–11 A de 12,5 A).
- Cable: 0,75 mm² ramales, 4 mm² troncos, 2,5 mm² para el retorno en la bornera de GND (J13).
- Fusibles coordinados: 25 A DC al SSR; ramal de lógica T3,15 A lento; polyfuse 1,5 A en la placa; térmica 2P 6 A curva C (D si salta al arrancar).
- Un solo punto de negativo (el − de la fuente) y un solo camino de retorno; corriente por pin de bornera.
- Qué pasa con un corto en una tira: la fuente limita, la placa se reinicia y el SSR abre. Dejarlo como prueba de puesta en marcha.

## 4. Checklist de protecciones y seguridad
- El SSR abre sin MARCHA o con el ESP32 en reset.
- Baliza con el + tomado antes del SSR.
- Electroválvula NC con diodo de rueda libre montado en la bobina y sin PWM en ese canal.
- Clamps en entradas ADC; 220 Ω en serie en la UART de la HMI; TX de la HMI a 3,3 V.
- Un solo negativo de entrada; sin portafusible duplicado en placa.
- Tierra de protección (PE) en gabinete y fuente; bornes y cables rotulados; pulsadores ON NA / OFF NC.

## 5. Lista de materiales en Drive
- Editar SIEMPRE el archivo existente (mismo link). Escribir con `update_values` (nunca `append_values`) y sin el parámetro `valueInputOption` (da HTTP 400).
- Antes de cada escritura, leer y confirmar el número de fila (una vez se pisó una fila por error).
- Precios nuevos = estimados: celda H en amarillo (rojo 1, verde 0,9411765, azul 0,8) + K = "Sí"; fórmulas I = H*A y J = I*'Fuentes de precios'!B1.
- Actualizar Resumen y Notas de ingeniería con fecha y revisión.
- Informar total, parte estimada y margen contra el tope, con palancas de recorte (SSR de 10–15 A, térmica genérica, descontar monitores ya comprados, cotizar cajas). Avisar piezas sin código y precios por confirmar.

## 6. Diagramas y entregables
- Esquema general por capas: alimentación, encendido/marcha/SSR, potencia 12 V, control, campo; con fotos de referencia.
- Conexionado de la placa y de la HMI (usar la skill crear-placa).
- Página artefacto HTML (misma URL si ya existe) + PDF A3 apaisado con Playwright, enviado con SendUserFile.
- Notas de armado y puesta en marcha paso a paso: sin ESP32/SSR, continuidad V12F–GND (no debe haber corto); 12 V con la fuente limitada a 1 A; medir 5 V y 3,3 V; MARCHA (≈3,75 V en la compuerta de QA); SSR con LED3; corto de prueba en una tira; medir corriente de entrada con la HMI a pleno brillo.

## 7. Subagentes de revisión (independientes, no editan)
Reportan ERROR / MEJORA / OK, máximo 500 palabras, en paralelo:
1. **Eléctrico/potencia:** cargas, cables, fusibles, selectividad, retorno, caídas.
2. **Seguridad/normativa:** térmica, diferencial, PE, bornes, separación de 220 V y 12 V.
3. **Lista de materiales:** cantidades contra el esquema, estimados marcados, totales y fórmulas.
4. **Documentación:** consistencia de textos y diagramas con la revisión vigente.
Corregir y re-verificar con el mismo subagente (SendMessage).

## 8. Entrega
Resumen corto: total y margen contra el tope, qué quedó estimado, qué depende del usuario (cotizaciones, mediciones, cables) y un próximo paso.