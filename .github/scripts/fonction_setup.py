#!/usr/bin/env python3
"""Ajoute l'onglet « Fonction » (description + captures + animation) à une appli Android.

Usage :
  fonction_setup.py <dossier_module_android> <config.json> <app.zip|-> [icon.png]

Le projet de l'utilisateur peut contenir, à sa racine :
  Description.md   texte de présentation (le champ « Description » du formulaire a priorité)
  Captures/        images (png, jpg, webp, gif, avif)
  Animation/       animation.html (ou index.html) + ses ressources éventuelles

Ce script :
  1. extrait ces éléments dans <module>/src/main/assets/omni_fonction/
  2. y copie l'écran d'affichage (.github/fonction/viewer/index.html) avec les données intégrées
  3. ajoute les classes Java studio.apk.fonction.* et leurs déclarations dans AndroidManifest.xml
Rien n'est modifié dans le code du projet : l'onglet est installé automatiquement au démarrage.
"""
import json
import os
import re
import shutil
import sys
import zipfile
from urllib.parse import quote

HERE = os.path.dirname(os.path.abspath(__file__))
TPL = os.path.normpath(os.path.join(HERE, '..', 'fonction'))
IMG = re.compile(r'\.(png|jpe?g|webp|gif|avif)$', re.I)
MAX_CAPS, MAX_CAP_BYTES, MAX_ANIM_BYTES = 30, 8 * 1024 * 1024, 12 * 1024 * 1024
PKG_DIR = os.path.join('studio', 'apk', 'fonction')


def nat(s):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r'(\d+)', s)]


def propre(nom):
    """Nom de fichier sûr (ASCII) : pas de chemin, pas d'espace."""
    nom = os.path.basename(nom.replace('\\', '/'))
    return re.sub(r'[^A-Za-z0-9._-]+', '_', nom).strip('._') or 'fichier'


def joli(nom):
    base = os.path.splitext(os.path.basename(nom))[0]
    base = re.sub(r'^\d+[\s._-]*', '', base)
    return re.sub(r'[_-]+', ' ', base).strip() or os.path.splitext(os.path.basename(nom))[0]


def lire_projet(zpath):
    """Retourne (description, [(nom, octets)], {chemin_relatif: octets}, page_animation)."""
    desc, caps, anim, page = '', [], {}, None
    if not zpath or zpath == '-' or not os.path.exists(zpath):
        return desc, caps, anim, page
    with zipfile.ZipFile(zpath) as z:
        noms = [n for n in z.namelist()
                if not n.endswith('/') and not n.startswith('__MACOSX') and not re.search(r'(^|/)\._', n)]
        prem = noms[0].split('/')[0] if noms else ''
        wrap = prem + '/' if noms and all('/' in n and n.split('/')[0] == prem for n in noms) else ''

        def rel(n):
            return n[len(wrap):] if wrap and n.startswith(wrap) else n

        md = next((n for n in noms if re.fullmatch(r'description\.md', rel(n), re.I)), None)
        if md:
            desc = z.read(md).decode('utf-8', 'replace').lstrip('\ufeff').replace('\r\n', '\n').replace('\r', '\n').strip()

        cn = sorted((n for n in noms if re.match(r'captures?/.', rel(n), re.I) and IMG.search(n)),
                    key=lambda n: nat(rel(n)))
        for n in cn:
            if len(caps) >= MAX_CAPS:
                print('Captures : limite de %d atteinte, les suivantes sont ignorées' % MAX_CAPS)
                break
            info = z.getinfo(n)
            if info.file_size > MAX_CAP_BYTES:
                print('Capture ignorée (> 8 Mo) :', rel(n))
                continue
            caps.append((rel(n).split('/', 1)[1], z.read(n)))

        an = [n for n in noms if re.match(r'animations?/.', rel(n), re.I)]
        total = 0
        for n in an:
            sous = rel(n).split('/', 1)[1]
            parts = [p for p in sous.split('/') if p]
            if not parts or any(p in ('.', '..') for p in parts):
                continue
            total += z.getinfo(n).file_size
            if total > MAX_ANIM_BYTES:
                print('Animation : dossier trop gros (> 12 Mo), fichiers suivants ignorés')
                break
            anim['/'.join(propre(p) for p in parts)] = z.read(n)
        tops = sorted((k for k in anim if '/' not in k and re.search(r'\.html?$', k, re.I)), key=nat)
        for pref in ('animation.html', 'index.html'):
            if pref in [t.lower() for t in tops]:
                page = next(t for t in tops if t.lower() == pref)
                break
        if not page and tops:
            page = tops[0]
        if not page:  # pas de page à la racine du dossier : première page trouvée
            deep = sorted((k for k in anim if re.search(r'\.html?$', k, re.I)), key=nat)
            page = deep[0] if deep else None
    return desc, caps, anim, page


