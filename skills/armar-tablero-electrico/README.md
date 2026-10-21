<div align="center">

<img src="../../assets/icon-tablero.svg" width="88" alt="">

# Armar tablero eléctrico

**Del relevamiento a la lista de materiales y las notas de puesta en marcha, con revisión independiente.**

![Estado](https://img.shields.io/badge/estado-en_uso-2ea44f?style=flat-square)
![Red](https://img.shields.io/badge/red-220_V-d63c3c?style=flat-square)
![Lógica](https://img.shields.io/badge/lógica-12_V-d63c3c?style=flat-square)
![Drive](https://img.shields.io/badge/BOM-Google_Sheets-34A853?style=flat-square&logo=googlesheets&logoColor=white)

</div>

## 🧭 Flujo de la skill

```mermaid
flowchart LR
    Q["❓ Preguntas<br/>cargas · red · HMI · presupuesto"] --> A["🏛️ Arquitectura rev C<br/>(punto de partida)"]
    A --> K["🧮 Cálculos<br/>potencia · cables · fusibles"]
    K --> S["🛡️ Checklist<br/>de protecciones"]
    S --> B["📋 BOM en Drive<br/>(mismo archivo)"]
    B --> D["📐 Diagramas<br/>HTML + PDF A3"]
    D --> R["🧑‍⚖️ 4 subagentes<br/>de revisión"]
    R -->|ERROR| K
    R -->|OK| E(["📦 Entrega"])
    style R fill:#eef3fd,stroke:#2f6fde
    style E fill:#e8f7ef,stroke:#1f9d63
```

## 🏛️ Arquitectura de referencia (rev C)

Un tablero por biorreactor, gabinete de ~300×300×150 mm.

```mermaid
flowchart TD
    RED["🔌 Red 220 V"] --> TM["Térmica 2P 6 A<br/>curva C"]
    TM --> FU["Fuente Mean Well<br/>LRS-150-12 · 12 V 12,5 A"]
    FU --> FL["Fusible T3,15 A<br/>(rama de lógica)"]
    FU --> F25["Fusible 25 A DC"]
    FL --> KA0["Relé KA0 MY2N-J<br/>enclavamiento ON/OFF"]
    KA0 -->|MARCHA 12 V| IO["Placa de E/S propia<br/>(skill crear-placa)"]
    IO --> HMI["HMI ESP32-S3<br/>Touch LCD 7&quot;"]
    IO -->|SSR_EN| SSR
    KA0 -->|MARCHA| SSR["SSR CC 25 A<br/>MOSFET ≤ 10 mΩ"]
    F25 --> SSR --> LED["💡 Tiras LED"]
    IO --> EV["Electroválvula NC<br/>+ diodo rueda libre"]
    IO --> RS["Sensor RS485<br/>(UTP)"]
    style RED fill:#fdecec,stroke:#d63c3c
    style SSR fill:#fff3e6,stroke:#f28c28
```

## 🧑‍⚖️ Revisión independiente

| Subagente | Revisa |
|---|---|
| ⚡ Eléctrico / potencia | Cargas, cables, fusibles, selectividad, retorno, caídas |
| 🛡️ Seguridad / normativa | Térmica, diferencial, PE, bornes, separación 220 V / 12 V |
| 📋 Lista de materiales | Cantidades contra el esquema, estimados marcados, totales y fórmulas |
| 📝 Documentación | Consistencia de textos y diagramas con la revisión vigente |

Cada uno reporta **ERROR / MEJORA / OK** (máx. 500 palabras) y no edita nada.

## 📦 Entregables

- Presupuesto de potencia y cálculos visibles
- Lista de materiales en Google Sheets (precios estimados en amarillo, total y margen contra el tope)
- Esquema por capas, conexionado de la placa y de la HMI (página HTML + PDF A3 apaisado)
- Notas de armado y puesta en marcha paso a paso

> [!IMPORTANT]
> La skill edita **siempre el mismo archivo** de Drive y confirma la fila antes de escribir. Necesita el conector de Google Drive / Sheets.

👉 Instrucciones completas en **[SKILL.md](SKILL.md)**.
