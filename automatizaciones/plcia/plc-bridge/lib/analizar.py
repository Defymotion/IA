# -*- coding: utf-8 -*-
"""analizar.py - leer bloques LAD exportados de TIA (Openness XML).
  python analizar.py resumen  bloque.xml            -> una linea por red: partes y simbolos
  python analizar.py cables   bloque.xml [redes] [texto]  -> cableado de cada red (redes '3,5'; texto filtra)
  python analizar.py buscar   carpeta_export simbolo -> en que bloque/red aparece un simbolo
"""
import sys, re, os
import xml.etree.ElementTree as ET
def dump(path,idxs=None,match=None):
    x=open(path,encoding='utf-8-sig').read()
    cus=re.findall(r'<SW.Blocks.CompileUnit .*?</SW.Blocks.CompileUnit>',x,re.S)
    for i,c in enumerate(cus):
        if idxs and i+1 not in idxs: continue
        if match and match not in c: continue
        ns=re.search(r'<NetworkSource>(.*?)</NetworkSource>',c,re.S)
        t=re.findall(r'<Text>([^<]+)</Text>',c)
        print('== red',i+1,'|',t[0][:80] if t else '')
        if not ns: continue
        ns=ns.group(1); acc={}
        for m in re.finditer(r'<Access Scope="(\w+)" UId="(\d+)">(.*?)</Access>',ns,re.S):
            comps=re.findall(r'<Component Name="([^"]+)"',m.group(3)); cv=re.findall(r'<ConstantValue>([^<]*)',m.group(3))
            acc[m.group(2)]='.'.join(comps) if comps else 'K'+(cv[0] if cv else '?')
        parts={u:n+('NEG' if b and 'Negated' in b else '') for n,u,b in re.findall(r'<Part Name="(\w+)" UId="(\d+)"[^>]*?(?:/>|>(.*?)</Part>)',ns,re.S)}
        for w in re.findall(r'<Wire UId="\d+">(.*?)</Wire>',ns,re.S):
            o=[]
            for e in re.findall(r'<(Powerrail|IdentCon UId="\d+"|NameCon UId="\d+" Name="\w+"|OpenCon UId="\d+")',w):
                if e=='Powerrail': o.append('RAIL')
                elif e.startswith('IdentCon'): o.append(acc[re.search(r'\d+',e).group()])
                elif e.startswith('NameCon'): u,nm=re.findall(r'UId="(\d+)" Name="(\w+)"',e)[0]; o.append(f'{parts.get(u,"?")}{u}.{nm}')
                else: o.append('open')
            print('   ',' -> '.join(o))
def strip(t): return re.sub(r'\{[^}]*\}','',t)
def resumen(f):
  r=ET.parse(f).getroot()
  for blk in r:
      if not strip(blk.tag).startswith('SW.Blocks'): continue
      al=blk.find('AttributeList')
      g=lambda k:(al.find(k).text if al is not None and al.find(k) is not None else None)
      print('##',strip(blk.tag),g('Name'),g('Number'),g('ProgrammingLanguage'))
      for cu in blk.iter('SW.Blocks.CompileUnit'):
          a=cu.find('AttributeList'); lang=a.find('ProgrammingLanguage').text if a.find('ProgrammingLanguage') is not None else ''
          tt=[t.text for t in cu.iter() if strip(t.tag)=='Text' and t.text]
          title=''
          for mt in cu.iter():
            if strip(mt.tag)=='MultilingualText' and mt.get('CompositionName')=='Title':
              xs=[t.text for t in mt.iter() if strip(t.tag)=='Text' and t.text]; title=xs[0] if xs else ''; break
          src=cu.find('.//NetworkSource')
          syms=[];parts=[];calls=[]
          if src is not None:
              for ac in src.iter():
                  if strip(ac.tag)=='Access':
                      comps=[c.get('Name') for c in ac.iter() if strip(c.tag)=='Component']
                      if comps: syms.append('.'.join(comps))
                      else:
                          c=[x for x in ac.iter() if strip(x.tag)=='ConstantValue']
                          if c: syms.append('#'+(c[0].text or ''))
                      ad=[x.get('Name') for x in ac.iter() if strip(x.tag)=='Address']
                  elif strip(ac.tag)=='Part': parts.append(ac.get('Name'))
                  elif strip(ac.tag)=='Call':
                      ci=[x for x in ac.iter() if strip(x.tag)=='CallInfo']; calls.append(ci[0].get('Name') if ci else '?')
          print(f' [{lang}] {title[:50]!r} parts={",".join(dict.fromkeys(parts))} calls={calls} syms={list(dict.fromkeys(syms))}')

def buscar(carpeta, simbolo):
    for dp, _, fs in os.walk(carpeta):
        for f in fs:
            if not f.endswith('.xml'): continue
            p = os.path.join(dp, f); x = open(p, encoding='utf-8-sig').read()
            if simbolo not in x: continue
            cus = re.findall(r'<SW.Blocks.CompileUnit .*?</SW.Blocks.CompileUnit>', x, re.S)
            redes = [str(i + 1) for i, c in enumerate(cus) if simbolo in c]
            print('%s  redes: %s' % (os.path.relpath(p, carpeta), ','.join(redes) if redes else '(interfaz/tags)'))
if __name__ == '__main__':
    c = sys.argv[1]
    if c == 'resumen': resumen(sys.argv[2])
    elif c == 'cables': dump(sys.argv[2], [int(a) for a in sys.argv[3].split(',')] if len(sys.argv) > 3 and sys.argv[3] else None, sys.argv[4] if len(sys.argv) > 4 else None)
    elif c == 'buscar': buscar(sys.argv[2], sys.argv[3])
    else: print(__doc__)
