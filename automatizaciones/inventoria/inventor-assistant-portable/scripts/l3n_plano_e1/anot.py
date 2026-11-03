# --- pasillos y zonas (coordenadas Inventor X, Z en mm) ---
PN=rect(3727,9468,-38573,-36386)      # pasillo transpaleta norte (entre T3 y la pared)
PE=rect(14206,16029,-36350,-30645)    # pasillo transpaleta este (desde la envolvedora)
AE=rect(5002,9012,-35019,-30572)      # zona de maniobra del autoelevador (retiro de la salida)
for R_,lay in ((PN,'DEFY_E1_PASILLOS_TRANSPALETA'),(PE,'DEFY_E1_PASILLOS_TRANSPALETA'),(AE,'DEFY_E1_ZONA_AUTOELEVADOR')):
    poly(R_,lay)
    hatch(R_,lay,'ANSI37' if 'AUTO' in lay else 'ANSI31',0.05)
texto("PASILLO TRANSPALETA\\P2,21 m libres",6600,-37480,0.22,'DEFY_E1_PASILLOS_TRANSPALETA')
texto("PASILLO TRANSPALETA\\P3,2 m libres desde la envolvedora",15120,-33500,0.22,'DEFY_E1_PASILLOS_TRANSPALETA',rot=90)
texto("ZONA AUTOELEVADOR\\P4,1 m x 4,5 m\\P(retiro de pallets envueltos)",7000,-32800,0.22,'DEFY_E1_ZONA_AUTOELEVADOR')
# --- recorridos ---
flecha([(7200,-26900),(7200,-32800),(-9200,-32800)],'DEFY_E1_RECORRIDO_REPOSICION_PALLETS')
texto("REPOSICIÓN DE BUFFERS DE PALLETS\\P(normal y exportación)",-1500,-32300,0.22,'DEFY_E1_RECORRIDO_REPOSICION_PALLETS')
flecha([(14600,-26900),(14600,-37500),(-3500,-37500),(-3500,-54100),(-9300,-54100)],'DEFY_E1_RECORRIDO_INSUMOS_CARTONES')
texto("INSUMOS DEL BUFFER DE CARTONES",5000,-38000,0.22,'DEFY_E1_RECORRIDO_INSUMOS_CARTONES')
texto("Insumos de cartones\\P(tramo a confirmar en planta)",-3000,-47000,0.2,'DEFY_E1_RECORRIDO_INSUMOS_CARTONES',rot=90)
# --- cotas de pasillos ---
cota(2500,-35041,2500,-31334,'3,70 m')
cota(4950,-30200,9040,-30200,'4,10 m')
cota(6000,-38590,6000,-36381,'2,21 m')
cota(12840,-33000,16036,-33000,'3,20 m')
# --- puerta a reubicar (pared norte del cuarto, junto al buffer de cartones) ---
x0,x1,yp=3862.75,3863.65,1299.40
msp.add_lwpolyline([(x0-0.15,yp-0.25),(x1+0.15,yp-0.25),(x1+0.15,yp+0.25),(x0-0.15,yp+0.25)],close=True,dxfattribs={'layer':'DEFY_E1_PUERTA_A_REUBICAR','const_width':0.04})
msp.add_line((x0,yp-0.25),(x1,yp+0.25),dxfattribs={'layer':'DEFY_E1_PUERTA_A_REUBICAR'})
msp.add_line((x0,yp+0.25),(x1,yp-0.25),dxfattribs={'layer':'DEFY_E1_PUERTA_A_REUBICAR'})
msp.add_mtext("PUERTA A ANULAR: se reubica en la pared contigua\\P(ubicación a definir) para dejar el paso al buffer de cartones",
              dxfattribs={'layer':'DEFY_E1_PUERTA_A_REUBICAR','char_height':0.2,'insert':(3858.0,1301.0),'attachment_point':5})
# --- rótulos de equipos ---
for t_,X,Z,r in [("CELDA A (nueva): mesas, pallet, barrera y reja este 300 mm hacia atrás",-11200,-37200,0),
                 ("Cruz A S-11211 (rodillos alineados con las camas B/C)",-5300,-34300,0),
                 ("T3: acumulación sobre cadenas (8 módulos)",2000,-34350,90),
                 ("Cruz S-11256",10800,-37000,0),("T2 S-11261",12300,-34284,0),
                 ("T2 S-11259 + envolvedora MP402 girada 90°",13300,-32880,90),
                 ("Salida S-11219 / S-11226",12300,-30200,90),
                 ("RESERVA ETAPA 2\\Ppallet cautivo 3,5 x 5,0 m",10640,-27900,0),
                 ("Extensión del riel del robot aéreo +2 m\\Py BUFFER DE CARTONES nuevo",-12900,-54800,0)]:
    texto(t_,X,Z,0.22,'DEFY_E1_TEXTOS',rot=r)
# --- leyenda ---
LEY=("MODIFICACIONES DEFYMOTION - ETAPA 1 (03/11/2026)\\P"
     "Layout final de la línea de pallets (v7) sobre el plano de planta.\\P"
     "Capas DEFY_E1_*: transportes redistribuidos (naranja), envolvedora MP402 girada 90° (magenta),\\P"
     "celda A nueva (azul), extensión del riel y buffer de cartones (cian), reserva etapa 2 (verde),\\P"
     "pasillos de transpaleta (gris), zona de autoelevador (rojo), recorridos de reposición de pallets\\P"
     "(rojo) e insumos de cartones (bordó), puerta a reubicar.\\P"
     "Pendiente: reforma de las cadenas de los transportes a ±450 mm o rodillos en la salida; ubicación de la\\P"
     "puerta nueva; durante el envuelto, T2 S-11261 y la salida 1 vacías (barrido del brazo).")
msp.add_mtext(LEY,dxfattribs={'layer':'DEFY_E1_TEXTOS','char_height':0.25,'insert':(3847.6,1281.5),'attachment_point':1,'width':12.0})
