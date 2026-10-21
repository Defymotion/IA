AddReference "System.Drawing"
' =====================================================================
'  GENERADOR DE LAYOUTS DE CELDAS DE PALETIZADO  -  regla iLogic  v3
' ---------------------------------------------------------------------
'  - Ventana de configuracion con pestanas y VISTA PREVIA en vivo
'    (planta + mosaico del pallet) antes de generar.
'  - Busca los modelos por nombre en las carpetas RAIZ de la biblioteca
'    (C:\Tadeo\CosasParaCAD). Detecta solos robots y maquinas.
'  - Pallets, cajas, transportadores, vallado, puerta y tope se generan
'    a medida. Todo se ubica por caja envolvente, sin depender del
'    origen de cada modelo; el robot se endereza y ancla en su base.
'
'  USO: ensamble (mejor guardado) -> ejecutar la regla -> configurar ->
'       "Generar layout". Todo lo LAY_* se borra y se regenera.
'
'  BIBLIOTECA: C:\Tadeo\Reglas iLogic\Biblioteca_Layout.txt
'   (o Biblioteca_Layout.txt al lado del ensamble). CLAVE = valor
'   ORIENT_<maquina> = rotX=90   corrige modelos acostados/girados
'   MAQUINA_<maquina> = archivo  elige el archivo principal de una maquina
'
'  CONVENCION: robot en (0,0,0), X derecha, Y atras, Z arriba, mm.
' =====================================================================
Sub Main()
	' >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
	'  CONFIGURACION DE ESTA PC: carpeta donde estan tus modelos CAD
	'  (robots, maquinas, bases, grippers). Cambiala por la tuya en cada PC.
	'  Si la dejas vacia ("") la regla te la pregunta y la recuerda.
	CARPETA_CAD = "C:\Tadeo\CosasParaCAD"
	' >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
	app = ThisApplication
	If ThisDoc.Document.DocumentType <> DocumentTypeEnum.kAssemblyDocumentObject Then
		MessageBox.Show("Ejecuta esta regla dentro de un ensamble (.iam).", "Layout paletizado")
		Exit Sub
	End If
	Dim asm As AssemblyDocument = ThisDoc.Document
	cd = asm.ComponentDefinition
	tg = app.TransientGeometry
	Dim asmDir As String = DirDatos()
	If asm.FullFileName <> "" Then
		asmDir = System.IO.Path.GetDirectoryName(asm.FullFileName)
	Else
		Lg("AVISO: el ensamble no esta guardado; las piezas generadas van a " & asmDir & "\LAY_Generados")
	End If
	genDir = System.IO.Path.Combine(asmDir, "LAY_Generados")
	System.IO.Directory.CreateDirectory(genDir)
	EscribirLog("INICIO " & DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss") & "  ensamble: " & If(asm.FullFileName = "", asm.DisplayName & " (sin guardar)", asm.FullFileName))

	CargarBiblioteca(asmDir)
	IndexarRaices()
	CargarCache()
	Dim nuevos As Boolean = CrearParametros()
	CargarCfg()

	Dim modo As String = PTxt("L_Modo")
	If modo = "Generar" AndAlso PBool("L_Dialogo") Then
		modo = MostrarDialogo()
		While modo = "Reabrir"
			' se cambio la carpeta de la biblioteca: se vuelve a indexar todo
			GuardarCfg()
			INDICE.Clear() : ROBOTS.Clear() : MAQUINAS.Clear() : BASES.Clear()
			CargarBiblioteca(asmDir)
			IndexarRaices()
			ctl.Clear() : ctlUnidad.Clear() : secciones.Clear() : navBotones.Clear()
			cargandoDlg = True : vistaIni = False : selGrupo = "" : ultimoPrev = "-"
			modo = MostrarDialogo()
		End While
		If modo = "Cancelar" Then Exit Sub
		GuardarCfg()
	ElseIf nuevos Then
		MessageBox.Show("Se crearon los parametros L_* en el ensamble.", "Layout paletizado")
	End If
	If modo = "Diagnostico" Then
		Diagnostico()
		EscribirLog("Diagnostico en " & genDir & "\Diagnostico_Biblioteca.txt")
		Exit Sub
	End If

	faltan.Clear()
	app.ScreenUpdating = False
	app.SilentOperation = True
	Dim ok As Boolean = False
	Try
		BorrarGenerados()
		If modo = "Generar" Then Generar()
		ok = True
	Catch ex As Exception
		Lg("ERROR: " & ex.Message & " | " & ex.StackTrace)
	Finally
		app.SilentOperation = False
		app.ScreenUpdating = True
	End Try
	asm.Update()
	Try
		app.ActiveView.Fit()
	Catch
	End Try
	GuardarCache()

	Dim res As New System.Text.StringBuilder
	res.AppendLine("LAYOUT PALETIZADO - " & DateTime.Now.ToString("yyyy-MM-dd HH:mm"))
	res.AppendLine("Biblioteca: " & bibUsada & "   (" & INDICE.Count & " modelos, " & ROBOTS.Count & " robots, " & MAQUINAS.Count & " maquinas)")
	res.AppendLine("")
	res.AppendLine("RESUMEN")
	For Each l As String In stats
		res.AppendLine("  " & l)
	Next
	If avisos.Count > 0 Then
		res.AppendLine("")
		res.AppendLine("ATENCION")
		For Each l As String In avisos
			res.AppendLine("  - " & l)
		Next
	End If
	If faltan.Count > 0 Then
		res.AppendLine("")
		res.AppendLine("NO ENCONTRADOS (se omitieron)")
		For Each f As String In faltan
			res.AppendLine("  - " & f)
		Next
	End If
	res.AppendLine("")
	res.AppendLine("REGISTRO")
	res.Append(logSb.ToString())
	Dim resPath As String = System.IO.Path.Combine(genDir, "Layout_Resumen.txt")
	Try
		System.IO.File.WriteAllText(resPath, res.ToString(), System.Text.Encoding.UTF8)
	Catch
	End Try
	EscribirLog(res.ToString())
	Dim corto As String = res.ToString()
	If corto.Length > 2200 Then corto = corto.Substring(0, 2200) & vbCrLf & "... (ver " & resPath & ")"
	MessageBox.Show(If(ok, "", "EL LAYOUT QUEDO INCOMPLETO POR UN ERROR (ver REGISTRO)" & vbCrLf & vbCrLf) & corto, "Layout paletizado")
End Sub

' ---- variables de la regla (en iLogic van DESPUES de Sub Main)
Private CARPETA_CAD As String = ""
Private Const BIB_GLOBAL As String = "C:\Tadeo\Reglas iLogic\Biblioteca_Layout.txt"
Private app As Inventor.Application
Private cd As AssemblyComponentDefinition
Private tg As TransientGeometry
Private LIBR As New Dictionary(Of String, String)(StringComparer.OrdinalIgnoreCase)
Private ROBOTS As New Dictionary(Of String, String)(StringComparer.OrdinalIgnoreCase)
Private MAQUINAS As New Dictionary(Of String, String)(StringComparer.OrdinalIgnoreCase)
Private BASES As New Dictionary(Of String, String)(StringComparer.OrdinalIgnoreCase)
Private rectV() As Double = Nothing
Private INDICE As New List(Of String)
Private logSb As New System.Text.StringBuilder
Private faltan As New List(Of String)
Private nOcc As Integer = 0
Private genDir As String = ""
Private bibUsada As String = ""
Private cfg As New Dictionary(Of String, Object)(StringComparer.OrdinalIgnoreCase)
Private CACHE As New Dictionary(Of String, Double())(StringComparer.OrdinalIgnoreCase)
Private plan As New List(Of ItemPlan)
Private stats As New List(Of String)
Private avisos As New List(Of String)
Private alcanceAct As Double = 2000
Private hayProblema As Boolean = False
' posiciones editadas a mano: grupo -> {dx, dy, giro, absoluto(0/1)}
Private offs As New Dictionary(Of String, Double())(StringComparer.OrdinalIgnoreCase)
Private robX As Double = 0, robY As Double = 0, robAng As Double = -90
' datos del mosaico (para la vista previa)
Private mosPx As Double, mosPy As Double, mosA As Double, mosB As Double
Private mosPW As Double, mosPD As Double, mosTipo As String = "Auto", mosCapas As Integer = 1

' cada cosa del layout, calculada antes de colocarla (la misma lista dibuja la vista previa)
Class ItemPlan
	Public Tipo As String = ""
	Public Nombre As String = ""
	Public Etiqueta As String = ""
	Public Ruta As String = ""
	Public Gen As String = ""
	Public GenP() As Double = Nothing
	Public Cx As Double = 0
	Public Cy As Double = 0
	Public Z0 As Double = 0
	Public W As Double = 0
	Public D As Double = 0
	Public H As Double = 0
	Public Rot As Double = 0
	Public Eje As String = ""
	Public RotBase() As Double = Nothing
	Public Capa As Integer = -1
	Public Cruza As Boolean = False
	Public Adentro As Boolean = False
	Public FaltaModelo As Boolean = False
	Public Borde As Integer = -1
	Public Function Clonar() As ItemPlan
		Return CType(Me.MemberwiseClone(), ItemPlan)
	End Function
End Class

' =====================================================================
'  DEFINICION DE TODOS LOS PARAMETROS (nombre|defecto|unidad|pestana|texto|control)
' =====================================================================
Function Defs() As String()
	Return New String() { _
	"L_Modo|Generar|txt|-|Modo|combo:Generar,Diagnostico,Borrar", _
	"L_Dialogo|True|bool|-|Mostrar ventana|bool", _
	"L_Posiciones||txt|-|Posiciones editadas|txt", _
	"L_Robot|BRTIRPZ3116B|txt|Robot|Modelo de robot|combo:@ROBOTS", _
	"L_AlcanceRobot|0|mm|Robot|Alcance (0 = segun modelo)|num", _
	"L_CargaRobot|0|ul|Robot|Carga max. kg (0 = segun modelo)|num", _
	"L_PesoGripper|60|ul|Robot|Peso del gripper (kg)|num", _
	"L_CajasPorToma|1|ul|Robot|Cajas por toma|num", _
	"L_CicloSeg|8|ul|Robot|Tiempo de ciclo por toma (s)|num1", _
	"L_Gripper|Generado (ventosas)|txt|Robot|Gripper|combo:@GRIP", _
	"L_RotGripper|0|deg|Robot|   giro del gripper|num", _
	"L_ModeloBase|Automatica|txt|Robot|Base del robot|combo:@BASES", _
	"L_LadoBaseGen|900|mm|Robot|   lado de base generada|num", _
	"L_AlturaBaseGen|500|mm|Robot|   altura de base generada|num", _
	"L_RobotArriba|Auto|txt|Robot|Eje hacia arriba del modelo|combo:Auto,Z,Y,-Y,X,-X", _
	"L_RotRobot|0|deg|Robot|Giro extra del robot|num", _
	"L_CorrEjeRobotX|0|mm|Robot|Correccion eje 1 en X|num", _
	"L_CorrEjeRobotY|0|mm|Robot|Correccion eje 1 en Y|num", _
	"L_Estaciones|1|ul|Linea|Estaciones de paletizado|combo:1,2", _
	"L_TramosVacio|0|ul|Linea|Tramos dispenser -> estacion|num", _
	"L_TramosSalida|1|ul|Linea|Tramos de salida|num", _
	"L_SentidoLinea|+X|txt|Linea|Sentido de avance|combo:+X,-X", _
	"L_DistRobotPallet|1500|mm|Linea|Robot -> eje de la linea|num", _
	"L_LargoTramo|1600|mm|Linea|Largo de cada tramo|num", _
	"L_AnchoLinea|0|mm|Linea|Ancho (0 = automatico)|num", _
	"L_AlturaLinea|450|mm|Linea|Altura de la linea|num", _
	"L_LadoEntrada|Atras|txt|Entrada|Lado de entrada|combo:Atras,Izquierda,Derecha", _
	"L_Entradas|1|ul|Entrada|Cantidad de cintas|combo:1,2", _
	"L_SepEntradas|900|mm|Entrada|Separacion entre cintas|num", _
	"L_DistRobotEntrada|1300|mm|Entrada|Robot -> fin de cinta|num", _
	"L_LargoCintaEntrada|4000|mm|Entrada|Largo de cinta|num", _
	"L_AnchoCinta|500|mm|Entrada|Ancho de cinta|num", _
	"L_AlturaCinta|800|mm|Entrada|Altura de cinta|num", _
	"L_OffsetEntrada|0|mm|Entrada|Corrimiento lateral|num", _
	"L_TipoTope|Generado|txt|Entrada|Tope de cajas|combo:Generado,Freno de cajas,Ninguno", _
	"L_RotTope|0|deg|Entrada|Giro del freno de cajas|num", _
	"L_PresetCaja|400x300x250|txt|Producto|Caja tipo|combo:@CAJAS", _
	"L_Caja_L|400|mm|Producto|Caja largo|num", _
	"L_Caja_A|300|mm|Producto|Caja ancho|num", _
	"L_Caja_H|250|mm|Producto|Caja alto|num", _
	"L_PesoCaja|12|ul|Producto|Peso de la caja (kg)|num1", _
	"L_PresetPallet|ARLOG 1200x1000x144|txt|Producto|Pallet tipo|combo:@PALLETS", _
	"L_Pallet_L|1200|mm|Producto|Pallet largo|num", _
	"L_Pallet_A|1000|mm|Producto|Pallet ancho|num", _
	"L_Pallet_H|144|mm|Producto|Pallet alto|num", _
	"L_PalletEje|X|txt|Producto|Lado largo del pallet sobre|combo:X,Y", _
	"L_Patron|Auto|txt|Producto|Patron de mosaico|combo:Auto,Columnar,Trabado,Mixto", _
	"L_ModoCapas|Por altura|txt|Producto|Cantidad de capas|combo:Por altura,Por cantidad", _
	"L_Capas|4|ul|Producto|Capas (si es por cantidad)|num", _
	"L_AlturaMaxCarga|1800|mm|Producto|Altura max. pallet cargado|num", _
	"L_Voladizo|0|mm|Producto|Voladizo (+) / margen (-)|num", _
	"L_Separadores|False|bool|Producto|Carton entre capas|bool", _
	"L_CajasEjemplo|True|bool|Producto|Mostrar cajas|bool", _
	"L_Dispenser|True|bool|Maquinas|Dispenser de pallets|bool", _
	"L_ModeloDispenser|Dispenser_Pallets|txt|Maquinas|   modelo|combo:@MAQ", _
	"L_RotDispenser|0|deg|Maquinas|   giro|num", _
	"L_Centrador|False|bool|Maquinas|Centrador de pallet (estacion 1)|bool", _
	"L_ModeloCentrador|Centrador de palet tucuman 2026|txt|Maquinas|   modelo|combo:@MAQ", _
	"L_RotCentrador|0|deg|Maquinas|   giro|num", _
	"L_Envolvedora|False|bool|Maquinas|Envolvedora al final de linea|bool", _
	"L_ModeloEnvolvedora|Envolvedora MP402|txt|Maquinas|   modelo|combo:@MAQ", _
	"L_RotEnvolvedora|0|deg|Maquinas|   giro|num", _
	"L_SepEnvolvedora|300|mm|Maquinas|   separacion|num", _
	"L_MesaCarton|True|bool|Maquinas|Mesa de carton (separadores)|bool", _
	"L_ModeloMesa|Mesa carton BLQ|txt|Maquinas|   modelo|combo:@MAQ", _
	"L_LadoMesa|Auto|txt|Maquinas|   lado|combo:Auto,Derecha,Izquierda,Atras", _
	"L_DistRobotMesa|1500|mm|Maquinas|   distancia al robot|num", _
	"L_RotMesa|0|deg|Maquinas|   giro|num", _
	"L_Tablero|True|bool|Maquinas|Tablero electrico|bool", _
	"L_ModeloTablero|Tablero|txt|Maquinas|   modelo|combo:@MAQ", _
	"L_RotTablero|0|deg|Maquinas|   giro|num", _
	"L_Vallado|True|bool|Vallado|Vallado perimetral|bool", _
	"L_MargenVallado|700|mm|Vallado|Margen alrededor de la celda|num", _
	"L_ValladoAlcance|False|bool|Vallado|Alejar vallado fuera del alcance|bool", _
	"L_AlturaValla|2000|mm|Vallado|Altura|num", _
	"L_PanelValla|1500|mm|Vallado|Ancho maximo de panel|num", _
	"L_Puerta|True|bool|Vallado|Puerta|bool", _
	"L_LadoPuerta|Auto|txt|Vallado|   lado de la puerta|combo:Auto,Frente,Fondo,Izquierda,Derecha", _
	"L_Extras||txt|-|Maquinas agregadas|txt",
	"L_Ocultos||txt|-|Grupos quitados|txt"}
End Function

Function PresetsCaja() As String()
	Return New String() {"Personalizada", "400x300x250", "400x300x200", "600x400x300", "600x400x200", "300x200x200", "500x350x300", "380x280x260", "Bolsa 600x400x150", "Bolsa 700x450x120"}
End Function
Function PresetsPallet() As String()
	Return New String() {"Personalizado", "ARLOG 1200x1000x144", "Europeo 1200x800x144", "Americano 1219x1016x150", "Medio pallet 800x600x144", "Industrial 1200x1200x150"}
End Function

Function CrearParametros() As Boolean
	Dim n0 As Integer = cd.Parameters.UserParameters.Count
	For Each d As String In Defs()
		Dim p() As String = d.Split("|"c)
		Select Case p(2)
			Case "txt"
				PDef(p(0), p(1))
			Case "bool"
				PDef(p(0), CBool(p(1)))
			Case Else
				PDef(p(0), CDbl(p(1)), p(2))
		End Select
	Next
	Try
		MultiValue.SetList("L_Modo", "Generar", "Diagnostico", "Borrar")
	Catch
	End Try
	Return cd.Parameters.UserParameters.Count > n0
End Function

' parametros del ensamble -> cfg (en mm / grados / unidades)
Sub CargarCfg()
	CargarCfgInterno()
	LeerPosiciones(PTxt("L_Posiciones"))
	LeerExtras(PTxt("L_Extras"))
	ocultos.Clear()
	For Each s As String In PTxt("L_Ocultos").Split("|"c)
		If s.Trim() <> "" Then ocultos.Add(s.Trim())
	Next
End Sub

Sub CargarCfgInterno()
	For Each d As String In Defs()
		Dim p() As String = d.Split("|"c)
		Try
			Dim up As UserParameter = PUp(p(0))
			Select Case p(2)
				Case "txt" : cfg(p(0)) = CStr(up.Value)
				Case "bool" : cfg(p(0)) = CBool(up.Value)
				Case "mm" : cfg(p(0)) = CDbl(up.Value) * 10.0
				Case "deg" : cfg(p(0)) = CDbl(up.Value) * 180.0 / Math.PI
				Case Else : cfg(p(0)) = CDbl(up.Value)
			End Select
		Catch
			cfg(p(0)) = p(1)
		End Try
	Next
End Sub

' cfg -> parametros del ensamble
Sub GuardarCfg()
	For Each d As String In Defs()
		Dim p() As String = d.Split("|"c)
		If Not cfg.ContainsKey(p(0)) Then Continue For
		Try
			Dim up As UserParameter = PUp(p(0))
			Select Case p(2)
				Case "txt" : up.Value = CStr(cfg(p(0)))
				Case "bool" : up.Value = CBool(cfg(p(0)))
				Case "mm" : up.Value = CDbl(cfg(p(0))) / 10.0
				Case "deg" : up.Value = CDbl(cfg(p(0))) * Math.PI / 180.0
				Case Else : up.Value = CDbl(cfg(p(0)))
			End Select
		Catch ex As Exception
			Lg("AVISO guardando " & p(0) & ": " & ex.Message)
		End Try
	Next
End Sub

Function PUp(n As String) As UserParameter
	Return cd.Parameters.UserParameters.Item(n)
End Function
Function PTxt(n As String) As String
	If cfg.ContainsKey(n) Then Return CStr(cfg(n))
	Return CStr(PUp(n).Value)
End Function
Function PBool(n As String) As Boolean
	If cfg.ContainsKey(n) Then Return CBool(cfg(n))
	Return CBool(PUp(n).Value)
End Function
Function PMM(n As String) As Double
	If cfg.ContainsKey(n) Then Return CDbl(cfg(n))
	Return CDbl(PUp(n).Value) * 10.0
End Function
Function PNum(n As String) As Double
	If cfg.ContainsKey(n) Then Return CDbl(cfg(n))
	Return CDbl(PUp(n).Value)
End Function
Function PDeg(n As String) As Double
	If cfg.ContainsKey(n) Then Return CDbl(cfg(n))
	Return CDbl(PUp(n).Value) * 180.0 / Math.PI
End Function

' =====================================================================
'  PLAN DEL LAYOUT (misma lista para la vista previa y para Inventor)
' =====================================================================
Sub CalcularPlan()
	plan = New List(Of ItemPlan)
	stats = New List(Of String)
	avisos = New List(Of String)
	hayProblema = False
	robX = 0 : robY = 0 : robAng = -90
	Dim sx As Double = 1.0
	If PTxt("L_SentidoLinea") = "-X" Then sx = -1.0

	' ---------- producto y pallet
	Dim PalL As Double = PMM("L_Pallet_L"), PalA As Double = PMM("L_Pallet_A"), PalH As Double = PMM("L_Pallet_H")
	Dim palX As Boolean = (PTxt("L_PalletEje") <> "Y")
	Dim pW As Double = If(palX, PalL, PalA), pD As Double = If(palX, PalA, PalL)
	Dim cL As Double = Math.Max(20, PMM("L_Caja_L")), cA As Double = Math.Max(20, PMM("L_Caja_A")), cH As Double = Math.Max(20, PMM("L_Caja_H"))
	Dim vol As Double = PMM("L_Voladizo")
	Dim sepT As Double = If(PBool("L_Separadores"), 3, 0)
	mosPW = pW : mosPD = pD
	mosPx = Math.Max(50, pW + 2 * vol) : mosPy = Math.Max(50, pD + 2 * vol)
	mosA = cL : mosB = cA : mosTipo = PTxt("L_Patron")
	Dim nCapas As Integer
	If PTxt("L_ModoCapas") = "Por cantidad" Then
		nCapas = CInt(PNum("L_Capas"))
	Else
		nCapas = CInt(Math.Floor((PMM("L_AlturaMaxCarga") - PalH) / (cH + sepT)))
	End If
	nCapas = Math.Max(1, Math.Min(40, nCapas))
	mosCapas = nCapas
	Dim cpc As Integer = PatronCapa(mosPx, mosPy, cL, cA, mosTipo, 0).Count
	Dim cajasPallet As Integer = 0
	For c As Integer = 0 To nCapas - 1
		cajasPallet += PatronCapa(mosPx, mosPy, cL, cA, mosTipo, c).Count
	Next
	Dim altCarga As Double = PalH + nCapas * (cH + sepT)
	Dim pesoPallet As Double = cajasPallet * PNum("L_PesoCaja") + 25

	' ---------- linea de pallets: medidas
	Dim T As Double = Math.Max(300, PMM("L_LargoTramo"))
	Dim Wl As Double = PMM("L_AnchoLinea")
	If Wl <= 0 Then Wl = pD + 100
	Dim Hl As Double = Math.Max(100, PMM("L_AlturaLinea"))
	Dim yL As Double = -PMM("L_DistRobotPallet")

	' ---------- base + robot
	Dim robNom As String = PTxt("L_Robot")
	alcanceAct = PMM("L_AlcanceRobot")
	If alcanceAct <= 0 Then alcanceAct = AlcanceDesdeNombre(robNom)
	Dim zRob As Double = 0
	Dim modeloBase As String = PTxt("L_ModeloBase")
	If modeloBase <> "Sin base" Then
		Dim ib As New ItemPlan
		ib.Tipo = "base" : ib.Nombre = "BaseRobot"
		Dim nomBase As String = ""
		If modeloBase = "Automatica" Then
			nomBase = BaseAuto(robNom)
		ElseIf modeloBase <> "Generada" Then
			nomBase = modeloBase
		End If
		If nomBase <> "" AndAlso (BASES.ContainsKey(nomBase) OrElse MAQUINAS.ContainsKey(nomBase)) Then
			ib.Ruta = If(BASES.ContainsKey(nomBase), BASES(nomBase), MAQUINAS(nomBase))
			ib.RotBase = RotModelo(nomBase, ib.Ruta)
			ib.Etiqueta = nomBase
		Else
			ib.Gen = "base"
			ib.GenP = New Double() {PMM("L_LadoBaseGen"), PMM("L_LadoBaseGen"), PMM("L_AlturaBaseGen")}
			ib.Etiqueta = "Base generada"
		End If
		Dimensionar(ib, 900, 900, 440)
		ib.Adentro = True
		plan.Add(ib)
		zRob = ib.H
	End If
	Dim ir As New ItemPlan
	ir.Tipo = "robot" : ir.Nombre = "Robot" : ir.Etiqueta = robNom
	If ROBOTS.ContainsKey(robNom) Then ir.Ruta = ROBOTS(robNom)
	ir.FaltaModelo = (ir.Ruta = "")
	ir.W = 700 : ir.D = 700 : ir.H = 2000 : ir.Z0 = zRob
	ir.Rot = PDeg("L_RotRobot")
	ir.RotBase = RotBib("ROBOT_" & robNom)
	plan.Add(ir)
	Dim grip As String = PTxt("L_Gripper")
	If grip <> "" AndAlso grip <> "Ninguno" Then
		Dim ig As New ItemPlan
		ig.Tipo = "gripper" : ig.Nombre = "Gripper" : ig.Etiqueta = grip
		ig.Rot = PDeg("L_RotGripper")
		If grip = "Generado (ventosas)" Then
			Dim nT As Integer = Math.Max(1, CInt(PNum("L_CajasPorToma")))
			ig.Gen = "gripper"
			ig.GenP = New Double() {Math.Max(200, PMM("L_Caja_L") * nT + 60), Math.Max(150, PMM("L_Caja_A") + 60), 320}
		Else
			ig.Ruta = RutaMaquina(grip)
			ig.RotBase = RotMaquina(grip)
			ig.FaltaModelo = (ig.Ruta = "")
		End If
		Dimensionar(ig, 600, 400, 400)
		plan.Add(ig)
	End If

	' ---------- linea de pallets
	Dim nEst As Integer = Math.Max(1, Math.Min(2, CInt(PNum("L_Estaciones"))))
	Dim nVac As Integer = Math.Max(0, Math.Min(6, CInt(PNum("L_TramosVacio"))))
	Dim nSal As Integer = Math.Max(0, Math.Min(8, CInt(PNum("L_TramosSalida"))))
	Dim xs As New List(Of Double)
	If nEst = 2 Then
		xs.Add(-T / 2) : xs.Add(T / 2)
	Else
		xs.Add(0)
	End If
	Dim conCajas As Boolean = PBool("L_CajasEjemplo")
	Dim estaciones As New List(Of ItemPlan)
	For i As Integer = 0 To xs.Count - 1
		Dim t1 As ItemPlan = Tramo("Est" & (i + 1) & "_Transp", sx * xs(i), yL, T, Wl, Hl)
		t1.Adentro = True
		estaciones.Add(t1)
		Dim nc As Integer = If(i = 0, nCapas, Math.Max(1, nCapas \ 2))
		AgregarPallet("Est" & (i + 1), t1.Cx, t1.Cy, t1.Z0 + t1.H, palX, PalL, PalA, PalH, If(conCajas, nc, 0), cL, cA, cH, sepT, True)
	Next
	For k As Integer = 1 To nVac
		Dim tv As ItemPlan = Tramo("Vacio" & k & "_Transp", sx * (xs(0) - k * T), yL, T, Wl, Hl)
		tv.Cruza = True
		AgregarPallet("Vacio" & k, tv.Cx, tv.Cy, tv.Z0 + tv.H, palX, PalL, PalA, PalH, 0, cL, cA, cH, sepT, False)
	Next
	If PBool("L_Dispenser") Then
		Dim xD As Double = sx * (xs(0) - (nVac + 1) * T)
		Dim td As ItemPlan = Tramo("Dispenser_Transp", xD, yL, T, Wl, Hl)
		td.Cruza = True
		AgregarPallet("Dispenser", td.Cx, td.Cy, td.Z0 + td.H, palX, PalL, PalA, PalH, 0, cL, cA, cH, sepT, False)
		Dim im As ItemPlan = Maquina("Dispenser", PTxt("L_ModeloDispenser"), xD, yL, PDeg("L_RotDispenser"), 2200, 1900, 2600)
		im.Cruza = True
	End If
	Dim xUlt As Double = xs(xs.Count - 1)
	Dim capasSal As Integer = nCapas
	If cajasPallet * (1 + nSal) > 500 Then capasSal = Math.Max(1, nCapas \ 2)
	For k As Integer = 1 To nSal
		Dim ts As ItemPlan = Tramo("Salida" & k & "_Transp", sx * (xUlt + k * T), yL, T, Wl, Hl)
		ts.Cruza = True
		AgregarPallet("Salida" & k, ts.Cx, ts.Cy, ts.Z0 + ts.H, palX, PalL, PalA, PalH, If(conCajas, capasSal, 0), cL, cA, cH, sepT, False)
	Next
	If PBool("L_Envolvedora") Then
		Dim ie As ItemPlan = Maquina("Envolvedora", PTxt("L_ModeloEnvolvedora"), 0, yL, PDeg("L_RotEnvolvedora"), 3000, 2600, 2700)
		ie.Cx = sx * (xUlt + nSal * T + T / 2 + PMM("L_SepEnvolvedora") + ie.W / 2)
		ie.Cruza = True
	End If
	If PBool("L_Centrador") AndAlso estaciones.Count > 0 Then
		Dim ic As ItemPlan = Maquina("Centrador", PTxt("L_ModeloCentrador"), estaciones(0).Cx, yL, PDeg("L_RotCentrador"), pW + 500, pD + 500, 900)
		ic.Adentro = True
	End If

	' ---------- entrada de cajas
	Dim lado As String = PTxt("L_LadoEntrada")
	Dim ux As Double = 0, uy As Double = 1
	If lado = "Izquierda" Then ux = -1 : uy = 0
	If lado = "Derecha" Then ux = 1 : uy = 0
	Dim px As Double = Math.Abs(uy), py As Double = Math.Abs(ux)     ' direccion lateral
	Dim Di As Double = PMM("L_DistRobotEntrada"), Lin As Double = Math.Max(500, PMM("L_LargoCintaEntrada"))
	Dim Wc As Double = Math.Max(100, PMM("L_AnchoCinta")), Hc As Double = Math.Max(100, PMM("L_AlturaCinta"))
	Dim offsE As New List(Of Double)
	If CInt(PNum("L_Entradas")) >= 2 Then
		offsE.Add(PMM("L_OffsetEntrada") - PMM("L_SepEntradas") / 2)
		offsE.Add(PMM("L_OffsetEntrada") + PMM("L_SepEntradas") / 2)
	Else
		offsE.Add(PMM("L_OffsetEntrada"))
	End If
	Dim rotFlujo As Double = If(uy <> 0, 90, 0)
	Dim cintaRuta As String = Resolver("CINTA_ENTRADA")
	Dim nE As Integer = 0
	For Each o As Double In offsE
		nE += 1
		Dim ic As New ItemPlan
		ic.Tipo = "cinta" : ic.Nombre = "Entrada" & nE & "_Cinta" : ic.Etiqueta = "Cinta " & nE
		ic.Cx = ux * (Di + Lin / 2) + px * o : ic.Cy = uy * (Di + Lin / 2) + py * o
		If cintaRuta <> "" Then
			ic.Ruta = cintaRuta : ic.RotBase = RotBib("CINTA_ENTRADA") : ic.Eje = If(uy <> 0, "Y", "X")
		Else
			ic.Gen = "cinta" : ic.GenP = New Double() {Lin, Wc, Hc} : ic.Rot = rotFlujo
		End If
		Dimensionar(ic, Lin, Wc, Hc)
		ic.Cruza = True
		plan.Add(ic)
		' la zona de toma queda adentro del vallado
		Dim iz As New ItemPlan
		iz.Tipo = "zona" : iz.Nombre = "Entrada" & nE & "_Zona"
		iz.Cx = ux * (Di + 350) + px * o : iz.Cy = uy * (Di + 350) + py * o
		iz.W = If(uy <> 0, Wc, 900) : iz.D = If(uy <> 0, 900, Wc)
		iz.Adentro = True
		plan.Add(iz)
		Dim tipoTope As String = PTxt("L_TipoTope")
		If tipoTope = "Generado" Then
			Dim it As New ItemPlan
			it.Tipo = "tope" : it.Nombre = "Entrada" & nE & "_Tope" : it.Gen = "tope"
			it.GenP = New Double() {60, Wc, 150}
			it.Rot = rotFlujo
			it.Cx = ux * (Di - 30) + px * o : it.Cy = uy * (Di - 30) + py * o : it.Z0 = Hc + 10
			Dimensionar(it, 60, Wc, 150)
			plan.Add(it)
		ElseIf tipoTope = "Freno de cajas" Then
			Maquina("Entrada" & nE & "_Freno", "Freno de cajas", ux * (Di + 300) + px * o, uy * (Di + 300) + py * o, rotFlujo + PDeg("L_RotTope"), 700, Wc + 300, 700)
		End If
		If conCajas Then
			Dim paso As Double = cL * 1.35
			Dim nIn As Integer = Math.Max(0, Math.Min(10, CInt(Math.Floor((Lin - 300) / paso))))
			For j As Integer = 0 To nIn - 1
				Dim dd As Double = Di + cL / 2 + 20 + j * paso
				Dim cj As ItemPlan = NuevaCaja("Entrada" & nE & "_Caja", ux * dd + px * o, uy * dd + py * o, Hc, rotFlujo, cL, cA, cH)
				cj.Capa = -1
			Next
		End If
		Dim ipk As New ItemPlan
		ipk.Tipo = "pick" : ipk.Nombre = "Entrada" & nE & "_Pick" : ipk.Etiqueta = "Toma de cajas cinta " & nE
		ipk.Cx = ux * Di + px * o : ipk.Cy = uy * Di + py * o
		plan.Add(ipk)
	Next

	' ---------- mesa de carton
	If PBool("L_MesaCarton") Then
		Dim mdx As Double = 1, mdy As Double = 0
		Select Case PTxt("L_LadoMesa")
			Case "Izquierda" : mdx = -1
			Case "Atras" : mdx = 0 : mdy = 1
			Case "Derecha" : mdx = 1
			Case Else : If lado = "Derecha" Then mdx = -1
		End Select
		Dim Dm0 As Double = PMM("L_DistRobotMesa")
		Dim imc As ItemPlan = Maquina("MesaCarton", PTxt("L_ModeloMesa"), mdx * Dm0, mdy * Dm0, PDeg("L_RotMesa"), 1200, 1100, 900)
		imc.Adentro = True
	End If

	' ---------- maquinas agregadas al plano
	For k As Integer = 0 To extras.Count - 1
		Dim exm As ExtraMaq = extras(k)
		Dim pre As String = "Extra" & (k + 1)
		Dim i0 As Integer = plan.Count
		Select Case exm.Tipo
			Case "copia"
				Continue For        ' se arman despues de acomodar el plano
			Case "cinta", "salida"
				Dim Lx As Double = Math.Max(300, exm.L), Ax As Double = Math.Max(100, exm.A), Hx As Double = Math.Max(50, exm.H)
				Dim icx As New ItemPlan
				icx.Tipo = "cinta" : icx.Nombre = pre & "_Cinta" : icx.Etiqueta = If(exm.Tipo = "salida", "Salida ", "") & exm.Nombre
				icx.Gen = "cinta" : icx.GenP = New Double() {Lx, Ax, Hx}
				Dimensionar(icx, Lx, Ax, Hx)
				icx.Cruza = True
				plan.Add(icx)
				If exm.Tipo = "cinta" Then
					Dim izx As New ItemPlan
					izx.Tipo = "zona" : izx.Nombre = pre & "_Zona"
					izx.Cx = -Lx / 2 + 350 : izx.W = 900 : izx.D = Ax
					izx.Adentro = Math.Sqrt((exm.X - robX) ^ 2 + (exm.Y - robY) ^ 2) < alcanceAct + Lx
					plan.Add(izx)
					If exm.Op2 Then
						Dim itx As New ItemPlan
						itx.Tipo = "tope" : itx.Nombre = pre & "_Tope" : itx.Gen = "tope"
						itx.GenP = New Double() {60, Ax, 150}
						itx.Cx = -Lx / 2 - 30 : itx.Z0 = Hx + 10
						Dimensionar(itx, 60, Ax, 150)
						plan.Add(itx)
					End If
					Dim ipx As New ItemPlan
					ipx.Tipo = "pick" : ipx.Nombre = pre & "_Pick" : ipx.Etiqueta = "Toma de cajas " & exm.Nombre
					ipx.Cx = -Lx / 2
					plan.Add(ipx)
				End If
				If exm.Op1 Then
					Dim pasoC As Double = cL * 1.35
					Dim nC As Integer = Math.Max(0, Math.Min(12, CInt(Math.Floor((Lx - 300) / pasoC))))
					For j As Integer = 0 To nC - 1
						Dim cjx As ItemPlan = NuevaCaja(pre & "_Caja", -Lx / 2 + cL / 2 + 20 + j * pasoC, 0, Hx, 0, cL, cA, cH)
						cjx.Capa = -1
					Next
				End If
			Case "rodillos"
				Dim Lx As Double = Math.Max(300, exm.L), Ax As Double = Math.Max(200, exm.A), Hx As Double = Math.Max(50, exm.H)
				Dim trx As New ItemPlan
				trx.Tipo = "conv" : trx.Nombre = pre & "_Transp" : trx.Etiqueta = exm.Nombre
				trx.Gen = "rodillos" : trx.GenP = New Double() {Lx, Ax, Hx}
				Dimensionar(trx, Lx, Ax, Hx)
				trx.Cruza = True
				plan.Add(trx)
				If exm.Op1 Then AgregarPallet(pre, 0, 0, Hx, True, PalL, PalA, PalH, If(exm.Op2, nCapas, 0), cL, cA, cH, sepT, False)
			Case "pallet"
				AgregarPallet(pre, 0, 0, 0, True, PalL, PalA, PalH, If(exm.Op1, nCapas, 0), cL, cA, cH, sepT, False)
			Case "bloque"
				Dim ibx As New ItemPlan
				ibx.Tipo = "maquina" : ibx.Nombre = pre : ibx.Etiqueta = exm.Nombre
				ibx.Gen = "bloque" : ibx.GenP = New Double() {Math.Max(50, exm.L), Math.Max(50, exm.A), Math.Max(10, exm.H)}
				Dimensionar(ibx, ibx.GenP(0), ibx.GenP(1), ibx.GenP(2))
				ibx.Cruza = True
				plan.Add(ibx)
			Case "valla"
				Dim Lx As Double = Math.Max(300, exm.L), Hv As Double = Math.Max(300, exm.H)
				Dim nP As Integer = Math.Max(1, CInt(Math.Ceiling(Lx / Math.Max(300, PMM("L_PanelValla")) - 0.001)))
				Dim Lp As Double = Lx / nP
				Dim vRuta As String = Resolver("VALLA"), pRuta As String = Resolver("PUERTA")
				For j As Integer = 0 To nP - 1
					Dim esP As Boolean = exm.Op1 AndAlso j = nP \ 2
					Dim ivx As New ItemPlan
					ivx.Tipo = If(esP, "puerta", "valla") : ivx.Nombre = pre & If(esP, "_Puerta", "_Valla")
					ivx.Cx = -Lx / 2 + (j + 0.5) * Lp
					Dim rl As String = If(esP, pRuta, vRuta)
					If rl <> "" Then
						ivx.Ruta = rl : ivx.Eje = "X" : ivx.W = Lp : ivx.D = 60 : ivx.H = Hv
					Else
						ivx.Gen = ivx.Tipo : ivx.GenP = New Double() {Lp, Hv}
						Dimensionar(ivx, Lp, 60, Hv)
					End If
					plan.Add(ivx)
				Next
			Case Else
				Dim ix As ItemPlan = Maquina(pre, exm.Nombre, exm.X, exm.Y, exm.Rot, 1500, 1500, 1500)
				ix.Cruza = True
				ix.Z0 += exm.Z
				Continue For
		End Select
		' piezas armadas en el origen -> giro y posicion del elemento
		Dim nuevos As New List(Of ItemPlan)
		For i As Integer = i0 To plan.Count - 1
			nuevos.Add(plan(i))
		Next
		RotarItems(nuevos, 0, 0, exm.Rot, exm.X, exm.Y, exm.Z)
	Next

	' ---------- posiciones editadas con el mouse
	AplicarPosiciones()
	For Each it As ItemPlan In plan
		If it.Tipo = "robot" AndAlso it.Nombre = "Robot" Then robX = it.Cx : robY = it.Cy
	Next
	' ---------- copias de grupos del plano y grupos quitados
	ArmarCopias(False)
	plan.RemoveAll(Function(q As ItemPlan) ocultos.Contains(GrupoDe(q)))

	' ---------- chequeos de robot (desde su posicion real)
	Dim nEstC As Integer = 0
	For Each it As ItemPlan In plan
		If it.Tipo = "pallet" AndAlso it.Nombre.StartsWith("Est") Then
			nEstC += 1
			Dim dMax As Double = 0
			For Each qx As Double In New Double() {it.Cx - it.W / 2, it.Cx + it.W / 2}
				For Each qy As Double In New Double() {it.Cy - it.D / 2, it.Cy + it.D / 2}
					dMax = Math.Max(dMax, Math.Sqrt((qx - robX) ^ 2 + (qy - robY) ^ 2))
				Next
			Next
			Chequeo("Esquina mas lejana pallet " & nEstC, dMax, alcanceAct)
			If nEstC = 1 Then robAng = Math.Atan2(it.Cy - robY, it.Cx - robX) * 180 / Math.PI
		End If
		If it.Tipo = "pick" Then
			' se mide desde el robot mas cercano (puede haber robots agregados)
			Dim dPk As Double = Math.Sqrt((it.Cx - robX) ^ 2 + (it.Cy - robY) ^ 2)
			For Each rb As ItemPlan In plan
				If rb.Tipo = "robot" Then dPk = Math.Min(dPk, Math.Sqrt((it.Cx - rb.Cx) ^ 2 + (it.Cy - rb.Cy) ^ 2))
			Next
			Chequeo(it.Etiqueta, dPk + cL / 2, alcanceAct)
		End If
		If it.Tipo = "maquina" AndAlso it.Nombre = "MesaCarton" AndAlso PBool("L_Separadores") Then Chequeo("Mesa de carton", Math.Sqrt((it.Cx - robX) ^ 2 + (it.Cy - robY) ^ 2), alcanceAct)
	Next
	Dim carga As Double = PNum("L_CargaRobot")
	If carga <= 0 Then carga = CargaDesdeNombre(robNom)
	Dim cargaToma As Double = PNum("L_CajasPorToma") * PNum("L_PesoCaja") + PNum("L_PesoGripper")
	Dim okCarga As Boolean = cargaToma <= carga
	stats.Insert(0, String.Format("Carga por toma {0:0} kg / robot {1:0} kg{2} -> {3}", cargaToma, carga, If(PNum("L_CargaRobot") <= 0, " (estimado)", ""), If(okCarga, "OK", "EXCEDE")))
	If Not okCarga Then
		avisos.Add(String.Format("La carga por toma ({0:0} kg) supera la del robot ({1:0} kg)", cargaToma, carga))
		hayProblema = True
	End If
	If cpc = 0 Then
		avisos.Add("La caja no entra en el pallet con esa orientacion/voladizo")
		hayProblema = True
	End If
	Dim ciclo As Double = Math.Max(0.5, PNum("L_CicloSeg"))
	Dim cph As Double = 3600 / ciclo * Math.Max(1, PNum("L_CajasPorToma"))
	stats.Insert(0, String.Format("Ciclo {0:0.0} s -> {1:0} cajas/h -> {2:0.0} pallets/h", ciclo, cph, If(cajasPallet > 0, cph / cajasPallet, 0)))
	stats.Insert(0, String.Format("{0} cajas/capa x {1} capas = {2} cajas/pallet | altura {3:0} mm | {4:0} kg", cpc, nCapas, cajasPallet, altCarga, pesoPallet))
	stats.Insert(0, String.Format("Pallet {0:0}x{1:0}  caja {2:0}x{3:0}x{4:0}  patron {5}", PalL, PalA, cL, cA, cH, mosTipo))
	stats.Insert(0, String.Format("Robot {0}  alcance {1:0} mm", robNom, alcanceAct))
	If PTxt("L_ModoCapas") = "Por altura" AndAlso altCarga > PMM("L_AlturaMaxCarga") + 1 Then avisos.Add("La pila supera la altura maxima")

	' ---------- vallado
	Dim interior As New List(Of Double())
	For Each it As ItemPlan In plan
		If it.Adentro Then interior.Add(RectItem(it))
	Next
	Dim r() As Double = Union(interior)
	Dim Mg As Double = PMM("L_MargenVallado")
	r(0) -= Mg : r(1) -= Mg : r(3) += Mg : r(4) += Mg
	If PBool("L_ValladoAlcance") Then
		Dim ra As Double = alcanceAct + 200
		r(0) = Math.Min(r(0), robX - ra) : r(1) = Math.Min(r(1), robY - ra) : r(3) = Math.Max(r(3), robX + ra) : r(4) = Math.Max(r(4), robY + ra)
	End If
	' lados del vallado movidos a mano
	If offs.ContainsKey("Valla0") Then r(1) += offs("Valla0")(1)
	If offs.ContainsKey("Valla1") Then r(4) += offs("Valla1")(1)
	If offs.ContainsKey("Valla2") Then r(0) += offs("Valla2")(0)
	If offs.ContainsKey("Valla3") Then r(3) += offs("Valla3")(0)
	If r(3) < r(0) + 500 Then r(3) = r(0) + 500
	If r(4) < r(1) + 500 Then r(4) = r(1) + 500
	rectV = Nothing
	If PBool("L_Vallado") Then
		rectV = CType(r.Clone(), Double())
		PlanVallado(r, lado)
		Dim dmin As Double = Math.Min(Math.Min(robX - r(0), r(3) - robX), Math.Min(robY - r(1), r(4) - robY))
		stats.Add(String.Format("Vallado {0:0.0} x {1:0.0} m, distancia minima al robot {2:0} mm", (r(3) - r(0)) / 1000, (r(4) - r(1)) / 1000, dmin))
		If alcanceAct > dmin Then avisos.Add(String.Format("El alcance ({0:0}) supera la distancia al vallado ({1:0}): limitar zonas del robot o alejar la valla", alcanceAct, dmin))
	End If

	' ---------- tablero: lugar libre afuera del vallado
	If PBool("L_Tablero") Then
		Dim itb As ItemPlan = Maquina("Tablero", PTxt("L_ModeloTablero"), 0, 0, PDeg("L_RotTablero"), 800, 500, 2000)
		Dim w As Double = itb.W, d As Double = itb.D
		Dim cand As New List(Of Double())
		cand.Add(New Double() {r(3) + 300 + w / 2, r(4) - d / 2})
		cand.Add(New Double() {r(0) - 300 - w / 2, r(4) - d / 2})
		cand.Add(New Double() {r(0) + w / 2 + 200, r(4) + 300 + d / 2})
		cand.Add(New Double() {r(3) - w / 2 - 200, r(4) + 300 + d / 2})
		cand.Add(New Double() {r(0) - 300 - w / 2, r(1) + d / 2})
		cand.Add(New Double() {r(3) + 300 + w / 2, r(1) + d / 2})
		Dim elegido() As Double = cand(0)
		For Each c As Double() In cand
			Dim pr() As Double = {c(0) - w / 2 - 100, c(1) - d / 2 - 100, 0, c(0) + w / 2 + 100, c(1) + d / 2 + 100, 1}
			Dim libre As Boolean = True
			For Each it As ItemPlan In plan
				If it Is itb OrElse it.Tipo = "caja" OrElse it.Tipo = "sep" OrElse it.Tipo = "zona" Then Continue For
				If Inter(pr, RectItem(it)) Then
					libre = False
					Exit For
				End If
			Next
			If libre Then
				elegido = c
				Exit For
			End If
		Next
		itb.Cx = elegido(0) : itb.Cy = elegido(1)
		If offs.ContainsKey("Tablero") Then
			Dim ot() As Double = offs("Tablero")
			If ot(3) > 0.5 Then
				itb.Cx = ot(0) : itb.Cy = ot(1)
			Else
				itb.Cx += ot(0) : itb.Cy += ot(1)
			End If
			If Math.Abs(Math.Round(ot(2)) Mod 180) = 90 Then
				Dim tw As Double = itb.W : itb.W = itb.D : itb.D = tw
			End If
			itb.Rot += ot(2)
		End If
	End If

	' ---------- copias del vallado / tablero y grupos quitados
	ArmarCopias(True)
	plan.RemoveAll(Function(q As ItemPlan) ocultos.Contains(GrupoDe(q)))
	If extras.Count > 0 OrElse ocultos.Count > 0 Then stats.Add(extras.Count & " elemento(s) agregado(s) al plano" & If(ocultos.Count > 0, ", " & ocultos.Count & " grupo(s) quitado(s)", ""))
End Sub

' ---- grupos que se mueven juntos al arrastrar en la vista previa
Function GrupoDe(it As ItemPlan) As String
	Dim n As String = it.Nombre
	If n.StartsWith("Extra") Then
		Dim ie As Integer = n.IndexOf("_"c)
		Return If(ie > 0, n.Substring(0, ie), n)
	End If
	If it.Tipo = "valla" OrElse it.Tipo = "puerta" Then Return "Valla" & it.Borde
	If n = "BaseRobot" OrElse n = "Robot" OrElse n = "Gripper" Then Return "Robot"
	If n.StartsWith("Est") OrElse n.StartsWith("Vacio") OrElse n.StartsWith("Salida") OrElse n.StartsWith("Dispenser") OrElse n.StartsWith("Centrador") Then Return "Linea"
	If n.StartsWith("Entrada") Then
		Dim i As Integer = n.IndexOf("_"c)
		Return If(i > 0, n.Substring(0, i), n)
	End If
	Return n
End Function

Function NombreGrupo(g As String) As String
	Select Case g
		Case "Linea" : Return "Linea de pallets"
		Case "Entrada1" : Return "Cinta de entrada 1"
		Case "Entrada2" : Return "Cinta de entrada 2"
		Case "MesaCarton" : Return "Mesa de carton"
		Case "Valla0" : Return "Vallado (frente)"
		Case "Valla1" : Return "Vallado (fondo)"
		Case "Valla2" : Return "Vallado (izquierda)"
		Case "Valla3" : Return "Vallado (derecha)"
		Case "Robot" : Return "Robot con base y gripper"
		Case "Robot" : Return "Robot con base y gripper"
	End Select
	Return g
End Function

' aplica giro (alrededor del centro del grupo) y desplazamiento guardados
Sub AplicarPosiciones()
	For Each kv As KeyValuePair(Of String, Double()) In offs
		Dim g As String = kv.Key
		If g.StartsWith("Valla") OrElse g = "Tablero" OrElse g.StartsWith("Extra") Then Continue For
		Dim o() As Double = kv.Value
		Dim miembros As New List(Of ItemPlan)
		For Each it As ItemPlan In plan
			If GrupoDe(it) = g Then miembros.Add(it)
		Next
		If miembros.Count = 0 Then Continue For
		Dim x1 As Double = 1.0E+30, y1 As Double = 1.0E+30, x2 As Double = -1.0E+30, y2 As Double = -1.0E+30
		For Each it As ItemPlan In miembros
			If it.Tipo = "caja" OrElse it.Tipo = "pick" OrElse it.Tipo = "zona" Then Continue For
			x1 = Math.Min(x1, it.Cx - it.W / 2) : x2 = Math.Max(x2, it.Cx + it.W / 2)
			y1 = Math.Min(y1, it.Cy - it.D / 2) : y2 = Math.Max(y2, it.Cy + it.D / 2)
		Next
		If x1 > x2 Then
			x1 = miembros(0).Cx : x2 = x1 : y1 = miembros(0).Cy : y2 = y1
		End If
		Dim cx As Double = (x1 + x2) / 2, cy As Double = (y1 + y2) / 2
		If g = "Robot" Then
			For Each it As ItemPlan In miembros
				If it.Tipo = "robot" Then cx = it.Cx : cy = it.Cy
			Next
		End If
		Dim q As Integer = CInt(((Math.Round(o(2) / 90) Mod 4) + 4) Mod 4)
		For Each it As ItemPlan In miembros
			Dim rx As Double = it.Cx - cx, ry As Double = it.Cy - cy
			For k As Integer = 1 To q
				Dim tx As Double = -ry : ry = rx : rx = tx
			Next
			it.Cx = cx + rx + o(0) : it.Cy = cy + ry + o(1)
			If q Mod 2 = 1 Then
				Dim tw As Double = it.W : it.W = it.D : it.D = tw
				If it.Eje = "X" Then
					it.Eje = "Y"
				ElseIf it.Eje = "Y" Then
					it.Eje = "X"
				End If
			End If
			it.Rot += q * 90
		Next
	Next
End Sub

' gira piezas alrededor de (cx, cy) en pasos de 90 grados y las lleva a (nx, ny)
Sub RotarItems(lista As List(Of ItemPlan), cx As Double, cy As Double, rotDeg As Double, nx As Double, ny As Double, dz As Double)
	Dim q As Integer = CInt(((Math.Round(rotDeg / 90) Mod 4) + 4) Mod 4)
	For Each it As ItemPlan In lista
		Dim rx As Double = it.Cx - cx, ry As Double = it.Cy - cy
		For k As Integer = 1 To q
			Dim tx As Double = -ry : ry = rx : rx = tx
		Next
		it.Cx = nx + rx : it.Cy = ny + ry : it.Z0 += dz
		If q Mod 2 = 1 Then
			Dim tw As Double = it.W : it.W = it.D : it.D = tw
			If it.Eje = "X" Then
				it.Eje = "Y"
			ElseIf it.Eje = "Y" Then
				it.Eje = "X"
			End If
		End If
		it.Rot += q * 90
	Next
End Sub

' copias de grupos del plano: se rearman cada vez, asi siguen los cambios de caja, pallet, etc.
'  tarde=False: grupos normales   tarde=True: vallado y tablero (se calculan al final)
Sub ArmarCopias(tarde As Boolean)
	For k As Integer = 0 To extras.Count - 1
		Dim ex As ExtraMaq = extras(k)
		If ex.Tipo <> "copia" Then Continue For
		Dim src As String = ex.Nombre
		Dim esTarde As Boolean = src.StartsWith("Valla") OrElse src = "Tablero"
		If esTarde <> tarde Then Continue For
		Dim c() As Double = CentroGrupo(src)
		If c Is Nothing Then Continue For
		Dim lejos As Boolean = Math.Sqrt((ex.X - robX) ^ 2 + (ex.Y - robY) ^ 2) > alcanceAct * 1.5 + 1500
		Dim nuevos As New List(Of ItemPlan)
		For Each it As ItemPlan In plan
			If GrupoDe(it) <> src Then Continue For
			Dim n As ItemPlan = it.Clonar()
			Dim i As Integer = it.Nombre.IndexOf("_"c)
			n.Nombre = "Extra" & (k + 1) & "_" & If(i >= 0, it.Nombre.Substring(i + 1), it.Nombre)
			If n.Tipo = "valla" OrElse n.Tipo = "puerta" Then n.Borde = -1
			If n.Tipo = "pick" Then n.Etiqueta = n.Etiqueta & " (copia " & (k + 1) & ")"
			If lejos Then n.Adentro = False
			nuevos.Add(n)
		Next
		RotarItems(nuevos, c(0), c(1), ex.Rot, ex.X, ex.Y, ex.Z)
		plan.AddRange(nuevos)
	Next
End Sub

Function SerializarPosiciones() As String
	Dim ci As System.Globalization.CultureInfo = System.Globalization.CultureInfo.InvariantCulture
	Dim partes As New List(Of String)
	For Each kv As KeyValuePair(Of String, Double()) In offs
		Dim v() As Double = kv.Value
		partes.Add(kv.Key & "=" & v(0).ToString("0", ci) & ";" & v(1).ToString("0", ci) & ";" & v(2).ToString("0", ci) & ";" & v(3).ToString("0", ci))
	Next
	Return String.Join("|", partes.ToArray())
End Function

Sub LeerPosiciones(txt As String)
	offs.Clear()
	If txt Is Nothing OrElse txt.Trim() = "" Then Exit Sub
	Dim ci As System.Globalization.CultureInfo = System.Globalization.CultureInfo.InvariantCulture
	For Each parte As String In txt.Split("|"c)
		Dim i As Integer = parte.IndexOf("="c)
		If i < 1 Then Continue For
		Dim v() As String = parte.Substring(i + 1).Split(";"c)
		If v.Length < 4 Then Continue For
		Try
			offs(parte.Substring(0, i)) = New Double() {Double.Parse(v(0), ci), Double.Parse(v(1), ci), Double.Parse(v(2), ci), Double.Parse(v(3), ci)}
		Catch
		End Try
	Next
End Sub

' ---- piezas del plan
Function Tramo(nombre As String, x As Double, y As Double, T As Double, Wl As Double, Hl As Double) As ItemPlan
	Dim it As New ItemPlan
	it.Tipo = "conv" : it.Nombre = nombre : it.Cx = x : it.Cy = y
	Dim ruta As String = Resolver("CONV_PALLET")
	If ruta <> "" Then
		it.Ruta = ruta : it.RotBase = RotBib("CONV_PALLET") : it.Eje = "X"
	Else
		it.Gen = "rodillos" : it.GenP = New Double() {T, Wl, Hl}
	End If
	Dimensionar(it, T, Wl, Hl)
	plan.Add(it)
	Return it
End Function

Function Maquina(nombre As String, modelo As String, x As Double, y As Double, rotDeg As Double, defW As Double, defD As Double, defH As Double) As ItemPlan
	Dim it As New ItemPlan
	it.Tipo = "maquina" : it.Nombre = nombre : it.Etiqueta = modelo
	it.Ruta = RutaMaquina(modelo)
	it.RotBase = RotMaquina(modelo)
	it.Rot = rotDeg
	it.Cx = x : it.Cy = y
	it.FaltaModelo = (it.Ruta = "")
	Dimensionar(it, defW, defD, defH)
	plan.Add(it)
	Return it
End Function

Function NuevaCaja(nombre As String, x As Double, y As Double, z As Double, rotDeg As Double, cL As Double, cA As Double, cH As Double) As ItemPlan
	Dim it As New ItemPlan
	it.Tipo = "caja" : it.Nombre = nombre : it.Cx = x : it.Cy = y : it.Z0 = z : it.Rot = rotDeg
	Dim ruta As String = Resolver("CAJA")
	If ruta <> "" Then
		it.Ruta = ruta : it.RotBase = RotBib("CAJA")
	Else
		it.Gen = "caja" : it.GenP = New Double() {Math.Max(10, cL - 4), Math.Max(10, cA - 4), Math.Max(10, cH - 2)}
	End If
	it.W = If(Math.Abs(rotDeg Mod 180) > 1, cA, cL) : it.D = If(Math.Abs(rotDeg Mod 180) > 1, cL, cA) : it.H = cH
	plan.Add(it)
	Return it
End Function

Sub AgregarPallet(pref As String, x As Double, y As Double, z As Double, palX As Boolean, PalL As Double, PalA As Double, PalH As Double, capas As Integer, cL As Double, cA As Double, cH As Double, sepT As Double, principal As Boolean)
	Dim it As New ItemPlan
	it.Tipo = "pallet" : it.Nombre = pref & "_Pallet" : it.Cx = x : it.Cy = y : it.Z0 = z
	it.Rot = If(palX, 0, 90)
	Dim ruta As String = Resolver("PALLET")
	If ruta <> "" Then
		it.Ruta = ruta : it.RotBase = RotBib("PALLET") : it.Eje = If(palX, "X", "Y") : it.Rot = 0
	Else
		it.Gen = "pallet" : it.GenP = New Double() {PalL, PalA, PalH}
	End If
	it.W = If(palX, PalL, PalA) : it.D = If(palX, PalA, PalL) : it.H = PalH
	If principal Then it.Adentro = True
	plan.Add(it)
	Dim zc As Double = z + PalH
	For c As Integer = 0 To capas - 1
		If sepT > 0 Then
			Dim sp As New ItemPlan
			sp.Tipo = "sep" : sp.Nombre = pref & "_Sep" : sp.Gen = "sep"
			sp.GenP = New Double() {mosPx, mosPy, sepT}
			sp.Cx = x : sp.Cy = y : sp.Z0 = zc : sp.W = mosPx : sp.D = mosPy : sp.H = sepT
			plan.Add(sp)
			zc += sepT
		End If
		For Each rc As Double() In PatronCapa(mosPx, mosPy, cL, cA, mosTipo, c)
			Dim girada As Boolean = (Math.Abs(rc(2) - cL) > 0.5)
			Dim cj As ItemPlan = NuevaCaja(pref & "_Caja", x + rc(0), y + rc(1), zc, If(girada, 90, 0), cL, cA, cH)
			cj.Capa = c
		Next
		zc += cH
	Next
End Sub

' medidas en planta (W en X, D en Y) segun archivo generado, memoria o valores por defecto
Sub Dimensionar(it As ItemPlan, defW As Double, defD As Double, defH As Double)
	Dim gira As Boolean = (Math.Abs(Math.Round(it.Rot) Mod 180) = 90)
	If it.Gen <> "" AndAlso it.GenP IsNot Nothing Then
		it.W = it.GenP(0) : it.D = it.GenP(1) : it.H = If(it.GenP.Length > 2, it.GenP(2), defH)
		If it.Gen = "base" OrElse it.Gen = "caja" OrElse it.Gen = "tope" Then it.H = it.GenP(2)
		If it.Gen = "valla" OrElse it.Gen = "puerta" Then
			it.W = it.GenP(0) : it.D = 60 : it.H = it.GenP(1)
		End If
		If gira Then
			Dim t As Double = it.W : it.W = it.D : it.D = t
		End If
		Return
	End If
	Dim m() As Double = Nothing
	If it.Ruta <> "" Then
		If CACHE.ContainsKey(ClaveCache(it.Ruta, it.RotBase, it.Rot)) Then
			m = CACHE(ClaveCache(it.Ruta, it.RotBase, it.Rot))
		ElseIf CACHE.ContainsKey(ClaveCache(it.Ruta, it.RotBase, it.Rot + 90)) Then
			Dim m2() As Double = CACHE(ClaveCache(it.Ruta, it.RotBase, it.Rot + 90))
			m = New Double() {m2(1), m2(0), m2(2)}
		End If
	End If
	If m Is Nothing AndAlso it.Ruta <> "" Then m = MedidasRotadas(it.Ruta, it.RotBase, it.Rot)
	If m IsNot Nothing Then
		it.W = m(0) : it.D = m(1) : it.H = m(2)
	Else
		it.W = If(gira, defD, defW) : it.D = If(gira, defW, defD) : it.H = defH
	End If
End Sub

Function RectItem(it As ItemPlan) As Double()
	Return New Double() {it.Cx - it.W / 2, it.Cy - it.D / 2, it.Z0, it.Cx + it.W / 2, it.Cy + it.D / 2, it.Z0 + it.H}
End Function

' vallado: cada lado se completa con paneles, dejando libre donde cruzan transportadores o maquinas
Sub PlanVallado(r() As Double, lado As String)
	Dim Hv As Double = PMM("L_AlturaValla")
	Dim Pmax As Double = Math.Max(300, PMM("L_PanelValla"))
	Dim bordes As New List(Of Double())
	bordes.Add(New Double() {r(0), r(1), r(3), r(1), 0})
	bordes.Add(New Double() {r(0), r(4), r(3), r(4), 0})
	bordes.Add(New Double() {r(0), r(1), r(0), r(4), 1})
	bordes.Add(New Double() {r(3), r(1), r(3), r(4), 1})
	Dim bordePuerta As Integer
	Select Case PTxt("L_LadoPuerta")
		Case "Frente" : bordePuerta = 0
		Case "Fondo" : bordePuerta = 1
		Case "Izquierda" : bordePuerta = 2
		Case "Derecha" : bordePuerta = 3
		Case Else : bordePuerta = If(lado = "Atras", 2, 1)
	End Select
	Dim obst As New List(Of Double())
	For Each it As ItemPlan In plan
		If it.Cruza Then obst.Add(RectItem(it))
	Next
	Dim vallaRuta As String = Resolver("VALLA")
	Dim puertaRuta As String = Resolver("PUERTA")
	For e As Integer = 0 To 3
		Dim bd() As Double = bordes(e)
		Dim horiz As Boolean = (bd(4) = 0)
		Dim e0 As Double = If(horiz, bd(0), bd(1)), e1 As Double = If(horiz, bd(2), bd(3))
		Dim c As Double = If(horiz, bd(1), bd(0))
		Dim ocup As New List(Of Double())
		For Each ob As Double() In obst
			If horiz Then
				If ob(1) < c + 100 AndAlso ob(4) > c - 100 Then ocup.Add(New Double() {ob(0) - 30, ob(3) + 30})
			Else
				If ob(0) < c + 100 AndAlso ob(3) > c - 100 Then ocup.Add(New Double() {ob(1) - 30, ob(4) + 30})
			End If
		Next
		ocup.Sort(Function(p1, p2) p1(0).CompareTo(p2(0)))
		Dim libres As New List(Of Double())
		Dim cur As Double = e0
		For Each o As Double() In ocup
			If o(0) > cur Then libres.Add(New Double() {cur, Math.Min(o(0), e1)})
			cur = Math.Max(cur, o(1))
			If cur >= e1 Then Exit For
		Next
		If cur < e1 Then libres.Add(New Double() {cur, e1})
		Dim iPuerta As Integer = -1
		If e = bordePuerta AndAlso PBool("L_Puerta") Then
			Dim mejorL As Double = 0
			For i As Integer = 0 To libres.Count - 1
				If libres(i)(1) - libres(i)(0) > mejorL Then
					mejorL = libres(i)(1) - libres(i)(0)
					iPuerta = i
				End If
			Next
		End If
		For i As Integer = 0 To libres.Count - 1
			Dim L As Double = libres(i)(1) - libres(i)(0)
			If L < 250 Then Continue For
			Dim n As Integer = Math.Max(1, CInt(Math.Ceiling(L / Pmax - 0.001)))
			Dim Lp As Double = L / n
			For j As Integer = 0 To n - 1
				Dim s0 As Double = libres(i)(0) + (j + 0.5) * Lp
				Dim it As New ItemPlan
				Dim esPuerta As Boolean = (i = iPuerta AndAlso j = n \ 2)
				it.Borde = e
				it.Tipo = If(esPuerta, "puerta", "valla")
				it.Nombre = If(esPuerta, "Puerta", "Valla")
				it.Cx = If(horiz, s0, c) : it.Cy = If(horiz, c, s0)
				Dim rl As String = If(esPuerta, puertaRuta, vallaRuta)
				If rl <> "" Then
					it.Ruta = rl : it.Eje = If(horiz, "X", "Y")
					it.W = If(horiz, Lp, 60) : it.D = If(horiz, 60, Lp) : it.H = Hv
				Else
					it.Gen = it.Tipo : it.GenP = New Double() {Lp, Hv}
					it.Rot = If(horiz, 0, 90)
					Dimensionar(it, Lp, 60, Hv)
				End If
				plan.Add(it)
			Next
		Next
	Next
End Sub

' ---- mosaico: rectangulos {x, y, ancho, prof} centrados en el pallet
Function PatronCapa(Px As Double, Py As Double, a As Double, b As Double, tipo As String, capa As Integer) As List(Of Double())
	Dim colA As List(Of Double()) = Grilla(Px, Py, a, b)
	Dim colB As List(Of Double()) = Grilla(Px, Py, b, a)
	Dim mejorCol As List(Of Double()) = If(colA.Count >= colB.Count, colA, colB)
	Dim par As Boolean = (capa Mod 2 = 0)
	Select Case tipo
		Case "Columnar"
			Return mejorCol
		Case "Mixto"
			Dim mx As List(Of Double()) = MejorMixto(Px, Py, a, b)
			If mx.Count < mejorCol.Count Then mx = mejorCol
			Return If(par, mx, Girar180(mx))
		Case "Trabado"
			If colA.Count = colB.Count AndAlso colA.Count > 0 Then Return If(par, colA, colB)
			Dim mx As List(Of Double()) = MejorMixto(Px, Py, a, b)
			If mx.Count < mejorCol.Count Then mx = mejorCol
			Return If(par, mx, Girar180(mx))
		Case Else
			Dim mx As List(Of Double()) = MejorMixto(Px, Py, a, b)
			If mx.Count > mejorCol.Count Then Return If(par, mx, Girar180(mx))
			If colA.Count = colB.Count AndAlso colA.Count > 0 Then Return If(par, colA, colB)
			Return mejorCol
	End Select
End Function

Function Grilla(Px As Double, Py As Double, w As Double, d As Double) As List(Of Double())
	Dim l As New List(Of Double())
	Dim nx As Integer = CInt(Math.Floor(Px / w)), ny As Integer = CInt(Math.Floor(Py / d))
	For ix As Integer = 0 To nx - 1
		For iy As Integer = 0 To ny - 1
			l.Add(New Double() {-nx * w / 2 + (ix + 0.5) * w, -ny * d / 2 + (iy + 0.5) * d, w, d})
		Next
	Next
	Return l
End Function

Function MejorMixto(Px As Double, Py As Double, a As Double, b As Double) As List(Of Double())
	Dim mejor As New List(Of Double())
	' filas: k filas con la caja a lo largo de X + el resto girado
	For k As Integer = 0 To CInt(Math.Floor(Py / b))
		Dim l As New List(Of Double())
		Dim h1 As Double = k * b
		Dim n1 As Integer = CInt(Math.Floor(Px / a))
		Dim m As Integer = CInt(Math.Floor((Py - h1) / a)), n2 As Integer = CInt(Math.Floor(Px / b))
		Dim y0 As Double = -(h1 + m * a) / 2
		For iy As Integer = 0 To k - 1
			For ix As Integer = 0 To n1 - 1
				l.Add(New Double() {-n1 * a / 2 + (ix + 0.5) * a, y0 + (iy + 0.5) * b, a, b})
			Next
		Next
		For iy As Integer = 0 To m - 1
			For ix As Integer = 0 To n2 - 1
				l.Add(New Double() {-n2 * b / 2 + (ix + 0.5) * b, y0 + h1 + (iy + 0.5) * a, b, a})
			Next
		Next
		If l.Count > mejor.Count Then mejor = l
	Next
	' columnas: k columnas con la caja a lo largo de X + el resto girado
	For k As Integer = 0 To CInt(Math.Floor(Px / a))
		Dim l As New List(Of Double())
		Dim w1 As Double = k * a
		Dim n1 As Integer = CInt(Math.Floor(Py / b))
		Dim m As Integer = CInt(Math.Floor((Px - w1) / b)), n2 As Integer = CInt(Math.Floor(Py / a))
		Dim x0 As Double = -(w1 + m * b) / 2
		For ix As Integer = 0 To k - 1
			For iy As Integer = 0 To n1 - 1
				l.Add(New Double() {x0 + (ix + 0.5) * a, -n1 * b / 2 + (iy + 0.5) * b, a, b})
			Next
		Next
		For ix As Integer = 0 To m - 1
			For iy As Integer = 0 To n2 - 1
				l.Add(New Double() {x0 + w1 + (ix + 0.5) * b, -n2 * a / 2 + (iy + 0.5) * a, b, a})
			Next
		Next
		If l.Count > mejor.Count Then mejor = l
	Next
	Return mejor
End Function

Function Girar180(l As List(Of Double())) As List(Of Double())
	Dim r As New List(Of Double())
	For Each q As Double() In l
		r.Add(New Double() {-q(0), -q(1), q(2), q(3)})
	Next
	Return r
End Function

' =====================================================================
'  GENERACION EN INVENTOR (recorre el plan)
' =====================================================================
Sub Generar()
	CalcularPlan()
	Dim robOcc As ComponentOccurrence = Nothing
	Dim zBase As Double = -1
	Dim nCajas As Integer = 0
	For Each it As ItemPlan In plan
		If it.Tipo = "zona" OrElse it.Tipo = "pick" Then Continue For
		If it.Tipo = "robot" Then
			robX = it.Cx : robY = it.Cy
			robOcc = ColocarRobot(it.Ruta, it.Etiqueta, If(zBase >= 0, zBase, it.Z0), it.Rot, it.RotBase)
			Continue For
		End If
		If it.Tipo = "gripper" Then
			Dim rg As String = RutaItem(it)
			If rg = "" OrElse robOcc Is Nothing Then
				Falta("Gripper", If(rg = "", it.Etiqueta, "(sin robot)"))
			Else
				MontarGripper(robOcc, rg, it.Rot, it.RotBase)
			End If
			Continue For
		End If
		Dim ruta As String = RutaItem(it)
		If ruta = "" Then
			Falta(it.Nombre, If(it.Etiqueta <> "", it.Etiqueta, "(sin modelo)"))
			Continue For
		End If
		Dim o As ComponentOccurrence = Colocar(ruta, it.Nombre, it.Cx, it.Cy, it.Z0, it.Rot, it.Eje, it.RotBase)
		If o Is Nothing Then Continue For
		If it.Tipo = "caja" Then nCajas += 1
		If it.Tipo = "base" Then zBase = BoxMM(o)(5)
		If it.Gen = "" AndAlso it.Tipo <> "caja" Then
			Dim b() As Double = BoxMM(o)
			CACHE(ClaveCache(it.Ruta, it.RotBase, it.Rot)) = New Double() {b(3) - b(0), b(4) - b(1), b(5) - b(2)}
		End If
	Next
	Lg("Cajas colocadas: " & nCajas)
End Sub

' gripper colgado de la brida: se toma la sub-pieza del robot mas alejada del eje 1 (la muneca)
Sub MontarGripper(robOcc As ComponentOccurrence, ruta As String, rotDeg As Double, rotBase() As Double)
	Lg("+ Gripper <- " & System.IO.Path.GetFileName(ruta))
	Dim br() As Double = BoxMM(robOcc)
	Dim muneca As ComponentOccurrence = Nothing
	Dim dMax As Double = -1
	Try
		For Each so As ComponentOccurrence In robOcc.SubOccurrences
			If Not so.Visible Then Continue For
			Dim b() As Double = BoxMM(so)
			Dim cx As Double = (b(0) + b(3)) / 2 - robX, cy As Double = (b(1) + b(4)) / 2 - robY
			Dim dd As Double = Math.Sqrt(cx * cx + cy * cy) + 0.001 * (b(5) - b(2))
			If dd > dMax Then
				dMax = dd : muneca = so
			End If
		Next
	Catch
	End Try
	Dim bm() As Double = If(muneca IsNot Nothing, BoxMM(muneca), br)
	Dim fxp As Double = (bm(0) + bm(3)) / 2, fyp As Double = (bm(1) + bm(4)) / 2, fzp As Double = bm(2)
	Dim og As ComponentOccurrence
	Try
		og = cd.Occurrences.Add(ruta, MatOrient(rotBase, rotDeg))
	Catch ex As Exception
		Lg("ERROR insertando gripper: " & ex.Message)
		Exit Sub
	End Try
	og.Grounded = False
	Dim bg() As Double = BoxMM(og)
	Dim t As Inventor.Matrix = og.Transformation
	t.Cell(1, 4) = t.Cell(1, 4) + (fxp - (bg(0) + bg(3)) / 2) / 10
	t.Cell(2, 4) = t.Cell(2, 4) + (fyp - (bg(1) + bg(4)) / 2) / 10
	t.Cell(3, 4) = t.Cell(3, 4) + (fzp - bg(5)) / 10
	og.Transformation = t
	og.Grounded = True
	Nombrar(og, "Gripper")
	Lg("Gripper montado debajo de: " & If(muneca IsNot Nothing, muneca.Name, "(robot)"))
End Sub

Function GenGripper(L As Double, A As Double, H As Double) As String
	Dim bl As New List(Of Double())
	Dim cy As New List(Of Double())
	bl.Add(New Double() {-60, -60, H - 40, 60, 60, H})                           ' brida
	bl.Add(New Double() {-30, -30, H - 160, 30, 30, H - 40})                     ' columna
	bl.Add(New Double() {-L / 2, -A / 2, H - 200, L / 2, A / 2, H - 160})        ' placa
	bl.Add(New Double() {-L / 2, -A / 2 - 20, H - 260, L / 2, -A / 2, H - 160})  ' laterales
	bl.Add(New Double() {-L / 2, A / 2, H - 260, L / 2, A / 2 + 20, H - 160})
	Dim nx As Integer = Math.Max(2, CInt(Math.Floor((L - 60) / 120)) + 1)
	Dim ny As Integer = Math.Max(2, CInt(Math.Floor((A - 60) / 120)) + 1)
	For ix As Integer = 0 To nx - 1
		For iy As Integer = 0 To ny - 1
			Dim x As Double = -L / 2 + 50 + ix * (L - 100) / (nx - 1)
			Dim y As Double = -A / 2 + 50 + iy * (A - 100) / (ny - 1)
			cy.Add(New Double() {x, y, 0, x, y, H - 200, 22})                     ' ventosas
		Next
	Next
	Return CrearPieza("Gripper_" & Dm(L) & "x" & Dm(A) & "x" & Dm(H), bl, cy, 60, 110, 170)
End Function

' devuelve el archivo a insertar (genera la pieza a medida si hace falta)
Function RutaItem(it As ItemPlan) As String
	If it.Ruta <> "" Then Return it.Ruta
	If it.GenP Is Nothing Then Return ""
	Dim p() As Double = it.GenP
	Select Case it.Gen
		Case "rodillos" : Return GenRodillos(p(0), p(1), p(2))
		Case "cinta" : Return GenCinta(p(0), p(1), p(2))
		Case "pallet" : Return GenPallet(p(0), p(1), p(2))
		Case "caja" : Return GenBloque("Caja", p(0), p(1), p(2), 196, 160, 110)
		Case "sep" : Return GenBloque("Separador", p(0), p(1), p(2), 225, 200, 160)
		Case "tope" : Return GenBloque("Tope", p(0), p(1), p(2), 200, 40, 40)
		Case "base" : Return GenBloque("Base_Robot", p(0), p(1), p(2), 30, 60, 160)
		Case "valla" : Return GenValla(p(0), p(1), False)
		Case "puerta" : Return GenValla(p(0), p(1), True)
		Case "gripper" : Return GenGripper(p(0), p(1), p(2))
		Case "bloque" : Return GenBloque("Bloque", p(0), p(1), p(2), 150, 160, 175)
	End Select
	Return ""
End Function

' ---- memoria de medidas reales de cada modelo (mejora la vista previa)
Function ClaveCache(ruta As String, rb() As Double, rotDeg As Double) As String
	Dim r As Integer = CInt(((Math.Round(rotDeg) Mod 180) + 180) Mod 180)
	Dim s As String = "0,0,0"
	If rb IsNot Nothing Then s = CInt(rb(0)) & "," & CInt(rb(1)) & "," & CInt(rb(2))
	Return ruta.ToLower() & "|" & s & "|" & r
End Function

Function RutaCache() As String
	Return System.IO.Path.Combine(DirDatos(), "Medidas_cache.txt")
End Function

Sub CargarCache()
	Try
		If Not System.IO.File.Exists(RutaCache()) Then Exit Sub
		For Each ln As String In System.IO.File.ReadAllLines(RutaCache(), System.Text.Encoding.UTF8)
			Dim i As Integer = ln.LastIndexOf("="c)
			If i < 1 Then Continue For
			Dim v() As String = ln.Substring(i + 1).Split(";"c)
			If v.Length < 3 Then Continue For
			Dim ci As System.Globalization.CultureInfo = System.Globalization.CultureInfo.InvariantCulture
			CACHE(ln.Substring(0, i)) = New Double() {Double.Parse(v(0), ci), Double.Parse(v(1), ci), Double.Parse(v(2), ci)}
		Next
	Catch ex As Exception
		Lg("AVISO cache: " & ex.Message)
	End Try
End Sub

Sub GuardarCache()
	Try
		Dim sb As New System.Text.StringBuilder
		Dim ci As System.Globalization.CultureInfo = System.Globalization.CultureInfo.InvariantCulture
		For Each kv As KeyValuePair(Of String, Double()) In CACHE
			sb.AppendLine(kv.Key & "=" & kv.Value(0).ToString("0", ci) & ";" & kv.Value(1).ToString("0", ci) & ";" & kv.Value(2).ToString("0", ci))
		Next
		System.IO.File.WriteAllText(RutaCache(), sb.ToString(), System.Text.Encoding.UTF8)
	Catch
	End Try
End Sub

' =====================================================================
'  VENTANA DE CONFIGURACION (editor grafico con vista previa en vivo)
' =====================================================================
Private ctl As New Dictionary(Of String, System.Windows.Forms.Control)(StringComparer.OrdinalIgnoreCase)
Private ctlUnidad As New Dictionary(Of String, String)(StringComparer.OrdinalIgnoreCase)
Private lienzo As LienzoPanel
Private cargandoDlg As Boolean = True
Private vistaMosaico As Boolean = False
Private verAlcance As Boolean = True
Private verCotas As Boolean = True
Private resumenAbierto As Boolean = True
Private rectResumen As New System.Drawing.RectangleF(14, 14, 300, 30)
Private vSc As Double = 0.1, vCx As Double = 0, vCy As Double = 0
Private vistaIni As Boolean = False
Private selGrupo As String = "", hoverGrupo As String = ""
Private modoArrastre As Integer = 0
Private dragIni() As Double = {0, 0}
Private dragOrig() As Double = {0, 0, 0, 0}
Private panIni As System.Drawing.Point
Private panC() As Double = {0, 0}
Private lblEstado As System.Windows.Forms.Label
Private lblSub As System.Windows.Forms.Label
Private secciones As New Dictionary(Of String, System.Windows.Forms.Panel)
Private navBotones As New List(Of System.Windows.Forms.Button)
Private propNombre As System.Windows.Forms.Label
Private propX As System.Windows.Forms.NumericUpDown
Private propY As System.Windows.Forms.NumericUpDown
Private propGiro As System.Windows.Forms.ComboBox
Private tablaMed As System.Windows.Forms.TableLayoutPanel
Private propMed(3) As System.Windows.Forms.NumericUpDown
Private propEtiq(3) As System.Windows.Forms.Label
Private propOp1 As System.Windows.Forms.CheckBox
Private propOp2 As System.Windows.Forms.CheckBox
Private cargandoProp As Boolean = False
Private lstBiblio As System.Windows.Forms.ListBox
Private txtBuscar As System.Windows.Forms.TextBox
Private lstAgregadas As System.Windows.Forms.ListBox
Private btnPlanta As System.Windows.Forms.Button
Private btnMosaico As System.Windows.Forms.Button
Private menuPlan As System.Windows.Forms.ContextMenuStrip
Private cargandoLista As Boolean = False
Private splitMain As System.Windows.Forms.SplitContainer
Private splitLado As System.Windows.Forms.SplitContainer
Private splitBiblio As System.Windows.Forms.SplitContainer

' tamanos iniciales de los divisores (se pueden arrastrar)
Sub FormularioMostrado(sender As Object, e As EventArgs)
	Try
		Dim f As System.Windows.Forms.Form = CType(sender, System.Windows.Forms.Form)
		Dim esc As Double = f.DeviceDpi / 96.0
		splitMain.Panel1MinSize = CInt(300 * esc)
		splitMain.SplitterDistance = CInt(430 * esc)
		splitLado.Panel2MinSize = CInt(150 * esc)
		splitLado.SplitterDistance = Math.Max(CInt(200 * esc), splitLado.Height - CInt(470 * esc))
		If splitBiblio IsNot Nothing Then splitBiblio.SplitterDistance = CInt(splitBiblio.Height * 0.6)
	Catch
	End Try
	vistaIni = False
	lienzo.Invalidate()
End Sub
Private picPrev As System.Windows.Forms.PictureBox
Private lblPrev As System.Windows.Forms.Label
Private miniaturas As New Dictionary(Of String, System.Drawing.Image)(StringComparer.OrdinalIgnoreCase)

' convierte la miniatura de Inventor (IPictureDisp) en imagen .NET
Class ConvImg
	Inherits System.Windows.Forms.AxHost
	Public Sub New()
		MyBase.New("59EE46BA-677D-4d20-BF10-8D8067CB8B33")
	End Sub
	Public Shared Function Convertir(p As Object) As System.Drawing.Image
		Return GetPictureFromIPicture(p)
	End Function
End Class

Function HashEstable(t As String) As String
	Dim h As Long = 1469598103
	For Each ch As Char In t.ToLower()
		h = (h * 31 + AscW(ch)) Mod 4294967291L
	Next
	Return h.ToString()
End Function

' vista isometrica guardada en el archivo de Inventor (se guarda una copia en Reglas iLogic\Miniaturas)
Function Miniatura(ruta As String) As System.Drawing.Image
	If ruta = "" OrElse Not System.IO.File.Exists(ruta) Then Return Nothing
	If miniaturas.ContainsKey(ruta) Then Return miniaturas(ruta)
	Dim img As System.Drawing.Image = Nothing
	Dim dirM As String = System.IO.Path.Combine(DirDatos(), "Miniaturas")
	Dim fi As New System.IO.FileInfo(ruta)
	Dim arch As String = System.IO.Path.Combine(dirM, HashEstable(ruta) & "_" & fi.Length & ".png")
	Try
		If System.IO.File.Exists(arch) Then
			Dim bytes() As Byte = System.IO.File.ReadAllBytes(arch)
			img = System.Drawing.Image.FromStream(New System.IO.MemoryStream(bytes))
		Else
			Dim ya As Boolean = EstaAbierto(ruta)
			app.SilentOperation = True
			Dim d As Document = app.Documents.Open(ruta, False)
			Dim od As Object = d
			Dim pic As Object = od.Thumbnail      ' enlace tardio: evita la referencia a stdole
			If pic IsNot Nothing Then img = ConvImg.Convertir(pic)
			If Not ya Then d.Close(True)
			app.SilentOperation = False
			If img IsNot Nothing Then
				System.IO.Directory.CreateDirectory(dirM)
				Dim bmp As New System.Drawing.Bitmap(img)
				bmp.Save(arch, System.Drawing.Imaging.ImageFormat.Png)
				img = bmp
			End If
		End If
	Catch ex As Exception
		app.SilentOperation = False
		Lg("AVISO miniatura " & System.IO.Path.GetFileName(ruta) & ": " & ex.Message)
	End Try
	miniaturas(ruta) = img
	Return img
End Function

Sub MostrarMiniatura(ruta As String, titulo As String)
	If picPrev Is Nothing Then Exit Sub
	MostrarIso(titulo, ruta)
	If ruta = "" Then
		picPrev.Image = Nothing
		lblPrev.Text = If(titulo = "", "", titulo & "  (pieza generada a medida)")
		Exit Sub
	End If
	Dim f As System.Windows.Forms.Form = picPrev.FindForm()
	If f IsNot Nothing Then f.Cursor = System.Windows.Forms.Cursors.WaitCursor
	lblPrev.Text = "Cargando vista previa..."
	lblPrev.Refresh()
	Dim img As System.Drawing.Image = Miniatura(ruta)
	picPrev.Image = img
	lblPrev.Text = titulo & If(img Is Nothing, "  (sin vista previa guardada)", "")
	If f IsNot Nothing Then f.Cursor = System.Windows.Forms.Cursors.Default
End Sub

Function RutaDeGrupo(g As String, ByRef titulo As String) As String
	titulo = NombreGrupo(g)
	Dim mejor As ItemPlan = Nothing
	For Each it As ItemPlan In plan
		If GrupoDe(it) <> g Then Continue For
		If it.Tipo = "robot" Then
			titulo = it.Etiqueta
			Return it.Ruta
		End If
		If (it.Tipo = "maquina" OrElse it.Tipo = "base") AndAlso mejor Is Nothing Then mejor = it
	Next
	If mejor IsNot Nothing Then
		titulo = If(mejor.Etiqueta <> "", mejor.Etiqueta, titulo)
		Return mejor.Ruta
	End If
	Return ""
End Function

' colores de la interfaz
Private Function CAcento() As System.Drawing.Color
	Return System.Drawing.Color.FromArgb(37, 99, 235)
End Function
Private Function CFondo() As System.Drawing.Color
	Return System.Drawing.Color.FromArgb(243, 245, 248)
End Function
Private Function CTexto() As System.Drawing.Color
	Return System.Drawing.Color.FromArgb(40, 48, 61)
End Function
Private Function CSuave() As System.Drawing.Color
	Return System.Drawing.Color.FromArgb(110, 120, 135)
End Function

' lienzo con doble buffer que recibe teclado y rueda del mouse
Class LienzoPanel
	Inherits System.Windows.Forms.Panel
	Public Sub New()
		Me.DoubleBuffered = True
		Me.SetStyle(System.Windows.Forms.ControlStyles.Selectable Or System.Windows.Forms.ControlStyles.UserPaint Or System.Windows.Forms.ControlStyles.AllPaintingInWmPaint Or System.Windows.Forms.ControlStyles.OptimizedDoubleBuffer Or System.Windows.Forms.ControlStyles.ResizeRedraw, True)
		Me.TabStop = True
	End Sub
	Protected Overrides Function IsInputKey(keyData As System.Windows.Forms.Keys) As Boolean
		Return True
	End Function
End Class

' elementos agregados libremente al plano (todos los que quieras)
'  Tipo: maq (modelo de la biblioteca), cinta (entrada de cajas), salida (cinta de salida),
'        rodillos (transportador de pallets), pallet, bloque, valla, copia (copia de un grupo del plano)
Class ExtraMaq
	Public Tipo As String = "maq"
	Public Nombre As String = ""
	Public X As Double = 0
	Public Y As Double = 0
	Public Rot As Double = 0
	Public L As Double = 0
	Public A As Double = 0
	Public H As Double = 0
	Public Z As Double = 0
	Public Op1 As Boolean = False
	Public Op2 As Boolean = False
	Public Function Copia() As ExtraMaq
		Return CType(Me.MemberwiseClone(), ExtraMaq)
	End Function
End Class
Private extras As New List(Of ExtraMaq)
Private ocultos As New HashSet(Of String)(StringComparer.OrdinalIgnoreCase)
Private portaExtra As ExtraMaq = Nothing

Function EscTxt(t As String) As String
	Return t.Replace("%", "%25").Replace(";", "%3B").Replace("|", "%7C")
End Function

Function DesEscTxt(t As String) As String
	Return t.Replace("%7C", "|").Replace("%3B", ";").Replace("%25", "%")
End Function

Function SerializarExtras() As String
	Dim ci As System.Globalization.CultureInfo = System.Globalization.CultureInfo.InvariantCulture
	Dim partes As New List(Of String)
	For Each e As ExtraMaq In extras
		partes.Add("v2;" & e.Tipo & ";" & EscTxt(e.Nombre) & ";" & e.X.ToString("0", ci) & ";" & e.Y.ToString("0", ci) & ";" & e.Rot.ToString("0", ci) & ";" & e.L.ToString("0", ci) & ";" & e.A.ToString("0", ci) & ";" & e.H.ToString("0", ci) & ";" & e.Z.ToString("0", ci) & ";" & If(e.Op1, "1", "0") & ";" & If(e.Op2, "1", "0"))
	Next
	Return String.Join("|", partes.ToArray())
End Function

Sub LeerExtras(txt As String)
	extras.Clear()
	Dim ci As System.Globalization.CultureInfo = System.Globalization.CultureInfo.InvariantCulture
	If txt IsNot Nothing AndAlso txt.Trim() <> "" Then
		For Each parte As String In txt.Split("|"c)
			Dim v() As String = parte.Split(";"c)
			If v.Length < 4 Then Continue For
			Try
				Dim e As New ExtraMaq
				If v(0) = "v2" AndAlso v.Length >= 12 Then
					e.Tipo = v(1) : e.Nombre = DesEscTxt(v(2))
					e.X = Double.Parse(v(3), ci) : e.Y = Double.Parse(v(4), ci) : e.Rot = Double.Parse(v(5), ci)
					e.L = Double.Parse(v(6), ci) : e.A = Double.Parse(v(7), ci) : e.H = Double.Parse(v(8), ci) : e.Z = Double.Parse(v(9), ci)
					e.Op1 = (v(10) = "1") : e.Op2 = (v(11) = "1")
				Else
					e.Nombre = v(0) : e.X = Double.Parse(v(1), ci) : e.Y = Double.Parse(v(2), ci) : e.Rot = Double.Parse(v(3), ci)
				End If
				extras.Add(e)
			Catch
			End Try
		Next
	End If
	' compatibilidad con las 3 maquinas extra de la version anterior
	If extras.Count = 0 Then
		For k As Integer = 1 To 3
			Try
				Dim nom As String = CStr(PUp("L_Extra" & k).Value)
				If nom <> "" AndAlso nom <> "Ninguna" Then
					Dim e As New ExtraMaq
					e.Nombre = nom
					e.X = CDbl(PUp("L_Extra" & k & "_X").Value) * 10
					e.Y = CDbl(PUp("L_Extra" & k & "_Y").Value) * 10
					e.Rot = CDbl(PUp("L_Extra" & k & "_Rot").Value) * 180 / Math.PI
					extras.Add(e)
				End If
			Catch
			End Try
		Next
	End If
End Sub

Sub GuardarEdicion()
	cfg("L_Posiciones") = SerializarPosiciones()
	cfg("L_Extras") = SerializarExtras()
	cfg("L_Ocultos") = String.Join("|", New List(Of String)(ocultos).ToArray())
End Sub

Function NuevoBoton(texto As String, ancho As Integer, primario As Boolean) As System.Windows.Forms.Button
	Dim b As New System.Windows.Forms.Button
	b.Text = texto
	b.Size = New System.Drawing.Size(ancho, 30)
	b.FlatStyle = System.Windows.Forms.FlatStyle.Flat
	b.Cursor = System.Windows.Forms.Cursors.Hand
	b.Font = New System.Drawing.Font("Segoe UI", 9)
	If primario Then
		b.BackColor = CAcento()
		b.ForeColor = System.Drawing.Color.White
		b.FlatAppearance.BorderSize = 0
		b.FlatAppearance.MouseOverBackColor = System.Drawing.Color.FromArgb(29, 78, 216)
		b.FlatAppearance.MouseDownBackColor = System.Drawing.Color.FromArgb(30, 64, 175)
		b.Font = New System.Drawing.Font("Segoe UI", 9.5F, System.Drawing.FontStyle.Bold)
	Else
		b.BackColor = System.Drawing.Color.White
		b.ForeColor = CTexto()
		b.FlatAppearance.BorderColor = System.Drawing.Color.FromArgb(210, 216, 226)
		b.FlatAppearance.BorderSize = 1
		b.FlatAppearance.MouseOverBackColor = System.Drawing.Color.FromArgb(232, 240, 254)
		b.FlatAppearance.MouseDownBackColor = System.Drawing.Color.FromArgb(210, 225, 252)
	End If
	AddHandler b.MouseEnter, Sub(sx As Object, ex As EventArgs)
		If b.BackColor <> CAcento() Then b.FlatAppearance.BorderColor = CAcento()
	End Sub
	AddHandler b.MouseLeave, Sub(sx As Object, ex As EventArgs)
		b.FlatAppearance.BorderColor = System.Drawing.Color.FromArgb(210, 216, 226)
	End Sub
	Return b
End Function

Function MostrarDialogo() As String
	Dim f As New System.Windows.Forms.Form
	f.Text = "Generador de layout de paletizado"
	f.BackColor = CFondo()
	f.Font = New System.Drawing.Font("Segoe UI", 9)
	f.StartPosition = System.Windows.Forms.FormStartPosition.CenterScreen
	f.Size = New System.Drawing.Size(1600, 950)
	f.MinimumSize = New System.Drawing.Size(1200, 720)
	f.WindowState = System.Windows.Forms.FormWindowState.Maximized
	f.KeyPreview = False
	f.SuspendLayout()

	' ---------- zona central: barra de herramientas + lienzo
	Dim principal As New System.Windows.Forms.Panel
	principal.Dock = System.Windows.Forms.DockStyle.Fill
	principal.Padding = New System.Windows.Forms.Padding(10, 10, 10, 6)
	lienzo = New LienzoPanel
	lienzo.Dock = System.Windows.Forms.DockStyle.Fill
	lienzo.BackColor = System.Drawing.Color.FromArgb(250, 251, 253)
	lienzo.AllowDrop = True
	AddHandler lienzo.Paint, AddressOf PintarLienzo
	AddHandler lienzo.MouseDown, AddressOf LienzoMouseDown
	AddHandler lienzo.MouseMove, AddressOf LienzoMouseMove
	AddHandler lienzo.MouseUp, AddressOf LienzoMouseUp
	AddHandler lienzo.MouseWheel, AddressOf LienzoRueda
	AddHandler lienzo.MouseEnter, AddressOf LienzoEntrar
	AddHandler lienzo.KeyDown, AddressOf LienzoTecla
	AddHandler lienzo.DragEnter, AddressOf LienzoDragEnter
	AddHandler lienzo.DragDrop, AddressOf LienzoDragDrop
	principal.Controls.Add(lienzo)
	Dim barra As New System.Windows.Forms.FlowLayoutPanel
	barra.Dock = System.Windows.Forms.DockStyle.Top
	barra.AutoSize = True
	barra.AutoSizeMode = System.Windows.Forms.AutoSizeMode.GrowAndShrink
	barra.WrapContents = True
	barra.Padding = New System.Windows.Forms.Padding(0, 4, 0, 4)
	barra.BackColor = CFondo()
	btnPlanta = NuevoBoton("Vista en planta", 120, True)
	btnMosaico = NuevoBoton("Mosaico del pallet", 140, False)
	btnPlanta.AutoSize = True : btnMosaico.AutoSize = True
	AddHandler btnPlanta.Click, AddressOf CambiarVista
	AddHandler btnMosaico.Click, AddressOf CambiarVista
	barra.Controls.Add(btnPlanta)
	barra.Controls.Add(btnMosaico)
	barra.Controls.Add(Separador())
	For Each tb As String In New String() {"Encuadrar", "Zoom +", "Zoom -", "|", "Girar -90", "Girar +90", "Posicion auto", "Quitar", "|", "Copiar", "Pegar", "Duplicar", "|", "Todo auto", "Restaurar quitados"}
		If tb = "|" Then
			barra.Controls.Add(Separador())
			Continue For
		End If
		Dim b As System.Windows.Forms.Button = NuevoBoton(tb, If(tb.Length > 9, 105, 82), False)
		b.AutoSize = True
		b.MinimumSize = New System.Drawing.Size(70, 30)
		AddHandler b.Click, AddressOf BotonEdicion
		barra.Controls.Add(b)
	Next
	barra.Controls.Add(Separador())
	For Each tc As String In New String() {"Alcance", "Cotas"}
		Dim c As New System.Windows.Forms.CheckBox
		c.Text = tc
		c.Checked = True
		c.AutoSize = True
		c.Margin = New System.Windows.Forms.Padding(6, 9, 6, 0)
		c.ForeColor = CTexto()
		AddHandler c.CheckedChanged, AddressOf CambiarCapas
		barra.Controls.Add(c)
	Next
	principal.Controls.Add(barra)

	' ---------- barra lateral
	' divisores que se pueden arrastrar: lateral | plano  y  secciones / seleccion
	splitMain = New System.Windows.Forms.SplitContainer
	splitMain.Dock = System.Windows.Forms.DockStyle.Fill
	splitMain.Orientation = System.Windows.Forms.Orientation.Vertical
	splitMain.FixedPanel = System.Windows.Forms.FixedPanel.Panel1
	splitMain.SplitterWidth = 6
	splitMain.BackColor = System.Drawing.Color.FromArgb(222, 227, 235)
	splitMain.Panel1.BackColor = System.Drawing.Color.White
	splitMain.Panel2.BackColor = CFondo()
	splitLado = New System.Windows.Forms.SplitContainer
	splitLado.Dock = System.Windows.Forms.DockStyle.Fill
	splitLado.Orientation = System.Windows.Forms.Orientation.Horizontal
	splitLado.FixedPanel = System.Windows.Forms.FixedPanel.Panel2
	splitLado.SplitterWidth = 6
	splitLado.BackColor = System.Drawing.Color.FromArgb(222, 227, 235)
	splitLado.Panel1.BackColor = System.Drawing.Color.White
	splitMain.Panel1.Controls.Add(splitLado)
	Dim contenido As New System.Windows.Forms.Panel
	contenido.Dock = System.Windows.Forms.DockStyle.Fill
	contenido.BackColor = System.Drawing.Color.White
	splitLado.Panel1.Controls.Add(contenido)
	Dim props As System.Windows.Forms.Panel = CrearPanelPropiedades()
	splitLado.Panel2.Controls.Add(props)
	Dim nav As New System.Windows.Forms.FlowLayoutPanel
	nav.Dock = System.Windows.Forms.DockStyle.Top
	nav.AutoSize = True
	nav.AutoSizeMode = System.Windows.Forms.AutoSizeMode.GrowAndShrink
	nav.Padding = New System.Windows.Forms.Padding(10, 10, 10, 4)
	nav.BackColor = System.Drawing.Color.White
	splitLado.Panel1.Controls.Add(nav)

	Dim claves() As String = {"Robot", "Linea", "Entrada", "Producto", "Maquinas", "Vallado", "Biblioteca"}
	Dim titulos() As String = {"Robot y gripper", "Linea de pallets", "Entrada de cajas", "Producto y pallet", "Maquinas", "Vallado", "+ Agregar maquinas"}
	For i As Integer = 0 To claves.Length - 1
		Dim pn As New System.Windows.Forms.Panel
		pn.Size = New System.Drawing.Size(410, 900)      ' tamano de diseno: los campos se estiran desde aca
		pn.Dock = System.Windows.Forms.DockStyle.Fill
		pn.AutoScroll = True
		pn.BackColor = System.Drawing.Color.White
		pn.Visible = (i = 0)
		pn.Tag = 56
		Dim tit As New System.Windows.Forms.Label
		tit.Text = titulos(i).Replace("+ ", "")
		tit.Font = New System.Drawing.Font("Segoe UI Semibold", 13)
		tit.ForeColor = CTexto()
		tit.Location = New System.Drawing.Point(16, 14)
		tit.AutoSize = True
		pn.Controls.Add(tit)
		contenido.Controls.Add(pn)
		secciones(claves(i)) = pn
		Dim nb As System.Windows.Forms.Button = NuevoBoton(titulos(i), 126, i = 0)
		nb.AutoSize = True
		nb.MinimumSize = New System.Drawing.Size(110, 30)
		nb.Tag = claves(i)
		nb.Margin = New System.Windows.Forms.Padding(0, 0, 4, 4)
		AddHandler nb.Click, AddressOf CambiarSeccion
		nav.Controls.Add(nb)
		navBotones.Add(nb)
	Next

	' filas de parametros
	Dim robs As New List(Of String)(ROBOTS.Keys)
	robs.Sort()
	Dim maqs As New List(Of String)(MAQUINAS.Keys)
	maqs.Sort()
	For Each d As String In Defs()
		Dim p() As String = d.Split("|"c)
		Dim nombre As String = p(0), unidad As String = p(2), pag As String = p(3), etiqueta As String = p(4), tipo As String = p(5)
		If pag = "-" OrElse Not secciones.ContainsKey(pag) Then Continue For
		Dim pn As System.Windows.Forms.Panel = secciones(pag)
		Dim y As Integer = CInt(pn.Tag)
		Dim sub1 As Boolean = etiqueta.StartsWith("   ")
		Dim lb As New System.Windows.Forms.Label
		lb.Text = etiqueta.Trim()
		lb.ForeColor = If(sub1, CSuave(), CTexto())
		lb.Location = New System.Drawing.Point(If(sub1, 34, 18), y + 5)
		lb.Size = New System.Drawing.Size(If(sub1, 168, 184), 20)
		lb.AutoEllipsis = True
		pn.Controls.Add(lb)
		Dim c As System.Windows.Forms.Control
		If tipo = "bool" Then
			Dim cb As New System.Windows.Forms.CheckBox
			cb.Checked = PBool(nombre)
			cb.Text = If(PBool(nombre), "Si", "No")
			cb.Appearance = System.Windows.Forms.Appearance.Button
			cb.FlatStyle = System.Windows.Forms.FlatStyle.Flat
			cb.TextAlign = System.Drawing.ContentAlignment.MiddleCenter
			EstiloInterruptor(cb)
			AddHandler cb.CheckedChanged, AddressOf AlCambiar
			c = cb
		ElseIf tipo.StartsWith("combo:") Then
			Dim co As New System.Windows.Forms.ComboBox
			co.DropDownStyle = System.Windows.Forms.ComboBoxStyle.DropDownList
			co.FlatStyle = System.Windows.Forms.FlatStyle.Flat
			Dim fuente As String = tipo.Substring(6)
			Dim items As New List(Of String)
			Select Case fuente
				Case "@ROBOTS" : items.AddRange(robs)
				Case "@MAQ" : items.AddRange(maqs)
				Case "@MAQN" : items.Add("Ninguna") : items.AddRange(maqs)
				Case "@GRIP"
					items.Add("Ninguno") : items.Add("Generado (ventosas)")
					For Each mq As String In maqs
						If mq.ToLower().Contains("grip") OrElse mq.ToLower().Contains("garra") Then items.Add(mq)
					Next
					For Each mq As String In maqs
						If Not items.Contains(mq) Then items.Add(mq)
					Next
				Case "@BASES"
					items.Add("Automatica") : items.Add("Generada") : items.Add("Sin base")
					Dim bs As New List(Of String)(BASES.Keys)
					bs.Sort()
					items.AddRange(bs)
					For Each mq As String In maqs
						If Not items.Contains(mq) Then items.Add(mq)
					Next
				Case "@CAJAS" : items.AddRange(PresetsCaja())
				Case "@PALLETS" : items.AddRange(PresetsPallet())
				Case Else : items.AddRange(fuente.Split(","c))
			End Select
			For Each it As String In items
				If it <> "" Then co.Items.Add(it)
			Next
			Dim actual As String
			If unidad = "txt" Then
				actual = PTxt(nombre)
			Else
				actual = CInt(PNum(nombre)).ToString()
			End If
			If Not co.Items.Contains(actual) AndAlso actual <> "" AndAlso (fuente.StartsWith("@MAQ") OrElse fuente = "@GRIP") Then co.Items.Add(actual)
			If co.Items.Contains(actual) Then
				co.SelectedItem = actual
			ElseIf co.Items.Count > 0 Then
				co.SelectedIndex = 0
			End If
			If fuente = "@ROBOTS" OrElse fuente = "@MAQ" OrElse fuente = "@GRIP" OrElse fuente = "@BASES" Then co.Tag = fuente
			AddHandler co.SelectedIndexChanged, AddressOf AlCambiar
			c = co
		Else
			Dim nu As New System.Windows.Forms.NumericUpDown
			nu.Minimum = -100000 : nu.Maximum = 100000
			nu.DecimalPlaces = If(tipo = "num1", 1, 0)
			nu.BorderStyle = System.Windows.Forms.BorderStyle.FixedSingle
			nu.TextAlign = System.Windows.Forms.HorizontalAlignment.Right
			If unidad = "deg" Then
				nu.Increment = 90
			ElseIf unidad = "ul" Then
				nu.Increment = 1
			Else
				nu.Increment = 50
			End If
			Dim v As Double
			If unidad = "mm" Then
				v = PMM(nombre)
			ElseIf unidad = "deg" Then
				v = PDeg(nombre)
			Else
				v = PNum(nombre)
			End If
			nu.Value = CDec(Math.Round(v, nu.DecimalPlaces))
			AddHandler nu.ValueChanged, AddressOf AlCambiar
			c = nu
		End If
		c.Location = New System.Drawing.Point(205, y)
		c.Size = New System.Drawing.Size(150, 26)
		c.Anchor = System.Windows.Forms.AnchorStyles.Top Or System.Windows.Forms.AnchorStyles.Left Or System.Windows.Forms.AnchorStyles.Right
		pn.Controls.Add(c)
		If unidad = "mm" OrElse unidad = "deg" Then
			Dim lu As New System.Windows.Forms.Label
			lu.Text = If(unidad = "mm", "mm", "grados")
			lu.ForeColor = CSuave()
			lu.Font = New System.Drawing.Font("Segoe UI", 8)
			lu.Location = New System.Drawing.Point(360, y + 6)
			lu.Anchor = System.Windows.Forms.AnchorStyles.Top Or System.Windows.Forms.AnchorStyles.Right
			lu.AutoSize = True
			pn.Controls.Add(lu)
		End If
		ctl(nombre) = c
		ctlUnidad(nombre) = unidad
		pn.Tag = y + 32
	Next
	CrearSeccionBiblioteca(secciones("Biblioteca"), maqs)

	' ---------- encabezado
	Dim cab As New System.Windows.Forms.Panel
	cab.Dock = System.Windows.Forms.DockStyle.Top
	cab.Height = 62
	cab.BackColor = System.Drawing.Color.FromArgb(22, 30, 46)
	Dim t1 As New System.Windows.Forms.Label
	t1.Text = "Generador de layout de paletizado"
	t1.Font = New System.Drawing.Font("Segoe UI Semibold", 15)
	t1.ForeColor = System.Drawing.Color.White
	t1.Location = New System.Drawing.Point(18, 8)
	t1.AutoSize = True
	cab.Controls.Add(t1)
	lblSub = New System.Windows.Forms.Label
	lblSub.Font = New System.Drawing.Font("Segoe UI", 9)
	lblSub.ForeColor = System.Drawing.Color.FromArgb(160, 175, 200)
	lblSub.Location = New System.Drawing.Point(20, 38)
	lblSub.AutoSize = True
	cab.Controls.Add(lblSub)
	Dim acciones As New System.Windows.Forms.FlowLayoutPanel
	acciones.Dock = System.Windows.Forms.DockStyle.Right
	acciones.FlowDirection = System.Windows.Forms.FlowDirection.RightToLeft
	acciones.WrapContents = False
	acciones.AutoSize = True
	acciones.AutoSizeMode = System.Windows.Forms.AutoSizeMode.GrowAndShrink
	acciones.Padding = New System.Windows.Forms.Padding(0, 11, 12, 0)
	acciones.BackColor = cab.BackColor
	Dim bGen As System.Windows.Forms.Button = NuevoBoton("Generar layout", 170, True)
	bGen.DialogResult = System.Windows.Forms.DialogResult.OK
	Dim bCan As System.Windows.Forms.Button = NuevoBoton("Cancelar", 110, False)
	bCan.DialogResult = System.Windows.Forms.DialogResult.Cancel
	Dim bDiag As System.Windows.Forms.Button = NuevoBoton("Diagnostico", 110, False)
	bDiag.DialogResult = System.Windows.Forms.DialogResult.Retry
	Dim bCarp As System.Windows.Forms.Button = NuevoBoton("Carpeta CAD...", 120, False)
	bCarp.BackColor = System.Drawing.Color.FromArgb(40, 52, 74)
	bCarp.ForeColor = System.Drawing.Color.White
	bCarp.FlatAppearance.BorderColor = System.Drawing.Color.FromArgb(70, 84, 110)
	bCarp.FlatAppearance.MouseOverBackColor = System.Drawing.Color.FromArgb(58, 72, 100)
	AddHandler bCarp.Click, Sub(sx As Object, ex As EventArgs)
		Dim nueva As String = CarpetaBiblioteca(True)
		If nueva <> "" AndAlso Not String.Equals(nueva, Bib("RAIZ"), StringComparison.OrdinalIgnoreCase) Then
			LeerControles()
			GuardarEdicion()
			f.DialogResult = System.Windows.Forms.DialogResult.Abort
		End If
	End Sub
	For Each b As System.Windows.Forms.Button In New System.Windows.Forms.Button() {bGen, bCan, bDiag, bCarp}
		b.AutoSize = True
		b.MinimumSize = New System.Drawing.Size(b.Width, 38)
		b.Margin = New System.Windows.Forms.Padding(8, 0, 0, 0)
		acciones.Controls.Add(b)
	Next
	cab.Controls.Add(acciones)

	' ---------- barra de estado
	Dim est As New System.Windows.Forms.Panel
	est.Dock = System.Windows.Forms.DockStyle.Bottom
	est.Height = 28
	est.BackColor = System.Drawing.Color.White
	lblEstado = New System.Windows.Forms.Label
	lblEstado.Dock = System.Windows.Forms.DockStyle.Fill
	lblEstado.TextAlign = System.Drawing.ContentAlignment.MiddleLeft
	lblEstado.Padding = New System.Windows.Forms.Padding(12, 0, 0, 0)
	lblEstado.ForeColor = CSuave()
	est.Controls.Add(lblEstado)

	splitMain.Panel2.Controls.Add(principal)
	f.Controls.Add(splitMain)
	f.Controls.Add(est)
	f.Controls.Add(cab)
	AddHandler f.Shown, AddressOf FormularioMostrado
	f.AcceptButton = Nothing
	f.CancelButton = Nothing
	' todo se diseno a 96 dpi: Windows lo escala solo en pantallas con zoom (notebooks)
	f.AutoScaleDimensions = New System.Drawing.SizeF(96.0F, 96.0F)
	f.AutoScaleMode = System.Windows.Forms.AutoScaleMode.Dpi
	f.ResumeLayout(False)

	' menu contextual del lienzo
	menuPlan = New System.Windows.Forms.ContextMenuStrip
	For Each tm As String In New String() {"Girar -90", "Girar +90", "Posicion auto", "-", "Copiar", "Cortar", "Pegar", "Duplicar", "Quitar", "-", "Encuadrar", "Todo auto", "Restaurar quitados"}
		If tm = "-" Then
			menuPlan.Items.Add(New System.Windows.Forms.ToolStripSeparator)
		Else
			Dim mi As New System.Windows.Forms.ToolStripMenuItem(tm)
			AddHandler mi.Click, AddressOf BotonEdicion
			menuPlan.Items.Add(mi)
		End If
	Next

	cargandoDlg = False
	Refrescar()
	ActualizarListaAgregadas()
	ActualizarPropiedades()
	Dim r As System.Windows.Forms.DialogResult = f.ShowDialog()
	If r = System.Windows.Forms.DialogResult.Abort Then Return "Reabrir"
	If r = System.Windows.Forms.DialogResult.Cancel OrElse r = System.Windows.Forms.DialogResult.None Then Return "Cancelar"
	LeerControles()
	GuardarEdicion()
	If r = System.Windows.Forms.DialogResult.Retry Then Return "Diagnostico"
	Return "Generar"
End Function

Function Separador() As System.Windows.Forms.Control
	Dim s As New System.Windows.Forms.Label
	s.Width = 1 : s.Height = 26
	s.BackColor = System.Drawing.Color.FromArgb(210, 216, 226)
	s.Margin = New System.Windows.Forms.Padding(8, 2, 8, 0)
	Return s
End Function

Sub EstiloInterruptor(cb As System.Windows.Forms.CheckBox)
	cb.FlatAppearance.BorderSize = 1
	cb.Cursor = System.Windows.Forms.Cursors.Hand
	cb.FlatAppearance.MouseOverBackColor = System.Drawing.Color.FromArgb(232, 240, 254)
	cb.FlatAppearance.CheckedBackColor = System.Drawing.Color.FromArgb(220, 232, 255)
	If cb.Checked Then
		cb.BackColor = System.Drawing.Color.FromArgb(220, 232, 255)
		cb.ForeColor = CAcento()
		cb.FlatAppearance.BorderColor = CAcento()
		cb.Text = "Si"
	Else
		cb.BackColor = System.Drawing.Color.FromArgb(245, 246, 248)
		cb.ForeColor = CSuave()
		cb.FlatAppearance.BorderColor = System.Drawing.Color.FromArgb(210, 216, 226)
		cb.Text = "No"
	End If
End Sub

Function CrearPanelPropiedades() As System.Windows.Forms.Panel
	Dim p As New System.Windows.Forms.Panel
	p.Dock = System.Windows.Forms.DockStyle.Fill
	p.Padding = New System.Windows.Forms.Padding(14, 8, 14, 8)
	p.BackColor = System.Drawing.Color.FromArgb(247, 249, 252)
	Dim t As New System.Windows.Forms.Label
	t.Text = "SELECCION"
	t.Font = New System.Drawing.Font("Segoe UI", 8, System.Drawing.FontStyle.Bold)
	t.ForeColor = CSuave()
	t.Dock = System.Windows.Forms.DockStyle.Top
	t.Height = 18
	propNombre = New System.Windows.Forms.Label
	propNombre.Font = New System.Drawing.Font("Segoe UI Semibold", 11)
	propNombre.ForeColor = CTexto()
	propNombre.Dock = System.Windows.Forms.DockStyle.Top
	propNombre.Height = 26
	propNombre.AutoEllipsis = True
	Dim tablaPrev As New System.Windows.Forms.TableLayoutPanel
	tablaPrev.Dock = System.Windows.Forms.DockStyle.Fill
	tablaPrev.ColumnCount = 2
	tablaPrev.RowCount = 1
	tablaPrev.ColumnStyles.Add(New System.Windows.Forms.ColumnStyle(System.Windows.Forms.SizeType.Percent, 50))
	tablaPrev.ColumnStyles.Add(New System.Windows.Forms.ColumnStyle(System.Windows.Forms.SizeType.Percent, 50))
	tablaPrev.RowStyles.Add(New System.Windows.Forms.RowStyle(System.Windows.Forms.SizeType.Percent, 100))
	picIso = New LienzoPanel
	picIso.Dock = System.Windows.Forms.DockStyle.Fill
	picIso.BackColor = System.Drawing.Color.White
	picIso.BorderStyle = System.Windows.Forms.BorderStyle.FixedSingle
	picIso.Margin = New System.Windows.Forms.Padding(3, 0, 0, 0)
	AddHandler picIso.Paint, AddressOf PintarIso
	picPrev = New System.Windows.Forms.PictureBox
	picPrev.Dock = System.Windows.Forms.DockStyle.Fill
	picPrev.Margin = New System.Windows.Forms.Padding(0, 0, 3, 0)
	picPrev.SizeMode = System.Windows.Forms.PictureBoxSizeMode.Zoom
	picPrev.BackColor = System.Drawing.Color.White
	picPrev.BorderStyle = System.Windows.Forms.BorderStyle.FixedSingle
	lblPrev = New System.Windows.Forms.Label
	lblPrev.ForeColor = CSuave()
	lblPrev.Font = New System.Drawing.Font("Segoe UI", 8)
	lblPrev.Dock = System.Windows.Forms.DockStyle.Bottom
	lblPrev.Height = 18
	lblPrev.AutoEllipsis = True
	' X / Y / giro
	Dim tabla As New System.Windows.Forms.TableLayoutPanel
	tabla.Dock = System.Windows.Forms.DockStyle.Bottom
	tabla.Height = 58
	tabla.ColumnCount = 3
	tabla.RowCount = 2
	For i As Integer = 0 To 2
		tabla.ColumnStyles.Add(New System.Windows.Forms.ColumnStyle(System.Windows.Forms.SizeType.Percent, 33.3F))
	Next
	tabla.RowStyles.Add(New System.Windows.Forms.RowStyle(System.Windows.Forms.SizeType.Absolute, 22))
	tabla.RowStyles.Add(New System.Windows.Forms.RowStyle(System.Windows.Forms.SizeType.Absolute, 32))
	Dim etiquetas() As String = {"X (mm)", "Y (mm)", "Giro"}
	For i As Integer = 0 To 2
		Dim l As New System.Windows.Forms.Label
		l.Text = etiquetas(i)
		l.ForeColor = CSuave()
		l.Dock = System.Windows.Forms.DockStyle.Fill
		l.TextAlign = System.Drawing.ContentAlignment.BottomLeft
		tabla.Controls.Add(l, i, 0)
	Next
	propX = New System.Windows.Forms.NumericUpDown
	propY = New System.Windows.Forms.NumericUpDown
	For Each n As System.Windows.Forms.NumericUpDown In New System.Windows.Forms.NumericUpDown() {propX, propY}
		n.Minimum = -200000 : n.Maximum = 200000 : n.Increment = 50
		n.BorderStyle = System.Windows.Forms.BorderStyle.FixedSingle
		n.TextAlign = System.Windows.Forms.HorizontalAlignment.Right
		n.Dock = System.Windows.Forms.DockStyle.Fill
		AddHandler n.ValueChanged, AddressOf PropCambio
	Next
	propGiro = New System.Windows.Forms.ComboBox
	propGiro.DropDownStyle = System.Windows.Forms.ComboBoxStyle.DropDownList
	propGiro.FlatStyle = System.Windows.Forms.FlatStyle.Flat
	propGiro.Items.AddRange(New Object() {"0", "90", "180", "270"})
	propGiro.Dock = System.Windows.Forms.DockStyle.Fill
	AddHandler propGiro.SelectedIndexChanged, AddressOf PropCambio
	tabla.Controls.Add(propX, 0, 1)
	tabla.Controls.Add(propY, 1, 1)
	tabla.Controls.Add(propGiro, 2, 1)
	' medidas y opciones de los elementos agregados (largo, ancho, alto, elevacion)
	tablaMed = New System.Windows.Forms.TableLayoutPanel
	tablaMed.Dock = System.Windows.Forms.DockStyle.Bottom
	tablaMed.Height = 90
	tablaMed.ColumnCount = 4
	tablaMed.RowCount = 3
	For i As Integer = 0 To 3
		tablaMed.ColumnStyles.Add(New System.Windows.Forms.ColumnStyle(System.Windows.Forms.SizeType.Percent, 25.0F))
	Next
	tablaMed.RowStyles.Add(New System.Windows.Forms.RowStyle(System.Windows.Forms.SizeType.Absolute, 22))
	tablaMed.RowStyles.Add(New System.Windows.Forms.RowStyle(System.Windows.Forms.SizeType.Absolute, 32))
	tablaMed.RowStyles.Add(New System.Windows.Forms.RowStyle(System.Windows.Forms.SizeType.Absolute, 32))
	Dim etM() As String = {"Largo", "Ancho", "Alto", "Elevacion Z"}
	For i As Integer = 0 To 3
		propEtiq(i) = New System.Windows.Forms.Label
		propEtiq(i).Text = etM(i)
		propEtiq(i).ForeColor = CSuave()
		propEtiq(i).Dock = System.Windows.Forms.DockStyle.Fill
		propEtiq(i).TextAlign = System.Drawing.ContentAlignment.BottomLeft
		tablaMed.Controls.Add(propEtiq(i), i, 0)
		propMed(i) = New System.Windows.Forms.NumericUpDown
		propMed(i).Minimum = If(i = 3, -5000, 0) : propMed(i).Maximum = 100000 : propMed(i).Increment = 50
		propMed(i).BorderStyle = System.Windows.Forms.BorderStyle.FixedSingle
		propMed(i).TextAlign = System.Windows.Forms.HorizontalAlignment.Right
		propMed(i).Dock = System.Windows.Forms.DockStyle.Fill
		AddHandler propMed(i).ValueChanged, AddressOf MedCambio
		tablaMed.Controls.Add(propMed(i), i, 1)
	Next
	propOp1 = New System.Windows.Forms.CheckBox
	propOp2 = New System.Windows.Forms.CheckBox
	For Each cb As System.Windows.Forms.CheckBox In New System.Windows.Forms.CheckBox() {propOp1, propOp2}
		cb.AutoSize = False
		cb.Dock = System.Windows.Forms.DockStyle.Fill
		cb.ForeColor = CTexto()
		AddHandler cb.CheckedChanged, AddressOf MedCambio
	Next
	tablaMed.Controls.Add(propOp1, 0, 2)
	tablaMed.SetColumnSpan(propOp1, 2)
	tablaMed.Controls.Add(propOp2, 2, 2)
	tablaMed.SetColumnSpan(propOp2, 2)
	tablaMed.Visible = False
	' botones (se acomodan en varias filas si no entran)
	Dim botones As New System.Windows.Forms.FlowLayoutPanel
	botones.Dock = System.Windows.Forms.DockStyle.Bottom
	botones.AutoSize = True
	botones.AutoSizeMode = System.Windows.Forms.AutoSizeMode.GrowAndShrink
	botones.WrapContents = True
	botones.Padding = New System.Windows.Forms.Padding(0, 6, 0, 0)
	For Each tb As String In New String() {"Girar -90", "Girar +90", "Posicion auto", "Quitar", "Copiar", "Pegar", "Duplicar"}
		Dim bt As System.Windows.Forms.Button = NuevoBoton(tb, 80, False)
		bt.AutoSize = True
		bt.Margin = New System.Windows.Forms.Padding(0, 0, 6, 4)
		AddHandler bt.Click, AddressOf BotonEdicion
		botones.Controls.Add(bt)
	Next
	tablaPrev.Controls.Add(picPrev, 0, 0)
	tablaPrev.Controls.Add(picIso, 1, 0)
	' orientacion del modelo
	panelOrient = New System.Windows.Forms.FlowLayoutPanel
	panelOrient.Dock = System.Windows.Forms.DockStyle.Bottom
	panelOrient.AutoSize = True
	panelOrient.AutoSizeMode = System.Windows.Forms.AutoSizeMode.GrowAndShrink
	panelOrient.WrapContents = True
	panelOrient.Padding = New System.Windows.Forms.Padding(0, 4, 0, 0)
	lblOrient = New System.Windows.Forms.Label
	lblOrient.Text = "Orientacion:"
	lblOrient.ForeColor = CSuave()
	lblOrient.AutoSize = True
	lblOrient.Margin = New System.Windows.Forms.Padding(0, 8, 6, 0)
	panelOrient.Controls.Add(lblOrient)
	For Each tb As String In New String() {"Parar en X", "Parar en Y", "Dar vuelta", "Automatica"}
		Dim bo As System.Windows.Forms.Button = NuevoBoton(tb, 70, False)
		bo.AutoSize = True
		bo.Height = 26
		bo.Margin = New System.Windows.Forms.Padding(0, 0, 4, 4)
		AddHandler bo.Click, AddressOf BotonOrient
		panelOrient.Controls.Add(bo)
	Next
	p.Controls.Add(tablaPrev)
	p.Controls.Add(lblPrev)
	p.Controls.Add(panelOrient)
	p.Controls.Add(tabla)
	p.Controls.Add(tablaMed)
	p.Controls.Add(botones)
	p.Controls.Add(propNombre)
	p.Controls.Add(t)
	Return p
End Function

Sub CrearSeccionBiblioteca(pn As System.Windows.Forms.Panel, maqs As List(Of String))
	pn.AutoScroll = False
	pn.Padding = New System.Windows.Forms.Padding(14, 50, 14, 10)
	splitBiblio = New System.Windows.Forms.SplitContainer
	splitBiblio.Dock = System.Windows.Forms.DockStyle.Fill
	splitBiblio.Orientation = System.Windows.Forms.Orientation.Horizontal
	splitBiblio.SplitterWidth = 6
	splitBiblio.BackColor = System.Drawing.Color.FromArgb(222, 227, 235)
	splitBiblio.Panel1.BackColor = System.Drawing.Color.White
	splitBiblio.Panel2.BackColor = System.Drawing.Color.White
	' arriba: biblioteca
	Dim ayuda As New System.Windows.Forms.Label
	ayuda.Text = "Arrastra una maquina al plano, o elegila y toca Agregar. Podes agregar todas las que quieras."
	' componentes genericos (medidas editables, todos los que quieras)
	Dim genericos As New System.Windows.Forms.FlowLayoutPanel
	genericos.Dock = System.Windows.Forms.DockStyle.Top
	genericos.AutoSize = True
	genericos.AutoSizeMode = System.Windows.Forms.AutoSizeMode.GrowAndShrink
	genericos.WrapContents = True
	genericos.Padding = New System.Windows.Forms.Padding(0, 2, 0, 6)
	Dim lblG As New System.Windows.Forms.Label
	lblG.Text = "Agregar componente:"
	lblG.ForeColor = CSuave()
	lblG.AutoSize = True
	lblG.Margin = New System.Windows.Forms.Padding(0, 8, 6, 0)
	genericos.Controls.Add(lblG)
	Dim tiposG()() As String = {New String() {"+ Cinta de entrada", "cinta"}, New String() {"+ Cinta de salida", "salida"}, New String() {"+ Transportador", "rodillos"}, New String() {"+ Pallet", "pallet"}, New String() {"+ Robot", "robot"}, New String() {"+ Bloque", "bloque"}, New String() {"+ Vallado", "valla"}}
	For Each tgi As String() In tiposG
		Dim bg As System.Windows.Forms.Button = NuevoBoton(tgi(0), 60, False)
		bg.AutoSize = True
		bg.Height = 28
		bg.Margin = New System.Windows.Forms.Padding(0, 0, 5, 5)
		bg.Tag = tgi(1)
		AddHandler bg.Click, AddressOf AgregarGenerico
		genericos.Controls.Add(bg)
	Next
	ayuda.ForeColor = CSuave()
	ayuda.Dock = System.Windows.Forms.DockStyle.Top
	ayuda.Height = 38
	txtBuscar = New System.Windows.Forms.TextBox
	txtBuscar.Dock = System.Windows.Forms.DockStyle.Top
	txtBuscar.BorderStyle = System.Windows.Forms.BorderStyle.FixedSingle
	AddHandler txtBuscar.TextChanged, AddressOf FiltrarBiblioteca
	lstBiblio = New System.Windows.Forms.ListBox
	lstBiblio.Dock = System.Windows.Forms.DockStyle.Fill
	lstBiblio.BorderStyle = System.Windows.Forms.BorderStyle.FixedSingle
	lstBiblio.IntegralHeight = False
	For Each m As String In maqs
		lstBiblio.Items.Add(m)
	Next
	AddHandler lstBiblio.MouseDown, AddressOf BiblioMouseDown
	AddHandler lstBiblio.MouseMove, AddressOf BiblioMouseMove
	AddHandler lstBiblio.MouseUp, AddressOf BiblioMouseUp
	AddHandler lstBiblio.DoubleClick, AddressOf AgregarDesdeBiblioteca
	AddHandler lstBiblio.SelectedIndexChanged, AddressOf BiblioSeleccion
	Dim bAdd As System.Windows.Forms.Button = NuevoBoton("Agregar al plano", 160, True)
	bAdd.Dock = System.Windows.Forms.DockStyle.Bottom
	bAdd.Height = 34
	AddHandler bAdd.Click, AddressOf AgregarDesdeBiblioteca
	splitBiblio.Panel1.Controls.Add(lstBiblio)
	splitBiblio.Panel1.Controls.Add(bAdd)
	splitBiblio.Panel1.Controls.Add(txtBuscar)
	splitBiblio.Panel1.Controls.Add(ayuda)
	splitBiblio.Panel1.Controls.Add(genericos)
	' abajo: agregadas
	Dim t As New System.Windows.Forms.Label
	t.Text = "Agregados al plano (clic para elegir, Ctrl+C / Ctrl+V para copiar)"
	t.Font = New System.Drawing.Font("Segoe UI Semibold", 10)
	t.ForeColor = CTexto()
	t.Dock = System.Windows.Forms.DockStyle.Top
	t.Height = 28
	t.TextAlign = System.Drawing.ContentAlignment.BottomLeft
	lstAgregadas = New System.Windows.Forms.ListBox
	lstAgregadas.Dock = System.Windows.Forms.DockStyle.Fill
	lstAgregadas.BorderStyle = System.Windows.Forms.BorderStyle.FixedSingle
	lstAgregadas.IntegralHeight = False
	AddHandler lstAgregadas.SelectedIndexChanged, AddressOf AgregadaSeleccionada
	Dim bDel As System.Windows.Forms.Button = NuevoBoton("Quitar", 100, False)
	bDel.Dock = System.Windows.Forms.DockStyle.Bottom
	bDel.Height = 34
	AddHandler bDel.Click, AddressOf BotonEdicion
	splitBiblio.Panel2.Controls.Add(lstAgregadas)
	splitBiblio.Panel2.Controls.Add(bDel)
	splitBiblio.Panel2.Controls.Add(t)
	pn.Controls.Add(splitBiblio)
End Sub

Sub FiltrarBiblioteca(sender As Object, e As EventArgs)
	Dim f As String = txtBuscar.Text.Trim().ToLower()
	lstBiblio.BeginUpdate()
	lstBiblio.Items.Clear()
	Dim maqs As New List(Of String)(MAQUINAS.Keys)
	maqs.Sort()
	For Each m As String In maqs
		If f = "" OrElse m.ToLower().Contains(f) Then lstBiblio.Items.Add(m)
	Next
	lstBiblio.EndUpdate()
End Sub

Sub BiblioSeleccion(sender As Object, e As EventArgs)
	If lstBiblio.SelectedItem Is Nothing Then Exit Sub
	Dim nom As String = CStr(lstBiblio.SelectedItem)
	If MAQUINAS.ContainsKey(nom) Then MostrarMiniatura(MAQUINAS(nom), nom)
	ultimoPrev = "-"
End Sub

Private biblioItem As String = ""
Private biblioIni As System.Drawing.Point
Private biblioArrastre As Boolean = False

' arrastre propio desde la lista al plano (no depende del arrastrar/soltar de Windows)
Sub BiblioMouseDown(sender As Object, e As System.Windows.Forms.MouseEventArgs)
	Dim i As Integer = lstBiblio.IndexFromPoint(e.Location)
	biblioItem = If(i >= 0, CStr(lstBiblio.Items(i)), "")
	biblioIni = e.Location
	biblioArrastre = False
End Sub

Sub BiblioMouseMove(sender As Object, e As System.Windows.Forms.MouseEventArgs)
	If biblioItem = "" OrElse e.Button <> System.Windows.Forms.MouseButtons.Left Then Exit Sub
	If Not biblioArrastre AndAlso (Math.Abs(e.X - biblioIni.X) > 6 OrElse Math.Abs(e.Y - biblioIni.Y) > 6) Then
		biblioArrastre = True
		lstBiblio.Cursor = System.Windows.Forms.Cursors.Hand
	End If
End Sub

Sub BiblioMouseUp(sender As Object, e As System.Windows.Forms.MouseEventArgs)
	lstBiblio.Cursor = System.Windows.Forms.Cursors.Default
	If biblioArrastre AndAlso biblioItem <> "" Then
		Dim pt As System.Drawing.Point = lienzo.PointToClient(lstBiblio.PointToScreen(e.Location))
		If lienzo.ClientRectangle.Contains(pt) Then
			Dim w() As Double = AMundo(pt.X, pt.Y)
			AgregarExtra(biblioItem, Math.Round(w(0) / 50) * 50, Math.Round(w(1) / 50) * 50)
		End If
	End If
	biblioArrastre = False
	biblioItem = ""
End Sub

Sub AgregarDesdeBiblioteca(sender As Object, e As EventArgs)
	If lstBiblio.SelectedItem Is Nothing Then Exit Sub
	AgregarExtra(CStr(lstBiblio.SelectedItem), Math.Round(vCx / 50) * 50, Math.Round(vCy / 50) * 50)
End Sub

' componentes genericos con medidas por defecto tomadas de la configuracion
Sub AgregarGenerico(sender As Object, e As EventArgs)
	Dim tipo As String = CStr(CType(sender, System.Windows.Forms.Control).Tag)
	Dim ex As New ExtraMaq
	ex.Tipo = tipo
	ex.X = Math.Round(vCx / 50) * 50 : ex.Y = Math.Round(vCy / 50) * 50
	Dim n As Integer = 1
	For Each o As ExtraMaq In extras
		If o.Tipo = tipo Then n += 1
	Next
	Select Case tipo
		Case "cinta"
			ex.Nombre = "Entrada " & (n + 2)
			ex.L = Math.Max(500, PMM("L_LargoCintaEntrada")) : ex.A = Math.Max(100, PMM("L_AnchoCinta")) : ex.H = Math.Max(100, PMM("L_AlturaCinta"))
			ex.Op1 = PBool("L_CajasEjemplo") : ex.Op2 = True
		Case "salida"
			ex.Nombre = "Salida " & n
			ex.L = 2000 : ex.A = Math.Max(100, PMM("L_AnchoCinta")) : ex.H = Math.Max(100, PMM("L_AlturaCinta"))
			ex.Op1 = PBool("L_CajasEjemplo")
		Case "rodillos"
			ex.Nombre = "Transportador " & n
			ex.L = Math.Max(300, PMM("L_LargoTramo")) : ex.A = If(PMM("L_AnchoLinea") > 0, PMM("L_AnchoLinea"), 1300) : ex.H = Math.Max(100, PMM("L_AlturaLinea"))
			ex.Op1 = True : ex.Op2 = False
		Case "pallet"
			ex.Nombre = "Pallet " & n
			ex.Op1 = True
		Case "bloque"
			ex.Nombre = "Bloque " & n
			ex.L = 1000 : ex.A = 1000 : ex.H = 1000
		Case "valla"
			ex.Nombre = "Valla " & n
			ex.L = 3000 : ex.A = 60 : ex.H = Math.Max(300, PMM("L_AlturaValla"))
		Case "robot"
			' robot adicional = copia del robot principal (con su base y gripper)
			ex.Tipo = "copia" : ex.Nombre = "Robot"
			ex.X = robX + Math.Max(2500, alcanceAct * 2) : ex.Y = robY
	End Select
	extras.Add(ex)
	GuardarEdicion()
	selGrupo = "Extra" & extras.Count
	Refrescar()
	ActualizarListaAgregadas()
	ActualizarPropiedades()
	lienzo.Invalidate()
End Sub

Sub AgregarExtra(nombre As String, x As Double, y As Double)
	Dim ex As New ExtraMaq
	ex.Nombre = nombre : ex.X = x : ex.Y = y
	extras.Add(ex)
	GuardarEdicion()
	Refrescar()
	selGrupo = "Extra" & extras.Count
	ActualizarListaAgregadas()
	ActualizarPropiedades()
	lienzo.Invalidate()
End Sub

Sub ActualizarListaAgregadas()
	If lstAgregadas Is Nothing Then Exit Sub
	cargandoLista = True
	lstAgregadas.Items.Clear()
	For i As Integer = 0 To extras.Count - 1
		lstAgregadas.Items.Add((i + 1) & ".  " & DescExtra(extras(i)))
	Next
	If selGrupo.StartsWith("Extra") Then
		Dim k As Integer = 0
		If Integer.TryParse(selGrupo.Substring(5), k) AndAlso k >= 1 AndAlso k <= extras.Count Then lstAgregadas.SelectedIndex = k - 1
	End If
	cargandoLista = False
End Sub

Sub AgregadaSeleccionada(sender As Object, e As EventArgs)
	If cargandoLista OrElse lstAgregadas.SelectedIndex < 0 Then Exit Sub
	selGrupo = "Extra" & (lstAgregadas.SelectedIndex + 1)
	ActualizarPropiedades()
	lienzo.Invalidate()
End Sub

Sub CambiarSeccion(sender As Object, e As EventArgs)
	Dim clave As String = CStr(CType(sender, System.Windows.Forms.Button).Tag)
	For Each kv As KeyValuePair(Of String, System.Windows.Forms.Panel) In secciones
		kv.Value.Visible = (kv.Key = clave)
	Next
	For Each b As System.Windows.Forms.Button In navBotones
		Dim activo As Boolean = (CStr(b.Tag) = clave)
		b.BackColor = If(activo, CAcento(), System.Drawing.Color.White)
		b.ForeColor = If(activo, System.Drawing.Color.White, CTexto())
		b.FlatAppearance.BorderSize = If(activo, 0, 1)
	Next
End Sub

Sub CambiarVista(sender As Object, e As EventArgs)
	vistaMosaico = (sender Is btnMosaico)
	btnPlanta.BackColor = If(vistaMosaico, System.Drawing.Color.White, CAcento())
	btnPlanta.ForeColor = If(vistaMosaico, CTexto(), System.Drawing.Color.White)
	btnMosaico.BackColor = If(vistaMosaico, CAcento(), System.Drawing.Color.White)
	btnMosaico.ForeColor = If(vistaMosaico, System.Drawing.Color.White, CTexto())
	lienzo.Invalidate()
End Sub

Sub CambiarCapas(sender As Object, e As EventArgs)
	Dim c As System.Windows.Forms.CheckBox = CType(sender, System.Windows.Forms.CheckBox)
	If c.Text = "Alcance" Then verAlcance = c.Checked
	If c.Text = "Cotas" Then verCotas = c.Checked
	lienzo.Invalidate()
End Sub

Sub AlCambiar(sender As Object, e As EventArgs)
	If TypeOf sender Is System.Windows.Forms.CheckBox Then EstiloInterruptor(CType(sender, System.Windows.Forms.CheckBox))
	If cargandoDlg Then Exit Sub
	Try
		If TypeOf sender Is System.Windows.Forms.ComboBox AndAlso CType(sender, System.Windows.Forms.ComboBox).Tag IsNot Nothing Then
			Dim co As System.Windows.Forms.ComboBox = CType(sender, System.Windows.Forms.ComboBox)
			Dim nom As String = CStr(co.SelectedItem)
			Dim rp As String = ""
			Select Case CStr(co.Tag)
				Case "@ROBOTS" : If ROBOTS.ContainsKey(nom) Then rp = ROBOTS(nom)
				Case "@BASES"
					If BASES.ContainsKey(nom) Then
						rp = BASES(nom)
					ElseIf MAQUINAS.ContainsKey(nom) Then
						rp = MAQUINAS(nom)
					End If
				Case Else : If MAQUINAS.ContainsKey(nom) Then rp = MAQUINAS(nom)
			End Select
			MostrarMiniatura(rp, nom)
			ultimoPrev = "-"
		End If
	Catch
	End Try
	Try
		If ctl.ContainsKey("L_PresetCaja") AndAlso sender Is ctl("L_PresetCaja") Then AplicarPreset(CStr(CType(sender, System.Windows.Forms.ComboBox).SelectedItem), "L_Caja_L", "L_Caja_A", "L_Caja_H")
		If ctl.ContainsKey("L_PresetPallet") AndAlso sender Is ctl("L_PresetPallet") Then AplicarPreset(CStr(CType(sender, System.Windows.Forms.ComboBox).SelectedItem), "L_Pallet_L", "L_Pallet_A", "L_Pallet_H")
	Catch
	End Try
	LeerControles()
	Refrescar()
End Sub

Sub AplicarPreset(txt As String, kL As String, kA As String, kH As String)
	If txt Is Nothing Then Exit Sub
	Dim m As System.Text.RegularExpressions.Match = System.Text.RegularExpressions.Regex.Match(txt, "(\d+)x(\d+)x(\d+)")
	If Not m.Success Then Exit Sub
	cargandoDlg = True
	CType(ctl(kL), System.Windows.Forms.NumericUpDown).Value = CDec(m.Groups(1).Value)
	CType(ctl(kA), System.Windows.Forms.NumericUpDown).Value = CDec(m.Groups(2).Value)
	CType(ctl(kH), System.Windows.Forms.NumericUpDown).Value = CDec(m.Groups(3).Value)
	cargandoDlg = False
End Sub

Sub LeerControles()
	For Each kv As KeyValuePair(Of String, System.Windows.Forms.Control) In ctl
		Try
			Dim u As String = ctlUnidad(kv.Key)
			If TypeOf kv.Value Is System.Windows.Forms.CheckBox Then
				cfg(kv.Key) = CType(kv.Value, System.Windows.Forms.CheckBox).Checked
			ElseIf TypeOf kv.Value Is System.Windows.Forms.ComboBox Then
				Dim s As String = CStr(CType(kv.Value, System.Windows.Forms.ComboBox).SelectedItem)
				If s Is Nothing Then Continue For
				If u = "txt" Then
					cfg(kv.Key) = s
				Else
					cfg(kv.Key) = CDbl(s)
				End If
			Else
				cfg(kv.Key) = CDbl(CType(kv.Value, System.Windows.Forms.NumericUpDown).Value)
			End If
		Catch
		End Try
	Next
End Sub

Sub Refrescar()
	Try
		CalcularPlan()
	Catch ex As Exception
		avisos.Add("Error en vista previa: " & ex.Message)
	End Try
	If lblSub IsNot Nothing Then lblSub.Text = PTxt("L_Robot") & "   |   " & If(stats.Count > 2, stats(2), "") & "   |   Biblioteca: " & Bib("RAIZ")
	If lblEstado IsNot Nothing Then
		lblEstado.Text = If(avisos.Count = 0, "Todo OK", avisos.Count & " aviso(s): " & avisos(0)) & "      |      Rueda: zoom  -  arrastrar el fondo: mover la vista  -  flechas: mover  -  R: girar  -  Supr: quitar  -  Ctrl+C / Ctrl+V / Ctrl+D: copiar, pegar, duplicar  -  F: encuadrar"
		lblEstado.ForeColor = If(avisos.Count = 0, System.Drawing.Color.FromArgb(22, 130, 80), System.Drawing.Color.FromArgb(200, 40, 40))
	End If
	If lienzo IsNot Nothing Then lienzo.Invalidate()
End Sub

' =====================================================================
'  LIENZO: transformaciones, mouse y teclado
' =====================================================================
Function SX(x As Double) As Single
	Return CSng(lienzo.Width / 2 + (x - vCx) * vSc)
End Function
Function SY(y As Double) As Single
	Return CSng(lienzo.Height / 2 - (y - vCy) * vSc)
End Function
Function AMundo(px As Integer, py As Integer) As Double()
	Return New Double() {vCx + (px - lienzo.Width / 2) / vSc, vCy - (py - lienzo.Height / 2) / vSc}
End Function

Sub Encuadrar()
	If lienzo Is Nothing OrElse lienzo.Width < 50 Then Exit Sub
	Dim x1 As Double = robX - alcanceAct, x2 As Double = robX + alcanceAct, y1 As Double = robY - alcanceAct, y2 As Double = robY + alcanceAct
	For Each it As ItemPlan In plan
		x1 = Math.Min(x1, it.Cx - it.W / 2) : x2 = Math.Max(x2, it.Cx + it.W / 2)
		y1 = Math.Min(y1, it.Cy - it.D / 2) : y2 = Math.Max(y2, it.Cy + it.D / 2)
	Next
	x1 -= 700 : x2 += 700 : y1 -= 700 : y2 += 700
	vSc = Math.Min(lienzo.Width / (x2 - x1), lienzo.Height / (y2 - y1))
	vCx = (x1 + x2) / 2 : vCy = (y1 + y2) / 2
	vistaIni = True
	lienzo.Invalidate()
End Sub

Function GrupoEn(px As Integer, py As Integer) As String
	Dim w() As Double = AMundo(px, py)
	Dim tol As Double = 5 / vSc
	For i As Integer = plan.Count - 1 To 0 Step -1
		Dim it As ItemPlan = plan(i)
		If it.Tipo = "zona" OrElse it.Tipo = "pick" OrElse it.Tipo = "sep" Then Continue For
		If it.Tipo = "robot" Then
			If Math.Sqrt((w(0) - it.Cx) ^ 2 + (w(1) - it.Cy) ^ 2) < 450 Then Return GrupoDe(it)
			Continue For
		End If
		Dim ex As Double = tol + If(it.Tipo = "valla" OrElse it.Tipo = "puerta", 120, 0)
		If w(0) >= it.Cx - it.W / 2 - ex AndAlso w(0) <= it.Cx + it.W / 2 + ex AndAlso w(1) >= it.Cy - it.D / 2 - ex AndAlso w(1) <= it.Cy + it.D / 2 + ex Then Return GrupoDe(it)
	Next
	Return ""
End Function

' estado editable de un grupo: {dx, dy, giro, absoluto}
Function EstadoGrupo(g As String) As Double()
	If g.StartsWith("Extra") Then
		Dim k As Integer = IndiceExtra(g)
		If k >= 0 Then Return New Double() {extras(k).X, extras(k).Y, extras(k).Rot, 1}
	End If
	If g = "Tablero" Then
		If offs.ContainsKey(g) AndAlso offs(g)(3) > 0.5 Then Return CType(offs(g).Clone(), Double())
		For Each it As ItemPlan In plan
			If it.Nombre = "Tablero" Then Return New Double() {it.Cx, it.Cy, If(offs.ContainsKey(g), offs(g)(2), 0), 1}
		Next
	End If
	If offs.ContainsKey(g) Then Return CType(offs(g).Clone(), Double())
	Return New Double() {0, 0, 0, 0}
End Function

Function DescExtra(ex As ExtraMaq) As String
	If ex Is Nothing Then Return ""
	Select Case ex.Tipo
		Case "copia" : Return "Copia de " & NombreGrupo(ex.Nombre)
		Case "cinta" : Return "Cinta de entrada: " & ex.Nombre
		Case "salida" : Return "Cinta de salida: " & ex.Nombre
		Case "rodillos" : Return "Transportador: " & ex.Nombre
		Case "pallet" : Return "Pallet: " & ex.Nombre
		Case "bloque" : Return "Bloque: " & ex.Nombre
		Case "valla" : Return "Tramo de vallado: " & ex.Nombre
	End Select
	Return ex.Nombre
End Function

Function IndiceExtra(g As String) As Integer
	Dim k As Integer
	If g.StartsWith("Extra") AndAlso Integer.TryParse(g.Substring(5), k) AndAlso k >= 1 AndAlso k <= extras.Count Then Return k - 1
	Return -1
End Function

Sub FijarEstado(g As String, v() As Double)
	If g.StartsWith("Extra") Then
		Dim k As Integer = IndiceExtra(g)
		If k >= 0 Then
			extras(k).X = v(0) : extras(k).Y = v(1) : extras(k).Rot = v(2)
		End If
	Else
		offs(g) = v
	End If
	GuardarEdicion()
End Sub

Sub MoverGrupo(g As String, base() As Double, ddx As Double, ddy As Double)
	If g = "" Then Exit Sub
	If g = "Valla0" OrElse g = "Valla1" Then ddx = 0
	If g = "Valla2" OrElse g = "Valla3" Then ddy = 0
	FijarEstado(g, New Double() {base(0) + ddx, base(1) + ddy, base(2), base(3)})
End Sub

Function CentroGrupo(g As String) As Double()
	Dim x1 As Double = 1.0E+30, y1 As Double = 1.0E+30, x2 As Double = -1.0E+30, y2 As Double = -1.0E+30
	For Each it As ItemPlan In plan
		If GrupoDe(it) <> g OrElse it.Tipo = "pick" OrElse it.Tipo = "zona" OrElse it.Tipo = "caja" Then Continue For
		If it.Tipo = "robot" Then Return New Double() {it.Cx, it.Cy}
		x1 = Math.Min(x1, it.Cx - it.W / 2) : x2 = Math.Max(x2, it.Cx + it.W / 2)
		y1 = Math.Min(y1, it.Cy - it.D / 2) : y2 = Math.Max(y2, it.Cy + it.D / 2)
	Next
	If x1 > x2 Then Return Nothing
	Return New Double() {(x1 + x2) / 2, (y1 + y2) / 2}
End Function

Sub LienzoEntrar(sender As Object, e As EventArgs)
	Dim f As System.Windows.Forms.Form = lienzo.FindForm()
	If f IsNot Nothing AndAlso f Is System.Windows.Forms.Form.ActiveForm Then lienzo.Focus()
End Sub

Sub LienzoMouseDown(sender As Object, e As System.Windows.Forms.MouseEventArgs)
	lienzo.Focus()
	If vistaMosaico Then Exit Sub
	If e.Button = System.Windows.Forms.MouseButtons.Middle Then
		modoArrastre = 2 : panIni = e.Location : panC = New Double() {vCx, vCy}
		Exit Sub
	End If
	' clic en el titulo del resumen: abrir / cerrar
	If e.Button = System.Windows.Forms.MouseButtons.Left AndAlso rectResumen.Contains(e.X, e.Y) Then
		resumenAbierto = Not resumenAbierto
		lienzo.Invalidate()
		Exit Sub
	End If
	Dim g As String = GrupoEn(e.X, e.Y)
	selGrupo = g
	ActualizarPropiedades()
	ActualizarListaAgregadas()
	If e.Button = System.Windows.Forms.MouseButtons.Right Then
		lienzo.Invalidate()
		If g <> "" Then menuPlan.Show(lienzo, e.Location)
		Exit Sub
	End If
	If g = "" Then
		modoArrastre = 2 : panIni = e.Location : panC = New Double() {vCx, vCy}
		lienzo.Cursor = System.Windows.Forms.Cursors.Hand
	Else
		modoArrastre = 1
		dragIni = AMundo(e.X, e.Y)
		dragOrig = EstadoGrupo(g)
	End If
	lienzo.Invalidate()
End Sub

Sub LienzoMouseMove(sender As Object, e As System.Windows.Forms.MouseEventArgs)
	If vistaMosaico Then Exit Sub
	' si se perdio el "soltar" del mouse, se termina el arrastre
	If modoArrastre <> 0 AndAlso e.Button = System.Windows.Forms.MouseButtons.None Then
		modoArrastre = 0
		lienzo.Capture = False
	End If
	If modoArrastre = 2 Then
		vCx = panC(0) - (e.X - panIni.X) / vSc
		vCy = panC(1) + (e.Y - panIni.Y) / vSc
		lienzo.Invalidate()
		Exit Sub
	End If
	If modoArrastre = 1 Then
		Dim w() As Double = AMundo(e.X, e.Y)
		Dim paso As Double = If((System.Windows.Forms.Control.ModifierKeys And System.Windows.Forms.Keys.Shift) = System.Windows.Forms.Keys.Shift, 10, 50)
		Dim ddx As Double = Math.Round((w(0) - dragIni(0)) / paso) * paso
		Dim ddy As Double = Math.Round((w(1) - dragIni(1)) / paso) * paso
		MoverGrupo(selGrupo, dragOrig, ddx, ddy)
		Refrescar()
		ActualizarPropiedades()
		Exit Sub
	End If
	If rectResumen.Contains(e.X, e.Y) Then
		lienzo.Cursor = System.Windows.Forms.Cursors.Hand
		hoverGrupo = ""
		Exit Sub
	End If
	Dim h As String = GrupoEn(e.X, e.Y)
	If lienzo.Cursor Is System.Windows.Forms.Cursors.Hand AndAlso modoArrastre = 0 Then lienzo.Cursor = If(h <> "", System.Windows.Forms.Cursors.SizeAll, System.Windows.Forms.Cursors.Default)
	If h <> hoverGrupo Then
		hoverGrupo = h
		lienzo.Cursor = If(h <> "", System.Windows.Forms.Cursors.SizeAll, System.Windows.Forms.Cursors.Default)
		lienzo.Invalidate()
	End If
End Sub

Sub LienzoMouseUp(sender As Object, e As System.Windows.Forms.MouseEventArgs)
	modoArrastre = 0
	lienzo.Capture = False
	lienzo.Cursor = If(hoverGrupo <> "", System.Windows.Forms.Cursors.SizeAll, System.Windows.Forms.Cursors.Default)
	ActualizarPropiedades()
End Sub

Sub LienzoRueda(sender As Object, e As System.Windows.Forms.MouseEventArgs)
	If vistaMosaico Then Exit Sub
	Dim w() As Double = AMundo(e.X, e.Y)
	Dim fz As Double = If(e.Delta > 0, 1.15, 1 / 1.15)
	vSc = Math.Max(0.005, Math.Min(5, vSc * fz))
	vCx = w(0) - (e.X - lienzo.Width / 2) / vSc
	vCy = w(1) + (e.Y - lienzo.Height / 2) / vSc
	lienzo.Invalidate()
End Sub

Sub LienzoTecla(sender As Object, e As System.Windows.Forms.KeyEventArgs)
	If e.Control Then
		Select Case e.KeyCode
			Case System.Windows.Forms.Keys.C : Accion("Copiar")
			Case System.Windows.Forms.Keys.X : Accion("Cortar")
			Case System.Windows.Forms.Keys.V : Accion("Pegar")
			Case System.Windows.Forms.Keys.D : Accion("Duplicar")
		End Select
		e.Handled = True
		Exit Sub
	End If
	Dim paso As Double = If(e.Shift, 10, 50)
	Select Case e.KeyCode
		Case System.Windows.Forms.Keys.Left : Empujar(-paso, 0)
		Case System.Windows.Forms.Keys.Right : Empujar(paso, 0)
		Case System.Windows.Forms.Keys.Up : Empujar(0, paso)
		Case System.Windows.Forms.Keys.Down : Empujar(0, -paso)
		Case System.Windows.Forms.Keys.R : Accion(If(e.Shift, "Girar -90", "Girar +90"))
		Case System.Windows.Forms.Keys.Delete : Accion("Quitar")
		Case System.Windows.Forms.Keys.F : Encuadrar()
		Case System.Windows.Forms.Keys.Escape
			selGrupo = ""
			ActualizarPropiedades()
			lienzo.Invalidate()
	End Select
	e.Handled = True
End Sub

Sub Empujar(dx As Double, dy As Double)
	If selGrupo = "" Then Exit Sub
	MoverGrupo(selGrupo, EstadoGrupo(selGrupo), dx, dy)
	Refrescar()
	ActualizarPropiedades()
End Sub

Sub LienzoDragEnter(sender As Object, e As System.Windows.Forms.DragEventArgs)
	If e.Data.GetDataPresent(System.Windows.Forms.DataFormats.Text) Then e.Effect = System.Windows.Forms.DragDropEffects.Copy
End Sub

Sub LienzoDragDrop(sender As Object, e As System.Windows.Forms.DragEventArgs)
	Dim nombre As String = CStr(e.Data.GetData(System.Windows.Forms.DataFormats.Text))
	If nombre Is Nothing OrElse nombre = "" Then Exit Sub
	Dim pt As System.Drawing.Point = lienzo.PointToClient(New System.Drawing.Point(e.X, e.Y))
	Dim w() As Double = AMundo(pt.X, pt.Y)
	AgregarExtra(nombre, Math.Round(w(0) / 50) * 50, Math.Round(w(1) / 50) * 50)
End Sub

Sub BotonEdicion(sender As Object, e As EventArgs)
	Dim txt As String = ""
	If TypeOf sender Is System.Windows.Forms.Button Then txt = CType(sender, System.Windows.Forms.Button).Text
	If TypeOf sender Is System.Windows.Forms.ToolStripItem Then txt = CType(sender, System.Windows.Forms.ToolStripItem).Text
	Accion(txt)
End Sub

Sub Accion(txt As String)
	Dim g As String = selGrupo
	Select Case txt
		Case "Encuadrar"
			Encuadrar()
			Exit Sub
		Case "Zoom +", "Zoom -"
			vSc = Math.Max(0.005, Math.Min(5, vSc * If(txt = "Zoom +", 1.25, 0.8)))
			lienzo.Invalidate()
			Exit Sub
		Case "Todo auto"
			offs.Clear()
		Case "Posicion auto"
			If g.StartsWith("Extra") Then Exit Sub
			If g <> "" AndAlso offs.ContainsKey(g) Then offs.Remove(g)
		Case "Girar -90", "Girar +90"
			If g = "" OrElse g.StartsWith("Valla") Then Exit Sub
			Dim o() As Double = EstadoGrupo(g)
			o(2) = (((o(2) + If(txt = "Girar +90", 90, -90)) Mod 360) + 360) Mod 360
			FijarEstado(g, o)
		Case "Copiar", "Cortar"
			If g = "" Then Exit Sub
			Dim k0 As Integer = IndiceExtra(g)
			If k0 >= 0 Then
				portaExtra = extras(k0).Copia()
			Else
				Dim c0() As Double = CentroGrupo(g)
				If c0 Is Nothing Then Exit Sub
				portaExtra = New ExtraMaq
				portaExtra.Tipo = "copia" : portaExtra.Nombre = g
				portaExtra.X = Math.Round(c0(0)) : portaExtra.Y = Math.Round(c0(1))
			End If
			If lblEstado IsNot Nothing Then lblEstado.Text = "Copiado: " & DescExtra(portaExtra) & "   (Ctrl+V o Pegar para ponerlo en el plano)"
			If txt = "Copiar" Then Exit Sub
			Accion("Quitar")
			Exit Sub
		Case "Pegar", "Duplicar"
			If txt = "Duplicar" Then
				If g = "" Then Exit Sub
				Accion("Copiar")
			End If
			If portaExtra Is Nothing Then
				If lblEstado IsNot Nothing Then lblEstado.Text = "Primero copia algo (clic en un equipo y Copiar / Ctrl+C)"
				Exit Sub
			End If
			Dim nx As ExtraMaq = portaExtra.Copia()
			Dim pt As System.Drawing.Point = lienzo.PointToClient(System.Windows.Forms.Cursor.Position)
			If txt = "Pegar" AndAlso lienzo.ClientRectangle.Contains(pt) Then
				Dim w() As Double = AMundo(pt.X, pt.Y)
				nx.X = Math.Round(w(0) / 50) * 50 : nx.Y = Math.Round(w(1) / 50) * 50
			Else
				nx.X = portaExtra.X + 1000 : nx.Y = portaExtra.Y - 1000
			End If
			portaExtra.X = nx.X : portaExtra.Y = nx.Y
			extras.Add(nx)
			g = "Extra" & extras.Count
		Case "Restaurar quitados"
			ocultos.Clear()
		Case "Quitar"
			If g = "" Then Exit Sub
			If g.StartsWith("Extra") Then
				Dim k As Integer = IndiceExtra(g)
				If k >= 0 Then extras.RemoveAt(k)
				g = ""
			Else
				Dim p As String = ""
				Dim v As String = ""
				Select Case g
					Case "MesaCarton" : p = "L_MesaCarton"
					Case "Tablero" : p = "L_Tablero"
					Case "Envolvedora" : p = "L_Envolvedora"
					Case "Entrada2" : p = "L_Entradas" : v = "1"
				End Select
				If p = "" OrElse Not ctl.ContainsKey(p) Then
					' cualquier otro grupo se oculta (vuelve con "Restaurar quitados")
					ocultos.Add(g)
				Else
					cargandoDlg = True
					If TypeOf ctl(p) Is System.Windows.Forms.CheckBox Then
						CType(ctl(p), System.Windows.Forms.CheckBox).Checked = False
					Else
						CType(ctl(p), System.Windows.Forms.ComboBox).SelectedItem = v
					End If
					cargandoDlg = False
					LeerControles()
				End If
				g = ""
			End If
		Case Else
			Exit Sub
	End Select
	GuardarEdicion()
	selGrupo = g
	Refrescar()
	ActualizarListaAgregadas()
	ActualizarPropiedades()
End Sub

Private ultimoPrev As String = "-"
Sub ActualizarPropiedades()
	If propNombre Is Nothing Then Exit Sub
	cargandoProp = True
	Dim g As String = selGrupo
	Dim activo As Boolean = (g <> "")
	propX.Enabled = activo : propY.Enabled = activo : propGiro.Enabled = activo AndAlso Not g.StartsWith("Valla")
	If Not activo Then
		propNombre.Text = "Nada seleccionado (clic en un equipo del plano)"
		propNombre.ForeColor = CSuave()
	Else
		propNombre.ForeColor = CTexto()
		Dim nom As String = NombreGrupo(g)
		Dim k As Integer = IndiceExtra(g)
		If k >= 0 Then nom = (k + 1) & ". " & DescExtra(extras(k))
		propNombre.Text = nom
		Dim c() As Double = CentroGrupo(g)
		If c IsNot Nothing Then
			propX.Value = CDec(Math.Max(-200000, Math.Min(200000, Math.Round(c(0)))))
			propY.Value = CDec(Math.Max(-200000, Math.Min(200000, Math.Round(c(1)))))
		End If
		Dim giro As Integer = CInt(((Math.Round(EstadoGrupo(g)(2) / 90) Mod 4) + 4) Mod 4) * 90
		propGiro.SelectedItem = giro.ToString()
	End If
	LlenarMedidas(IndiceExtra(g))
	cargandoProp = False
	If g <> ultimoPrev Then
		ultimoPrev = g
		If g = "" Then
			MostrarMiniatura("", "")
		Else
			Dim tit As String = ""
			Dim rp As String = RutaDeGrupo(g, tit)
			MostrarMiniatura(rp, tit)
		End If
	End If
End Sub

' medidas / opciones del elemento agregado seleccionado
Sub LlenarMedidas(k As Integer)
	If tablaMed Is Nothing Then Exit Sub
	If k < 0 Then
		tablaMed.Visible = False
		Exit Sub
	End If
	Dim ex As ExtraMaq = extras(k)
	tablaMed.Visible = True
	Dim usaMed As Boolean = (ex.Tipo = "cinta" OrElse ex.Tipo = "salida" OrElse ex.Tipo = "rodillos" OrElse ex.Tipo = "bloque" OrElse ex.Tipo = "valla")
	Dim vals() As Double = {ex.L, ex.A, ex.H, ex.Z}
	For i As Integer = 0 To 3
		propMed(i).Enabled = usaMed OrElse i = 3
		If ex.Tipo = "valla" AndAlso i = 1 Then propMed(i).Enabled = False
		propMed(i).Value = CDec(Math.Max(CDbl(propMed(i).Minimum), Math.Min(CDbl(propMed(i).Maximum), Math.Round(vals(i)))))
	Next
	Dim t1 As String = "", t2 As String = ""
	Select Case ex.Tipo
		Case "cinta" : t1 = "Con cajas" : t2 = "Con tope"
		Case "salida" : t1 = "Con cajas"
		Case "rodillos" : t1 = "Con pallet" : t2 = "Pallet cargado"
		Case "pallet" : t1 = "Pallet cargado"
		Case "valla" : t1 = "Con puerta"
	End Select
	propOp1.Text = t1 : propOp1.Visible = (t1 <> "") : propOp1.Checked = ex.Op1
	propOp2.Text = t2 : propOp2.Visible = (t2 <> "") : propOp2.Checked = ex.Op2
End Sub

Sub MedCambio(sender As Object, e As EventArgs)
	If cargandoProp Then Exit Sub
	Dim k As Integer = IndiceExtra(selGrupo)
	If k < 0 Then Exit Sub
	Dim ex As ExtraMaq = extras(k)
	ex.L = CDbl(propMed(0).Value) : ex.A = CDbl(propMed(1).Value) : ex.H = CDbl(propMed(2).Value) : ex.Z = CDbl(propMed(3).Value)
	ex.Op1 = propOp1.Checked : ex.Op2 = propOp2.Checked
	GuardarEdicion()
	Refrescar()
End Sub

Sub PropCambio(sender As Object, e As EventArgs)
	If cargandoProp OrElse selGrupo = "" Then Exit Sub
	Dim g As String = selGrupo
	If sender Is propGiro Then
		Dim o() As Double = EstadoGrupo(g)
		o(2) = CDbl(CStr(propGiro.SelectedItem))
		FijarEstado(g, o)
	Else
		Dim c() As Double = CentroGrupo(g)
		If c Is Nothing Then Exit Sub
		MoverGrupo(g, EstadoGrupo(g), CDbl(propX.Value) - c(0), CDbl(propY.Value) - c(1))
	End If
	Refrescar()
End Sub

' =====================================================================
'  DIBUJO DEL LIENZO
' =====================================================================
Function Redondeado(x As Single, y As Single, w As Single, h As Single, r As Single) As System.Drawing.Drawing2D.GraphicsPath
	Dim gp As New System.Drawing.Drawing2D.GraphicsPath
	Dim d As Single = Math.Max(1, Math.Min(r * 2, Math.Min(w, h)))
	gp.AddArc(x, y, d, d, 180, 90)
	gp.AddArc(x + w - d, y, d, d, 270, 90)
	gp.AddArc(x + w - d, y + h - d, d, d, 0, 90)
	gp.AddArc(x, y + h - d, d, d, 90, 90)
	gp.CloseFigure()
	Return gp
End Function

Sub PintarLienzo(sender As Object, e As System.Windows.Forms.PaintEventArgs)
	Dim g As System.Drawing.Graphics = e.Graphics
	g.SmoothingMode = System.Drawing.Drawing2D.SmoothingMode.AntiAlias
	g.TextRenderingHint = System.Drawing.Text.TextRenderingHint.ClearTypeGridFit
	g.Clear(System.Drawing.Color.FromArgb(250, 251, 253))
	If vistaMosaico Then
		PintarMosaico(g)
	Else
		If Not vistaIni Then Encuadrar()
		PintarPlanta(g)
	End If
End Sub

Sub PintarPlanta(g As System.Drawing.Graphics)
	If plan Is Nothing OrElse plan.Count = 0 Then Exit Sub
	Dim W As Integer = lienzo.Width, H As Integer = lienzo.Height
	Dim fuente As New System.Drawing.Font("Segoe UI", 8)
	Dim fuenteB As New System.Drawing.Font("Segoe UI Semibold", 9)

	' cuadricula (1 m y 5 m)
	Dim w0() As Double = AMundo(0, H), w1() As Double = AMundo(W, 0)
	Dim paso As Double = If(vSc * 1000 < 14, 5000, 1000)
	Dim penG As New System.Drawing.Pen(System.Drawing.Color.FromArgb(234, 238, 244), 1)
	Dim penG5 As New System.Drawing.Pen(System.Drawing.Color.FromArgb(214, 221, 232), 1)
	Dim gx As Double = Math.Floor(w0(0) / paso) * paso
	While gx <= w1(0)
		g.DrawLine(If(Math.Abs(gx Mod 5000) < 1, penG5, penG), SX(gx), 0, SX(gx), H)
		gx += paso
	End While
	Dim gy As Double = Math.Floor(w0(1) / paso) * paso
	While gy <= w1(1)
		g.DrawLine(If(Math.Abs(gy Mod 5000) < 1, penG5, penG), 0, SY(gy), W, SY(gy))
		gy += paso
	End While

	' alcance del robot
	If verAlcance Then
		Dim ra As Single = CSng(alcanceAct * vSc)
		Dim colA As System.Drawing.Color = If(hayProblema, System.Drawing.Color.FromArgb(220, 50, 50), System.Drawing.Color.FromArgb(30, 150, 90))
		g.FillEllipse(New System.Drawing.SolidBrush(System.Drawing.Color.FromArgb(16, colA)), SX(robX) - ra, SY(robY) - ra, 2 * ra, 2 * ra)
		Dim penA As New System.Drawing.Pen(System.Drawing.Color.FromArgb(150, colA), 1.5F)
		penA.DashStyle = System.Drawing.Drawing2D.DashStyle.Dash
		g.DrawEllipse(penA, SX(robX) - ra, SY(robY) - ra, 2 * ra, 2 * ra)
		' robots agregados (copias)
		Dim penA2 As New System.Drawing.Pen(System.Drawing.Color.FromArgb(140, 90, 110, 160), 1.2F)
		penA2.DashStyle = System.Drawing.Drawing2D.DashStyle.Dash
		For Each it As ItemPlan In plan
			If it.Tipo = "robot" AndAlso it.Nombre <> "Robot" Then g.DrawEllipse(penA2, SX(it.Cx) - ra, SY(it.Cy) - ra, 2 * ra, 2 * ra)
		Next
	End If

	' piezas (sombra + relleno)
	Dim sombra As New System.Drawing.SolidBrush(System.Drawing.Color.FromArgb(28, 0, 0, 0))
	For pasada As Integer = 0 To 2
		For Each it As ItemPlan In plan
			If CapaDibujo(it) <> pasada Then Continue For
			If it.Tipo = "caja" AndAlso it.Capa > 0 Then Continue For
			Dim rx As Single = SX(it.Cx - it.W / 2), ry As Single = SY(it.Cy + it.D / 2)
			Dim rw As Single = CSng(it.W * vSc), rh As Single = CSng(it.D * vSc)
			Select Case it.Tipo
				Case "conv"
					g.FillRectangle(sombra, rx + 3, ry + 3, rw, rh)
					g.FillRectangle(New System.Drawing.SolidBrush(System.Drawing.Color.FromArgb(62, 104, 138)), rx, ry, rw, rh)
					Dim penR As New System.Drawing.Pen(System.Drawing.Color.FromArgb(140, 178, 204), 1)
					Dim largoX As Boolean = it.W >= it.D
					If 125 * vSc > 3 Then
						Dim q As Double = 125
						While q < Math.Max(it.W, it.D)
							If largoX Then
								g.DrawLine(penR, SX(it.Cx - it.W / 2 + q), ry + 2, SX(it.Cx - it.W / 2 + q), ry + rh - 2)
							Else
								g.DrawLine(penR, rx + 2, SY(it.Cy - it.D / 2 + q), rx + rw - 2, SY(it.Cy - it.D / 2 + q))
							End If
							q += 125
						End While
					End If
				Case "cinta"
					g.FillRectangle(sombra, rx + 3, ry + 3, rw, rh)
					g.FillRectangle(New System.Drawing.SolidBrush(System.Drawing.Color.FromArgb(52, 56, 64)), rx, ry, rw, rh)
				Case "pallet"
					g.FillRectangle(New System.Drawing.SolidBrush(System.Drawing.Color.FromArgb(158, 104, 60)), rx, ry, rw, rh)
				Case "caja"
					g.FillRectangle(New System.Drawing.SolidBrush(System.Drawing.Color.FromArgb(222, 190, 138)), rx, ry, rw, rh)
					g.DrawRectangle(New System.Drawing.Pen(System.Drawing.Color.FromArgb(140, 105, 60), 1), rx, ry, rw, rh)
				Case "tope"
					g.FillRectangle(System.Drawing.Brushes.Firebrick, rx, ry, Math.Max(rw, 2), Math.Max(rh, 2))
				Case "base"
					g.FillRectangle(sombra, rx + 3, ry + 3, rw, rh)
					g.FillRectangle(New System.Drawing.SolidBrush(System.Drawing.Color.FromArgb(40, 70, 150)), rx, ry, rw, rh)
				Case "valla", "puerta"
					Dim col As System.Drawing.Color = If(it.Tipo = "puerta", System.Drawing.Color.FromArgb(240, 140, 20), System.Drawing.Color.FromArgb(214, 186, 0))
					Dim penV As New System.Drawing.Pen(col, If(it.Tipo = "puerta", 6, 4))
					If it.W >= it.D Then
						g.DrawLine(penV, SX(it.Cx - it.W / 2), SY(it.Cy), SX(it.Cx + it.W / 2), SY(it.Cy))
					Else
						g.DrawLine(penV, SX(it.Cx), SY(it.Cy - it.D / 2), SX(it.Cx), SY(it.Cy + it.D / 2))
					End If
				Case "maquina"
					If it.FaltaModelo Then
						Dim penF As New System.Drawing.Pen(System.Drawing.Color.Red, 2)
						penF.DashStyle = System.Drawing.Drawing2D.DashStyle.Dash
						g.DrawRectangle(penF, rx, ry, rw, rh)
					Else
						g.FillRectangle(sombra, rx + 4, ry + 4, rw, rh)
						Dim esExtra As Boolean = it.Nombre.StartsWith("Extra")
						g.FillRectangle(New System.Drawing.SolidBrush(If(esExtra, System.Drawing.Color.FromArgb(225, 235, 250), System.Drawing.Color.FromArgb(232, 235, 240))), rx, ry, rw, rh)
						g.DrawRectangle(New System.Drawing.Pen(If(esExtra, System.Drawing.Color.FromArgb(90, 130, 200), System.Drawing.Color.FromArgb(120, 128, 140)), 1.5F), rx, ry, rw, rh)
					End If
				Case "gripper"
					g.FillRectangle(New System.Drawing.SolidBrush(System.Drawing.Color.FromArgb(120, 60, 110, 170)), rx, ry, rw, rh)
			End Select
		Next
	Next

	' robot con direccion del brazo
	For Each it As ItemPlan In plan
		If it.Tipo <> "robot" Then Continue For
		Dim cxr As Single = SX(it.Cx), cyr As Single = SY(it.Cy)
		Dim rr As Single = Math.Max(6, CSng(300 * vSc))
		Dim ang As Double = robAng * Math.PI / 180
		Dim penB As New System.Drawing.Pen(System.Drawing.Color.FromArgb(200, 35, 35), Math.Max(3, CSng(140 * vSc)))
		penB.EndCap = System.Drawing.Drawing2D.LineCap.Round
		g.DrawLine(penB, cxr, cyr, cxr + CSng(Math.Cos(ang) * alcanceAct * 0.45 * vSc), cyr - CSng(Math.Sin(ang) * alcanceAct * 0.45 * vSc))
		g.FillEllipse(New System.Drawing.SolidBrush(System.Drawing.Color.FromArgb(40, 0, 0, 0)), cxr - rr + 3, cyr - rr + 3, 2 * rr, 2 * rr)
		g.FillEllipse(New System.Drawing.SolidBrush(System.Drawing.Color.FromArgb(215, 38, 38)), cxr - rr, cyr - rr, 2 * rr, 2 * rr)
		g.DrawEllipse(New System.Drawing.Pen(System.Drawing.Color.White, 2), cxr - rr * 0.45F, cyr - rr * 0.45F, rr * 0.9F, rr * 0.9F)
		Chip(g, it.Etiqueta & If(it.FaltaModelo, " (FALTA MODELO)", ""), cxr + rr + 6, cyr - rr - 10, fuenteB, If(it.FaltaModelo, System.Drawing.Color.Red, System.Drawing.Color.FromArgb(170, 30, 30)))
	Next

	' flechas de las cintas
	For Each it As ItemPlan In plan
		If it.Tipo <> "cinta" Then Continue For
		Dim penF As New System.Drawing.Pen(System.Drawing.Color.FromArgb(230, 255, 255, 255), 2)
		penF.CustomEndCap = New System.Drawing.Drawing2D.AdjustableArrowCap(4, 4)
		If it.W >= it.D Then
			Dim dirX As Double = If(it.Cx > robX, -1, 1) * If(it.Etiqueta.StartsWith("Salida"), -1, 1)
			g.DrawLine(penF, SX(it.Cx - dirX * it.W / 3), SY(it.Cy), SX(it.Cx + dirX * it.W / 3), SY(it.Cy))
		Else
			Dim dirY As Double = If(it.Cy > robY, -1, 1) * If(it.Etiqueta.StartsWith("Salida"), -1, 1)
			g.DrawLine(penF, SX(it.Cx), SY(it.Cy - dirY * it.D / 3), SX(it.Cx), SY(it.Cy + dirY * it.D / 3))
		End If
	Next

	' resaltado (hover y seleccion)
	ResaltarGrupo(g, hoverGrupo, System.Drawing.Color.FromArgb(120, 37, 99, 235), False)
	ResaltarGrupo(g, selGrupo, CAcento(), True)

	' etiquetas de maquinas
	For Each it As ItemPlan In plan
		If it.Tipo <> "maquina" Then Continue For
		Dim txt As String = If(it.FaltaModelo, "FALTA: " & it.Etiqueta, it.Etiqueta)
		Chip(g, txt, SX(it.Cx) - g.MeasureString(txt, fuente).Width / 2 - 4, SY(it.Cy + it.D / 2) + 4, fuente, If(it.FaltaModelo, System.Drawing.Color.Red, CTexto()))
	Next

	' cotas del vallado
	If verCotas AndAlso rectV IsNot Nothing Then
		Dim penC As New System.Drawing.Pen(System.Drawing.Color.FromArgb(120, 130, 145), 1)
		penC.StartCap = System.Drawing.Drawing2D.LineCap.ArrowAnchor
		penC.EndCap = System.Drawing.Drawing2D.LineCap.ArrowAnchor
		Dim yC As Single = SY(rectV(1)) + 26
		g.DrawLine(penC, SX(rectV(0)), yC, SX(rectV(3)), yC)
		Dim t1 As String = String.Format("{0:0.00} m", (rectV(3) - rectV(0)) / 1000)
		Chip(g, t1, (SX(rectV(0)) + SX(rectV(3))) / 2 - g.MeasureString(t1, fuente).Width / 2, yC - 9, fuente, CTexto())
		Dim xC As Single = SX(rectV(3)) + 26
		g.DrawLine(penC, xC, SY(rectV(1)), xC, SY(rectV(4)))
		Dim t2 As String = String.Format("{0:0.00} m", (rectV(4) - rectV(1)) / 1000)
		Chip(g, t2, xC - 4, (SY(rectV(1)) + SY(rectV(4))) / 2 - 9, fuente, CTexto())
	End If

	' tarjeta de resumen (clic en el titulo para abrir/cerrar)
	Dim lineas As New List(Of String)(stats)
	Dim flecha As String = If(resumenAbierto, ChrW(&H25BE), ChrW(&H25B8))
	Dim titRes As String = flecha & "  Resumen de la celda" & If(resumenAbierto, "", If(avisos.Count > 0, "   (" & avisos.Count & " aviso" & If(avisos.Count > 1, "s", "") & ")", "   (todo OK)"))
	Dim ancho As Single = g.MeasureString(titRes, fuenteB).Width + 30
	Dim alto As Single = 30
	If resumenAbierto Then
		alto = 34 + lineas.Count * 15 + avisos.Count * 16
		ancho = Math.Max(ancho, 420)
		For Each s As String In lineas
			ancho = Math.Max(ancho, g.MeasureString(s, fuente).Width + 30)
		Next
		For Each s As String In avisos
			ancho = Math.Max(ancho, g.MeasureString("! " & s, fuente).Width + 30)
		Next
	End If
	rectResumen = New System.Drawing.RectangleF(14, 14, ancho, 30)
	Dim tarjeta As System.Drawing.Drawing2D.GraphicsPath = Redondeado(14, 14, ancho, alto, 10)
	g.TranslateTransform(2, 3)
	g.FillPath(New System.Drawing.SolidBrush(System.Drawing.Color.FromArgb(25, 0, 0, 0)), tarjeta)
	g.ResetTransform()
	g.FillPath(New System.Drawing.SolidBrush(System.Drawing.Color.FromArgb(245, 255, 255, 255)), tarjeta)
	g.DrawPath(New System.Drawing.Pen(If(Not resumenAbierto AndAlso avisos.Count > 0, System.Drawing.Color.FromArgb(230, 150, 150), System.Drawing.Color.FromArgb(222, 227, 235))), tarjeta)
	Dim colTit As System.Drawing.Color = If(Not resumenAbierto AndAlso avisos.Count > 0, System.Drawing.Color.FromArgb(200, 40, 40), CTexto())
	g.DrawString(titRes, fuenteB, New System.Drawing.SolidBrush(colTit), 24, 20)
	If resumenAbierto Then
		Dim yt As Single = 44
		For Each s As String In lineas
			g.DrawString(s, fuente, New System.Drawing.SolidBrush(CSuave()), 26, yt)
			yt += 15
		Next
		For Each s As String In avisos
			g.DrawString("! " & s, fuente, New System.Drawing.SolidBrush(System.Drawing.Color.FromArgb(200, 40, 40)), 26, yt)
			yt += 16
		Next
	End If

	' escala
	Dim lm As Single = CSng(1000 * vSc)
	Dim txtE As String = "1 m"
	If lm < 40 Then
		lm = CSng(5000 * vSc) : txtE = "5 m"
	End If
	g.DrawLine(New System.Drawing.Pen(CTexto(), 2), 18, H - 20, 18 + lm, H - 20)
	g.DrawString(txtE, fuente, New System.Drawing.SolidBrush(CTexto()), 22 + lm, H - 28)
End Sub

Sub ResaltarGrupo(g As System.Drawing.Graphics, grupo As String, col As System.Drawing.Color, conManijas As Boolean)
	If grupo = "" Then Exit Sub
	Dim x1 As Double = 1.0E+30, y1 As Double = 1.0E+30, x2 As Double = -1.0E+30, y2 As Double = -1.0E+30
	For Each it As ItemPlan In plan
		If GrupoDe(it) <> grupo OrElse it.Tipo = "pick" OrElse it.Tipo = "zona" Then Continue For
		Dim ww As Double = it.W, dd As Double = it.D
		If it.Tipo = "robot" Then
			ww = 600 : dd = 600
		End If
		x1 = Math.Min(x1, it.Cx - ww / 2) : x2 = Math.Max(x2, it.Cx + ww / 2)
		y1 = Math.Min(y1, it.Cy - dd / 2) : y2 = Math.Max(y2, it.Cy + dd / 2)
	Next
	If x1 > x2 Then Exit Sub
	Dim rx As Single = SX(x1) - 6, ry As Single = SY(y2) - 6
	Dim rw As Single = CSng((x2 - x1) * vSc) + 12, rh As Single = CSng((y2 - y1) * vSc) + 12
	Dim pen As New System.Drawing.Pen(col, If(conManijas, 2, 1.5F))
	pen.DashStyle = System.Drawing.Drawing2D.DashStyle.Dash
	g.DrawRectangle(pen, rx, ry, rw, rh)
	If conManijas Then
		Dim b As New System.Drawing.SolidBrush(System.Drawing.Color.White)
		Dim pm As New System.Drawing.Pen(col, 2)
		For Each q As System.Drawing.PointF In New System.Drawing.PointF() {New System.Drawing.PointF(rx, ry), New System.Drawing.PointF(rx + rw, ry), New System.Drawing.PointF(rx, ry + rh), New System.Drawing.PointF(rx + rw, ry + rh)}
			g.FillRectangle(b, q.X - 4, q.Y - 4, 8, 8)
			g.DrawRectangle(pm, q.X - 4, q.Y - 4, 8, 8)
		Next
	End If
End Sub

Sub Chip(g As System.Drawing.Graphics, txt As String, x As Single, y As Single, fuente As System.Drawing.Font, col As System.Drawing.Color)
	Dim tam As System.Drawing.SizeF = g.MeasureString(txt, fuente)
	Dim gp As System.Drawing.Drawing2D.GraphicsPath = Redondeado(x, y, tam.Width + 8, tam.Height + 2, 6)
	g.FillPath(New System.Drawing.SolidBrush(System.Drawing.Color.FromArgb(235, 255, 255, 255)), gp)
	g.DrawPath(New System.Drawing.Pen(System.Drawing.Color.FromArgb(215, 220, 228)), gp)
	g.DrawString(txt, fuente, New System.Drawing.SolidBrush(col), x + 4, y + 1)
End Sub

Function CapaDibujo(it As ItemPlan) As Integer
	Select Case it.Tipo
		Case "conv", "cinta", "base", "maquina", "zona" : Return 0
		Case "pallet", "caja", "sep", "tope" : Return 1
		Case Else : Return 2
	End Select
End Function

Sub PintarMosaico(g As System.Drawing.Graphics)
	Dim W As Integer = lienzo.Width, H As Integer = lienzo.Height
	Dim fuente As New System.Drawing.Font("Segoe UI", 9)
	Dim fuenteB As New System.Drawing.Font("Segoe UI Semibold", 12)
	Dim anchoPanel As Double = (W - 90) / 2
	Dim altoPanel As Double = H - 190
	Dim ext As Double = Math.Max(Math.Max(mosPW, mosPx), 1) + 200
	Dim extY As Double = Math.Max(Math.Max(mosPD, mosPy), 1) + 200
	Dim sc As Double = Math.Min(anchoPanel / ext, altoPanel / extY)
	For c As Integer = 0 To 1
		Dim x0 As Single = CSng(30 + c * (anchoPanel + 30))
		Dim tarjeta As System.Drawing.Drawing2D.GraphicsPath = Redondeado(x0, 20, CSng(anchoPanel), CSng(altoPanel + 60), 12)
		g.FillPath(New System.Drawing.SolidBrush(System.Drawing.Color.White), tarjeta)
		g.DrawPath(New System.Drawing.Pen(System.Drawing.Color.FromArgb(222, 227, 235)), tarjeta)
		Dim cx As Double = x0 + anchoPanel / 2
		Dim cy As Double = 60 + altoPanel / 2
		g.DrawString("Capa " & (c + 1) & If(c = 1, "  (pares)", "  (impares)"), fuenteB, New System.Drawing.SolidBrush(CTexto()), x0 + 16, 30)
		g.FillRectangle(New System.Drawing.SolidBrush(System.Drawing.Color.FromArgb(158, 104, 60)), CSng(cx - mosPW * sc / 2), CSng(cy - mosPD * sc / 2), CSng(mosPW * sc), CSng(mosPD * sc))
		Dim lista As List(Of Double()) = PatronCapa(mosPx, mosPy, mosA, mosB, mosTipo, c)
		Dim n As Integer = 0
		For Each q As Double() In lista
			n += 1
			Dim rx As Single = CSng(cx + (q(0) - q(2) / 2) * sc), ry As Single = CSng(cy - (q(1) + q(3) / 2) * sc)
			Dim rw As Single = CSng(q(2) * sc), rh As Single = CSng(q(3) * sc)
			g.FillRectangle(New System.Drawing.SolidBrush(System.Drawing.Color.FromArgb(28, 0, 0, 0)), rx + 4, ry + 4, rw - 2, rh - 2)
			g.FillRectangle(New System.Drawing.SolidBrush(System.Drawing.Color.FromArgb(222, 190, 138)), rx + 1, ry + 1, rw - 2, rh - 2)
			g.DrawRectangle(New System.Drawing.Pen(System.Drawing.Color.FromArgb(130, 95, 50), 1.5F), rx + 1, ry + 1, rw - 2, rh - 2)
			Dim tam As System.Drawing.SizeF = g.MeasureString(n.ToString(), fuente)
			g.DrawString(n.ToString(), fuente, New System.Drawing.SolidBrush(CTexto()), rx + (rw - tam.Width) / 2, ry + (rh - tam.Height) / 2)
		Next
		g.DrawString(lista.Count & " cajas por capa", fuente, New System.Drawing.SolidBrush(CSuave()), x0 + 16, CSng(altoPanel + 52))
	Next
	Dim yt As Single = CSng(H - 110)
	For Each s As String In stats
		g.DrawString(s, fuente, New System.Drawing.SolidBrush(CSuave()), 34, yt)
		yt += 16
		If yt > H - 8 Then Exit For
	Next
End Sub


' =====================================================================
'  ORIENTACION AUTOMATICA DE MODELOS (y correccion manual con memoria)
' =====================================================================
Class ModeloInfo
	Public Ruta As String = ""
	Public AutoRot() As Double = {0, 0, 0}
	Public Cajas As New List(Of Double())
End Class
Private INFO As New Dictionary(Of String, ModeloInfo)(StringComparer.OrdinalIgnoreCase)
Private infoCargada As Boolean = False

Function RutaInfo() As String
	Return System.IO.Path.Combine(DirDatos(), "Modelos_info.txt")
End Function

Sub CargarInfo()
	If infoCargada Then Exit Sub
	infoCargada = True
	Try
		If Not System.IO.File.Exists(RutaInfo()) Then Exit Sub
		Dim ci As System.Globalization.CultureInfo = System.Globalization.CultureInfo.InvariantCulture
		For Each ln As String In System.IO.File.ReadAllLines(RutaInfo(), System.Text.Encoding.UTF8)
			Dim p() As String = ln.Split("|"c)
			If p.Length < 3 Then Continue For
			Dim mi As New ModeloInfo
			mi.Ruta = p(0)
			Dim r() As String = p(1).Split(","c)
			mi.AutoRot = New Double() {Double.Parse(r(0), ci), Double.Parse(r(1), ci), Double.Parse(r(2), ci)}
			For Each cj As String In p(2).Split(";"c)
				Dim v() As String = cj.Split(","c)
				If v.Length = 6 Then mi.Cajas.Add(New Double() {Double.Parse(v(0), ci), Double.Parse(v(1), ci), Double.Parse(v(2), ci), Double.Parse(v(3), ci), Double.Parse(v(4), ci), Double.Parse(v(5), ci)})
			Next
			INFO(mi.Ruta) = mi
		Next
	Catch ex As Exception
		Lg("AVISO Modelos_info: " & ex.Message)
	End Try
End Sub

Sub GuardarInfo()
	Try
		Dim ci As System.Globalization.CultureInfo = System.Globalization.CultureInfo.InvariantCulture
		Dim sb As New System.Text.StringBuilder
		For Each mi As ModeloInfo In INFO.Values
			Dim cajas As New List(Of String)
			For Each b As Double() In mi.Cajas
				cajas.Add(String.Join(",", New String() {b(0).ToString("0", ci), b(1).ToString("0", ci), b(2).ToString("0", ci), b(3).ToString("0", ci), b(4).ToString("0", ci), b(5).ToString("0", ci)}))
			Next
			sb.AppendLine(mi.Ruta & "|" & mi.AutoRot(0).ToString("0", ci) & "," & mi.AutoRot(1).ToString("0", ci) & "," & mi.AutoRot(2).ToString("0", ci) & "|" & String.Join(";", cajas.ToArray()))
		Next
		System.IO.File.WriteAllText(RutaInfo(), sb.ToString(), System.Text.Encoding.UTF8)
	Catch
	End Try
End Sub

' abre el modelo una sola vez: guarda las cajas de sus piezas y calcula su orientacion
Function InfoModelo(ruta As String) As ModeloInfo
	If ruta = "" OrElse Not System.IO.File.Exists(ruta) Then Return Nothing
	CargarInfo()
	If INFO.ContainsKey(ruta) Then Return INFO(ruta)
	Dim mi As New ModeloInfo
	mi.Ruta = ruta
	Dim cur As System.Windows.Forms.Cursor = System.Windows.Forms.Cursor.Current
	System.Windows.Forms.Cursor.Current = System.Windows.Forms.Cursors.WaitCursor
	Try
		Dim ya As Boolean = EstaAbierto(ruta)
		app.SilentOperation = True
		Dim d As Document = app.Documents.Open(ruta, False)
		Dim todas As New List(Of Double())
		If d.DocumentType = DocumentTypeEnum.kAssemblyDocumentObject Then
			Dim ad As AssemblyDocument = d
			Dim n As Integer = 0
			For Each lo As ComponentOccurrence In ad.ComponentDefinition.Occurrences.AllLeafOccurrences
				n += 1
				If n > 4000 Then Exit For
				Try
					If lo.Visible Then todas.Add(BoxMM(lo))
				Catch
				End Try
			Next
		ElseIf d.DocumentType = DocumentTypeEnum.kPartDocumentObject Then
			Dim pd As PartDocument = d
			For Each sb As SurfaceBody In pd.ComponentDefinition.SurfaceBodies
				Dim b As Inventor.Box = sb.RangeBox
				todas.Add(New Double() {b.MinPoint.X * 10, b.MinPoint.Y * 10, b.MinPoint.Z * 10, b.MaxPoint.X * 10, b.MaxPoint.Y * 10, b.MaxPoint.Z * 10})
			Next
		End If
		If todas.Count = 0 Then
			Dim o As Object = d
			Dim b As Inventor.Box = o.ComponentDefinition.RangeBox
			todas.Add(New Double() {b.MinPoint.X * 10, b.MinPoint.Y * 10, b.MinPoint.Z * 10, b.MaxPoint.X * 10, b.MaxPoint.Y * 10, b.MaxPoint.Z * 10})
		End If
		If Not ya Then d.Close(True)
		app.SilentOperation = False
		' se guardan las 250 piezas mas grandes
		todas.Sort(Function(p1, p2) VolCaja(p2).CompareTo(VolCaja(p1)))
		For i As Integer = 0 To Math.Min(249, todas.Count - 1)
			mi.Cajas.Add(todas(i))
		Next
		mi.AutoRot = OrientAuto(todas)
		Lg("Orientacion automatica " & System.IO.Path.GetFileName(ruta) & ": rotX=" & mi.AutoRot(0) & " rotY=" & mi.AutoRot(1))
	Catch ex As Exception
		app.SilentOperation = False
		Lg("AVISO analizando " & System.IO.Path.GetFileName(ruta) & ": " & ex.Message)
	End Try
	System.Windows.Forms.Cursor.Current = cur
	INFO(ruta) = mi
	GuardarInfo()
	Return mi
End Function

Function VolCaja(b() As Double) As Double
	Return Math.Abs((b(3) - b(0)) * (b(4) - b(1)) * (b(5) - b(2)))
End Function

' prueba las 6 formas de apoyar el modelo y elige la mas logica:
' muchas patas/apoyos chicos tocando el piso + el peso abajo (+ preferencia por Z arriba)
Function OrientAuto(cajas As List(Of Double())) As Double()
	Dim cands As New List(Of Double())
	cands.Add(New Double() {0, 0, 0})
	cands.Add(New Double() {90, 0, 0})
	cands.Add(New Double() {-90, 0, 0})
	cands.Add(New Double() {0, -90, 0})
	cands.Add(New Double() {0, 90, 0})
	cands.Add(New Double() {180, 0, 0})
	Dim mejor() As Double = cands(0)
	Dim mejorP As Double = -1.0E+30
	For ci As Integer = 0 To cands.Count - 1
		Dim c() As Double = cands(ci)
		Dim rot As New List(Of Double())
		For Each b As Double() In cajas
			rot.Add(RotarCaja(b, c, 0))
		Next
		Dim g() As Double = Union(rot)
		Dim H As Double = g(5) - g(2)
		If H <= 0 Then Continue For
		Dim A As Double = Math.Max(1, (g(3) - g(0)) * (g(4) - g(1)))
		Dim tol As Double = Math.Max(3, H * 0.01)
		Dim chicos As Integer = 0, grandes As Integer = 0
		Dim vol As Double = 0, zc As Double = 0
		For Each b As Double() In rot
			Dim v As Double = Math.Max(1, VolCaja(b))
			vol += v
			zc += v * ((b(2) + b(5)) / 2 - g(2))
			If b(2) <= g(2) + tol Then
				If (b(3) - b(0)) * (b(4) - b(1)) < 0.25 * A Then chicos += 1 Else grandes += 1
			End If
		Next
		Dim relZ As Double = zc / vol / H
		Dim puntos As Double = Math.Min(chicos, 12) + 0.5 * Math.Min(grandes, 2) + (0.5 - relZ) * 6
		If ci = 0 Then puntos += 2.5
		If puntos > mejorP Then
			mejorP = puntos
			mejor = c
		End If
	Next
	Return mejor
End Function

' rota una caja {x1,y1,z1,x2,y2,z2} con rotX, rotY, rotZ (en ese orden) y un giro extra en planta
Function RotarCaja(b() As Double, rb() As Double, rotPlanta As Double) As Double()
	Dim r() As Double = {1.0E+30, 1.0E+30, 1.0E+30, -1.0E+30, -1.0E+30, -1.0E+30}
	For Each x As Double In New Double() {b(0), b(3)}
		For Each y As Double In New Double() {b(1), b(4)}
			For Each z As Double In New Double() {b(2), b(5)}
				Dim q() As Double = RotarPunto(x, y, z, rb, rotPlanta)
				For k As Integer = 0 To 2
					r(k) = Math.Min(r(k), q(k))
					r(k + 3) = Math.Max(r(k + 3), q(k))
				Next
			Next
		Next
	Next
	Return r
End Function

Function RotarPunto(x As Double, y As Double, z As Double, rb() As Double, rotPlanta As Double) As Double()
	Dim ax As Double = 0, ay As Double = 0, az As Double = rotPlanta
	If rb IsNot Nothing Then
		ax = rb(0) : ay = rb(1) : az += rb(2)
	End If
	Dim a As Double, c As Double, s As Double, t As Double
	a = ax * Math.PI / 180 : c = Math.Cos(a) : s = Math.Sin(a)
	t = y * c - z * s : z = y * s + z * c : y = t
	a = ay * Math.PI / 180 : c = Math.Cos(a) : s = Math.Sin(a)
	t = x * c + z * s : z = -x * s + z * c : x = t
	a = az * Math.PI / 180 : c = Math.Cos(a) : s = Math.Sin(a)
	t = x * c - y * s : y = x * s + y * c : x = t
	Return New Double() {x, y, z}
End Function

' orientacion de un modelo: la corregida a mano (ORIENT_ en la biblioteca) o la automatica
Function RotModelo(nombre As String, ruta As String) As Double()
	Dim manual() As Double = RotBib("ORIENT_" & nombre)
	If manual IsNot Nothing Then Return manual
	If Bib("ORIENT_" & nombre).Trim().ToLower() = "ninguna" Then Return Nothing
	Dim mi As ModeloInfo = InfoModelo(ruta)
	If mi Is Nothing Then Return Nothing
	If mi.AutoRot(0) = 0 AndAlso mi.AutoRot(1) = 0 AndAlso mi.AutoRot(2) = 0 Then Return Nothing
	Return CType(mi.AutoRot.Clone(), Double())
End Function

Function OrientEsManual(nombre As String) As Boolean
	Return Bib("ORIENT_" & nombre) <> ""
End Function

' guarda la orientacion corregida en la biblioteca (Nothing = volver a automatica)
Sub GuardarOrient(nombre As String, rb() As Double)
	Dim clave As String = "ORIENT_" & nombre
	Try
		Dim lineas As New List(Of String)
		If System.IO.File.Exists(bibUsada) Then lineas.AddRange(System.IO.File.ReadAllLines(bibUsada, System.Text.Encoding.UTF8))
		lineas.RemoveAll(Function(l) l.Trim().StartsWith(clave & " ", StringComparison.OrdinalIgnoreCase) OrElse l.Trim().StartsWith(clave & "=", StringComparison.OrdinalIgnoreCase))
		If rb IsNot Nothing Then
			Dim v As String = "rotX=" & CInt(rb(0)) & " | rotY=" & CInt(rb(1)) & " | rotZ=" & CInt(rb(2))
			lineas.Add(clave & " = " & v)
			LIBR(clave) = v
		ElseIf LIBR.ContainsKey(clave) Then
			LIBR.Remove(clave)
		End If
		System.IO.File.WriteAllLines(bibUsada, lineas.ToArray(), New System.Text.UTF8Encoding(True))
	Catch ex As Exception
		MessageBox.Show("No pude guardar la orientacion en la biblioteca: " & ex.Message, "Layout paletizado")
	End Try
End Sub

' medidas en planta a partir de las piezas del modelo (para cualquier orientacion)
Function MedidasRotadas(ruta As String, rb() As Double, rotPlanta As Double) As Double()
	CargarInfo()
	If ruta = "" OrElse Not INFO.ContainsKey(ruta) Then Return Nothing
	Dim mi As ModeloInfo = INFO(ruta)
	If mi.Cajas.Count = 0 Then Return Nothing
	Dim rot As New List(Of Double())
	For Each b As Double() In mi.Cajas
		rot.Add(RotarCaja(b, rb, rotPlanta))
	Next
	Dim g() As Double = Union(rot)
	Return New Double() {g(3) - g(0), g(4) - g(1), g(5) - g(2)}
End Function

' ---------------- vista isometrica "asi va a quedar" ----------------
Private isoNombre As String = "", isoRuta As String = "", isoEsRobot As Boolean = False
Private picIso As LienzoPanel
Private lblOrient As System.Windows.Forms.Label
Private panelOrient As System.Windows.Forms.FlowLayoutPanel

Sub PintarIso(sender As Object, e As System.Windows.Forms.PaintEventArgs)
	Dim g As System.Drawing.Graphics = e.Graphics
	g.SmoothingMode = System.Drawing.Drawing2D.SmoothingMode.AntiAlias
	g.Clear(System.Drawing.Color.White)
	Dim W As Integer = picIso.Width, H As Integer = picIso.Height
	Dim fuente As New System.Drawing.Font("Segoe UI", 8)
	If isoRuta = "" OrElse isoEsRobot Then
		Dim txt As String = If(isoEsRobot, "El robot se endereza solo" & vbCrLf & "(usa su pieza Base)", "")
		g.DrawString(txt, fuente, New System.Drawing.SolidBrush(CSuave()), 8, 8)
		Exit Sub
	End If
	CargarInfo()
	If Not INFO.ContainsKey(isoRuta) OrElse INFO(isoRuta).Cajas.Count = 0 Then
		g.DrawString("Sin datos de geometria", fuente, New System.Drawing.SolidBrush(CSuave()), 8, 8)
		Exit Sub
	End If
	Dim rb() As Double = RotModelo(isoNombre, isoRuta)
	Dim cajas As New List(Of Double())
	For Each b As Double() In INFO(isoRuta).Cajas
		cajas.Add(RotarCaja(b, rb, 0))
	Next
	Dim gb() As Double = Union(cajas)
	' proyeccion isometrica
	Dim c30 As Double = Math.Cos(Math.PI / 6), s30 As Double = 0.5
	Dim pxMin As Double = 1.0E+30, pxMax As Double = -1.0E+30, pyMin As Double = 1.0E+30, pyMax As Double = -1.0E+30
	For Each x As Double In New Double() {gb(0), gb(3)}
		For Each y As Double In New Double() {gb(1), gb(4)}
			For Each z As Double In New Double() {gb(2), gb(5)}
				Dim u As Double = (x - y) * c30, v As Double = (x + y) * s30 - z
				pxMin = Math.Min(pxMin, u) : pxMax = Math.Max(pxMax, u) : pyMin = Math.Min(pyMin, v) : pyMax = Math.Max(pyMax, v)
			Next
		Next
	Next
	Dim sc As Double = Math.Min((W - 20) / Math.Max(1, pxMax - pxMin), (H - 34) / Math.Max(1, pyMax - pyMin))
	Dim ox As Double = 10 + ((W - 20) - (pxMax - pxMin) * sc) / 2 - pxMin * sc
	Dim oy As Double = 24 + ((H - 34) - (pyMax - pyMin) * sc) / 2 - pyMin * sc
	Dim P As Func(Of Double, Double, Double, System.Drawing.PointF) = Function(x As Double, y As Double, z As Double) New System.Drawing.PointF(CSng(ox + (x - y) * c30 * sc), CSng(oy + ((x + y) * s30 - z) * sc))
	' piso
	Dim z0 As Double = gb(2)
	Dim piso() As System.Drawing.PointF = {P(gb(0), gb(1), z0), P(gb(3), gb(1), z0), P(gb(3), gb(4), z0), P(gb(0), gb(4), z0)}
	g.FillPolygon(New System.Drawing.SolidBrush(System.Drawing.Color.FromArgb(232, 236, 242)), piso)
	' piezas de atras hacia adelante
	cajas.Sort(Function(a1, a2) (a1(0) + a1(1) + a1(2)).CompareTo(a2(0) + a2(1) + a2(2)))
	Dim bTop As New System.Drawing.SolidBrush(System.Drawing.Color.FromArgb(226, 231, 240))
	Dim bX As New System.Drawing.SolidBrush(System.Drawing.Color.FromArgb(178, 188, 205))
	Dim bY As New System.Drawing.SolidBrush(System.Drawing.Color.FromArgb(150, 162, 182))
	Dim pen As New System.Drawing.Pen(System.Drawing.Color.FromArgb(90, 100, 118), 0.8F)
	For Each b As Double() In cajas
		Dim x1 As Double = b(0), y1 As Double = b(1), z1 As Double = b(2), x2 As Double = b(3), y2 As Double = b(4), z2 As Double = b(5)
		Dim top() As System.Drawing.PointF = {P(x1, y1, z2), P(x2, y1, z2), P(x2, y2, z2), P(x1, y2, z2)}
		Dim cx() As System.Drawing.PointF = {P(x2, y1, z1), P(x2, y2, z1), P(x2, y2, z2), P(x2, y1, z2)}
		Dim cy() As System.Drawing.PointF = {P(x1, y2, z1), P(x2, y2, z1), P(x2, y2, z2), P(x1, y2, z2)}
		g.FillPolygon(bX, cx) : g.DrawPolygon(pen, cx)
		g.FillPolygon(bY, cy) : g.DrawPolygon(pen, cy)
		g.FillPolygon(bTop, top) : g.DrawPolygon(pen, top)
	Next
	' flecha "arriba"
	Dim penZ As New System.Drawing.Pen(System.Drawing.Color.FromArgb(37, 99, 235), 2)
	penZ.CustomEndCap = New System.Drawing.Drawing2D.AdjustableArrowCap(4, 4)
	g.DrawLine(penZ, W - 18, H - 10, W - 18, H - 40)
	g.DrawString("Z", fuente, New System.Drawing.SolidBrush(CAcento()), W - 30, H - 44)
	g.DrawString("Asi va a quedar" & If(OrientEsManual(isoNombre), "  (corregido)", "  (automatico)"), fuente, New System.Drawing.SolidBrush(CTexto()), 6, 4)
End Sub

Sub BotonOrient(sender As Object, e As EventArgs)
	If isoNombre = "" OrElse isoRuta = "" OrElse isoEsRobot Then Exit Sub
	Dim txt As String = CType(sender, System.Windows.Forms.Button).Text
	Dim rb() As Double = RotModelo(isoNombre, isoRuta)
	If rb Is Nothing Then rb = New Double() {0, 0, 0}
	rb = CType(rb.Clone(), Double())
	Select Case txt
		Case "Parar en X" : rb(0) = ((rb(0) + 90) Mod 360 + 360) Mod 360
		Case "Parar en Y" : rb(1) = ((rb(1) + 90) Mod 360 + 360) Mod 360
		Case "Dar vuelta" : rb(0) = ((rb(0) + 180) Mod 360 + 360) Mod 360
		Case "Automatica"
			GuardarOrient(isoNombre, Nothing)
			picIso.Invalidate()
			Refrescar()
			Exit Sub
	End Select
	If rb(0) = 0 AndAlso rb(1) = 0 AndAlso rb(2) = 0 Then
		' sin giro: se guarda explicito para que no vuelva a la automatica
		GuardarOrient(isoNombre, New Double() {0, 0, 0})
	Else
		GuardarOrient(isoNombre, rb)
	End If
	picIso.Invalidate()
	Refrescar()
End Sub

Sub MostrarIso(nombre As String, ruta As String)
	If picIso Is Nothing Then Exit Sub
	isoNombre = nombre
	isoRuta = ruta
	isoEsRobot = ROBOTS.ContainsKey(nombre)
	If ruta <> "" AndAlso Not isoEsRobot Then InfoModelo(ruta)
	panelOrient.Enabled = (ruta <> "" AndAlso Not isoEsRobot)
	picIso.Invalidate()
End Sub

' =====================================================================
'  INDICE DE MODELOS, ROBOTS Y MAQUINAS
' =====================================================================
Sub IndexarRaices()
	Dim exc() As String = Excluidos()
	For Each raiz As String In Bib("RAIZ").Split(";"c)
		Dim rz As String = raiz.Trim()
		If rz = "" Then Continue For
		If Not System.IO.Directory.Exists(rz) Then
			Lg("AVISO: no existe la carpeta RAIZ " & rz)
			Continue For
		End If
		Recorrer(rz, exc)
		For Each dGrupo As String In System.IO.Directory.GetDirectories(rz)
			Dim esRobot As Boolean = System.IO.Path.GetFileName(dGrupo).StartsWith("Robots", StringComparison.OrdinalIgnoreCase)
			For Each dMod As String In System.IO.Directory.GetDirectories(dGrupo)
				Dim principal As String = IamPrincipal(dMod)
				If principal = "" Then Continue For
				If esRobot Then
					Dim nom As String = System.IO.Path.GetFileNameWithoutExtension(principal)
					If Not ROBOTS.ContainsKey(nom) Then ROBOTS(nom) = principal
				Else
					Dim nom As String = System.IO.Path.GetFileName(dMod)
					If Not MAQUINAS.ContainsKey(nom) Then MAQUINAS(nom) = principal
				End If
			Next
		Next
	Next
	' bases de robot: ensambles en carpetas cuyo nombre contiene "base", y bases sueltas tipo BaseRobot/BasePaletizado
	For Each f As String In INDICE
		Dim carpeta As String = System.IO.Path.GetFileName(System.IO.Path.GetDirectoryName(f))
		Dim nomF As String = System.IO.Path.GetFileNameWithoutExtension(f)
		Dim esIam As Boolean = f.ToLower().EndsWith(".iam")
		Dim enRobot As Boolean = f.ToLower().Contains("\robots")
		If esIam AndAlso Not enRobot AndAlso carpeta.ToLower().Contains("base") Then
			BASES(carpeta & " - " & nomF) = f
		ElseIf System.Text.RegularExpressions.Regex.IsMatch(nomF, "^(.*_)?Base(Robot|Paletizado|Extensible)$", System.Text.RegularExpressions.RegexOptions.IgnoreCase) Then
			BASES(carpeta & " - " & nomF) = f
		End If
	Next
	For Each k As String In LIBR.Keys
		If k.StartsWith("BASE_", StringComparison.OrdinalIgnoreCase) AndAlso Not k.StartsWith("BASE_PARA_", StringComparison.OrdinalIgnoreCase) AndAlso Not k.StartsWith("BASE_ROBOT", StringComparison.OrdinalIgnoreCase) Then
			Dim r As String = Resolver(k)
			If r <> "" Then BASES(k.Substring(5)) = r
		End If
	Next
	For Each k As String In LIBR.Keys
		If k.StartsWith("ROBOT_", StringComparison.OrdinalIgnoreCase) Then
			Dim r As String = Resolver(k)
			If r <> "" Then ROBOTS(k.Substring(6)) = r
		End If
		If k.StartsWith("MAQUINA_", StringComparison.OrdinalIgnoreCase) Then
			Dim r As String = Resolver(k)
			If r <> "" Then MAQUINAS(k.Substring(8)) = r
		End If
	Next
End Sub

' .iam principal de una carpeta: el menos profundo; a igual profundidad el que se llama como su carpeta, y si no el mas grande
Function IamPrincipal(dMod As String) As String
	Dim mejor As String = "", prof As Integer = 999, coincide As Boolean = False, tam As Long = 0
	For Each f As String In INDICE
		If Not f.StartsWith(dMod & "\", StringComparison.OrdinalIgnoreCase) Then Continue For
		If Not f.ToLower().EndsWith(".iam") Then Continue For
		Dim p As Integer = f.Split("\"c).Length
		Dim nom As String = System.IO.Path.GetFileNameWithoutExtension(f).ToLower()
		Dim carpeta As String = System.IO.Path.GetFileName(System.IO.Path.GetDirectoryName(f)).ToLower()
		Dim co As Boolean = (nom = carpeta) OrElse carpeta.Contains(nom) OrElse nom.Contains(carpeta)
		Dim sz As Long = New System.IO.FileInfo(f).Length
		Dim mejora As Boolean = False
		If p < prof Then
			mejora = True
		ElseIf p = prof Then
			If co AndAlso Not coincide Then
				mejora = True
			ElseIf co = coincide AndAlso sz > tam Then
				mejora = True
			End If
		End If
		If mejora Then
			mejor = f : prof = p : coincide = co : tam = sz
		End If
	Next
	Return mejor
End Function

Function RutaMaquina(nombre As String) As String
	If nombre Is Nothing OrElse nombre = "" OrElse nombre = "Ninguna" Then Return ""
	If MAQUINAS.ContainsKey(nombre) Then Return MAQUINAS(nombre)
	Falta("Maquina " & nombre, "(no esta en la biblioteca)")
	Return ""
End Function

' base que corresponde a cada robot (BASE_PARA_<robot> en la biblioteca manda)
Function BaseAuto(robNom As String) As String
	Dim manual As String = Bib("BASE_PARA_" & robNom)
	If manual <> "" Then
		For Each k As String In BASES.Keys
			If k.ToLower().Contains(manual.ToLower()) Then Return k
		Next
	End If
	Dim u As String = robNom.ToUpper()
	Dim buscar() As String
	If u.StartsWith("KR") Then
		buscar = New String() {"circular"}
	ElseIf u.StartsWith("BRTMD") Then
		buscar = New String() {"baserobot", "basepaletizado"}
	Else
		buscar = New String() {"ensamble base", "configuraci", "borunte"}
	End If
	For Each b As String In buscar
		For Each k As String In BASES.Keys
			If k.ToLower().Contains(b) Then Return k
		Next
	Next
	Return ""
End Function

Function RotMaquina(nombre As String) As Double()
	Return RotModelo(nombre, If(MAQUINAS.ContainsKey(nombre), MAQUINAS(nombre), ""))
End Function

' lee "rotX=90 | rotY=0 | rotZ=180" de una clave de la biblioteca
Function RotBib(clave As String) As Double()
	Dim v As String = Bib(clave)
	If v = "" OrElse Not v.ToLower().Contains("rot") Then Return Nothing
	Dim r() As Double = {0, 0, 0}
	Dim hay As Boolean = False
	For Each parte As String In v.Split("|"c)
		Dim p As String = parte.Trim().ToLower().Replace(" ", "")
		Dim k As Integer = -1
		If p.StartsWith("rotx=") Then k = 0
		If p.StartsWith("roty=") Then k = 1
		If p.StartsWith("rotz=") Then k = 2
		If k >= 0 Then
			r(k) = Double.Parse(p.Substring(5), System.Globalization.CultureInfo.InvariantCulture)
			hay = True
		End If
	Next
	If Not hay Then Return Nothing
	Return r
End Function

Function BibliotecaPorDefecto() As String
	Dim s As New System.Text.StringBuilder
	s.AppendLine("# Biblioteca del generador de layouts. CLAVE = valor")
	s.AppendLine("# valor: nombre de archivo (admite *), Carpeta\archivo, ruta completa, o GENERAR")
	s.AppendLine("# ORIENT_<maquina> = rotX=90 | rotY=0 | rotZ=0   corrige modelos acostados/girados")
	s.AppendLine("# MAQUINA_<nombre> = archivo                      agrega o reemplaza una maquina")
	s.AppendLine("# ROBOT_<nombre> = archivo                        agrega un robot")
	s.AppendLine("RAIZ = C:\Tadeo\CosasParaCAD")
	s.AppendLine("EXCLUIR = OldVersions;Templates;Design Data;Libraries;Content Center")
	s.AppendLine("BASE_ROBOT = Ensamble base.iam")
	s.AppendLine("BASE_ROBOT_KR = base_principal_circular.iam")
	s.AppendLine("CONV_PALLET = GENERAR")
	s.AppendLine("CINTA_ENTRADA = GENERAR")
	s.AppendLine("PALLET = GENERAR")
	s.AppendLine("CAJA = GENERAR")
	s.AppendLine("VALLA = GENERAR")
	s.AppendLine("PUERTA = GENERAR")
	s.AppendLine("ORIENT_Dispenser_Pallets = rotX=90")
	s.AppendLine("ORIENT_Mesa carton BLQ = rotX=90")
	s.AppendLine("ORIENT_Mesa carton = rotX=90")
	Return s.ToString()
End Function

' =====================================================================
'  DIAGNOSTICO
' =====================================================================
Sub Diagnostico()
	Dim sb As New System.Text.StringBuilder
	sb.AppendLine("DIAGNOSTICO - " & DateTime.Now.ToString("yyyy-MM-dd HH:mm"))
	sb.AppendLine("Biblioteca: " & bibUsada)
	sb.AppendLine("RAIZ: " & Bib("RAIZ") & "   modelos indexados: " & INDICE.Count)
	sb.AppendLine("")
	sb.AppendLine("ROBOTS (" & ROBOTS.Count & ")")
	For Each kv As KeyValuePair(Of String, String) In ROBOTS
		sb.AppendLine(String.Format("  {0,-22} alcance {1,5:0} mm  carga {2,4:0} kg   {3}", kv.Key, AlcanceDesdeNombre(kv.Key), CargaDesdeNombre(kv.Key), kv.Value))
	Next
	sb.AppendLine("")
	sb.AppendLine("MAQUINAS (" & MAQUINAS.Count & ")")
	For Each kv As KeyValuePair(Of String, String) In MAQUINAS
		Dim rb() As Double = RotBib("ORIENT_" & kv.Key)
		sb.AppendLine(String.Format("  {0,-34} {1}{2}", kv.Key, kv.Value, If(rb Is Nothing, "", "   [rot " & rb(0) & "," & rb(1) & "," & rb(2) & "]")))
	Next
	sb.AppendLine("")
	sb.AppendLine("CLAVES DE LA BIBLIOTECA")
	For Each kv As KeyValuePair(Of String, String) In LIBR
		sb.AppendLine("  " & kv.Key & " = " & kv.Value)
	Next
	Dim robSel As String = PTxt("L_Robot")
	If ROBOTS.ContainsKey(robSel) Then
		sb.AppendLine("")
		sb.AppendLine("=== ROBOT SELECCIONADO " & robSel)
		DiagArchivo(ROBOTS(robSel), sb)
	End If
	Dim rutaTxt As String = System.IO.Path.Combine(genDir, "Diagnostico_Biblioteca.txt")
	System.IO.File.WriteAllText(rutaTxt, sb.ToString(), System.Text.Encoding.UTF8)
	Try
		System.Diagnostics.Process.Start("notepad.exe", """" & rutaTxt & """")
	Catch
		MessageBox.Show("Diagnostico guardado en " & rutaTxt, "Layout paletizado")
	End Try
End Sub

' carga util aproximada segun el nombre (verificar en la ficha del robot)
Function CargaDesdeNombre(nom As String) As Double
	Dim u As String = nom.ToUpper()
	Dim m As System.Text.RegularExpressions.Match = System.Text.RegularExpressions.Regex.Match(u, "^KR_?(\d+)")
	If m.Success Then Return CDbl(m.Groups(1).Value)
	m = System.Text.RegularExpressions.Regex.Match(u, "BRTIR([A-Z]{2})(\d{3,4})")
	If m.Success Then
		Dim g As String = m.Groups(2).Value.PadLeft(4, "0"c)
		Dim c As Double = CDbl(g.Substring(2, 2))
		If m.Groups(1).Value = "PZ" AndAlso c < 20 Then c *= 10
		Return c
	End If
	Return 20
End Function

Sub Chequeo(que As String, d As Double, alcance As Double)
	Dim est As String = If(d <= alcance * 0.95, "OK", If(d <= alcance, "JUSTO", "FUERA DE ALCANCE"))
	stats.Add(String.Format("{0}: {1:0} mm -> {2}", que, d, est))
	If est = "FUERA DE ALCANCE" Then
		avisos.Add(que & " fuera del alcance del robot")
		hayProblema = True
	End If
End Sub
' =====================================================================
'  PIEZAS GENERADAS (a medida; se guardan en LAY_Generados y se reusan)
' =====================================================================
Function GenBloque(nombre As String, L As Double, A As Double, H As Double, cr As Integer, cg As Integer, cb As Integer) As String
	Dim bl As New List(Of Double())
	bl.Add(New Double() {-L / 2, -A / 2, 0, L / 2, A / 2, H})
	Return CrearPieza(nombre & "_" & Dm(L) & "x" & Dm(A) & "x" & Dm(H), bl, Nothing, cr, cg, cb)
End Function

Function GenPallet(L As Double, A As Double, H As Double) As String
	Dim bl As New List(Of Double())
	Dim t As Double = 22, hb As Double = Math.Max(20, H - 2 * t)
	For Each y As Double In New Double() {-A / 2 + 50, 0, A / 2 - 50}          ' patines
		bl.Add(New Double() {-L / 2, y - 50, 0, L / 2, y + 50, t})
	Next
	For Each x As Double In New Double() {-L / 2 + 72, 0, L / 2 - 72}           ' tacos
		For Each y As Double In New Double() {-A / 2 + 50, 0, A / 2 - 50}
			bl.Add(New Double() {x - 72, y - 50, t, x + 72, y + 50, t + hb})
		Next
	Next
	For Each x As Double In New Double() {-L / 2 + 72, 0, L / 2 - 72}           ' largueros
		bl.Add(New Double() {x - 72, -A / 2, t + hb, x + 72, A / 2, H - t})
	Next
	Dim nTab As Integer = 7
	For k As Integer = 0 To nTab - 1                                              ' tablas superiores
		Dim y As Double = -A / 2 + 50 + k * (A - 100) / (nTab - 1)
		bl.Add(New Double() {-L / 2, y - 50, H - t, L / 2, y + 50, H})
	Next
	Return CrearPieza("Pallet_" & Dm(L) & "x" & Dm(A) & "x" & Dm(H), bl, Nothing, 150, 95, 55)
End Function

Function GenRodillos(T As Double, W As Double, H As Double) As String
	Dim bl As New List(Of Double())
	Dim cy As New List(Of Double())
	Dim rr As Double = 30
	bl.Add(New Double() {-T / 2, -W / 2, H - 140, T / 2, -W / 2 + 50, H - 20})    ' largueros
	bl.Add(New Double() {-T / 2, W / 2 - 50, H - 140, T / 2, W / 2, H - 20})
	For Each x As Double In New Double() {-T / 2 + 80, T / 2 - 80}                  ' patas + travesanos
		For Each y As Double In New Double() {-W / 2 + 25, W / 2 - 25}
			bl.Add(New Double() {x - 30, y - 25, 0, x + 30, y + 25, H - 140})
		Next
		bl.Add(New Double() {x - 30, -W / 2 + 50, 150, x + 30, W / 2 - 50, 210})
	Next
	Dim nR As Integer = Math.Max(2, CInt(Math.Floor((T - 60) / 125)))
	Dim paso As Double = (T - 60) / (nR - 1)
	For k As Integer = 0 To nR - 1                                                  ' rodillos
		Dim x As Double = -T / 2 + 30 + k * paso
		cy.Add(New Double() {x, -W / 2 + 50, H - rr, x, W / 2 - 50, H - rr, rr})
	Next
	Return CrearPieza("TranspRodillos_" & Dm(T) & "x" & Dm(W) & "x" & Dm(H), bl, cy, 40, 95, 120)
End Function

Function GenCinta(T As Double, W As Double, H As Double) As String
	Dim bl As New List(Of Double())
	Dim cy As New List(Of Double())
	bl.Add(New Double() {-T / 2, -W / 2, H - 140, T / 2, -W / 2 + 40, H + 10})     ' laterales
	bl.Add(New Double() {-T / 2, W / 2 - 40, H - 140, T / 2, W / 2, H + 10})
	bl.Add(New Double() {-T / 2 + 50, -W / 2 + 40, H - 12, T / 2 - 50, W / 2 - 40, H})  ' banda
	cy.Add(New Double() {-T / 2 + 50, -W / 2 + 40, H - 50, -T / 2 + 50, W / 2 - 40, H - 50, 50})
	cy.Add(New Double() {T / 2 - 50, -W / 2 + 40, H - 50, T / 2 - 50, W / 2 - 40, H - 50, 50})
	Dim nP As Integer = Math.Max(2, CInt(Math.Ceiling(T / 2000)) + 1)
	For k As Integer = 0 To nP - 1                                                  ' patas
		Dim x As Double = -T / 2 + 100 + k * (T - 200) / (nP - 1)
		For Each y As Double In New Double() {-W / 2 + 20, W / 2 - 20}
			bl.Add(New Double() {x - 25, y - 20, 0, x + 25, y + 20, H - 140})
		Next
	Next
	Return CrearPieza("Cinta_" & Dm(T) & "x" & Dm(W) & "x" & Dm(H), bl, cy, 55, 60, 65)
End Function

Function GenValla(P As Double, H As Double, puerta As Boolean) As String
	Dim bl As New List(Of Double())
	bl.Add(New Double() {-P / 2, -30, 0, -P / 2 + 60, 30, H})                      ' postes
	bl.Add(New Double() {P / 2 - 60, -30, 0, P / 2, 30, H})
	For Each z As Double In New Double() {150, H / 2, H - 30}                       ' travesanos
		bl.Add(New Double() {-P / 2 + 60, -15, z - 15, P / 2 - 60, 15, z + 15})
	Next
	If puerta Then
		bl.Add(New Double() {-P / 2 + 60, -20, 100, -P / 2 + 100, 20, H - 60})    ' marco hoja
		bl.Add(New Double() {P / 2 - 100, -20, 100, P / 2 - 60, 20, H - 60})
		bl.Add(New Double() {P / 2 - 160, 20, H * 0.45, P / 2 - 120, 60, H * 0.55}) ' manija
	Else
		Dim paso As Double = 100                                                    ' malla de alambre
		Dim nv As Integer = CInt(Math.Floor((P - 120) / paso))
		For k As Integer = 1 To nv
			Dim x As Double = -P / 2 + 60 + k * (P - 120) / (nv + 1)
			bl.Add(New Double() {x - 3, -3, 165, x + 3, 3, H - 45})
		Next
		Dim nh As Integer = CInt(Math.Floor((H - 210) / paso))
		For k As Integer = 1 To nh
			Dim z As Double = 165 + k * (H - 210) / (nh + 1)
			bl.Add(New Double() {-P / 2 + 60, -3, z - 3, P / 2 - 60, 3, z + 3})
		Next
	End If
	Dim nombre As String = If(puerta, "Puerta_", "Valla2_") & Dm(P) & "x" & Dm(H)
	If puerta Then Return CrearPieza(nombre, bl, Nothing, 220, 120, 0)
	Return CrearPieza(nombre, bl, Nothing, 190, 170, 0)
End Function

' bloques {x1,y1,z1,x2,y2,z2} y cilindros {x1,y1,z1,x2,y2,z2,radio} en mm
Function CrearPieza(nombre As String, bloques As List(Of Double()), cilindros As List(Of Double()), cr As Integer, cg As Integer, cb As Integer) As String
	Dim ruta As String = System.IO.Path.Combine(genDir, "LAY_" & nombre & ".ipt")
	If System.IO.File.Exists(ruta) Then Return ruta
	Dim tpl As String = app.FileManager.GetTemplateFile(DocumentTypeEnum.kPartDocumentObject, SystemOfMeasureEnum.kMetricSystemOfMeasure)
	Dim pd As PartDocument = app.Documents.Add(DocumentTypeEnum.kPartDocumentObject, tpl, False)
	Dim tb As TransientBRep = app.TransientBRep
	Dim cuerpo As SurfaceBody = Nothing
	If bloques IsNot Nothing Then
		For Each b As Double() In bloques
			Dim bx As Inventor.Box = tg.CreateBox()
			bx.MinPoint = tg.CreatePoint(Math.Min(b(0), b(3)) / 10, Math.Min(b(1), b(4)) / 10, Math.Min(b(2), b(5)) / 10)
			bx.MaxPoint = tg.CreatePoint(Math.Max(b(0), b(3)) / 10, Math.Max(b(1), b(4)) / 10, Math.Max(b(2), b(5)) / 10)
			Dim s As SurfaceBody = tb.CreateSolidBlock(bx)
			If cuerpo Is Nothing Then
				cuerpo = s
			Else
				tb.DoBoolean(cuerpo, s, BooleanTypeEnum.kBooleanTypeUnion)
			End If
		Next
	End If
	If cilindros IsNot Nothing Then
		For Each c As Double() In cilindros
			Dim s As SurfaceBody = tb.CreateSolidCylinderCone(tg.CreatePoint(c(0) / 10, c(1) / 10, c(2) / 10), _
				tg.CreatePoint(c(3) / 10, c(4) / 10, c(5) / 10), c(6) / 10, c(6) / 10, c(6) / 10)
			If cuerpo Is Nothing Then
				cuerpo = s
			Else
				tb.DoBoolean(cuerpo, s, BooleanTypeEnum.kBooleanTypeUnion)
			End If
		Next
	End If
	Dim pcd As PartComponentDefinition = pd.ComponentDefinition
	Try
		Dim def As NonParametricBaseFeatureDefinition = pcd.Features.NonParametricBaseFeatures.CreateDefinition()
		Dim col As ObjectCollection = app.TransientObjects.CreateObjectCollection()
		col.Add(cuerpo)
		def.BRepEntities = col
		def.OutputType = BaseFeatureOutputTypeEnum.kSolidOutputType
		pcd.Features.NonParametricBaseFeatures.AddByDefinition(def)
	Catch
		pcd.Features.NonParametricBaseFeatures.Add(cuerpo)
	End Try
	Try
		Dim an As String = "LAY_" & cr & "_" & cg & "_" & cb
		Dim ap As Asset = pd.Assets.Add(AssetTypeEnum.kAssetTypeAppearance, "Generic", an, an)
		Dim cv As ColorAssetValue = ap.Item("generic_diffuse")
		cv.Value = app.TransientObjects.CreateColor(cr, cg, cb)
		pd.ActiveAppearance = ap
	Catch ex As Exception
		Lg("AVISO color " & nombre & ": " & ex.Message)
	End Try
	pd.SaveAs(ruta, False)
	pd.Close(True)
	Lg("Pieza generada: " & System.IO.Path.GetFileName(ruta))
	Return ruta
End Function

Function Dm(v As Double) As String
	Return CLng(Math.Round(v)).ToString()
End Function

Sub PDef(nombre As String, valor As Object, Optional unidad As String = "")
	Dim ups As UserParameters = cd.Parameters.UserParameters
	For Each u As UserParameter In ups
		If u.Name = nombre Then Exit Sub
	Next
	If TypeOf valor Is String Then
		ups.AddByValue(nombre, valor, UnitsTypeEnum.kTextUnits)
	ElseIf TypeOf valor Is Boolean Then
		ups.AddByValue(nombre, valor, UnitsTypeEnum.kBooleanUnits)
	Else
		ups.AddByExpression(nombre, CLng(valor).ToString() & " " & unidad, unidad)
	End If
End Sub

' =====================================================================
'  COLOCACION (independiente del origen de cada modelo)
' =====================================================================
Function Colocar(ruta As String, nombre As String, xmm As Double, ymm As Double, zmm As Double, rotDeg As Double, ejeLargo As String, rotBase() As Double) As ComponentOccurrence
	If Not Existe(ruta, nombre) Then Return Nothing
	If Not nombre.EndsWith("_Caja") Then Lg("+ " & nombre & " <- " & System.IO.Path.GetFileName(ruta))
	Dim occ As ComponentOccurrence
	Try
		occ = cd.Occurrences.Add(ruta, MatOrient(rotBase, rotDeg))
	Catch ex As Exception
		' segundo intento: abrir el modelo y insertarlo por su definicion
		Try
			Dim d As Document = app.Documents.Open(ruta, False)
			Dim od As Object = d
			occ = cd.Occurrences.AddByComponentDefinition(od.ComponentDefinition, MatOrient(rotBase, rotDeg))
			Lg("  (insertado por definicion tras: " & ex.Message & ")")
		Catch ex2 As Exception
			Lg("ERROR insertando " & nombre & ": " & ex.Message & " / " & ex2.Message)
			Return Nothing
		End Try
	End Try
	occ.Grounded = False
	If ejeLargo <> "" Then
		Dim b0() As Double = BoxMM(occ)
		Dim dx As Double = b0(3) - b0(0), dy As Double = b0(4) - b0(1)
		If (ejeLargo = "X" AndAlso dy > dx * 1.001) OrElse (ejeLargo = "Y" AndAlso dx > dy * 1.001) Then
			occ.Transformation = MatOrient(rotBase, rotDeg + 90)
		End If
	End If
	Mover(occ, xmm, ymm, zmm)
	occ.Grounded = True
	Nombrar(occ, nombre)
	Return occ
End Function

' robot: detecta solo hacia donde esta "arriba" usando su sub-pieza "Base"
' (su lado mas corto es la altura), lo endereza y lo ancla en el centro de esa base.
Function ColocarRobot(ruta As String, nombre As String, zmm As Double, rotDeg As Double, rotBase() As Double) As ComponentOccurrence
	If Not Existe(ruta, "Robot " & nombre) Then Return Nothing
	Lg("+ Robot <- " & ruta)
	Dim occ As ComponentOccurrence
	Try
		occ = cd.Occurrences.Add(ruta, MatOrient(rotBase, 0))
	Catch ex As Exception
		Lg("ERROR insertando robot: " & ex.Message)
		Return Nothing
	End Try
	occ.Grounded = False
	Dim baseOcc As ComponentOccurrence = Nothing
	Dim bajo As ComponentOccurrence = Nothing
	Try
		Dim zMin As Double = 1.0E+30, area As Double = 0
		For Each so As ComponentOccurrence In occ.SubOccurrences
			If baseOcc Is Nothing AndAlso so.Name.ToLower().Contains("base") Then baseOcc = so
			Dim b() As Double = BoxMM(so)
			Dim ar As Double = (b(3) - b(0)) * (b(4) - b(1))
			If b(2) < zMin - 1 OrElse (Math.Abs(b(2) - zMin) <= 1 AndAlso ar > area) Then
				zMin = b(2) : area = ar : bajo = so
			End If
		Next
	Catch
	End Try

	Dim rb() As Double = If(rotBase Is Nothing, New Double() {0, 0, 0}, rotBase)
	Dim modoEje As String = PTxt("L_RobotArriba")
	If rotBase Is Nothing Then
		Dim arriba As String = modoEje
		If arriba = "Auto" Then
			arriba = "Z"
			If baseOcc IsNot Nothing Then
				Dim bb() As Double = BoxMM(baseOcc)
				Dim ex As Double = bb(3) - bb(0), ey As Double = bb(4) - bb(1), ez As Double = bb(5) - bb(2)
				If ey < ex AndAlso ey < ez Then arriba = "Y"
				If ex < ey AndAlso ex < ez Then arriba = "X"
			End If
		End If
		If arriba = "Y" Then rb = New Double() {90, 0, 0}
		If arriba = "-Y" Then rb = New Double() {-90, 0, 0}
		If arriba = "X" Then rb = New Double() {0, -90, 0}
		If arriba = "-X" Then rb = New Double() {0, 90, 0}
		occ.Transformation = MatOrient(rb, rotDeg)
		' si la base quedo arriba, dar vuelta 180
		If modoEje = "Auto" AndAlso baseOcc IsNot Nothing Then
			Dim br() As Double = BoxMM(occ), bs() As Double = BoxMM(baseOcc)
			If (bs(2) - br(2)) > 0.3 * (br(5) - br(2)) Then
				If arriba = "X" Then rb(1) += 180 Else rb(0) += 180
				occ.Transformation = MatOrient(rb, rotDeg)
			End If
		End If
		Lg("Robot: arriba = " & arriba & "  (rotX=" & rb(0) & " rotY=" & rb(1) & ")")
	Else
		occ.Transformation = MatOrient(rotBase, rotDeg)
	End If

	Dim refOcc As ComponentOccurrence = If(baseOcc IsNot Nothing, baseOcc, bajo)
	AnclarRobot(occ, refOcc, zmm)
	' girar en planta para que el brazo mire hacia la linea de pallets (-Y); L_RotRobot se suma
	Try
		Dim bR() As Double = BoxMM(occ)
		Dim ax As Double = (bR(0) + bR(3)) / 2 - robX, ay As Double = (bR(1) + bR(4)) / 2 - robY
		If Math.Sqrt(ax * ax + ay * ay) > 100 Then
			Dim ang As Double = Math.Atan2(ay, ax) * 180 / Math.PI
			Dim delta As Double = robAng - ang
			occ.Grounded = False
			occ.Transformation = MatOrient(rb, rotDeg + delta)
			AnclarRobot(occ, refOcc, zmm)
			Lg(String.Format("Robot girado {0:0} grados para mirar a la linea de pallets", delta))
		End If
	Catch
	End Try
	occ.Grounded = True
	Nombrar(occ, "Robot")
	Lg("Robot " & nombre & " anclado por: " & If(refOcc IsNot Nothing, refOcc.Name, "(caja completa)"))
	Return occ
End Function

Sub AnclarRobot(occ As ComponentOccurrence, refOcc As ComponentOccurrence, zmm As Double)
	occ.Grounded = False
	Dim ref() As Double = If(refOcc IsNot Nothing, BoxMM(refOcc), BoxMM(occ))
	Dim zBot As Double = BoxMM(occ)(2)
	' L_CorrEjeRobotX/Y: correccion fina si el eje 1 no cae en el centro de la base
	Dim t As Inventor.Matrix = occ.Transformation
	t.Cell(1, 4) = t.Cell(1, 4) + (robX - (ref(0) + ref(3)) / 2 - PMM("L_CorrEjeRobotX")) / 10
	t.Cell(2, 4) = t.Cell(2, 4) + (robY - (ref(1) + ref(4)) / 2 - PMM("L_CorrEjeRobotY")) / 10
	t.Cell(3, 4) = t.Cell(3, 4) + (zmm - zBot) / 10
	occ.Transformation = t
End Sub

Sub Mover(occ As ComponentOccurrence, xmm As Double, ymm As Double, zmm As Double)
	Dim g As Boolean = occ.Grounded
	occ.Grounded = False
	Dim b() As Double = BoxMM(occ)
	Dim t As Inventor.Matrix = occ.Transformation
	t.Cell(1, 4) = t.Cell(1, 4) + (xmm - (b(0) + b(3)) / 2) / 10
	t.Cell(2, 4) = t.Cell(2, 4) + (ymm - (b(1) + b(4)) / 2) / 10
	t.Cell(3, 4) = t.Cell(3, 4) + (zmm - b(2)) / 10
	occ.Transformation = t
	occ.Grounded = g
End Sub

' rotBase = {rotX, rotY, rotZ} de la biblioteca; luego giro en planta del layout
Function MatOrient(rotBase() As Double, rotDeg As Double) As Inventor.Matrix
	Dim m As Inventor.Matrix = tg.CreateMatrix()
	Dim o As Inventor.Point = tg.CreatePoint(0, 0, 0)
	If rotBase IsNot Nothing Then
		Dim ejes() As Inventor.Vector = {tg.CreateVector(1, 0, 0), tg.CreateVector(0, 1, 0), tg.CreateVector(0, 0, 1)}
		For k As Integer = 0 To 2
			If rotBase(k) <> 0 Then
				Dim mk As Inventor.Matrix = tg.CreateMatrix()
				mk.SetToRotation(rotBase(k) * Math.PI / 180.0, ejes(k), o)
				m.TransformBy(mk)
			End If
		Next
	End If
	If rotDeg <> 0 Then
		Dim mz As Inventor.Matrix = tg.CreateMatrix()
		mz.SetToRotation(rotDeg * Math.PI / 180.0, tg.CreateVector(0, 0, 1), o)
		m.TransformBy(mz)
	End If
	Return m
End Function

Function BoxMM(occ As ComponentOccurrence) As Double()
	Dim b As Inventor.Box = occ.RangeBox
	Return New Double() {b.MinPoint.X * 10, b.MinPoint.Y * 10, b.MinPoint.Z * 10, _
		b.MaxPoint.X * 10, b.MaxPoint.Y * 10, b.MaxPoint.Z * 10}
End Function

Sub Nombrar(occ As ComponentOccurrence, nombre As String)
	nOcc += 1
	Try
		occ.Name = "LAY_" & nombre & "_" & nOcc.ToString()
	Catch
	End Try
End Sub

Sub BorrarGenerados()
	Dim n As Integer = 0
	For i As Integer = cd.Occurrences.Count To 1 Step -1
		Dim o As ComponentOccurrence = cd.Occurrences.Item(i)
		If o.Name.StartsWith("LAY_") Then
			o.Delete()
			n += 1
		End If
	Next
	If n > 0 Then Lg("Se borraron " & n & " componentes LAY_ anteriores")
End Sub

' =====================================================================
'  BIBLIOTECA E INDICE DE MODELOS
' =====================================================================
' carpeta de datos de esta PC (miniaturas, medidas, registro): %APPDATA%\GeneradorLayoutPaletizado
Function DirDatos() As String
	Dim d As String = System.IO.Path.Combine(System.Environment.GetFolderPath(System.Environment.SpecialFolder.ApplicationData), "GeneradorLayoutPaletizado")
	Try
		System.IO.Directory.CreateDirectory(d)
	Catch
	End Try
	Return d
End Function

Function RutaConfig() As String
	Return System.IO.Path.Combine(DirDatos(), "config.txt")
End Function

' carpeta de la biblioteca CAD de esta PC (se elige una vez y se recuerda)
Function CarpetaBiblioteca(forzarElegir As Boolean) As String
	Dim raiz As String = ""
	Try
		If System.IO.File.Exists(RutaConfig()) Then
			For Each ln As String In System.IO.File.ReadAllLines(RutaConfig(), System.Text.Encoding.UTF8)
				If ln.StartsWith("RAIZ=") Then raiz = ln.Substring(5).Trim()
			Next
		End If
	Catch
	End Try
	' 1) la carpeta escrita al principio de la regla (CARPETA_CAD)
	If Not forzarElegir AndAlso CARPETA_CAD <> "" Then
		If System.IO.Directory.Exists(CARPETA_CAD) Then Return CARPETA_CAD
		MessageBox.Show("La carpeta CARPETA_CAD escrita al principio de la regla no existe:" & vbCrLf & CARPETA_CAD & vbCrLf & vbCrLf & "Elegila ahora (y corregila en la regla).", "Layout paletizado")
		forzarElegir = True
	End If
	' 2) la ultima elegida en esta PC
	If Not forzarElegir AndAlso raiz <> "" AndAlso System.IO.Directory.Exists(raiz) Then Return raiz
	' 3) se pregunta
	If True Then
		Dim fb As New System.Windows.Forms.FolderBrowserDialog
		fb.Description = "Elegi la carpeta donde estan tus modelos CAD (robots, maquinas, bases, grippers...)"
		fb.UseDescriptionForTitle = True
		If raiz <> "" AndAlso System.IO.Directory.Exists(raiz) Then fb.SelectedPath = raiz
		If fb.ShowDialog() <> System.Windows.Forms.DialogResult.OK Then Return raiz
		raiz = fb.SelectedPath
		CARPETA_CAD = raiz      ' vale para esta sesion; para dejarla fija, escribila al principio de la regla
	End If
	Try
		System.IO.File.WriteAllText(RutaConfig(), "RAIZ=" & raiz & vbCrLf, System.Text.Encoding.UTF8)
	Catch
	End Try
	Return raiz
End Function

' la biblioteca (correcciones de orientacion, bases por robot, etc.) vive DENTRO de la carpeta CAD,
' asi viaja con los modelos. Un Biblioteca_Layout.txt al lado del ensamble tiene prioridad.
Sub CargarBiblioteca(asmDir As String)
	LIBR.Clear()
	Dim raiz As String = CarpetaBiblioteca(False)
	Dim local As String = System.IO.Path.Combine(asmDir, "Biblioteca_Layout.txt")
	Dim enRaiz As String = If(raiz <> "", System.IO.Path.Combine(raiz, "Biblioteca_Layout.txt"), "")
	If System.IO.File.Exists(local) Then
		bibUsada = local
	ElseIf enRaiz <> "" Then
		bibUsada = enRaiz
	Else
		bibUsada = System.IO.Path.Combine(DirDatos(), "Biblioteca_Layout.txt")
	End If
	If Not System.IO.File.Exists(bibUsada) Then
		Try
			If System.IO.File.Exists(BIB_GLOBAL) Then
				System.IO.File.Copy(BIB_GLOBAL, bibUsada)        ' se conserva lo de la version anterior
			Else
				System.IO.File.WriteAllText(bibUsada, BibliotecaPorDefecto(), New System.Text.UTF8Encoding(True))
			End If
			Lg("Se creo la biblioteca " & bibUsada)
		Catch ex As Exception
			Lg("AVISO creando biblioteca: " & ex.Message)
		End Try
	End If
	Try
		For Each ln As String In System.IO.File.ReadAllLines(bibUsada, System.Text.Encoding.UTF8)
			Dim s As String = ln.Trim()
			If s = "" OrElse s.StartsWith("#") OrElse s.StartsWith("'") Then Continue For
			Dim i As Integer = s.IndexOf("="c)
			If i < 1 Then Continue For
			LIBR(s.Substring(0, i).Trim()) = s.Substring(i + 1).Trim()
		Next
	Catch
	End Try
	' la carpeta elegida en esta PC manda sobre la RAIZ escrita en el archivo
	If raiz <> "" Then LIBR("RAIZ") = raiz
End Sub

Function Excluidos() As String()
	Dim ex As String = Bib("EXCLUIR")
	If ex = "" Then ex = "OldVersions;Templates;Design Data;Libraries;Content Center"
	Return ex.Split(";"c)
End Function

Sub Recorrer(dir As String, exc() As String)
	Try
		For Each f As String In System.IO.Directory.GetFiles(dir)
			Dim fl As String = f.ToLower()
			If fl.EndsWith(".ipt") OrElse fl.EndsWith(".iam") Then INDICE.Add(f)
		Next
		For Each d As String In System.IO.Directory.GetDirectories(dir)
			Dim nm As String = System.IO.Path.GetFileName(d)
			Dim saltar As Boolean = False
			For Each e As String In exc
				If e.Trim() <> "" AndAlso String.Equals(nm, e.Trim(), StringComparison.OrdinalIgnoreCase) Then saltar = True
			Next
			If Not saltar Then Recorrer(d, exc)
		Next
	Catch ex As Exception
		Lg("AVISO leyendo " & dir & ": " & ex.Message)
	End Try
End Sub

' devuelve la ruta del modelo de una clave, o "" si es GENERAR / no se encuentra
Function Resolver(clave As String) As String
	Dim v As String = Bib(clave)
	If v.Contains("|") Then v = v.Substring(0, v.IndexOf("|"c))
	v = v.Trim()
	If v = "" OrElse v.ToUpper() = "GENERAR" Then Return ""
	If System.IO.Path.IsPathRooted(v) Then
		If System.IO.File.Exists(v) Then Return v
		Falta(clave, v)
		Return ""
	End If
	Dim patron As String = v.ToLower()
	' "Carpeta\archivo.iam": busca por el final de la ruta (sigue sin depender de donde este la RAIZ)
	If patron.Contains("\") Then
		For Each f As String In INDICE
			If f.ToLower().EndsWith("\" & patron) Then Return f
		Next
		Falta(clave, v & " (no esta en RAIZ)")
		Return ""
	End If
	Dim conComodin As Boolean = patron.Contains("*") OrElse patron.Contains("?")
	Dim mejor As String = "", prof As Integer = 999, tam As Long = 0
	For Each f As String In INDICE
		Dim nm As String = System.IO.Path.GetFileName(f).ToLower()
		Dim coincide As Boolean
		If conComodin Then
			coincide = nm Like patron
		Else
			coincide = (nm = patron)
		End If
		If coincide Then
			Dim p As Integer = f.Split("\"c).Length
			Dim sz As Long = New System.IO.FileInfo(f).Length
			If p < prof OrElse (p = prof AndAlso sz > tam) Then
				mejor = f : prof = p : tam = sz
			End If
		End If
	Next
	If mejor = "" Then Falta(clave, v & " (no esta en RAIZ)")
	Return mejor
End Function

Function Bib(clave As String) As String
	If LIBR.ContainsKey(clave) Then Return LIBR(clave)
	Return ""
End Function

Function MedidasMM(ruta As String) As Double()
	If ruta = "" OrElse Not System.IO.File.Exists(ruta) Then Return New Double() {1000, 1000, 1000}
	Lg("medir " & System.IO.Path.GetFileName(ruta))
	Dim ya As Boolean = EstaAbierto(ruta)
	Dim d As Document = app.Documents.Open(ruta, False)
	Dim o As Object = d
	Dim b As Inventor.Box = o.ComponentDefinition.RangeBox
	Dim r() As Double = {(b.MaxPoint.X - b.MinPoint.X) * 10, (b.MaxPoint.Y - b.MinPoint.Y) * 10, (b.MaxPoint.Z - b.MinPoint.Z) * 10}
	If Not ya Then d.Close(True)
	Return r
End Function

Function EstaAbierto(ruta As String) As Boolean
	For Each d As Document In app.Documents
		If String.Equals(d.FullFileName, ruta, StringComparison.OrdinalIgnoreCase) Then Return True
	Next
	Return False
End Function

Function Existe(ruta As String, nombre As String) As Boolean
	If ruta <> "" AndAlso System.IO.File.Exists(ruta) Then Return True
	If ruta = "" Then Falta(nombre, "(sin modelo)")
	Return False
End Function

Sub Falta(nombre As String, ruta As String)
	Dim s As String = nombre & " -> " & ruta
	If Not faltan.Contains(s) Then faltan.Add(s)
End Sub

Sub DiagArchivo(ruta As String, sb As System.Text.StringBuilder)
	Try
		Dim ya As Boolean = EstaAbierto(ruta)
		Dim d As Document = app.Documents.Open(ruta, False)
		Dim o As Object = d
		Dim b As Inventor.Box = o.ComponentDefinition.RangeBox
		Dim dx As Double = (b.MaxPoint.X - b.MinPoint.X) * 10, dy As Double = (b.MaxPoint.Y - b.MinPoint.Y) * 10, dz As Double = (b.MaxPoint.Z - b.MinPoint.Z) * 10
		sb.AppendLine(String.Format("   Caja (mm): X {0:0}  Y {1:0}  Z {2:0}    min = ({3:0}, {4:0}, {5:0})", dx, dy, dz, b.MinPoint.X * 10, b.MinPoint.Y * 10, b.MinPoint.Z * 10))
		If dz < 0.4 * Math.Max(dx, dy) AndAlso dy > dz Then sb.AppendLine("   (?) parece acostado: si Y es la altura, agregar  | rotX=90  en la biblioteca")
		Dim n As Integer = 0
		For Each p As Inventor.Parameter In o.ComponentDefinition.Parameters
			If Not System.Text.RegularExpressions.Regex.IsMatch(p.Name, "^d\d+$") Then
				sb.AppendLine("   " & p.Name & " = " & p.Expression)
				n += 1
				If n > 40 Then Exit For
			End If
		Next
		If Not ya Then d.Close(True)
	Catch ex As Exception
		sb.AppendLine("   ERROR: " & ex.Message)
	End Try
End Sub

' =====================================================================
'  UTILIDADES
' =====================================================================
' Borunte BRTIRPZ3116B -> 3100 mm ; BRTIRSC810A -> 800 ; KUKA KR_140_R3200 -> 3200
Function AlcanceDesdeNombre(nom As String) As Double
	Dim m As System.Text.RegularExpressions.Match = System.Text.RegularExpressions.Regex.Match(nom.ToUpper(), "BRTIR[A-Z]{2}(\d{3,4})")
	If m.Success Then
		Dim g As String = m.Groups(1).Value.PadLeft(4, "0"c)
		Return CDbl(g.Substring(0, 2)) * 100.0
	End If
	m = System.Text.RegularExpressions.Regex.Match(nom.ToUpper(), "_R(\d{3,4})")
	If m.Success Then Return CDbl(m.Groups(1).Value)
	Return 2000
End Function

Function Union(lst As List(Of Double())) As Double()
	Dim r() As Double = {1.0E+30, 1.0E+30, 1.0E+30, -1.0E+30, -1.0E+30, -1.0E+30}
	For Each b As Double() In lst
		For k As Integer = 0 To 2
			r(k) = Math.Min(r(k), Math.Min(b(k), b(k + 3)))
			r(k + 3) = Math.Max(r(k + 3), Math.Max(b(k), b(k + 3)))
		Next
	Next
	Return r
End Function

Function Inter(a() As Double, b() As Double) As Boolean
	Return a(0) < b(3) AndAlso a(3) > b(0) AndAlso a(1) < b(4) AndAlso a(4) > b(1)
End Function

Sub Lg(s As String)
	logSb.AppendLine("  " & s)
	EscribirLog("  " & DateTime.Now.ToString("HH:mm:ss") & " " & s)
End Sub

' registro fijo de la ultima corrida (para poder revisarlo a distancia)
Sub EscribirLog(s As String)
	Try
		Dim f As String = System.IO.Path.Combine(DirDatos(), "Ultima_corrida.txt")
		System.IO.File.AppendAllText(f, s & vbCrLf, System.Text.Encoding.UTF8)
	Catch
	End Try
End Sub