def patcher_manifeste(mp):
    s = open(mp, encoding='utf-8').read()
    if 'studio.apk.fonction' in s:
        print('Manifeste : onglet Fonction déjà déclaré')
        return
    bloc = (
        '    <activity android:name="studio.apk.fonction.FonctionActivity" android:exported="false"\n'
        '        android:label="Fonction" android:theme="@android:style/Theme.DeviceDefault.Light.NoActionBar"\n'
        '        android:configChanges="orientation|screenSize|keyboardHidden|smallestScreenSize|screenLayout|uiMode"/>\n'
        '    <provider android:name="studio.apk.fonction.FonctionInit"\n'
        '        android:authorities="${applicationId}.fonctioninit" android:exported="false" android:initOrder="100"/>\n')
    if '</application>' not in s:
        sys.exit('AndroidManifest.xml sans balise </application> : onglet Fonction impossible.')
    s = s.replace('</application>', bloc + '  </application>', 1)
    open(mp, 'w', encoding='utf-8').write(s)
    print('Manifeste : onglet Fonction déclaré')


def main():
    if len(sys.argv) < 4:
        sys.exit(__doc__)
    mod, cfgp, zpath = sys.argv[1], sys.argv[2], sys.argv[3]
    iconp = sys.argv[4] if len(sys.argv) > 4 else ''
    cfg = json.load(open(cfgp, encoding='utf-8'))
    main_dir = os.path.join(mod, 'src', 'main')
    mp = os.path.join(main_dir, 'AndroidManifest.xml')
    if not os.path.exists(mp):
        sys.exit('AndroidManifest.xml introuvable dans ' + main_dir)

    desc_zip, caps, anim, page = lire_projet(zpath)
    desc = (cfg.get('description') or '').strip() or desc_zip

    # style d'animation choisi dans le générateur : on ajoute seulement une feuille de style,
    # le scénario et les données de l'animation restent intacts
    css = cfg.get('animCss')
    if isinstance(css, str) and css and '<' not in css and len(css) < 20000 and page and page in anim:
        h = anim[page].decode('utf-8', 'replace')
        tag = '<style id="omni-style">' + css + '</style>'
        h = re.sub(r'</head>', lambda m: tag + '</head>', h, count=1, flags=re.I) if re.search(r'</head>', h, re.I) else tag + h
        anim[page] = h.encode('utf-8')
        print("Animation : style « %s » appliqué" % cfg.get('animStyle', '?'))

    out = os.path.join(main_dir, 'assets', 'omni_fonction')
    shutil.rmtree(out, ignore_errors=True)
    os.makedirs(os.path.join(out, 'captures'), exist_ok=True)

    data = {'name': cfg.get('name') or 'Application', 'version': cfg.get('versionName') or '',
            'icon': None, 'description': desc, 'captures': [], 'animation': None,
            'color': cfg.get('color') if re.fullmatch(r'#[0-9a-fA-F]{6}', str(cfg.get('color') or '')) else None}

    for i, (nom, octets) in enumerate(caps, 1):
        fich = '%02d_%s' % (i, propre(nom))
        open(os.path.join(out, 'captures', fich), 'wb').write(octets)
        data['captures'].append({'src': 'captures/' + quote(fich), 'name': joli(nom)})

    if anim and page:
        for k, octets in anim.items():
            dest = os.path.join(out, 'animation', *k.split('/'))
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            open(dest, 'wb').write(octets)
        data['animation'] = 'animation/' + '/'.join(quote(p) for p in page.split('/'))

    if iconp and os.path.exists(iconp):
        shutil.copy(iconp, os.path.join(out, 'icon.png'))
        data['icon'] = 'icon.png'

    # écran d'affichage avec les données intégrées (pas de fetch : file:// l'interdit dans une WebView)
    html = open(os.path.join(TPL, 'viewer', 'index.html'), encoding='utf-8').read()
    js = json.dumps(data, ensure_ascii=False).replace('</', '<\\/').replace('\u2028', '\\u2028').replace('\u2029', '\\u2029')
    html, n = re.subn(r'/\*__DATA_START__\*/.*?/\*__DATA_END__\*/',
                      lambda m: '/*__DATA_START__*/' + js + '/*__DATA_END__*/', html, count=1, flags=re.S)
    if n != 1:
        sys.exit('Marqueurs de données introuvables dans viewer/index.html')
    open(os.path.join(out, 'index.html'), 'w', encoding='utf-8').write(html)

    # classes Java
    jd = os.path.join(main_dir, 'java', PKG_DIR)
    os.makedirs(jd, exist_ok=True)
    for f in ('FonctionInit.java', 'FonctionTab.java', 'FonctionActivity.java'):
        shutil.copy(os.path.join(TPL, 'java', f), os.path.join(jd, f))

    patcher_manifeste(mp)

    # R8/ProGuard (builds release) : garde les classes de l'onglet
    pg = os.path.join(mod, 'proguard-rules.pro')
    try:
        with open(pg, 'a', encoding='utf-8') as f:
            f.write('\n# Onglet Fonction (APK Studio)\n-keep class studio.apk.fonction.** { *; }\n'
                    '-keepclassmembers class * { @android.webkit.JavascriptInterface <methods>; }\n')
    except OSError:
        pass

    print('Onglet Fonction : description %s · %d capture(s) · animation %s'
          % ('oui (%d car.)' % len(desc) if desc else 'non', len(data['captures']),
             data['animation'] or 'non'))


if __name__ == '__main__':
    main()
