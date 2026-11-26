# PLC_Bridge - watcher
# Mira la carpeta inbox\ y ejecuta los trabajos (*.job.json) que deja Claude.
# Cada trabajo es una lista de pasos (ping, info, export, import, compile) para UNA marca de PLC.
# Escribe el resultado en outbox\<id>.result.json y el log en outbox\<id>.log.txt.
# NO descarga nada al PLC ni al panel: cargar en el equipo siempre lo hace una persona.
$ErrorActionPreference = 'Stop'
$Root = $PSScriptRoot
$Cfg = Get-Content (Join-Path $Root 'config.json') -Raw -Encoding UTF8 | ConvertFrom-Json
foreach ($d in 'inbox','outbox','done','logs') { New-Item -ItemType Directory -Force -Path (Join-Path $Root $d) | Out-Null }
$Inbox = Join-Path $Root 'inbox'; $Outbox = Join-Path $Root 'outbox'; $Done = Join-Path $Root 'done'
$Adapters = @{}
foreach ($f in Get-ChildItem (Join-Path $Root 'adapters') -Filter *.ps1) { . $f.FullName; $Adapters[$f.BaseName] = $true }

function New-Log($id) {
  $p = Join-Path $Outbox "$id.log.txt"; Set-Content -Path $p -Value "" -Encoding UTF8
  return { param($m) $l = "[{0}] {1}" -f (Get-Date -Format 'HH:mm:ss'), $m; Write-Host $l; Add-Content -Path $p -Value $l -Encoding UTF8 }.GetNewClosure()
}
function Write-Json($obj, $path) { $obj | ConvertTo-Json -Depth 12 | Set-Content -Path $path -Encoding UTF8 }
function Write-Heartbeat($estado) {
  Write-Json ([ordered]@{ hora = (Get-Date -Format 's'); pid = $PID; estado = $estado; adaptadores = @($Adapters.Keys); config = $Cfg }) (Join-Path $Outbox 'heartbeat.json')
}
function Test-ProyectoPermitido($ruta) {
  $perm = @($Cfg.proyectos_permitidos)
  if ($perm.Count -eq 0) { return $true }
  foreach ($p in $perm) { if ($ruta -and $ruta.ToLower().StartsWith($p.ToLower())) { return $true } }
  return $false
}

function Invoke-Job($jobFile) {
  $job = Get-Content $jobFile.FullName -Raw -Encoding UTF8 | ConvertFrom-Json
  $id = if ($job.id) { $job.id } else { $jobFile.BaseName -replace '\.job$','' }
  $log = New-Log $id
  $res = [ordered]@{ id = $id; vendor = $job.vendor; ok = $true; inicio = (Get-Date -Format 's'); pasos = @(); salidas = @() }
  & $log "=== Trabajo $id ($($job.vendor)) - $(@($job.steps).Count) pasos"
  if (-not $Adapters.ContainsKey($job.vendor)) { $res.ok = $false; $res.error = "Marca desconocida: $($job.vendor). Hay: $(@($Adapters.Keys) -join ', ')" ; & $log $res.error }
  else {
    $ctx = @{ Root = $Root; JobDir = (Join-Path $Inbox $id); OutDir = (Join-Path $Outbox $id); Id = $id; Log = $log; Cfg = $Cfg; Salidas = (New-Object System.Collections.ArrayList) }
    New-Item -ItemType Directory -Force -Path $ctx.OutDir | Out-Null
    $fn = "Invoke-Step_" + $job.vendor
    foreach ($st in @($job.steps)) {
      $r = [ordered]@{ action = $st.action; ok = $false }
      try {
        & $log "--- paso: $($st.action)"
        if ($st.action -eq 'import' -and $Cfg.confirmar_importaciones) {
          $a = Read-Host "Claude quiere IMPORTAR $(@($st.items).Count) objetos en el proyecto. Confirmar? (s/n)"
          if ($a -ne 's') { throw "Importacion rechazada por el usuario en el watcher." }
        }
        $out = & $fn $st $ctx
        $r.ok = $true
        if ($out) { foreach ($k in @($out.Keys)) { $r[$k] = $out[$k] } }
      } catch {
        $r.ok = $false; $r.error = $_.Exception.Message; & $log "ERROR: $($r.error)"
      }
      $res.pasos += $r
      if (-not $r.ok) { $res.ok = $false; if (-not $st.seguir_si_falla) { & $log "Se corta el trabajo (paso fallido)."; break } }
    }
    $res.salidas = @($ctx.Salidas)
  }
  $res.fin = (Get-Date -Format 's')
  Write-Json $res (Join-Path $Outbox "$id.result.json")
  # el trabajo y su carga pasan a done\
  $dst = Join-Path $Done $id; New-Item -ItemType Directory -Force -Path $dst | Out-Null
  Move-Item $jobFile.FullName (Join-Path $dst $jobFile.Name) -Force
  $pl = Join-Path $Inbox $id; if (Test-Path $pl) { Get-ChildItem $pl | Move-Item -Destination $dst -Force; Remove-Item $pl -Recurse -Force -ErrorAction SilentlyContinue }
  & $log ("=== Fin {0}: {1}" -f $id, $(if ($res.ok) { 'OK' } else { 'CON ERRORES' }))
}

Write-Host "PLC_Bridge watcher - carpeta: $Root"
Write-Host "Adaptadores: $(@($Adapters.Keys) -join ', ')"
Write-Host "Esperando trabajos en inbox\  (Ctrl+C para cortar)"
$last = Get-Date '2000-01-01'
while ($true) {
  if (((Get-Date) - $last).TotalSeconds -ge 5) { Write-Heartbeat 'esperando'; $last = Get-Date }
  $jobs = Get-ChildItem $Inbox -Filter '*.job.json' -File -ErrorAction SilentlyContinue | Sort-Object Name
  foreach ($j in $jobs) {
    Start-Sleep -Milliseconds 500   # deja terminar de escribir la carga
    Write-Heartbeat "ejecutando $($j.Name)"
    try { Invoke-Job $j } catch { Write-Host "ERROR inesperado con $($j.Name): $($_.Exception.Message)"; Move-Item $j.FullName (Join-Path $Done ($j.Name + '.fallido')) -Force -ErrorAction SilentlyContinue }
    Write-Heartbeat 'esperando'; $last = Get-Date
  }
  Start-Sleep -Milliseconds ([int]$Cfg.poll_ms)
}
