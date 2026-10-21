"""Dimensionamiento de grippers por apriete lateral (DEFYMOTION).

Configuración tipo (ADECO2):
- Una pala fija corrida y una fila de N cajas.
- Un módulo de pala móvil por caja: pala de chapa + goma, 2 guías lineales y 1 cilindro compacto.
- Cada pala toma una sola caja y no debe tocar la de al lado.

Criterio de apriete: la caja queda sostenida por fricción en sus dos caras (pala fija y pala móvil):
    2 · μ · F_cilindro ≥ m · (g + a) · FS
Sin dependencias de Inventor: se puede usar y probar en cualquier PC.
Los valores de catálogo son de referencia y deben verificarse con el catálogo vigente del fabricante.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field, asdict

G = 9.81

# Festo ADN (cilindro compacto): diámetro de émbolo → (Ø vástago, carrera máx. de referencia)
ADN_BORES = {12: (6, 60), 16: (8, 80), 20: (10, 150), 25: (10, 300), 32: (12, 300),
             40: (12, 300), 50: (16, 300), 63: (16, 300), 80: (20, 300), 100: (25, 300)}
ADN_STROKES = [5, 10, 15, 20, 25, 30, 40, 50, 60, 80, 100, 125, 150, 200, 250, 300]
# masa aprox. (kg) con carrera 80, para estimar la masa del gripper
ADN_MASS_KG = {12: 0.10, 16: 0.14, 20: 0.22, 25: 0.39, 32: 0.52, 40: 0.75, 50: 1.10,
               63: 1.50, 80: 2.60, 100: 4.00}

# HIWIN HG, bloque tipo CA: largo del bloque (mm), masa bloque (kg), masa riel (kg/m)
HIWIN = {"HGH15CA": (61.4, 0.18, 1.45), "HGH20CA": (77.5, 0.30, 2.21)}

# Masas de referencia medidas en ADECO2 (acero), para estimar
REF = {"chasis_kg_por_m": 21.05 / 0.96, "pala_fija_kg_por_m": 6.54 / 0.94, "brida_kg": 10.6,
       "neumatica_base_kg": 1.5, "neumatica_por_valvula_kg": 0.15}


@dataclass
class Caja:
    ancho_fila_mm: float      # medida a lo largo de la fila (define el paso y el ancho de pala)
    largo_apriete_mm: float   # medida entre pala fija y pala móvil
    alto_mm: float
    masa_kg: float
    nombre: str = "caja"


@dataclass
class Criterios:
    presion_bar: float = 8.0
    mu: float = 0.4               # goma / cartón (a calibrar con ensayos)
    fs: float = 2.0               # factor de seguridad sobre la retención
    aceleracion_ms2: float = 5.0  # aceleración vertical máxima del robot con carga
    huelgo_entre_cajas_mm: float = 0.0
    margen_pala_mm: float = 10.0  # por lado: la pala queda más angosta que la caja para no morder la vecina
    apertura_mm: float = 70.0     # apertura total para que entre la caja (calibrado con ADECO2: carrera 80)
    tolerancia_caja_mm: float = 10.0
    extremos_chasis_mm: float = 0.0
    carga_robot_kg: float | None = None


@dataclass
class Resultado:
    entradas: dict
    paso_mm: float
    ancho_pala_mm: float
    alto_pala_sugerido_mm: float
    fuerza_requerida_n: float
    cilindro: str
    diametro_mm: int
    carrera_mm: int
    fuerza_cilindro_n: float
    fs_real: float
    guia: str
    riel_mm: int
    largo_chasis_mm: float
    largo_pala_fija_mm: float
    masa_gripper_kg: float
    masa_total_kg: float
    alternativas: list = field(default_factory=list)
    avisos: list = field(default_factory=list)


def fuerza_adn(diametro_mm: float, presion_bar: float) -> float:
    """Fuerza teórica de avance (N)."""
    return math.pi * (diametro_mm / 2) ** 2 * presion_bar * 0.1


def dimensionar(caja: Caja, n_cajas: int, c: Criterios = Criterios()) -> Resultado:
    avisos = []
    # geometría
    paso = caja.ancho_fila_mm + c.huelgo_entre_cajas_mm
    ancho_pala = caja.ancho_fila_mm - 2 * c.margen_pala_mm
    if ancho_pala <= 0:
        raise ValueError("El margen de pala es mayor que la caja")
    if paso - ancho_pala < 2 * c.margen_pala_mm:
        avisos.append("Luz entre palas vecinas menor a 2 × margen: riesgo de morder la caja de al lado.")
    alto_pala = caja.alto_mm + 2                  # ADECO2: pala 132 para caja de 130

    # fuerza
    f_req = caja.masa_kg * (G + c.aceleracion_ms2) * c.fs / (2 * c.mu)
    carrera_min = c.apertura_mm + c.tolerancia_caja_mm
    carrera = next((s for s in ADN_STROKES if s >= carrera_min), None)
    if carrera is None:
        raise ValueError(f"Carrera necesaria {carrera_min} mm fuera de catálogo ADN")
    elegido, alternativas = None, []
    for d, (_, s_max) in ADN_BORES.items():
        f = fuerza_adn(d, c.presion_bar)
        ok = f >= f_req and carrera <= s_max and d * 1.6 <= ancho_pala
        alternativas.append({"cilindro": f"ADN-{d}-{carrera}", "fuerza_n": round(f), "fs": round(
            2 * c.mu * f / (caja.masa_kg * (G + c.aceleracion_ms2)), 2), "cumple": ok})
        if ok and elegido is None:
            elegido = d
    if elegido is None:
        raise ValueError("Ningún ADN cumple: revisar criterios, cantidad de cilindros por pala o ancho de pala")
    f_cil = fuerza_adn(elegido, c.presion_bar)
    fs_real = 2 * c.mu * f_cil / (caja.masa_kg * (G + c.aceleracion_ms2))

    # guías
    guia = "HGH15CA" if ancho_pala <= 200 and caja.masa_kg <= 25 else "HGH20CA"
    riel = int(math.ceil((carrera + HIWIN[guia][0]) / 10.0) * 10)

    # chasis
    largo_chasis = n_cajas * paso + 2 * c.extremos_chasis_mm
    largo_pala_fija = largo_chasis - 20

    # masa estimada
    blk_len, blk_kg, rail_kg_m = HIWIN[guia]
    modulo = (0.715 * ancho_pala / 140) + 2 * (blk_kg + rail_kg_m * riel / 1000) \
        + ADN_MASS_KG[elegido] + 0.05
    masa_gripper = (REF["chasis_kg_por_m"] * largo_chasis / 1000 + REF["pala_fija_kg_por_m"]
                    * largo_pala_fija / 1000 + REF["brida_kg"] + n_cajas * modulo
                    + REF["neumatica_base_kg"] + n_cajas * REF["neumatica_por_valvula_kg"])
    masa_total = masa_gripper + n_cajas * caja.masa_kg
    if c.carga_robot_kg and masa_total > c.carga_robot_kg:
        avisos.append(f"Masa total {masa_total:.1f} kg supera la carga del robot ({c.carga_robot_kg} kg).")
    if c.mu > 0.6:
        avisos.append("μ > 0,6 es optimista para goma sobre cartón; confirmar con ensayo.")

    return Resultado(
        entradas={"caja": asdict(caja), "n_cajas": n_cajas, "criterios": asdict(c)},
        paso_mm=paso, ancho_pala_mm=ancho_pala, alto_pala_sugerido_mm=alto_pala,
        fuerza_requerida_n=round(f_req, 1), cilindro=f"Festo ADN-{elegido}-{carrera}",
        diametro_mm=elegido, carrera_mm=carrera, fuerza_cilindro_n=round(f_cil, 1),
        fs_real=round(fs_real, 2), guia=f"HIWIN {guia} ×2, riel {riel} mm", riel_mm=riel,
        largo_chasis_mm=largo_chasis, largo_pala_fija_mm=largo_pala_fija,
        masa_gripper_kg=round(masa_gripper, 1), masa_total_kg=round(masa_total, 1),
        alternativas=alternativas, avisos=avisos)


def memoria_md(r: Resultado) -> str:
    cj, cr = r.entradas["caja"], r.entradas["criterios"]
    m, a = cj["masa_kg"], cr["aceleracion_ms2"]
    lines = [
        f"# Memoria de cálculo — gripper de apriete, {r.entradas['n_cajas']} × {cj['nombre']}", "",
        "## Datos",
        f"- Caja: {cj['ancho_fila_mm']} (fila) × {cj['largo_apriete_mm']} (apriete) × {cj['alto_mm']} (alto) mm — {m} kg",
        f"- Presión {cr['presion_bar']} bar · μ goma = {cr['mu']} · FS = {cr['fs']} · aceleración vertical {a} m/s²", "",
        "## Fuerza de apriete por caja",
        "La caja se sostiene por fricción en sus dos caras: 2·μ·F ≥ m·(g+a)·FS",
        f"- F requerida = {m}·({G}+{a})·{cr['fs']} / (2·{cr['mu']}) = **{r.fuerza_requerida_n} N**",
        f"- Cilindro elegido: **{r.cilindro}** → {r.fuerza_cilindro_n} N a {cr['presion_bar']} bar (teórica)",
        f"- Factor de seguridad real: **{r.fs_real}**", "",
        "| Cilindro | Fuerza N | FS | Cumple |", "|---|---|---|---|",
        *[f"| {x['cilindro']} | {x['fuerza_n']} | {x['fs']} | {'sí' if x['cumple'] else 'no'} |"
          for x in r.alternativas[:7]], "",
        "## Geometría",
        f"- Paso entre palas: {r.paso_mm} mm · ancho de pala: {r.ancho_pala_mm} mm (margen {cr['margen_pala_mm']} mm por lado)",
        f"- Alto de pala sugerido: {r.alto_pala_sugerido_mm} mm",
        f"- Carrera: {r.carrera_mm} mm (apertura {cr['apertura_mm']} + tolerancia {cr['tolerancia_caja_mm']})",
        f"- Guías: {r.guia}",
        f"- Chasis: {r.largo_chasis_mm} mm · pala fija: {r.largo_pala_fija_mm} mm", "",
        "## Masas (estimadas con referencias de ADECO2)",
        f"- Gripper: ~{r.masa_gripper_kg} kg · con cajas: ~{r.masa_total_kg} kg", "",
    ]
    if r.avisos:
        lines += ["## Avisos", *[f"- {w}" for w in r.avisos], ""]
    lines += ["> Valores teóricos de catálogo y μ supuesto. El cálculo debe ser revisado y aprobado por el "
              "ingeniero responsable antes de fabricar."]
    return "\n".join(lines)


if __name__ == "__main__":  # validación contra ADECO2
    adeco = Caja(ancho_fila_mm=161, largo_apriete_mm=333, alto_mm=130, masa_kg=7.0, nombre="TBA200")
    res = dimensionar(adeco, 6)
    print(memoria_md(res))
