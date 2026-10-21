# Simulaciones y videos: receta concreta

Complementa `Guia_IA_Inventor.md` (§11–§14). El método general está explicado ahí; acá están **los comandos
exactos, los tiempos y cómo adaptar el simulador a un proyecto nuevo**. Ejemplo de referencia: celda **NewPack2**
(KUKA KR 140, gripper de cajas con garras de pallet, almacén de pallets, centrador con cadenas y pistones, cinta
de entrada), resuelta con `armar_newpack.py` + `simular_newpack.py`.

---

## 1. Piezas del sistema

| Archivo | Rol |
|---|---|
| `scripts/armar_<proyecto>.py` | Arma la **escena copia** y escribe `escena.json` con las matrices base. Se corre una vez; los flags extra la completan |
| `scripts/simular_<proyecto>.py` | Anima la escena, guarda los cuadros PNG y el zip, y escribe `resultado.json`. Es **determinístico** |
| `scripts/celda_kin.py` | Cinemática directa del KUKA KR 140 (ejes relevados del modelo) |
| `scripts/partir_zip.py`, `partir_zip_existente.py` | Parten los cuadros en zips de menos de 350 MB para traerlos por el puente |
| Del lado de la IA | `unzip`, hoja de contacto con Pillow y `ffmpeg` para armar el MP4 |

Salida en la PC: `Documents\InventorIA\Generados\<PROYECTO>_SIM\`, con la escena `.iam`, `escena.json` y
`Animacion\` (cuadros, cuadros.zip, resultado.json, fotos de prueba y MP4 final).

## 2. Proyecto nuevo, paso a paso

1. **Relevar el layout** (sólo lectura) con `relevar_activo.py --nombre <PROY>` o un `relevar_<proy>.py` propio.
   - Robot, gripper, almacén, centrador, cintas, pallets y producto: archivo, matriz, caja, restricciones.
   - Qué subensambles son **flexibles**.
   - Topes y caras de apoyo reales.
   - Guardar el resultado en `Analisis\<PROY>\`.
2. **Copiar los scripts de NewPack2 como plantilla:** `armar_newpack.py` → `armar_<proy>.py` y
   `simular_newpack.py` → `simular_<proy>.py`. Cambiar:
   - las rutas (`LAYOUT`, `GRIP`, `OUT`);
   - los nombres de las ocurrencias móviles: palas, garras, empuje, robot armado, pallets, paquete, centrador;
   - la geometría de la tarea (§3): topes, alturas, patrón de palletizado, punto de toma en la cinta.
3. **Armar la escena** (`armar_<proy>.py`). Hace esto:
   1. `SaveAs` de los subensambles a mover (gripper, centrador, pistones, cilindros) y **después** del general.
   2. Suprime las restricciones de lo móvil y saca `Grounded`.
   3. Oculta el robot armado y agrega los eslabones V02…V05.
   4. Agrega cajas extra (N pisos × cajas por piso + 1).
   5. Guarda `escena.json`.
4. **Fotos del mecanismo:** `--test-garras "a_neg/a_pos"` en el armador o `--test-agarre` en el simulador.
   Mostrárselas al usuario: "¿así cierran las garras?". Ajustar los ángulos.
5. **Plan sin render:** `--sin-animar` escribe la IK, el error de la IK y el plan por piso (costo 0 = la pala móvil
   no cae sobre cajas ya puestas).
6. **Encuadres:**
   - `--prueba-vistas="cx,cy,cz,alto,dx,dy,dz;..."` saca varias fotos fijas en unos 20 s.
   - En montaje o dron, `--prueba-planos` saca una foto de cada plano.
   - Elegirlas con el usuario.
7. **Un cuadro:** `--max-cuadros 1`, para revisar luz, sombras y que no haya duplicados.
8. **Render completo** (ver los tiempos en §6).
9. **Armar el video del lado de la IA** (§5) y **mirar** la hoja de contacto y los cuadros críticos.
10. **Correcciones:** sólo el tramo (§4).

## 3. Lo que hay que definir del proyecto (valores de NewPack2 como ejemplo)

| Dato | NewPack2 | Cómo se obtuvo |
|---|---|---|
| Robot | KUKA KR 140 R3200-2 PA; `T_robot` del layout | `escena.json` (matriz del robot armado) |
| Montaje del gripper | `R_G` = X_g→Z_r, Y_g→Y_r, Z_g→−X_r; `BRIDA_G` = (7,8; 128,5; 0) (brida invisible) | Relevando el gripper |
| Pallet | 1000 × 1200 × 152; origen en el centro de la base | `RangeBox` |
| Almacén | Toma del pallet de más arriba; pasa 120 mm sobre los topes (z 1504,8) | Relevamiento |
| Garras | Abierta −28°, cerrada −7°, plegada +90°; palas 51 mm sobre la tabla | `--test-agarre` + fotos del usuario |
| Centrador | Cadenas z 360; tope del fondo x −566,4; tope lateral y −1121,2; chapa de pistones 60 mm de carrera | `diag_centrador.py`, `--diag` |
| Soltado | Desplazado −250 mm en X y −40 mm en Y; las cadenas y los pistones lo acomodan | Diseño de la secuencia |
| Paquete | 430 × 550 × 165; molinete de 4 por piso; pisos espejados; la pala aprieta el lado de 430 | Imagen del patrón del usuario |
| Cinta | La caja llega desde 1400 mm antes del tope | Layout |

## 4. Variantes de render (todas con el mismo script)

Comandos (con el puente: un pedido `{"script":"simular_newpack.py","args":[...]}`):

```text
# Horizontal Full HD con zooms (video "clásico")
--centro-vista=-300,-900,1250 --alto-vista 430 --vista=0.2,-1,0.75 --velocidad 1.5

