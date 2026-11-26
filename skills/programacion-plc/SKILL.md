---
name: programacion-plc
description: Leer y modificar programas de PLC/HMI (Siemens TIA Portal vía Openness; Schneider Machine Expert en beta) exportando XML, generando cambios e importándolos con el watcher PLC_Bridge.
---

# Programación PLC (export → análisis → cambio → import → verificación)

Usar cuando el usuario pide entender, corregir o agregar lógica de PLC o pantallas HMI en un proyecto real
(TIA Portal, Machine Expert, Control Expert), o cuando pide "bajá el proyecto", "fijate cómo quedó", "armame el script".

## 0. Reglas que no se negocian
- Trabajar siempre sobre una **COPIA** del proyecto. Si `info` dice `escritura_permitida: false`, no importar: avisar.
- **No tocar Devices & networks** (hardware, IPs, módulos) salvo pedido explícito.
- **Nunca cargar al PLC/panel**: el watcher no lo hace y Claude no lo pide. Cargar es de una persona (y probar robot en T1).
- Cambios de programas de robot (KUKA, etc.): los carga una persona. Claude entrega el archivo y explica.
- Antes de cambiar lógica vieja o renombrar variables, confirmar que el usuario lo autorizó.
- Hablar en el idioma del usuario (rioplatense si escribe así), corto y directo. Siempre decir **qué red/bloque** cambia.

## 1. Puente con la PC (PLC_Bridge)
El watcher vive en `C:\PLC_Bridge` (repo: `automatizaciones/plcia/plc-bridge`), se abre con `INICIAR_WATCHER.cmd`
y la carpeta tiene que estar conectada en el chat (app de escritorio → + → Agregar carpeta).
- Vivo: `device_stage_files` de `C:\PLC_Bridge\outbox\heartbeat.json` (hora < 10 s). Si no está, pedir que abra `INICIAR_WATCHER.cmd` con TIA abierto.
- Trabajo: 1) `device_commit_files` de la carga a `C:\PLC_Bridge\inbox\<id>\...`; 2) **después**, en otra llamada, `inbox\<id>.job.json`.
- `id` = `AAAAMMDD_HHMM_descripcion` (único). Esperar con `device_list_dir` de `outbox\` hasta ver `<id>.result.json`; leerlo con `device_stage_files` (y `<id>.log.txt` si falló).
- Export: `outbox\<id>_export.zip` → stage → descomprimir en una carpeta nueva y analizar.
- Si no hay herramientas de escritura en el dispositivo o no hay watcher: fallback = carpeta `pasoNN\` con XML + `openness_pasoNN.ps1` y el comando de PowerShell para que el usuario lo corra.

Job (Siemens):
```json
{ "id": "20261126_0910_x", "vendor": "siemens_tia", "steps": [
  { "action": "import", "items": [ { "kind": "plc_tagtable", "file": "import_plc/Tabla.xml" },
                                   { "kind": "plc_block", "file": "import_plc/FC30.xml", "carpeta": "Grupo/Sub" } ] },
  { "action": "compile", "objetivo": "plc" },
  { "action": "import", "items": [ { "kind": "hmi_tagtable", "file": "import_hmi/tags/Default tag table.xml" },
                                   { "kind": "hmi_screen", "file": "import_hmi/pantallas/Principal.xml" } ] },
  { "action": "compile", "objetivo": "hmi" },
  { "action": "export", "alcance": ["plc","hmi"], "solo": ["FC30","Principal"] } ] }
