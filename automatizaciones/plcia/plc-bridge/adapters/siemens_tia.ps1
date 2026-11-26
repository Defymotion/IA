# Adaptador Siemens TIA Portal (Openness). Probado con V17 + S7-1500 + panel Comfort (WinCC Advanced).
# Pasos: ping | info | export | import | compile
# Requisitos: TIA abierto con el proyecto, usuario en el grupo "Siemens TIA Openness",
# y aceptar una vez el cartel de acceso de Openness ("Si a todo") cuando aparezca en TIA.
$script:TiaConn = $null

function Tia-LoadDll($ctx) {
  if ($script:TiaDllOk) { return }
  $dll = $ctx.Cfg.siemens_tia.dll
  if (-not (Test-Path $dll)) {
    $c = Get-ChildItem 'C:\Program Files\Siemens\Automation' -Recurse -Filter 'Siemens.Engineering.dll' -ErrorAction SilentlyContinue | Where-Object { $_.FullName -match 'PublicAPI' } | Select-Object -First 1
    if ($c) { $dll = $c.FullName } else { throw "No encuentro Siemens.Engineering.dll. Revisar siemens_tia.dll en config.json" }
  }
  Add-Type -Path $dll
  $h = Join-Path (Split-Path $dll) 'Siemens.Engineering.Hmi.dll'; if (Test-Path $h) { try { Add-Type -Path $h } catch { } }
  $script:TiaDllOk = $true
}
function Tia-Connect($st, $ctx) {
  Tia-LoadDll $ctx
  if ($script:TiaConn) { try { $null = $script:TiaConn.Proj.Name; return $script:TiaConn } catch { $script:TiaConn = $null } }
  $procs = [Siemens.Engineering.TiaPortal]::GetProcesses()
  if ($procs.Count -eq 0) { throw "No hay ningun TIA Portal abierto." }
  $want = if ($st.proyecto) { $st.proyecto } else { $ctx.Cfg.siemens_tia.proyecto_contiene }
  $sel = $null
  foreach ($p in $procs) { $pp = try { $p.ProjectPath.FullName } catch { '' }; if (-not $want -or ($pp -and $pp -like "*$want*")) { $sel = $p; break } }
  if (-not $sel) { throw "Ningun TIA abierto tiene un proyecto que contenga '$want'." }
  $tia = $sel.Attach(); $proj = $tia.Projects[0]
  if (-not $proj) { throw "El TIA abierto no tiene proyecto." }
  $plc = $null; $hmi = $null
  foreach ($d in $proj.Devices) {
    if (-not $plc) { $plc = Tia-FindSw $d.DeviceItems ([Siemens.Engineering.SW.PlcSoftware]) }
    if (-not $hmi) { try { $hmi = Tia-FindSw $d.DeviceItems ([Siemens.Engineering.Hmi.HmiTarget]) } catch { } }
  }
  $script:TiaConn = @{ Tia = $tia; Proj = $proj; Plc = $plc; Hmi = $hmi; Path = $proj.Path.FullName }
  & $ctx.Log "Conectado a: $($proj.Name)  ($($proj.Path.FullName))  PLC: $($plc.Name)  HMI: $($hmi.Name)"
  return $script:TiaConn
}
function Tia-FindSw($items, $type) {
  foreach ($it in $items) {
    $m = $it.GetType().GetMethod('GetService').MakeGenericMethod([Siemens.Engineering.HW.Features.SoftwareContainer])
    $sc = $m.Invoke($it, @())
    if ($sc -ne $null -and $sc.Software -is $type) { return $sc.Software }
    $r = Tia-FindSw $it.DeviceItems $type
    if ($r) { return $r }
  }
}
function Tia-Safe($s) { ($s -replace '[\\/:*?"<>|]','_') }
function Tia-Want($name, $only) { if (-not $only -or @($only).Count -eq 0) { return $true }; return (@($only) -contains $name) }

