<div align="center">

<img src="../../assets/logo-inventoria.svg" width="96" alt="InventorIA">

# InventorIA

**Claude maneja Autodesk Inventor por script: diseña, dibuja planos y simula celdas robotizadas.**

![Estado](https://img.shields.io/badge/estado-en_uso-2ea44f?style=flat-square)
![Versión](https://img.shields.io/badge/versión-1.1-f28c28?style=flat-square)
![Inventor](https://img.shields.io/badge/Inventor-2025-0696D7?style=flat-square&logo=autodesk&logoColor=white)
![Python](https://img.shields.io/badge/Python-3.13-3776AB?style=flat-square&logo=python&logoColor=white)
![Windows](https://img.shields.io/badge/Windows-10%2F11-0078D6?style=flat-square&logo=windows&logoColor=white)

</div>

| | |
|---|---|
| **Qué hace** | Piezas y ensambles paramétricos (grippers, rejas, estructuras), planos A4, DXF de corte, listas de materiales y animaciones de celdas KUKA cuadro a cuadro |
| **Para quién** | Ingeniería y diseño mecánico |
| **Estado** | ✅ En uso |
| **Responsable** | _completar_ |
| **Versión** | 1.1 · 21 de octubre de 2026 |

---

## 🧩 Cómo funciona

Inventor corre en tu PC. Claude no lo toca directamente: deja **pedidos** (scripts Python) en una carpeta y un programa chico, el **vigilante**, los ejecuta en tu Inventor y le devuelve los resultados.

```mermaid
flowchart LR
    subgraph NUBE["☁️ Claude"]
        C1[Escribe script<br/>con argumentos]
        C5[Mira imágenes<br/>y resultado.json]
    end
    subgraph PC["🖥️ Tu PC · Documents\\InventorIA"]
        P[(_pedidos/<br/>pNNN.json)]
        V[👀 vigilante.bat]
        I[🛠️ Inventor 2025<br/>COM · pywin32]
        G[(Generados/<br/>PROYECTO)]
    end
    C1 -- copia script + pedido --> P
    P --> V --> I --> G
    V -- pNNN.resultado.json --> P
    P -- trae resultado --> C5
    G -- PNG · PDF · ZIP --> C5
    style NUBE fill:#fff3e6,stroke:#f28c28
    style PC fill:#eef3fd,stroke:#2f6fde
```

> Si Claude corre **en la misma PC** (Claude Code con terminal en Windows) no hace falta el vigilante: ejecuta `.venv\Scripts\python.exe scripts\<script>.py` directo.

---

## 📦 Entregables

| | Entregable | Formato | Dónde queda |
|:-:|---|---|---|
| 🦾 | Piezas de chapa y ensambles con restricciones | `.ipt` `.iam` | `Generados\<PROYECTO>\` |
| 📐 | Planos A4 de chapas y conjunto | `.dwg` + `.pdf` | ídem |
| ✂️ | DXF de corte 1:1 por chapa | `.dxf` | ídem |
| 📋 | BOM con fórmulas (piezas, caños, herrajes, bulonería) | `.xlsx` | ídem |
| 🎬 | Video de la celda funcionando, horizontal o vertical | MP4 Full HD | ídem |

---

## 🚀 Inicio rápido

> Detalle completo en **[INSTALACION.md](INSTALACION.md)** (unos 30 minutos).

```mermaid
flowchart TD
    A["1️⃣ Windows + Inventor 2025<br/>+ Python 3.13 + app de Claude"] --> B["2️⃣ Doble clic en<br/><b>instalar.bat</b>"]
    B --> C["3️⃣ Abrir Inventor y después<br/>'Vigilante InventorIA'"]
    C --> D["4️⃣ En Claude: tarea vinculada a la PC<br/>con acceso a Documents\\InventorIA"]
    D --> E["5️⃣ Pegar el mensaje de arranque<br/>(lee CLAUDE.md)"]
    E --> F(["✅ Listo para pedir"])
    style F fill:#e8f7ef,stroke:#1f9d63
```

1. Tener **Windows + Autodesk Inventor 2025** con licencia, **Python 3.13** (no el alias de la Microsoft Store) y la **app de escritorio de Claude**.
2. Clonar o bajar este repositorio, entrar a `automatizaciones/inventoria/` y ejecutar **`instalar.bat`**. Crea `Documents\InventorIA`, copia todo e instala las dependencias.
3. Abrir **Inventor** y después el acceso directo **"Vigilante InventorIA"** del escritorio. Dejar las dos ventanas abiertas.
4. En la app de Claude, abrir una tarea **vinculada a esta computadora** con acceso a `Documents\InventorIA`.
5. Pegar el mensaje de arranque de [INSTALACION.md §6](INSTALACION.md#6-primer-mensaje-a-claude).
6. Antes de cualquier trabajo caro: **relevamiento + una imagen de prueba aprobada**.

---

## 📚 Contenido

| Ruta | Qué es |
|---|---|
| [`CLAUDE.md`](CLAUDE.md) | 🤖 **Instrucciones para la IA**: reglas, protocolo del vigilante y por dónde empezar. La IA lo lee primero |
| [`INSTALACION.md`](INSTALACION.md) | 🧰 Instalación paso a paso y conexión con Claude |
| [`GUIA.pdf`](GUIA.pdf) | 📕 Guía maestra para imprimir |
| [`docs/Guia_IA_Inventor.md`](docs/Guia_IA_Inventor.md) | 📘 **Guía maestra**: método completo de diseño, planos y animaciones |
| [`docs/SIMULACIONES.md`](docs/SIMULACIONES.md) | 🎬 Receta para simulaciones y videos (comandos, tiempos, variantes) |
| [`docs/SCRIPTS.md`](docs/SCRIPTS.md) | 🗂️ Índice de todos los scripts |
| [`docs/Receta_IA_Inventor.md`](docs/Receta_IA_Inventor.md) | 🧪 Receta técnica original (API de Inventor, planos, robots) |
| [`docs/InventorIA_contexto.md`](docs/InventorIA_contexto.md) | 🕓 Historial y estado de cada proyecto |
| `inventor-assistant-portable/server/` | 🐍 Librería de Inventor por COM (`inventor_mcp.py`) y motor de grippers (`gripper_design.py`, `gripper_calc.py`) |
| `inventor-assistant-portable/scripts/` | ⚙️ Un script por tarea + `vigilante.py` / `.bat` + `verificar_instalacion` |
| `instalar.bat` / `instalar.ps1` | 💾 Instalador para una PC nueva |
| `plantillas/pedido_ejemplo.json` | 📝 Formato de un pedido para el vigilante |

### Scripts por familia

```mermaid
pie showData
    title Scripts en inventor-assistant-portable/scripts
    "Relevamiento, diagnóstico y pruebas" : 29
    "Simulación y animación" : 11
    "Diseño y construcción" : 11
    "Vigilante e instalación" : 6
    "Planos" : 3
```

Ver la lista completa con descripción en **[docs/SCRIPTS.md](docs/SCRIPTS.md)**.

---

## 🏆 Reglas de oro

| # | Regla | Por qué |
|:-:|---|---|
| 1 | 🛡️ **Nunca tocar originales** — copias o `Generados\` | Los modelos del cliente no se pueden romper |
| 2 | ✏️ **Editar, no regenerar** — en videos, re-renderizar sólo el tramo que cambia | Ahorra horas de render y tokens |
| 3 | 📜 **Todo por script** con argumentos y `resultado.json` | Repetible y auditable |
| 4 | 📏 **Medir antes de suponer** y mirar la imagen antes de decir que funciona | La IA no "ve" Inventor si no le mostrás |
| 5 | 🔬 **Probar en chico**: 1 foto → 1 cuadro → tramo → render completo | Los errores caros se ven en la primera foto |

---

## ⚠️ Limitaciones y avisos

> [!CAUTION]
> **No usar `AnalyzeInterference` durante una simulación**: cierra Inventor.

- La API de Inventor 2025 no permite crear presentaciones (`.ipn`): las animaciones se hacen cuadro a cuadro y se arman con `ffmpeg`.
- No abrir Inventor "como administrador": la conexión COM falla (`MK_E_UNAVAILABLE` / `0x80080005`).
- **Modelos CAD no incluidos** (layouts de clientes, robots, comerciales). Las simulaciones con KUKA KR 140 necesitan el ensamble del robot del servidor de proyectos; ver [INSTALACION.md §7](INSTALACION.md#7-modelos-cad-necesarios).
- Los cálculos son preliminares; los aprueba un ingeniero antes de fabricar.

---

## 🕓 Historial

| Versión | Fecha | Cambio |
|---|---|---|
| 1.1 | 2026-10-21 | Repositorio completo (instalador, scripts, docs) integrado en `automatizaciones/inventoria/` |
| 1.0 | 2026-10-07 | Primera versión de la guía maestra |
