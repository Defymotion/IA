<div align="center">

<img src="assets/banner.svg" alt="DEFYMOTION · Laboratorio IA" width="100%">

<br>

[![Automatizaciones](https://img.shields.io/badge/automatizaciones-2-f28c28?style=for-the-badge&logo=githubactions&logoColor=white)](#-automatizaciones)
[![Skills](https://img.shields.io/badge/skills_de_Claude-3-ffb35c?style=for-the-badge&logo=anthropic&logoColor=white)](#-skills-de-claude)
[![Inventor](https://img.shields.io/badge/Autodesk_Inventor-2025-0696D7?style=for-the-badge&logo=autodesk&logoColor=white)](automatizaciones/inventoria/)
[![Python](https://img.shields.io/badge/Python-3.13-3776AB?style=for-the-badge&logo=python&logoColor=white)](automatizaciones/inventoria/)
[![KiCad](https://img.shields.io/badge/KiCad-7-314CB0?style=for-the-badge&logo=kicad&logoColor=white)](skills/crear-placa/)
[![Idioma](https://img.shields.io/badge/idioma-espa%C3%B1ol_rioplatense-75AADB?style=for-the-badge)](#)

**Todo lo que ya le enseñamos a la IA, en un solo lugar.**<br>
Scripts, guías y skills para que cualquier persona del equipo reutilice lo que funciona en vez de empezar de cero.

[Qué hay](#-qué-hay-acá) · [Automatizaciones](#-automatizaciones) · [Skills](#-skills-de-claude) · [Empezar](#-empezar-en-3-pasos) · [Contribuir](docs/CONTRIBUIR.md)

</div>

---

## 🗺️ Qué hay acá

```mermaid
mindmap
  root((DEFYMOTION<br/>IA))
    Automatizaciones
      InventorIA
        Grippers de chapa
        Planos A4 · DXF · BOM
        Simulación KUKA en video
      Layout de paletizado iLogic
        Celda completa en 1 clic
        Mosaico del pallet
        Chequeo de alcance y carga
    Skills de Claude
      InventorIA
      Armar tablero eléctrico
      Crear placa PCB
    Plantillas
      Ficha de automatización
      SKILL.md
    Docs
      Convenciones
      Cómo contribuir
```

<table>
<tr>
<td width="25%" align="center" valign="top">
<a href="automatizaciones/inventoria/"><img src="assets/logo-inventoria.svg" width="72" alt=""></a><br>
<b><a href="automatizaciones/inventoria/">InventorIA</a></b><br>
<sub>Claude diseña, dibuja y simula en Inventor por script</sub>
</td>
<td width="25%" align="center" valign="top">
<a href="automatizaciones/ilogic-layout-paletizado/"><img src="assets/icon-ilogic.svg" width="72" alt=""></a><br>
<b><a href="automatizaciones/ilogic-layout-paletizado/">Layout de paletizado</a></b><br>
<sub>Regla iLogic que arma la celda entera con vista previa</sub>
</td>
<td width="25%" align="center" valign="top">
<a href="skills/armar-tablero-electrico/"><img src="assets/icon-tablero.svg" width="72" alt=""></a><br>
<b><a href="skills/armar-tablero-electrico/">Tablero eléctrico</a></b><br>
<sub>Potencia, protecciones, BOM en Drive y revisión</sub>
</td>
<td width="25%" align="center" valign="top">
<a href="skills/crear-placa/"><img src="assets/icon-placa.svg" width="72" alt=""></a><br>
<b><a href="skills/crear-placa/">Crear placa</a></b><br>
<sub>PCB en KiCad 7 como código, sin pistas a 90°</sub>
</td>
</tr>
</table>

---

## ⚙️ Automatizaciones

| | Nombre | Qué hace | Herramientas | Estado |
|:-:|---|---|---|:-:|
| <img src="assets/logo-inventoria.svg" width="32"> | **[InventorIA](automatizaciones/inventoria/)** | Diseño paramétrico en Inventor (grippers, rejas, estructuras), planos A4/DXF, BOM y animaciones de celdas KUKA cuadro a cuadro, todo por script manejado por IA | Inventor 2025 · Python 3.13 · pywin32 · ffmpeg | ✅ En uso |
| <img src="assets/icon-ilogic.svg" width="32"> | **[Layout de paletizado](automatizaciones/ilogic-layout-paletizado/)** | Regla iLogic con ventana de configuración y vista previa: ubica robot, cintas, pallets, máquinas, vallado y puerta, y avisa si algo queda fuera de alcance o excede la carga | Inventor 2025 · iLogic (VB.NET) | 🧪 En prueba |

### Cómo trabaja InventorIA

```mermaid
sequenceDiagram
    autonumber
    actor U as 👷 Ingeniero
    participant C as 🤖 Claude (nube)
    participant P as 📂 _pedidos/
    participant V as 👀 Vigilante (PC)
    participant I as 🛠️ Inventor 2025
    U->>C: "Haceme un gripper para 4 cajas de 12 kg"
    C->>C: Releva, calcula apriete y escribe el script
    C->>P: script.py + pNNN.json
    V->>P: Detecta el pedido
    V->>I: Ejecuta por COM
    I-->>V: Piezas, planos, imágenes
    V->>P: pNNN.resultado.json + PNG / ZIP
    C->>P: Trae el resultado
    C->>C: Mira la imagen antes de dar el OK
    C-->>U: Ensamble + planos A4 + DXF + BOM + video
```

---

## 🧠 Skills de Claude

Una **skill** es un `SKILL.md` que le enseña a Claude un procedimiento completo. Se carga una vez y Claude la usa sola cuando el pedido coincide.

| | Skill | Se dispara cuando pedís… | Entrega |
|:-:|---|---|---|
| <img src="assets/logo-inventoria.svg" width="28"> | [`inventoria`](skills/inventoria/SKILL.md) | algo en Inventor, un gripper, planos o una simulación | Modelos, planos y videos en `Generados\` |
| <img src="assets/icon-tablero.svg" width="28"> | [`armar-tablero-electrico`](skills/armar-tablero-electrico/SKILL.md) | el tablero de un equipo o biorreactor | Presupuesto de potencia, protecciones, BOM en Drive, diagramas y notas de armado |
| <img src="assets/icon-placa.svg" width="28"> | [`crear-placa`](skills/crear-placa/SKILL.md) | una placa PCB desde especificaciones | Proyecto KiCad 7, Gerber/BOM/CPL, esquemático PDF y diagramas |

Las tres siguen el mismo método:

```mermaid
flowchart LR
    A[❓ Preguntar<br/><sub>lo que cambia el diseño</sub>] --> B[🧮 Calcular<br/><sub>y mostrar las cuentas</sub>]
    B --> C[🏗️ Construir<br/><sub>como código</sub>]
    C --> D[🔍 Verificar<br/><sub>scripts propios</sub>]
    D --> E[🧑‍⚖️ Subagentes<br/><sub>revisión independiente</sub>]
    E -->|ERROR| C
    E -->|OK| F[📦 Entregar<br/><sub>+ qué falta verificar</sub>]
    style A fill:#fff3e6,stroke:#f28c28
    style F fill:#e8f7ef,stroke:#1f9d63
    style E fill:#eef3fd,stroke:#2f6fde
```

---

## 🚀 Empezar en 3 pasos

<table>
<tr>
<th width="33%">1 · Elegí</th>
<th width="33%">2 · Cargá</th>
<th width="33%">3 · Pedí</th>
</tr>
<tr valign="top">
<td>

Buscá en las tablas de arriba la automatización o skill que te sirve y entrá a su carpeta.

</td>
<td>

**Skill:** comprimí la carpeta `skills/<nombre>/` en un .zip y cargala en Claude como skill.<br>
**Automatización:** leé su `README.md` y seguí *Cómo arrancar*.

</td>
<td>

Hablale a Claude normal: *"armame el tablero del biorreactor 2"*. Revisá las listas de control antes de entregar.

</td>
</tr>
</table>

---

## 📁 Estructura

```text
IA/
├── 📄 README.md                    ← estás acá
├── 🎨 assets/                      banner e íconos del README
├── ⚙️ automatizaciones/
│   ├── inventoria/                 InventorIA completo (instalador, scripts, guías)
│   │   ├── README.md               ficha
│   │   ├── CLAUDE.md               instrucciones que lee la IA
│   │   ├── INSTALACION.md          paso a paso en una PC nueva
│   │   ├── GUIA.pdf                guía maestra impresa
│   │   ├── docs/                   guía, simulaciones, índice de scripts, historial
│   │   └── inventor-assistant-portable/   server/ + scripts/ + vigilante
│   └── ilogic-layout-paletizado/
│       ├── Generador_Layout_Paletizado.vb
│       ├── Biblioteca_Layout.ejemplo.txt
│       └── ejemplos/
├── 🧠 skills/
│   ├── inventoria/SKILL.md
│   ├── armar-tablero-electrico/SKILL.md
│   └── crear-placa/SKILL.md
├── 📋 plantillas/                  ficha de automatización + SKILL.md base
└── 📚 docs/                        convenciones y cómo contribuir
```

---

## 📏 Convenciones de la casa

| | |
|---|---|
| 🗣️ **Idioma** | Español rioplatense, mensajes cortos |
| 📐 **Unidades** | mm · hojas A4 · DXF 1:1 |
| 🛡️ **Originales** | Nunca se tocan: se trabaja sobre copias |
| ✏️ **Cambios** | Editar lo que existe, no regenerar |
| 🔬 **Pruebas** | Primero en chico: 1 imagen → 1 cuadro → render completo |
| 👁️ **Verificación** | Nada está "listo" sin haberlo mirado |

Detalle en [docs/convenciones.md](docs/convenciones.md).

---

## 🤝 Contribuir

```mermaid
gitGraph
    commit id: "main"
    branch nueva/mi-skill
    commit id: "copiar plantilla"
    commit id: "completar SKILL.md"
    commit id: "fila en el índice"
    checkout main
    merge nueva/mi-skill id: "PR revisado ✅"
```

Reglas rápidas: **nada de archivos de clientes** (`.ipt`, `.iam`, `.idw`, `.dwg`, planos reales), **nada de secretos** y **nada pesado o generado** (zips, MP4, `Generados/`). Todo el detalle en **[docs/CONTRIBUIR.md](docs/CONTRIBUIR.md)**.

**Estados:** ✅ En uso · 🧪 En prueba · 📝 Borrador · 🗄️ Archivada

---

> [!WARNING]
> Los cálculos que generan estas herramientas (retención, estructura, neumática, carga del robot, protecciones eléctricas) son **preliminares**. Los aprueba un ingeniero responsable antes de fabricar.

<div align="center">
<sub>Hecho en Argentina 🇦🇷 por <b>DEFYMOTION</b> · robótica y paletizado</sub>
</div>
