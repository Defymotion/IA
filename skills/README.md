# 🧠 Skills de Claude

Cada carpeta es una skill lista para cargar: contiene un `SKILL.md` (y, si hace falta, `recursos/`).

| Skill | Qué hace | Ficha |
|---|---|---|
| <img src="../assets/logo-inventoria.svg" width="20"> `inventoria` | Trabajar con Autodesk Inventor por el método InventorIA | [SKILL.md](inventoria/SKILL.md) |
| <img src="../assets/icon-tablero.svg" width="20"> `armar-tablero-electrico` | Tablero eléctrico de un equipo o biorreactor | [README](armar-tablero-electrico/README.md) |
| <img src="../assets/icon-placa.svg" width="20"> `crear-placa` | Placa PCB en KiCad 7 desde especificaciones | [README](crear-placa/README.md) |

## Cómo cargar una skill

1. Comprimí la carpeta de la skill (por ejemplo `crear-placa/`) en un `.zip`, con el `SKILL.md` adentro de la carpeta.
2. Cargá el zip en Claude como skill.
3. Pedile la tarea con tus palabras: la `description` del `SKILL.md` es lo que hace que Claude la use.

¿Querés crear una? Partí de [`plantillas/skill/SKILL.md`](../plantillas/skill/SKILL.md) y seguí [docs/CONTRIBUIR.md](../docs/CONTRIBUIR.md).