# ---------------- export ----------------
function Tia-Export($st, $ctx, $c) {
  $root = Join-Path $ctx.OutDir 'export'
  if (Test-Path $root) { Remove-Item $root -Recurse -Force }
  $script:xo = 0; $script:xe = 0; $errs = New-Object System.Collections.ArrayList
  $only = $st.solo   # opcional: lista de nombres (bloques, tablas, pantallas)
  $scope = if ($st.alcance) { @($st.alcance) } else { @('plc','hmi') }
  $exp = {
    param($obj, $dir, $name)
    New-Item -ItemType Directory -Force -Path $dir | Out-Null
    $f = New-Object System.IO.FileInfo (Join-Path $dir ((Tia-Safe $name) + '.xml'))
    if ($f.Exists) { $f.Delete() }
    try { $obj.Export($f, [Siemens.Engineering.ExportOptions]::WithDefaults); $script:xo++ }
    catch { $script:xe++; [void]$errs.Add("$name : $($_.Exception.Message)") }
  }
  function ExpTags($grp, $dir, $pre) { foreach ($t in $grp.TagTables) { if (Tia-Want $t.Name $only) { & $exp $t $dir ($pre + $t.Name) } }; foreach ($g in $grp.Groups) { ExpTags $g $dir ($pre + $g.Name + '_') } }
  function ExpBlocks($grp, $dir) { foreach ($b in $grp.Blocks) { if (Tia-Want $b.Name $only) { & $exp $b $dir $b.Name } }; foreach ($g in $grp.Groups) { ExpBlocks $g (Join-Path $dir (Tia-Safe $g.Name)) } }
  function ExpTypes($grp, $dir) { foreach ($t in $grp.Types) { if (Tia-Want $t.Name $only) { & $exp $t $dir $t.Name } }; foreach ($g in $grp.Groups) { ExpTypes $g (Join-Path $dir (Tia-Safe $g.Name)) } }
  function ExpScreens($fo, $dir) { foreach ($s in $fo.Screens) { if (Tia-Want $s.Name $only) { & $exp $s $dir $s.Name } }; foreach ($g in $fo.Folders) { ExpScreens $g (Join-Path $dir (Tia-Safe $g.Name)) } }
  if ($scope -contains 'plc' -and $c.Plc) {
    ExpTags $c.Plc.TagTableGroup (Join-Path $root 'tags_plc') ''
    ExpBlocks $c.Plc.BlockGroup (Join-Path $root 'bloques_plc')
    try { ExpTypes $c.Plc.TypeGroup (Join-Path $root 'tipos_plc') } catch { }
  }
  if ($scope -contains 'hmi' -and $c.Hmi) {
    ExpScreens $c.Hmi.ScreenFolder (Join-Path $root 'pantallas')
    foreach ($pf in 'ScreenPopupFolder','ScreenTemplateFolder') { $f = try { $c.Hmi.$pf } catch { $null }; if ($f) { try { foreach ($s in $f.Screens) { if (Tia-Want $s.Name $only) { & $exp $s (Join-Path $root 'pantallas') ($pf + '_' + $s.Name) } } } catch { } } }
    ExpTags $c.Hmi.TagFolder (Join-Path $root 'tags_hmi') ''
    foreach ($p in 'DiscreteAlarms','AnalogAlarms','AlarmClasses') { $col = try { $c.Hmi.$p } catch { $null }; if ($col) { try { foreach ($a in $col) { & $exp $a (Join-Path $root 'alarmas_hmi') ($p + '_' + $a.Name) } } catch { } } }
  }
  $zip = Join-Path $ctx.Root ("outbox\{0}_export.zip" -f $ctx.Id)
  if (Test-Path $zip) { Remove-Item $zip -Force }
  if (Test-Path $root) { Compress-Archive -Path (Join-Path $root '*') -DestinationPath $zip; [void]$ctx.Salidas.Add($zip) }
  & $ctx.Log "Exportados: $($script:xo)  con error: $($script:xe)"
  if ($script:xe -gt 0) { & $ctx.Log "Si dice 'Inconsistent', compilar y volver a exportar." }
  return [ordered]@{ ok = ($script:xe -eq 0 -or $st.tolerar_errores); exportados = $script:xo; errores = @($errs); zip = $zip }
}

