"""Dimensiona un gripper de apriete y escribe la memoria de cálculo.

Uso (no necesita Inventor):
    .\\.venv\\Scripts\\python.exe .\\scripts\\calc_gripper.py --nombre TBA200 --fila 161 --apriete 333 --alto 130 --masa 7 --cajas 6
Opciones: --presion 8 --mu 0.4 --fs 2 --acel 5 --margen 10 --apertura 70 --robot-kg 120
Resultado: Documents\\InventorIA\\Calculos\\<nombre>_x<cajas>\\ (memoria.md y resultado.json)
"""
import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
from gripper_calc import Caja, Criterios, dimensionar, memoria_md  # noqa: E402

a = argparse.ArgumentParser()
a.add_argument("--nombre", default="caja")
a.add_argument("--fila", type=float, required=True, help="medida de la caja a lo largo de la fila (mm)")
a.add_argument("--apriete", type=float, required=True, help="medida entre pala fija y móvil (mm)")
a.add_argument("--alto", type=float, required=True)
a.add_argument("--masa", type=float, required=True, help="kg por caja")
a.add_argument("--cajas", type=int, required=True)
a.add_argument("--presion", type=float, default=8.0)
a.add_argument("--mu", type=float, default=0.4)
a.add_argument("--fs", type=float, default=2.0)
a.add_argument("--acel", type=float, default=5.0)
a.add_argument("--margen", type=float, default=10.0)
a.add_argument("--apertura", type=float, default=70.0)
a.add_argument("--robot-kg", type=float, default=None)
x = a.parse_args()

r = dimensionar(Caja(x.fila, x.apriete, x.alto, x.masa, x.nombre), x.cajas,
                Criterios(presion_bar=x.presion, mu=x.mu, fs=x.fs, aceleracion_ms2=x.acel,
                          margen_pala_mm=x.margen, apertura_mm=x.apertura, carga_robot_kg=x.robot_kg))
out = Path.home() / "Documents" / "InventorIA" / "Calculos" / f"{x.nombre}_x{x.cajas}"
out.mkdir(parents=True, exist_ok=True)
(out / "memoria.md").write_text(memoria_md(r), encoding="utf-8")
(out / "resultado.json").write_text(json.dumps(asdict(r), ensure_ascii=False, indent=1), encoding="utf-8")
print(memoria_md(r))
print(f"\nGuardado en {out}")
