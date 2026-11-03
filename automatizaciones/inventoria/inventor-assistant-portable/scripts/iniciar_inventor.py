"""Abre Inventor si no está abierto (visible) y espera a que esté listo. Uso: python iniciar_inventor.py"""
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
import inventor_mcp as inv  # noqa: E402

t0 = time.time()
app = inv._inventor(start_if_needed=True, timeout_s=400)
for _ in range(120):
    if inv._safe(lambda: app.Ready, False):
        break
    time.sleep(2)
print("Inventor listo:", inv._safe(lambda: app.SoftwareVersion.DisplayVersion, "?"), round(time.time() - t0, 1), "s")
