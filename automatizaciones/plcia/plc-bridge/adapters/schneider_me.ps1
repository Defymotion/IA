# Adaptador Schneider EcoStruxure Machine Expert (base CODESYS) - BETA, sin probar en planta.
# Usa el motor de scripts Python de Machine Expert en modo sin interfaz:
#   LogicBuilder.exe --noui --runscript="script.py"
# Los parametros van por un .json cuya ruta se pasa en la variable de entorno PLC_BRIDGE_PARAMS.
# IMPORTANTE: el proyecto (.project) tiene que estar CERRADO en Machine Expert (lo abre el script).
# Pasos: ping | export | import | compile.  Formato de intercambio: PLCopenXML.
# Control Expert (Unity / M340 / M580) NO tiene esta API: ahi se trabaja con .XEF/.ZEF exportado a mano.
function Invoke-Step_schneider_me($st, $ctx) {
  if ($st.action -eq 'ping') { return [ordered]@{ ok = $true; msg = 'watcher vivo' } }
  $exe = $ctx.Cfg.schneider_me.exe
  if (-not (Test-Path $exe)) { throw "No encuentro Machine Expert en '$exe' (config.json -> schneider_me.exe)" }
  if (-not $st.proyecto) { throw "Falta 'proyecto' (ruta del .project)" }
  if ($st.action -in 'import','compile' -and -not (Test-ProyectoPermitido $st.proyecto)) { throw "Proyecto NO permitido para escribir: $($st.proyecto)" }
  $py = Join-Path $ctx.Root 'adapters\schneider_me\bridge_me.py'
  $p = [ordered]@{ action = $st.action; proyecto = $st.proyecto; salida_dir = $ctx.OutDir; job_dir = $ctx.JobDir; archivos = @($st.archivos); guardar = [bool]($st.action -eq 'import'); resultado = (Join-Path $ctx.OutDir ($st.action + '_me.json')) }
  $pj = Join-Path $ctx.OutDir ($st.action + '_params.json'); $p | ConvertTo-Json -Depth 6 | Set-Content $pj -Encoding UTF8
  $env:PLC_BRIDGE_PARAMS = $pj
  & $ctx.Log "Machine Expert: $($st.action) $($st.proyecto)"
  $argList = @('--noui', "--runscript=`"$py`"") + @($ctx.Cfg.schneider_me.args_extra)
  $pr = Start-Process -FilePath $exe -ArgumentList $argList -PassThru -WindowStyle Minimized
  $lim = if ($st.timeout_s) { [int]$st.timeout_s } else { 900 }
  if (-not $pr.WaitForExit($lim * 1000)) { try { $pr.Kill() } catch { }; throw "Machine Expert no termino en $lim s" }
  if (-not (Test-Path $p.resultado)) { throw "El script no dejo resultado (ver log de Machine Expert)." }
  $r = Get-Content $p.resultado -Raw -Encoding UTF8 | ConvertFrom-Json
  foreach ($m in @($r.msgs)) { & $ctx.Log $m }
  if ($st.action -eq 'export') {
    $zip = Join-Path $ctx.Root ("outbox\{0}_export.zip" -f $ctx.Id)
    if (Test-Path $zip) { Remove-Item $zip -Force }
    Compress-Archive -Path (Join-Path $ctx.OutDir 'export\*') -DestinationPath $zip; [void]$ctx.Salidas.Add($zip)
  }
  return [ordered]@{ ok = [bool]$r.ok; detalle = $r }
}