# Vertical 1080x1920 "editado" (cortes secos entre planos)
--ancho 1080 --alto 1920 --centro-vista=-500,-900,1000 --alto-vista 850 --vista=0.6,-1,1.3 --zoom-escala 1.6 --montaje --velocidad 1.5

# Vertical "dron" (sin cortes: la cámara viaja suave mientras el robot se mueve)  ← el preferido
--ancho 1080 --alto 1920 --centro-vista=-500,-900,1000 --alto-vista 850 --vista=0.6,-1,1.3 --zoom-escala 1.6 --dron --velocidad 1.5

# Pruebas
--prueba-planos            fotos fijas de cada plano del montaje/dron
--prueba-vistas="..."      fotos fijas de encuadres candidatos
--test-agarre              3 vistas de la garra abierta / cerrada / plegada
--sin-animar               sólo plan + IK
--max-cuadros 1            un cuadro
--diag                     sin grabar: mide cajas en cada etapa del centrador + fotos de cerca

# Re-render de un tramo (mismos números de cuadro) para empalmar
--solo-centrador           (mismos argumentos que el render original)
```

- **Planos del montaje** (`PLANOS` en el simulador): general, toma_pallet, traslado, deja, centrador, cinta,
  toma_paquete, palet_a, palet_b y medio.
  - Están en mm/cm relativos a la geometría de la tarea.
  - Para otro layout se recalculan solos si se definen igual, a partir del pallet, el destino y la toma.
- **Zooms que pidió el usuario:** a la **toma del pallet** (cómo baja y junta), al **centrador** (cadenas y pistones)
  y a la **primera caja** (sistema de agarre).
- **Calidad:** igual que en ADECO.
  - "Luz suave", sombras ambiente + objeto + suelo, sin plano de suelo, ortográfica, planos ocultos.
  - También se probaron otros modos de visualización (sombreado con aristas, ilustración), el trazado de rayos (no
    funciona por la API) y el supermuestreo ×2 (mejora muy poco y tarda 5 veces más). Quedó la configuración de
    ADECO.

## 5. Del lado de la IA: traer cuadros y armar el MP4

1. Al final del render, el simulador deja `Animacion\cuadros.zip`.
   - Si pesa más de 350 MB, pedir `partir_zip.py <carpeta_cuadros> <prefijo>`, o `partir_zip_existente.py
     <zip> <prefijo>` si los PNG ya se borraron.
   - Traer cada parte por separado: máximo 500 MB por llamada.
2. Descomprimir en una carpeta propia y armar una **hoja de contacto** (cada 32–40 cuadros) para mirarla.
   - Revisar en grande los cuadros de contacto (pallet con chapa, pala con caja) y los de zoom.
3. Detectar saltos: diferencia media entre cuadros consecutivos. Un pico aislado es un corte o un error.
4. Codificar:
   ```bash
   ffmpeg -y -framerate 30 -i c%04d.png -c:v libx264 -crf 18 -preset slow -pix_fmt yuv420p salida.mp4
   # vertical: -crf 20 -movflags +faststart
   ```
5. Mandar el MP4 al usuario y copiarlo a la PC (`Generados\<PROY>_SIM\Animacion\`).

**Empalmar un tramo re-renderizado:** copiar los PNG nuevos sobre los viejos con el mismo nombre, revisar los
bordes (cuadro anterior y posterior al tramo) y volver a codificar. Sólo vale si el tramo tiene la misma cantidad de
cuadros; si cambió, hay que re-renderizar desde ahí hasta el final.

## 6. Tiempos de referencia (PC de diseño, Inventor 2025)

| Qué | Cuadros | Tiempo |
|---|---|---|
| Render completo NewPack2, 2 pisos, horizontal o vertical | 1286–1366 | 27–30 min (≈1,2 s por cuadro) |
| Tramo del centrador | 243 | ≈5 min |
| `--diag` | — | ≈2 min |
| Fotos de prueba (4–10) | — | 20–40 s |
| Partir zip / traer 1,3 GB / armar MP4 | — | ≈5 min |

## 7. Lecciones que costaron caro (resumen; la tabla completa está en la guía §17)

- **Subensamble flexible:** sus piezas no siguen a su `.iam`. Se mueven por el **proxy** en el contexto del padre.
  No apagar `Flexible`, porque se corren otras piezas.
- **Cadena de `Update()`:** de adentro hacia afuera (cilindro → pistones → centrador → escena).
- **Error de la IK** (4,5 mm): calcular los recorridos finales desde el `RangeBox` medido, para que las caras
  toquen justo.
- **Dos robots en el video:** ocultar el robot armado del layout.
- **Cuadros grises:** re-aplicar la cámara en cada cuadro.
- **Sin sombras al inicio:** renders de calentamiento y nada escondido bajo el piso.
- **Garras simétricas:** la segunda es `R180 ·` la primera, alrededor del eje vertical del gripper.
- **Pala móvil hacia el lado libre:** el plan por piso prueba todas las permutaciones × 0°/180°.
- **`AnalyzeInterference` en una escena animada cierra Inventor:** no usarlo; comparar `RangeBox`.
- **Vigilante cerrado a mitad de un pedido:** el pedido se repite al reabrirlo; neutralizarlo antes.
