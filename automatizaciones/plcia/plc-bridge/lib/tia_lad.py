# -*- coding: utf-8 -*-
"""tia_lad.py - generar redes LAD (FlgNet v4) e insertarlas en bloques exportados de TIA Portal (Openness V17).
Probado con S7-1500 y TIA V17. Uso tipico:

    from tia_lad import *
    x = rd('export/bloques_plc/FC30.xml'); base = [max(0x900, maxid(x) + 0x10)]
    red = new_cu(base[0], 'Titulo de la red', net_move([('Mi_Bit', False)], 'HMI_DB|Origen', 'HMI_DB|Destino'))
    x = insertar_despues(x, 'texto que identifica la red anterior', red)
    validar(x); wr('import_plc/FC30.xml', x)

Simbolos: 'Tag' o 'DB|Miembro' (| separa componentes). Contactos: (tag, negado) o ('P'|'N', tag, memoria_flanco).
Salidas de bobinas: [('Coil'|'SCoil'|'RCoil', tag)].
Reglas: IDs de CompileUnit/MultilingualText en HEX y unicos en el archivo (arrancar en maxid+0x10);
UIds unicos dentro de cada red; TON con instancia en un DB global (db, miembro IEC_TIMER).
"""
import re, collections
def rd(p): return open(p,encoding='utf-8-sig').read()
def wr(p,s): open(p,'w',encoding='utf-8-sig',newline='\r\n').write(s)
def esc(s): return s.replace('&','&amp;')
class Net:
    def __init__(s): s.acc=[];s.parts=[];s.wires=[];s.u=20
    def uid(s): s.u+=1; return s.u
    def sym(s,name):
        u=s.uid(); comps=''.join(f'<Component Name="{esc(c)}" />' for c in name.split('|'))
        s.acc.append(f'<Access Scope="GlobalVariable" UId="{u}"><Symbol>{comps}</Symbol></Access>'); return u
    def part(s,name,neg=False,extra=''):
        u=s.uid()
        if neg: s.parts.append(f'<Part Name="{name}" UId="{u}"><Negated Name="operand" /></Part>')
        elif extra: s.parts.append(f'<Part Name="{name}" UId="{u}"{extra[0]}>{extra[1]}</Part>')
        else: s.parts.append(f'<Part Name="{name}" UId="{u}" />')
        return u
    def wire(s,*cons):
        u=s.uid(); s.wires.append(f'<Wire UId="{u}">'+''.join(cons)+'</Wire>')
    def ident(s,u): return f'<IdentCon UId="{u}" />'
    def name(s,u,n): return f'<NameCon UId="{u}" Name="{n}" />'
    def xml(s):
        return ('<FlgNet xmlns="http://www.siemens.com/automation/Openness/SW/NetworkSource/FlgNet/v4"><Parts>'+''.join(s.acc+s.parts)+'</Parts><Wires>'+''.join(s.wires)+'</Wires></FlgNet>')
def k(n,val,typ):
    u=n.uid(); n.acc.append(f'<Access Scope="LiteralConstant" UId="{u}"><Constant><ConstantType>{typ}</ConstantType><ConstantValue>{val}</ConstantValue></Constant></Access>'); return u
def chain(n,conds,prev=None):
    for c in conds:
        if c[0]=='P' or c[0]=='N':
            kind,tag,mem=c; ut=n.sym(tag); um=n.sym(mem); p=n.part('PContact' if kind=='P' else 'NContact')
            n.wire('<Powerrail />' if prev is None else n.name(prev,'out'),n.name(p,'pre')); n.wire(n.ident(um),n.name(p,'bit')); n.wire(n.ident(ut),n.name(p,'operand'))
        else:
            tag,neg=c; u=n.sym(tag); p=n.part('Contact',neg)
            n.wire('<Powerrail />' if prev is None else n.name(prev,'out'),n.name(p,'in')); n.wire(n.ident(u),n.name(p,'operand'))
        prev=p
    return prev
def outs(n,prev,o,pin='out'):
    cs=[]
    for kind,tag in o: ut=n.sym(tag); p=n.part(kind); cs.append((p,ut))
    n.wire(n.name(prev,pin),*[n.name(p,'in') for p,_ in cs])
    for p,ut in cs: n.wire(n.ident(ut),n.name(p,'operand'))
def net_flanks(conds,o): n=Net(); prev=chain(n,conds); outs(n,prev,o); return n.xml()
def net_movek(conds,val,typ,dst):
    n=Net(); prev=chain(n,conds); uk=k(n,val,typ); ud=n.sym(dst)
    m=n.part('Move',extra=(' DisabledENO="true"','<TemplateValue Name="Card" Type="Cardinality">1</TemplateValue>'))
    n.wire(n.name(prev,'out'),n.name(m,'en')); n.wire(n.ident(uk),n.name(m,'in')); n.wire(n.name(m,'out1'),n.ident(ud)); return n.xml()
def net_move(conds,src,dst):
    n=Net(); prev=chain(n,conds); us=n.sym(src); ud=n.sym(dst)
    m=n.part('Move',extra=(' DisabledENO="true"','<TemplateValue Name="Card" Type="Cardinality">1</TemplateValue>'))
    n.wire('<Powerrail />' if prev is None else n.name(prev,'out'),n.name(m,'en')); n.wire(n.ident(us),n.name(m,'in')); n.wire(n.name(m,'out1'),n.ident(ud)); return n.xml()
