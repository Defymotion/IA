# Instalador InventorIA para una PC nueva (Windows). Ejecutar desde la carpeta del repositorio:
#   powershell -ExecutionPolicy Bypass -File .\instalar.ps1
# 1) crea Documents\InventorIA y sus subcarpetas  2) copia el complemento y la documentación
# 3) crea el entorno Python (.venv) e instala pywin32, mcp y pillow  4) verifica la instalación
$ErrorActionPreference = "Stop"
$Repo = $PSScriptRoot
# Misma carpeta que usan vigilante.py y los scripts (Path.home() / "Documents"). No usar MyDocuments: con la copia de
# seguridad de OneDrive activa apunta a OneDrive\Documentos y la instalación quedaría separada de la cola de pedidos.
$Docs = Join-Path $env:USERPROFILE "Documents"
$Base = Join-Path $Docs "InventorIA"
Write-Host "Carpeta de trabajo: $Base" -ForegroundColor Cyan
foreach ($d in @("", "_pedidos", "Generados", "Analisis", "Comerciales", "Plantillas", "Calculos")) {
    New-Item -ItemType Directory -Force -Path (Join-Path $Base $d) | Out-Null
}
$Dest = Join-Path $Base "inventor-assistant-portable"
$Src = Join-Path $Repo "inventor-assistant-portable"
if ((Resolve-Path $Src).Path -ne $Dest) {
    New-Item -ItemType Directory -Force -Path $Dest | Out-Null
    # copia todo menos .venv (si ya existe se conserva)
    robocopy $Src $Dest /E /XD ".venv" "__pycache__" /NFL /NDL /NJH /NJS | Out-Null
}
New-Item -ItemType Directory -Force -Path (Join-Path $Dest "docs") | Out-Null
foreach ($f in Get-ChildItem (Join-Path $Repo "docs") -Filter *.md) {
    Copy-Item $f.FullName (Join-Path $Dest "docs") -Force
    $t = Join-Path $Base $f.Name
    if (-not (Test-Path $t)) { Copy-Item $f.FullName $t }      # no pisa la memoria local si ya existe
}
Copy-Item (Join-Path $Repo "CLAUDE.md") (Join-Path $Base "CLAUDE.md") -Force
& powershell -ExecutionPolicy Bypass -File (Join-Path $Dest "scripts\setup.ps1")
if ($LASTEXITCODE -ne 0) { throw "Fallo setup.ps1" }
# acceso directo al vigilante en el escritorio
try {
    $sh = New-Object -ComObject WScript.Shell
    $lnk = $sh.CreateShortcut((Join-Path ([Environment]::GetFolderPath("Desktop")) "Vigilante InventorIA.lnk"))
    $lnk.TargetPath = Join-Path $Dest "scripts\vigilante.bat"
    $lnk.WorkingDirectory = $Dest
    $lnk.Save()
} catch { Write-Host "No se pudo crear el acceso directo (no es grave)." }
Write-Host ""
Write-Host "Verificando (abri Inventor antes para que pase el chequeo de COM)..." -ForegroundColor Cyan
& (Join-Path $Dest ".venv\Scripts\python.exe") (Join-Path $Dest "scripts\verificar_instalacion.py")
Write-Host ""
Write-Host "Listo. Siguiente paso: ver INSTALACION.md, punto 5 (conectar Claude)." -ForegroundColor Green
