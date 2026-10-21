# 📏 Convenciones DEFYMOTION

Lo que toda skill y automatización respeta, salvo que el pedido diga otra cosa.

## Comunicación
- Español rioplatense, mensajes cortos.
- Empezar con una frase de qué se va a hacer; terminar con qué salió, dónde quedó y qué falta.
- Preguntar primero lo que cambia el diseño, con opciones.

## Unidades y planos
- Milímetros.
- Hojas A4, todas en un mismo archivo de dibujo y un solo PDF.
- Escala normalizada máxima; DXF de corte 1:1 por chapa; sin cotas de radio de plegado.

## Método
1. **Nunca tocar originales**: se trabaja sobre copias.
2. **Editar, no regenerar.**
3. **Todo por script**, con argumentos y un `resultado.json`.
4. **Medir antes de suponer**; mirar la imagen, el PDF o el cuadro antes de decir que funciona.
5. **Primero en chico**: 1 imagen → 1 cuadro → tramo → completo.
6. **Verificar al final** y, en trabajos grandes, con subagentes independientes que no editan.

## Mecánica (grippers de apriete lateral)
- Una pala fija y una pala móvil por caja; cilindros Festo y guías HIWIN por dentro del chasis.
- Chasis en C, brida en U invertida, chapa plegada con soldadura mínima.
- Cálculo: `F = m·(g + a)·FS / (2·μ)` con 8 bar, μ = 0,4, FS = 2, a = 5 m/s². Verificar la carga del robot con gripper + producto.

## Videos
- 1920×1080 horizontal (o 1080×1920 vertical).
- "Luz suave", sombras, sin plano de suelo, cámara ortográfica, planos de trabajo ocultos.

## Electrónica
- Ninguna pista a 90° (sólo 45°).
- Un solo punto de negativo de entrada y un solo camino de retorno.
- Rótulos de serigrafía y notas en español.

> ⚠️ Todo cálculo es preliminar hasta que lo aprueba un ingeniero responsable.
