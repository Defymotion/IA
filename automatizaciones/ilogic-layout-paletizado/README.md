<div align="center">

<img src="../../assets/icon-ilogic.svg" width="96" alt="">

# Generador de layout de paletizado

**Una regla iLogic que arma la celda de paletizado completa —robot, línea, pallets, máquinas y vallado— desde una ventana con vista previa en vivo.**

![Estado](https://img.shields.io/badge/estado-en_prueba-dbab09?style=flat-square)
![Versión](https://img.shields.io/badge/versión-3-2f6fde?style=flat-square)
![Inventor](https://img.shields.io/badge/Inventor-2025-0696D7?style=flat-square&logo=autodesk&logoColor=white)
![iLogic](https://img.shields.io/badge/iLogic-VB.NET-512BD4?style=flat-square&logo=dotnet&logoColor=white)

</div>

| | |
|---|---|
| **Qué hace** | Genera el layout preliminar de una celda de paletizado en un ensamble de Inventor y verifica alcance, carga y producción |
| **Para quién** | Ingeniería comercial y diseño (cotizaciones y anteproyectos) |
| **Estado** | 🧪 En prueba |
| **Responsable** | _completar_ |
| **Versión** | 3 · 21 de octubre de 2026 |

---

## 🧭 Flujo

```mermaid
flowchart LR
    A["📂 Ensamble .iam<br/>(mejor guardado)"] --> B["▶️ Ejecutar regla"]
    B --> C["📚 Indexa la biblioteca<br/>robots · máquinas · bases"]
    C --> D["🪟 Ventana con pestañas<br/>+ vista previa en planta<br/>+ mosaico del pallet"]
    D -->|Generar layout| E["🗑️ Borra todo lo LAY_*"]
    E --> F["🏗️ Inserta y genera<br/>componentes a medida"]
    F --> G["🧮 Chequeos<br/>alcance · carga · vallado"]
    G --> H["📄 Layout_Resumen.txt"]
    D -->|Diagnóstico| I["📄 Diagnostico_Biblioteca.txt"]
    style D fill:#eef3fd,stroke:#2f6fde
    style G fill:#fff3e6,stroke:#f28c28
```

**Convención:** robot en `(0,0,0)`, X a la derecha, Y hacia atrás, Z arriba, en mm. Todo se ubica por **caja envolvente**, sin depender del origen de cada modelo; el robot se endereza y se ancla en su base.

---

## 🧱 Qué arma

| Grupo | Componentes | De dónde salen |
|---|---|---|
| 🤖 **Robot** | Robot, base, gripper | Biblioteca (detecta robots solos) o base/gripper generados |
| 🛤️ **Línea** | 1–2 estaciones, tramos de vacío y salida, transportadores de rodillos | Generados a medida |
| 📥 **Entrada** | 1–2 cintas, tope o freno de cajas | Generados a medida |
| 📦 **Producto** | Pallets y cajas de ejemplo con mosaico *Columnar / Trabado / Mixto / Auto*, cartón entre capas | Generados a medida |
| 🏭 **Máquinas** | Dispenser de pallets, centrador, envolvedora, mesa de cartón, tablero eléctrico | Biblioteca |
| 🚧 **Vallado** | Paneles perimetrales y puerta | Generados a medida |

**Presets incluidos** — Cajas: 400×300×250, 600×400×300, 500×350×300, bolsas… · Pallets: ARLOG 1200×1000, Europeo 1200×800, Americano 1219×1016, medio pallet, industrial 1200×1200.

### Chequeos automáticos

```mermaid
flowchart TD
    R(["Resultado del layout"]) --> A{"¿Esquina más lejana<br/>del pallet ≤ alcance?"}
    R --> B{"¿Toma de cajas<br/>≤ alcance?"}
    R --> C{"¿Gripper + cajas por toma<br/>≤ carga del robot?"}
    R --> D{"¿Alcance ≤ distancia<br/>al vallado?"}
    A -->|No| X["⚠️ FUERA DE ALCANCE"]
    B -->|No| X
    C -->|No| Y["⚠️ EXCEDE la carga"]
    D -->|No| Z["⚠️ Limitar zonas del robot<br/>o alejar la valla"]
    R --> P["📈 Cajas/capa · capas · altura · kg<br/>cajas/h · pallets/h"]
```

Ejemplo real de salida en [`ejemplos/Layout_Resumen.txt`](ejemplos/Layout_Resumen.txt):

```text
Pallet 1200x1000  caja 500x350x300  patron Columnar
6 cajas/capa x 5 capas = 30 cajas/pallet | altura 1644 mm | 385 kg
Ciclo 8,0 s -> 450 cajas/h -> 15,0 pallets/h
Carga por toma 72 kg / robot 25 kg (estimado) -> EXCEDE
```

---

## 🚀 Cómo arrancar

1. Copiá `Generador_Layout_Paletizado.vb` como **regla externa de iLogic** (por ejemplo en `C:\<tu carpeta>\Reglas iLogic\`).
2. Copiá `Biblioteca_Layout.ejemplo.txt` al lado de la regla como **`Biblioteca_Layout.txt`** y cambiá `RAIZ` por la carpeta donde tenés tus modelos CAD.
3. En la regla, ajustá `CARPETA_CAD` (al principio de `Sub Main`) o dejala en `""` para que la pregunte la primera vez y la recuerde.
4. Abrí o creá un ensamble `.iam` (mejor guardado), ejecutá la regla, configurá en la ventana y tocá **Generar layout**.
5. Si un modelo no aparece o sale acostado, corré el modo **Diagnóstico** y corregí con `ORIENT_<máquina>` / `MAQUINA_<nombre>` en la biblioteca.

### Biblioteca (`Biblioteca_Layout.txt`)

| Clave | Ejemplo | Para qué |
|---|---|---|
| `RAIZ` | `C:\CAD\Biblioteca` | Carpeta(s) donde se buscan los modelos |
| `EXCLUIR` | `OldVersions;Templates` | Subcarpetas que se ignoran |
| `BASE_ROBOT` | `Ensamble base.iam` | Base por defecto |
| `PALLET`, `CAJA`, `VALLA`… | `GENERAR` | Generar a medida en vez de buscar archivo |
| `ORIENT_<máquina>` | `rotX=90` | Corrige modelos acostados o girados |
| `MAQUINA_<nombre>` | `archivo.iam` | Agrega o reemplaza una máquina |
| `ROBOT_<nombre>` | `archivo.iam` | Agrega un robot |

---

## 📚 Contenido

| Archivo | Para qué |
|---|---|
| `Generador_Layout_Paletizado.vb` | La regla iLogic (VB.NET, ~4.500 líneas) |
| `Biblioteca_Layout.ejemplo.txt` | Configuración de la biblioteca de modelos |
| `ejemplos/Layout_Resumen.txt` | Resumen de una corrida real con avisos |

> [!NOTE]
> Las piezas `LAY_*.ipt`, miniaturas, caché de medidas y logs se regeneran solos en `LAY_Generados\` al lado del ensamble; **no se suben al repositorio**.

## ⚠️ Limitaciones y avisos

- Todo lo que empieza con `LAY_` en el ensamble **se borra y se regenera** en cada corrida.
- La carga y el alcance "según modelo" se estiman por el nombre del robot; si el resumen dice *(estimado)*, cargá el dato real en la pestaña **Robot**.
- Conocido: con algunos robots Borunte la inserción falla con `E_INVALIDARG` (ver el resumen de ejemplo).
- Es un **anteproyecto**: distancias de seguridad y vallado se validan con la normativa antes de fabricar.

## 🕓 Historial

| Versión | Fecha | Cambio |
|---|---|---|
| 3 | 2026-10-21 | Ventana con pestañas y vista previa en vivo, chequeos de alcance/carga, modo Diagnóstico |