```
Acciones: `ping`, `info`, `export` (`alcance`, `solo`), `import` (kinds `plc_tagtable|plc_block|plc_type|hmi_tagtable|hmi_screen`), `compile` (`plc|hmi|todo`), `save`. `seguir_si_falla: true` para no cortar.
Orden de import: tablas de tags PLC → UDT → DB → FC/FB → **compilar PLC** → tags HMI → pantallas → compilar HMI.

## 2. Flujo de trabajo
1. **Contexto**: `info` + `export` completo (compilar antes si hay bloques inconsistentes). Guardar el export como base (`expNN`).
2. **Analizar** con `C:\PLC_Bridge\lib\analizar.py` (stagearlo): `resumen bloque.xml`, `cables bloque.xml 3,5`, `buscar carpeta simbolo`.
   Cruzar con tags (direcciones %I/%Q/%M), DBs y pantallas. Si hay robot, leer su programa antes de opinar del protocolo.
3. **Diseñar** el cambio y explicarlo en 3-6 líneas (qué red, qué condición, qué riesgo). Si hay una decisión de proceso dudosa, preguntar.
4. **Generar** con `C:\PLC_Bridge\lib\tia_lad.py` siempre partiendo del **último export** (nunca de un archivo viejo: el usuario edita a mano).
   Usar marcas de texto (título de la red) para ubicar redes, no números. Validar con `validar()` cada archivo.
5. **Importar + compilar** con un job. Leer errores de compilación y corregir.
6. **Verificar**: re-exportar solo lo tocado y confirmar que quedó como se diseñó. Recién ahí decir "listo, cargá".
7. Resumen final: qué cambió (bloque/red), qué tiene que hacer el usuario (cargar, probar en T1) y advertencias.

## 3. Siemens TIA (Openness V17) – lo aprendido
PLC / LAD (FlgNet v4):
- IDs de `CompileUnit`/`MultilingualText` en **hex** y únicos en el archivo: arrancar en `maxid+0x10` (error típico: "Duplicate Simatic ML ID").
- UIds únicos **dentro de cada red**. Símbolos DB como `DB|Miembro`.
- Constantes: `LiteralConstant` + `ConstantType` (Int/Byte/Bool); tiempos `TypedConstant` (`T#1500ms`).
- TON/TOF: instancia en un DB global (`<Instance Scope="GlobalVariable"><Component DB/><Component miembro/>`), miembros `IEC_TIMER`.
- Flancos P/N: una memoria de flanco **propia por cada uso** (nunca reutilizar la de otra red).
- Bits en Word: en `MW90`, `M91.x` = bits 0–7 y `M90.x` = bits 8–15.
- Agregar miembros a un DB: clonar un `<Member>` existente; `Remanence="Retain"` y `<StartValue>` cuando corresponda. Avisar que cargar el DB lo reinicializa.
- No escribir en direcciones `%I`/`%IW` (las pisa el periférico/IO-Link): usar `%M`/DB.
- Antes de tocar un tag, buscar **todos** los usos (`buscar`): resets en otras redes suelen explicar "algo me lo resetea".
- Señales del robot que son pulsos cortos no sirven como condición de nivel: usar memoria (S/R) o flanco.

HMI (WinCC Comfort/Advanced):
- Tags internos: sin `ControllerTag`; clonar uno interno y ajustar tipo/longitud.
- `MultilingualText`: actualizar **todas** las culturas (en-US y es-ES).
- Cambio de color al presionar: tag interno + `Press`→SetBit / `Release`→ResetBit + `RangeAppearanceAnimation`.
- Clonar objetos con `renumerar()`; `ObjectName` únicos. Mostrar una maqueta (PNG) antes de importar si cambia el layout.
- Import de pantalla falla si está **abierta en el editor**: pedir que la cierren.

Scripts PowerShell (fallback): primera línea con `$dll = ...Siemens.Engineering.dll` + `Add-Type` (si falta: "No se encuentra el tipo [Siemens.Engineering.TiaPortal]"); Windows PowerShell 5.1, archivos UTF-8 con BOM.

Carga (la hace el usuario): la IP de un panel Comfort se cambia en el Control Panel del panel, no compilando; "Fit" falla a distancia → cargar con solo "Overwrite all".

## 4. Schneider
- **Machine Expert** (M241/M251/M262, base CODESYS): `vendor: "schneider_me"`, acciones `export|import|compile` con `"proyecto": "C:\\...\\x.project"`; formato PLCopenXML. El proyecto debe estar cerrado en la GUI. Adaptador **beta**: la primera vez probar `export` y revisar el log antes de importar nada.
- **Control Expert** (M340/M580): sin API. Pedir export `.ZEF` (zip con `.XEF`) a mano a `inbox\`, modificar el XEF (texto ST/LD/FBD + variables) y devolverlo para "Proyecto → Importar" manual.
- Otras marcas: si el software tiene API/CLI de import/export (Rockwell L5X, Beckhoff/CODESYS), agregar `adapters\<marca>.ps1` con `Invoke-Step_<marca>($st,$ctx)`.

## 5. Errores frecuentes
| Síntoma | Causa / acción |
|---|---|
| No aparece result.json | Watcher cerrado o TIA con cartel de Openness esperando "Sí a todo" |
| Export "Inconsistent" | Compilar el PLC y re-exportar |
| Duplicate ID | IDs no hex/únicos: regenerar desde `maxid` |
| Pantalla no importa | Abierta en el editor |
| Robot no reacciona | Mirar el programa del robot: qué entrada lee y en qué momento (flanco vs nivel) |

## Convenciones DEFYMOTION
Ver [docs/convenciones.md](../../docs/convenciones.md): copias, editar no regenerar, todo por script, verificar al final.
