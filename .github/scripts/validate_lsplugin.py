#!/usr/bin/env python3
"""Validation stricte d'un paquet LinkShare contrat 2 / v1.7."""
import hashlib,json,re,struct,sys,zipfile

def fail(s): raise SystemExit('ERREUR VALIDATION .lsplugin: '+s)
def uleb(b,o):
    v=0; shift=0
    while True:
        x=b[o];o+=1;v|=(x&127)<<shift
        if not x&128:return v,o
        shift+=7

def dex_info(b):
    if len(b)<112 or b[:4]!=b'dex\n' or b[7]!=0: fail('classes.dex absent ou signature DEX invalide.')
    def u(off): return struct.unpack_from('<I',b,off)[0]
    ss,so,ts,to,cs,co=u(56),u(60),u(64),u(68),u(96),u(100)
    strings=[]
    for i in range(ss):
        off=u(so+4*i);_,off=uleb(b,off);end=b.find(b'\0',off)
        if end<0: fail('table des chaînes DEX corrompue.')
        strings.append(b[off:end].decode('utf-8','replace'))
    types=[strings[u(to+4*i)] for i in range(ts)]
    defs=[]; direct={}
    for i in range(cs):
        p=co+32*i; ci=u(p); desc=types[ci]
        defs.append(desc)
        interfaces=u(p+12)
        if interfaces:
            count=u(interfaces); vals=[struct.unpack_from('<H',b,interfaces+4+2*j)[0] for j in range(count)]
            direct[desc]=[types[x] for x in vals]
    return set(defs),direct,set(strings)

def main(path):
    try: z=zipfile.ZipFile(path)
    except Exception as e: fail('archive ZIP illisible: '+str(e))
    if z.testzip(): fail('CRC ZIP invalide: '+str(z.testzip()))
    names=z.namelist()
    if len(names)!=len(set(names)): fail('entrées ZIP en double.')
    for n in names:
        if n.startswith('/') or '\\' in n or any(x in ('..','') for x in n.split('/')[:-1]): fail('chemin dangereux: '+n)
        if n.endswith('.class') or n.endswith('.jar') or n.endswith('android.jar'): fail('fichier interdit embarqué: '+n)
    if 'plugin.json' not in names or 'classes.dex' not in names: fail('plugin.json et classes.dex sont obligatoires.')
    try: m=json.loads(z.read('plugin.json'))
    except Exception as e: fail('plugin.json invalide: '+str(e))
    required=('id','name','version','description','entryClass','contract','permissions','actions','settings','sha256')
    for k in required:
        if k not in m: fail('champ obligatoire absent: '+k)
    if m['contract']!=2: fail('contract doit être 2.')
    if not re.fullmatch(r'[a-z0-9][a-z0-9_-]{1,39}',str(m['id'])): fail('id invalide.')
    if not isinstance(m['sha256'],dict): fail('sha256 doit être un objet.')
    if set(m['sha256'])!=set(names)-{'plugin.json'}: fail('sha256 doit couvrir exactement chaque fichier sauf plugin.json.')
    for n,h in m['sha256'].items():
        if not re.fullmatch(r'[0-9a-f]{64}',str(h)) or hashlib.sha256(z.read(n)).hexdigest()!=h: fail('empreinte SHA-256 incorrecte: '+n)
    if not isinstance(m['permissions'],list) or any(x not in ('storage','notifications','network') for x in m['permissions']): fail('permission non autorisée.')
    if not isinstance(m['actions'],list) or not m['actions']: fail('actions[] doit contenir au moins une action.')
    ids=[]
    for a in m['actions']:
        if not isinstance(a,dict) or not re.fullmatch(r'[A-Za-z0-9_.-]{1,40}',str(a.get('id',''))) or not a.get('label'): fail('action invalide.')
        ids.append(a['id'])
    if len(ids)!=len(set(ids)): fail('IDs actions dupliqués.')
    if not isinstance(m['settings'],list): fail('settings doit être une liste.')
    defs,direct,strings=dex_info(z.read('classes.dex'))
    entry='L'+str(m['entryClass']).replace('.','/')+';'
    if entry not in defs: fail('entryClass absente des définitions DEX: '+str(m['entryClass']))
    api='Lcom/linkshare/plugin/api/LinkSharePlugin;'
    if api not in direct.get(entry,[]): fail('entryClass ne déclare pas directement LinkSharePlugin dans le DEX.')
    forbidden=('Lcom/linkshare/plugin/api/','Lkotlin/','Lkotlinx/','Landroid/','Landroidx/','Ljava/','Ljavax/','Ldalvik/')
    for d in defs:
        if d.startswith(forbidden): fail('classe fournie par Android/LinkShare embarquée dans DEX: '+d)
    for aid in ids:
        if aid not in strings: fail('ID action non retrouvé dans les constantes DEX: '+aid)
    print('VALIDATION OK: contrat 2, entryClass, actions, ZIP et SHA-256 ('+str(len(names)-1)+' fichier(s)).')
if __name__=='__main__':
    if len(sys.argv)!=2: fail('usage: validate_lsplugin.py fichier.lsplugin')
    main(sys.argv[1])
