"""Especificaciones de la PC (sólo lectura): CPU, RAM, placas de video, discos, sistema y Blender si está instalado.
Uso: python info_pc.py
"""
import json
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
PS = r"""
$o = [ordered]@{}
$o.cpu = Get-CimInstance Win32_Processor | Select-Object Name, NumberOfCores, NumberOfLogicalProcessors, MaxClockSpeed
$o.ram_gb = [math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1GB, 1)
$o.modulos_ram = Get-CimInstance Win32_PhysicalMemory | Select-Object Capacity, Speed, Manufacturer
$o.video = Get-CimInstance Win32_VideoController | Select-Object Name, AdapterRAM, DriverVersion, VideoProcessor, CurrentHorizontalResolution, CurrentVerticalResolution
$o.equipo = Get-CimInstance Win32_ComputerSystem | Select-Object Manufacturer, Model
$o.so = Get-CimInstance Win32_OperatingSystem | Select-Object Caption, Version, OSArchitecture
$o.discos = Get-CimInstance Win32_LogicalDisk -Filter "DriveType=3" | Select-Object DeviceID, @{n='libre_gb';e={[math]::Round($_.FreeSpace/1GB,1)}}, @{n='total_gb';e={[math]::Round($_.Size/1GB,1)}}
$o.discos_fisicos = Get-PhysicalDisk | Select-Object FriendlyName, MediaType, BusType, @{n='gb';e={[math]::Round($_.Size/1GB)}}
$o | ConvertTo-Json -Depth 4
"""
res = {}
try:
    r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", PS], capture_output=True,
                       text=True, timeout=120)
    res["pc"] = json.loads(r.stdout) if r.stdout.strip() else None
    if r.stderr.strip():
        res["ps_errores"] = r.stderr[-1500:]
except Exception as e:  # noqa: BLE001
    res["error"] = repr(e)
# Blender instalado?
cands = list(Path(r"C:\Program Files\Blender Foundation").glob("Blender*/blender.exe")) if Path(r"C:\Program Files\Blender Foundation").exists() else []
res["blender"] = [str(c) for c in cands]
print(json.dumps(res, ensure_ascii=False, indent=1, default=str))