# ---------------- import ----------------
# items: [{ "kind": "...", "file": "ruta relativa a inbox\<id>\", "carpeta": "Grupo/Sub" (opcional) }]
# kinds: plc_tagtable, plc_block, plc_type, hmi_tagtable, hmi_screen
function Tia-Group($grp, $path, $kind) {
  if (-not $path) { return $grp }
  foreach ($n in ($path -split '[\\/]')) {
    if (-not $n) { continue }
    $sub = $grp.Groups | Where-Object { $_.Name -eq $n } | Select-Object -First 1
    if (-not $sub) { $sub = $grp.Groups.Create($n) }
    $grp = $sub
  }
  return $grp
}
function Tia-Import($st, $ctx, $c) {
  if (-not (Test-ProyectoPermitido $c.Path)) { throw "Proyecto NO permitido para escribir: $($c.Path). Agregarlo a proyectos_permitidos en config.json" }
  $opt = [Siemens.Engineering.ImportOptions]::Override
  $done = New-Object System.Collections.ArrayList
  foreach ($it in @($st.items)) {
    $f = Join-Path $ctx.JobDir $it.file
    if (-not (Test-Path $f)) { throw "Falta el archivo $($it.file)" }
    $fi = New-Object System.IO.FileInfo $f
    try {
      switch ($it.kind) {
        'plc_tagtable' { $null = (Tia-Group $c.Plc.TagTableGroup $it.carpeta).TagTables.Import($fi, $opt) }
        'plc_block'    { $null = (Tia-Group $c.Plc.BlockGroup $it.carpeta).Blocks.Import($fi, $opt) }
        'plc_type'     { $null = (Tia-Group $c.Plc.TypeGroup $it.carpeta).Types.Import($fi, $opt) }
        'hmi_tagtable' { if (-not $c.Hmi) { throw 'No hay HMI (o no es WinCC Comfort/Advanced)' }; $null = $c.Hmi.TagFolder.TagTables.Import($fi, $opt) }
        'hmi_screen'   {
          $fo = $c.Hmi.ScreenFolder
          if ($it.carpeta) { foreach ($n in ($it.carpeta -split '[\\/]')) { if ($n) { $x = $fo.Folders | Where-Object { $_.Name -eq $n } | Select-Object -First 1; if (-not $x) { $x = $fo.Folders.Create($n) }; $fo = $x } } }
          $null = $fo.Screens.Import($fi, $opt)
        }
        default { throw "kind desconocido: $($it.kind)" }
      }
      & $ctx.Log "OK  $($it.kind)  $($it.file)"; [void]$done.Add($it.file)
    } catch {
      $m = $_.Exception.Message
      if ($it.kind -eq 'hmi_screen') { $m += "  (si la pantalla esta abierta en el editor de TIA, cerrarla)" }
      throw "Import $($it.file): $m"
    }
  }
  return [ordered]@{ ok = $true; importados = @($done) }
}

# ---------------- compile ----------------
function Tia-Msgs($msgs, $acc, $depth) {
  foreach ($m in $msgs) {
    if ($acc.Count -ge 300) { return }
    $st = "$($m.State)"
    if ($st -ne 'Success' -or $depth -le 1) { [void]$acc.Add(("{0} | {1} | {2}" -f $st, $m.Path, $m.Description)) }
    try { Tia-Msgs $m.Messages $acc ($depth + 1) } catch { }
  }
}
function Tia-CompileOne($sw, $name, $ctx) {
  if (-not $sw) { throw "No hay $name en el proyecto." }
  $m = $sw.GetType().GetMethod('GetService').MakeGenericMethod([Siemens.Engineering.Compiler.ICompilable])
  $svc = $m.Invoke($sw, @())
  if (-not $svc) { throw "$name no se puede compilar por Openness." }
  $r = $svc.Compile()
  $acc = New-Object System.Collections.ArrayList; Tia-Msgs $r.Messages $acc 0
  & $ctx.Log "Compilar $name : $($r.State)  errores $($r.ErrorCount)  avisos $($r.WarningCount)"
  return [ordered]@{ objetivo = $name; estado = "$($r.State)"; errores = $r.ErrorCount; avisos = $r.WarningCount; mensajes = @($acc) }
}
function Tia-Compile($st, $ctx, $c) {
  $t = if ($st.objetivo) { $st.objetivo } else { 'plc' }
  $out = @()
  if ($t -in 'plc','todo') { $out += Tia-CompileOne $c.Plc 'PLC' $ctx }
  if ($t -in 'hmi','todo') { $out += Tia-CompileOne $c.Hmi 'HMI' $ctx }
  $err = 0; foreach ($o in $out) { $err += [int]$o.errores }
  return [ordered]@{ ok = ($err -eq 0); resultados = $out }
}

function Invoke-Step_siemens_tia($st, $ctx) {
  switch ($st.action) {
    'ping'    { return [ordered]@{ ok = $true; msg = 'watcher vivo' } }
    'info'    {
      $c = Tia-Connect $st $ctx
      $devs = @($c.Proj.Devices | ForEach-Object { $_.Name })
      return [ordered]@{ ok = $true; proyecto = $c.Proj.Name; ruta = $c.Path; plc = $c.Plc.Name; hmi = $c.Hmi.Name; dispositivos = $devs; escritura_permitida = (Test-ProyectoPermitido $c.Path) }
    }
    'export'  { $c = Tia-Connect $st $ctx; return Tia-Export $st $ctx $c }
    'import'  { $c = Tia-Connect $st $ctx; return Tia-Import $st $ctx $c }
    'compile' { $c = Tia-Connect $st $ctx; return Tia-Compile $st $ctx $c }
    'save'    { $c = Tia-Connect $st $ctx; if (-not (Test-ProyectoPermitido $c.Path)) { throw "Proyecto no permitido" }; $c.Proj.Save(); return [ordered]@{ ok = $true } }
    default   { throw "Accion no soportada en siemens_tia: $($st.action)" }
  }
}
