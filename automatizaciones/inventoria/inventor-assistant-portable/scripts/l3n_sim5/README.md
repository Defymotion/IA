# Planificador v5 de la planta L3N (Python puro, corre en la nube o en la PC)

Celdas A y B con robot aéreo, giratorias, línea y envolvedora MP402 compartidos.

- `plan5.py rel.json plan.json [--capacidad-robot] [--capacidad-planta T] [--sin-cuadros]` genera el plan por cuadro que
  aplica `simular_l3n_v5.py` sobre la escena de `armar_l3n_sim5.py`.
- `rel.json` es `Analisis\L3N\sim_relevamiento.json` (de `l3n_sim_relevar.py`).
- `ocultos_celdas.json` (de `l3n_listar_ocultos.py`), junto a `plan5.py`: lo oculto dentro de cada celda se repite en la
  escena (en el layout no se ve oculto).
- `kuka_puntos.json` (nube de puntos de los eslabones, de `exportar_stl.py`), junto a `chk5.py`.
- `chk5.py rel.json T`: choques de gripper, cajas, eslabones y robot aéreo.

Módulos: `comun` (álgebra, perfiles), `robot` (IK y tiempos KUKA), `celda5` (ciclos y cruces), `config5` (celdas A y B),
`ingreso5` (pateador, freno con contador), `linea5` (robot aéreo, giratorias, línea, MP402).