def net_eq(conds,a,val,typ,o):
    n=Net(); prev=chain(n,conds); ua=n.sym(a); uk=k(n,val,typ)
    e=n.part('Eq',extra=('',f'<TemplateValue Name="SrcType" Type="Type">{typ}</TemplateValue>'))
    n.wire(n.name(prev,'out'),n.name(e,'pre')); n.wire(n.ident(ua),n.name(e,'in1')); n.wire(n.ident(uk),n.name(e,'in2'))
    outs(n,e,o); return n.xml()
def net_ton(conds,timer,pt,o,db):
    n=Net(); prev=chain(n,conds)
    upt=n.uid(); n.acc.append(f'<Access Scope="TypedConstant" UId="{upt}"><Constant><ConstantValue>{pt}</ConstantValue></Constant></Access>')
    ui=n.uid()
    t=n.part('TON',extra=(' Version="1.0"',f'<Instance Scope="GlobalVariable" UId="{ui}"><Component Name="{db}" /><Component Name="{timer}" /></Instance><TemplateValue Name="time_type" Type="Type">Time</TemplateValue>'))
    n.wire(n.name(prev,'out'),n.name(t,'IN')); n.wire(n.ident(upt),n.name(t,'PT'))
    uo=n.uid(); n.wire(n.name(t,'ET'),f'<OpenCon UId="{uo}" />')
    outs(n,t,o,'Q'); return n.xml()
def cus_of(x): return list(re.finditer(r'<SW.Blocks.CompileUnit .*?</SW.Blocks.CompileUnit>',x,re.S))
def ml(i,txt,comp):
    return f'<MultilingualText ID="{i:X}" CompositionName="{comp}"><ObjectList><MultilingualTextItem ID="{i+1:X}" CompositionName="Items"><AttributeList><Culture>en-US</Culture><Text>{esc(txt)}</Text></AttributeList></MultilingualTextItem><MultilingualTextItem ID="{i+2:X}" CompositionName="Items"><AttributeList><Culture>es-ES</Culture><Text>{esc(txt)}</Text></AttributeList></MultilingualTextItem></ObjectList></MultilingualText>'
def new_cu(i,title,x):
    return f'''<SW.Blocks.CompileUnit ID="{i:X}" CompositionName="CompileUnits">
        <AttributeList>
          <NetworkSource>{x}</NetworkSource>
          <ProgrammingLanguage>LAD</ProgrammingLanguage>
        </AttributeList>
        <ObjectList>
          {ml(i+1,'','Comment')}
          {ml(i+4,title,'Title')}
        </ObjectList>
      </SW.Blocks.CompileUnit>
      '''
def maxid(x): return max(int(v,16) for v in re.findall(r'(?<![A-Za-z])ID="([0-9A-Fa-f]+)"',x))
def insertar_antes(x, marca, redes):
    m = [c for c in cus_of(x) if marca in c.group()]; assert len(m) == 1, 'marca ambigua o inexistente: %r (%d)' % (marca, len(m))
    return x[:m[0].start()] + redes + x[m[0].start():]
def insertar_despues(x, marca, redes):
    m = [c for c in cus_of(x) if marca in c.group()]; assert len(m) == 1, 'marca ambigua o inexistente: %r (%d)' % (marca, len(m))
    return x[:m[0].end()] + '\n      ' + redes.rstrip() + x[m[0].end():]
def reemplazar(x, marca, redes):
    m = [c for c in cus_of(x) if marca in c.group()]; assert len(m) == 1, 'marca ambigua o inexistente: %r (%d)' % (marca, len(m))
    return x[:m[0].start()] + redes.rstrip() + x[m[0].end():]

# ---------- HMI (WinCC Comfort/Advanced) ----------
def hmi_obj(t, nombre):
    """(inicio, fin) del objeto de pantalla con ObjectName = nombre"""
    i = t.find('<ObjectName>%s</ObjectName>' % nombre); assert i > 0, nombre
    st = t.rfind('<Hmi.Screen.', 0, i); tag = re.match(r'<(Hmi\.Screen\.\w+)', t[st:]).group(1)
    return st, t.find('</%s>' % tag, i) + len(tag) + 3
def set_attr(b, k, v):
    assert re.search('<%s>[^<]*</%s>' % (k, k), b), k
    return re.sub('<%s>[^<]*</%s>' % (k, k), '<%s>%s</%s>' % (k, v, k), b, count=1)
_cnt = [0]
def renumerar(s, prefijo):
    """IDs nuevos para un objeto clonado (los IDs de pantallas/tags HMI pueden ser texto)"""
    def f(m): _cnt[0] += 1; return 'ID="%s%d"' % (prefijo, _cnt[0])
    return re.sub(r'(?<![A-Za-z])ID="[^"]*"', f, s)

# ---------- validacion ----------
def validar(s, nombre='xml'):
    import xml.dom.minidom as xd
    xd.parseString(s.encode('utf-8'))
    c = collections.Counter(re.findall(r'(?<![A-Za-z])ID="([^"]*)"', s)); dup = [a for a, v in c.items() if v > 1]
    assert not dup, '%s: IDs duplicados %s' % (nombre, dup[:5])
    for net in re.findall(r'<NetworkSource>(.*?)</NetworkSource>', s, re.S):
        u = collections.Counter(re.findall(r'UId="(\d+)"', re.sub(r'<(?:IdentCon|NameCon)[^>]*>', '', net)))
        assert not any(v > 1 for v in u.values()), '%s: UId duplicado en una red' % nombre
    return len(re.findall('<SW.Blocks.CompileUnit ', s))
net_coils = net_flanks  # contactos en serie -> bobinas en paralelo
