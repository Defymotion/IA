$ErrorActionPreference = "Stop"
$PluginRoot = Split-Path -Parent $PSScriptRoot
$VenvPython = Join-Path $PluginRoot ".venv\Scripts\python.exe"

function Find-Python {
    # Preferir el lanzador "py"; evitar el alias de Microsoft Store (WindowsApps)
    foreach ($cmd in @("py", "python")) {
        $c = Get-Command $cmd -ErrorAction SilentlyContinue
        if ($c -and $c.Source -notlike "*\WindowsApps\*") {
            & $c.Source -c "import sys; assert sys.version_info >= (3, 10)" 2>$null
            if ($LASTEXITCODE -eq 0) { return $c.Source }
        }
    }
    return $null
}

if (-not (Test-Path -LiteralPath $VenvPython)) {
    $Python = Find-Python
    if (-not $Python) {
        Write-Host "No se encontro Python 3.10+ en este equipo." -ForegroundColor Red
        Write-Host "Instalalo con:  winget install -e --id Python.Python.3.13"
        Write-Host "Despues cerra y volve a abrir PowerShell, y ejecuta este script de nuevo."
        exit 1
    }
    Write-Host "Usando $Python"
    & $Python -m venv (Join-Path $PluginRoot ".venv")
    if ($LASTEXITCODE -ne 0) { throw "No se pudo crear el entorno .venv" }
}

& $VenvPython -m pip install --upgrade pip
& $VenvPython -m pip install -r (Join-Path $PluginRoot "requirements.txt")
if ($LASTEXITCODE -ne 0) { throw "Fallo la instalacion de dependencias" }
Write-Host "Inventor Assistant listo. Reinicia Codex para cargar el servidor MCP." -ForegroundColor Green
