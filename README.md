# DEFYMOTION · Skills de Claude y automatizaciones

Repositorio central de skills de Claude y automatizaciones de DEFYMOTION: scripts, guías y plantillas para que cualquier equipo reutilice lo que ya funciona en vez de empezar de cero.

---

## Qué hay acá

| Carpeta | Contenido |
|---|---|
| `skills/` | Skills de Claude (cada una con su `SKILL.md`) listas para cargar en Claude |
| `automatizaciones/` | Automatizaciones completas: scripts, guía maestra, plantillas y ejemplos |
| `plantillas/` | Plantillas para crear una skill o automatización nueva |
| `docs/` | Convenciones generales de la empresa (unidades, planos, videos, nombres) |

```
.
├── README.md
├── skills/
│   └── <nombre-skill>/
│       ├── SKILL.md
│       └── recursos/            # scripts, ejemplos, plantillas que usa la skill
├── automatizaciones/
│   └── <nombre-automatizacion>/
│       ├── README.md            # ficha (ver plantilla abajo)
│       ├── GUIA.md              # guía maestra / instrucciones para la IA
│       ├── scripts/
│       └── ejemplos/
├── plantillas/
└── docs/
```

## Índice

### Automatizaciones

| Nombre | Qué hace | Herramientas | Estado |
|---|---|---|---|
| [InventorIA](automatizaciones/inventoria/README.md) | Diseño paramétrico en Autodesk Inventor (grippers, rejas, estructuras), planos A4/DXF, BOM y animaciones de celdas robotizadas KUKA, todo por script manejado por IA | Inventor 2025, Python 3.13, pywin32, ffmpeg | ✅ En uso |
| _(próxima)_ | | | |

### Skills

| Nombre | Para qué sirve | Estado |
|---|---|---|
| _(próxima)_ | | |

Estados: ✅ En uso · 🧪 En prueba · 📝 Borrador · 🗄️ Archivada

---

## Cómo usar una automatización

1. Entrá a su carpeta y leé el `README.md` (ficha corta: qué hace, requisitos, cómo arrancar).
2. Pasale la `GUIA.md` completa a Claude al empezar el proyecto.
3. Seguí las listas de control de la guía antes de entregar.

## Cómo agregar algo nuevo

1. Creá una rama: `nueva/<nombre-corto>`.
2. Copiá la plantilla de `plantillas/` a `skills/<nombre>/` o `automatizaciones/<nombre>/`.
3. Completá la ficha (README) y la guía o el `SKILL.md`.
4. Agregá la fila en el índice de este README.
5. Abrí un pull request y pedí revisión a alguien que la haya usado.

### Reglas para subir

- **Nada de archivos de clientes**: ni modelos (`.ipt`, `.iam`, `.idw`, `.dwg`), ni layouts, ni PDFs de planos reales. Sólo scripts, guías y ejemplos anonimizados.
- **Nada de secretos**: contraseñas, API keys, rutas de servidores internos.
- **Nada pesado ni generado**: `.venv/`, `Generados/`, cuadros de video, zips, MP4.
- Nombres de carpetas en minúscula y con guiones: `simulacion-celdas`, `bom-excel`.
- Cada lección nueva (error + solución) se agrega a la guía de esa automatización.

`.gitignore` recomendado:

```gitignore
.venv/
__pycache__/
Generados/
_pedidos/
*.ipt
*.iam
*.idw
*.ipn
*.dwg
*.png
*.zip
*.mp4
!**/ejemplos/*.png
```

---

## Plantilla de ficha (README de cada automatización)

```markdown
# <Nombre>

**Qué hace:** una o dos frases.
**Para quién:** equipo / rol que la usa.
**Estado:** ✅ En uso · 🧪 En prueba · 📝 Borrador
**Responsable:** <nombre>
**Versión:** 1.0 · <fecha>

## Requisitos
- Software y versiones
- Dependencias (Python, librerías)
- Accesos (carpetas, licencias)

## Cómo arrancar
1. ...
2. ...

## Entregables
- ...

## Contenido de la carpeta
| Archivo | Para qué |
|---|---|

## Limitaciones y avisos
- ...

## Historial
| Versión | Fecha | Cambio |
|---|---|---|
```

---

> ⚠️ Los cálculos que generan estas automatizaciones (retención, estructura, neumática, carga de robot) son preliminares y los aprueba un ingeniero responsable antes de fabricar.
