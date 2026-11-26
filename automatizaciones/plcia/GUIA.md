# PLC IA · guía del watcher (PLC_Bridge)

Ventana que deja a Claude leer y escribir el proyecto de TIA Portal (y, en beta, Machine Expert)
sin que tengas que correr scripts a mano. Claude deja un trabajo en `inbox\`, el watcher lo ejecuta
y deja el resultado en `outbox\`.

## Instalar (una vez)
1. Copiar la carpeta `plc-bridge` de este repo a `C:\PLC_Bridge` (o descargar el repo y copiarla).
2. Revisar `config.json`: ruta de la DLL de Openness (`siemens_tia.dll`) y, si se usa,
   la de Machine Expert (`schneider_me.exe`).
3. Recomendado: en `proyectos_permitidos` poner la carpeta de las COPIAS de trabajo,
   por ejemplo `"D:\\Proyectos\\Copias_trabajo"`. Fuera de ahi el watcher no importa nada.
4. Tu usuario de Windows tiene que estar en el grupo **Siemens TIA Openness**.
5. En la app de Claude, conectar la carpeta `C:\PLC_Bridge` (+ → Agregar carpeta).

## Usar
1. Abrir TIA con el proyecto.
2. Doble clic en `INICIAR_WATCHER.cmd` y dejar la ventana abierta.
3. La primera vez TIA pregunta si permite el acceso de Openness: **Sí a todo**.
4. Pedirle a Claude lo que necesites. En la ventana se ve cada paso.

## Qué puede hacer
| Acción | Qué hace |
|---|---|
| `ping` | Prueba que el watcher esté vivo |
| `info` | Proyecto, PLC, HMI y si se permite escribir |
| `export` | Exporta bloques, tablas, tipos, pantallas, tags y alarmas a XML y arma un zip (`solo` filtra por nombre) |
| `import` | Importa XML (`plc_tagtable`, `plc_block`, `plc_type`, `hmi_tagtable`, `hmi_screen`) con reemplazo |
| `compile` | Compila `plc`, `hmi` o `todo` y devuelve errores y avisos |
| `save` | Guarda el proyecto |

**No carga nada al PLC ni al panel.** Cargar al equipo lo hace siempre una persona desde TIA.
Si `confirmar_importaciones` es `true`, antes de cada importación pregunta en la ventana.

## Protocolo (para Claude)
- `inbox\<id>\...` : archivos a importar (primero se copian estos).
- `inbox\<id>.job.json` : el trabajo (se copia último). Ver `ejemplos\`.
- `outbox\<id>.result.json` : resultado por paso. `outbox\<id>.log.txt` : log. `outbox\<id>_export.zip` : export.
- `outbox\heartbeat.json` : se actualiza cada 5 s mientras el watcher está corriendo.
- Al terminar, el trabajo y su carga pasan a `done\<id>\`.

## Marcas
- `siemens_tia` : TIA Portal Openness (probado con V17, S7-1500, panel Comfort).
- `schneider_me` : EcoStruxure Machine Expert (base CODESYS), PLCopenXML vía `--noui --runscript`. **Beta, sin probar.**
  El proyecto tiene que estar cerrado en Machine Expert.
- Schneider Control Expert (Unity, M340/M580) no tiene API de automatización: se trabaja exportando
  `.XEF`/`.ZEF` a mano en `inbox\` y Claude devuelve el archivo para importar a mano.
- Para otra marca: agregar `adapters\<marca>.ps1` con una función `Invoke-Step_<marca>($st, $ctx)`.

## lib\ (herramientas de Claude)
- `analizar.py` : resumen de redes, cableado y búsqueda de símbolos en un export de TIA.
- `tia_lad.py` : genera redes LAD (FlgNet) y las inserta en bloques exportados; validación de IDs/UIds.
