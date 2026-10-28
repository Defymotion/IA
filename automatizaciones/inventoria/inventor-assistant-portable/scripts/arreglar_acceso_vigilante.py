"""Apunta el acceso directo 'Vigilante InventorIA' del escritorio al vigilante bueno
(C:\\Users\\nm\\Documents\\InventorIA\\inventor-assistant-portable\\scripts\\vigilante.bat). Guarda copia del .lnk viejo."""
import json, shutil, sys
from pathlib import Path
import win32com.client
sys.stdout.reconfigure(encoding="utf-8")
sh = win32com.client.Dispatch("WScript.Shell")
esc = Path(sh.SpecialFolders("Desktop"))
lnk = esc / "Vigilante InventorIA.lnk"
bueno = Path.home() / "Documents" / "InventorIA" / "inventor-assistant-portable" / "scripts" / "vigilante.bat"
res = {"lnk": str(lnk), "existe": lnk.exists(), "bat_bueno": str(bueno), "bat_existe": bueno.exists()}
if lnk.exists() and bueno.exists():
    s = sh.CreateShortcut(str(lnk))
    res["destino_antes"] = s.TargetPath
    copia = Path.home() / "Documents" / "InventorIA" / "_staging" / "Vigilante InventorIA_viejo.lnk"
    copia.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(lnk, copia)
    res["copia"] = str(copia)
    s.TargetPath = str(bueno)
    s.WorkingDirectory = str(bueno.parent)
    s.Save()
    res["destino_despues"] = sh.CreateShortcut(str(lnk)).TargetPath
print(json.dumps(res, ensure_ascii=False, indent=1))
