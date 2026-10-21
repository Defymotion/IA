"""Genera las chapas de un gripper nuevo en Inventor a partir del diseñador (gripper_design).

Uso:
    .\\.venv\\Scripts\\python.exe .\\scripts\\construir_chapas.py                 -> réplica de ADECO2 (6 × TBA200)
    ... --nombre X --fila 161 --apriete 333 --alto 130 --masa 7 --cajas 6 [--paso 160] [--ancho-pala 140]
    ... --solo "Pala movil"        (construye solo las chapas cuyo nombre contenga el texto)
Salida: Documents\\InventorIA\\Generados\\<nombre>\\ (Chapas\\*.ipt, Corte_laser\\*.dxf, diseno.json, resultado.json)
"""
import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
import inventor_mcp as inv  # noqa: E402
from gripper_calc import Caja  # noqa: E402
from gripper_design import disenar_gripper  # noqa: E402

a = argparse.ArgumentParser()
a.add_argument("--nombre", default="ADECO2_GEN")
a.add_argument("--fila", type=float, default=161)
a.add_argument("--apriete", type=float, default=333)
a.add_argument("--alto", type=float, default=130)
a.add_argument("--masa", type=float, default=7.0)
a.add_argument("--cajas", type=int, default=6)
a.add_argument("--paso", type=float, default=160)
a.add_argument("--ancho-pala", type=float, default=140)
a.add_argument("--solo", default="")
x = a.parse_args()

d = disenar_gripper(Caja(x.fila, x.apriete, x.alto, x.masa, x.nombre), x.cajas,
                    paso=x.paso or None, ancho_pala=x.ancho_pala or None)
base = Path.home() / "Documents" / "InventorIA" / "Generados" / x.nombre
base.mkdir(parents=True, exist_ok=True)
specs = []
for p in d["chapas"]:
    s = asdict(p)
    s["desarrollo"] = p.flat_size()
    specs.append(s)
(base / "diseno.json").write_text(json.dumps({"calculo": d["calculo"], "chapas": specs,
                                              "reutilizadas": d["reutilizadas"],
                                              "comerciales": d["comerciales"], "avisos": d["avisos"]},
                                             ensure_ascii=False, indent=1), encoding="utf-8")
app = inv._inventor()
results = []
for s in specs:
    if x.solo and x.solo.lower() not in s["nombre"].lower():
        continue
    print(f"Construyendo {s['nombre']} ({len(s['circulos'])} agujeros, {len(s['hexagonos'])} hexágonos)...",
          flush=True)
    try:
        r = inv.build_flat_part(app, s, base / "Chapas" / f"{s['nombre']}.ipt",
                                base / "Corte_laser" / f"{s['nombre']}.dxf")
        doc = r.pop("documento")
        inv._safe(lambda: doc.Close(True))
    except Exception as exc:  # noqa: BLE001
        import traceback
        r = {"pieza": s["nombre"], "error": repr(exc), "traza": traceback.format_exc()[-1500:]}
    print("   ", r, flush=True)
    results.append(r)
(base / "resultado.json").write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
print("\nCarpeta:", base)
