<div align="center">

<img src="../../assets/icon-placa.svg" width="88" alt="">

# Crear placa

**PCB en KiCad 7 como código: netlist en Python, autoruteo, chaflanes a 45° y tres revisores independientes.**

![Estado](https://img.shields.io/badge/estado-en_uso-2ea44f?style=flat-square)
![KiCad](https://img.shields.io/badge/KiCad-7-314CB0?style=flat-square&logo=kicad&logoColor=white)
![Python](https://img.shields.io/badge/Python-design.py-3776AB?style=flat-square&logo=python&logoColor=white)
![Fabricante](https://img.shields.io/badge/fab-JLCPCB_2_capas-1f9d63?style=flat-square)
![Regla](https://img.shields.io/badge/pistas_a_90°-0-critical?style=flat-square)

</div>

> [!IMPORTANT]
> **Regla fija:** ninguna pista a 90° en ninguna placa. Sólo chaflanes de 45°, incluidas las uniones en T.

## 🧭 Pipeline

```mermaid
flowchart LR
    subgraph DIS["✍️ Diseño como código"]
        D1[design.py<br/>+ params.json]
    end
    subgraph RUT["🛣️ Ruteo"]
        R1[route.py → DSN] --> R2[freerouting 1.9.0] --> R3[SES]
    end
    subgraph POST["🧽 post.sh"]
        P1[stitch GND · islas] --> P2[chaflanes · neck-down] --> P3[zonas] --> P4[corner45.py]
    end
    subgraph VER["🔍 Verificar"]
        V1[DRC = 0] --- V2[corner45 --check = 0] --- V3[ir.py caída GND] --- V4[sch_check PASS]
    end
    DIS --> RUT --> POST --> VER --> SCH[📑 Esquemático<br/>jerárquico]
    SCH --> DG[🗺️ Diagramas<br/>HTML + PDF A3]
    DG --> SA[🧑‍⚖️ 3 subagentes]
    SA -->|ERROR| DIS
    SA -->|OK| Z([📦 Zip de fabricación])
    style Z fill:#e8f7ef,stroke:#1f9d63
```

## 📏 Reglas de fabricación (JLCPCB, 2 capas)

| Parámetro | Mínimo |
|---|---|
| Ancho de pista | 0,15 mm |
| Separación | 0,15 mm (clase 0,2) |
| Vía | 0,6 / 0,3 mm |
| Agujero | 0,3 mm |
| Cobre al borde | 0,3 mm |

## 🧑‍⚖️ Revisión independiente

| Subagente | Revisa |
|---|---|
| ⚡ Eléctrico | Huérfanos, corriente por borne, strapping pins, ADC, protecciones, retorno único, niveles 3,3/5 V |
| 🛣️ Ruteo | Ángulos de 90° con script propio, DRC, plano de GND, pistas de potencia, antena, USB |
| 🏭 Disposición y fabricación | Ubicación, montaje, serigrafía, Gerber/BOM/CPL, esquemático ↔ placa |

## 📦 Entrega

`kicad/` (pcb, pro, sch) · `fab/` (Gerber, BOM, CPL) · esquemático PDF · vista PNG · notas de armado · scripts — y una lista clara de **qué quedó sin verificar**.

👉 Instrucciones completas en **[SKILL.md](SKILL.md)**.
