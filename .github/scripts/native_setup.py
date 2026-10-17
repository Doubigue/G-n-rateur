#!/usr/bin/env python3
"""Adapte un projet fourni par l'utilisateur (Android natif, React Native/Expo, Python/Kivy)
aux réglages saisis dans APK Studio : nom, paquet, version, orientation, autorisations.

Usage :
  native_setup.py gradle <config.json> <racine_du_projet_android>   (Kotlin/Java et React Native)
  native_setup.py expo   <config.json> <racine_du_projet>            (React Native / Expo : app.json)
  native_setup.py spec   <config.json> <buildozer.spec>             (Python / Kivy)
  native_setup.py find   <dossier> <fichier> [<fichier>…]           (affiche le chemin le moins profond)
"""
import glob
import html
import json
import os
import re
import sys

TABLE = {
    'storage': ['READ_EXTERNAL_STORAGE', 'WRITE_EXTERNAL_STORAGE'],
    'media': ['READ_MEDIA_IMAGES', 'READ_MEDIA_VIDEO', 'READ_MEDIA_AUDIO'],
    'allfiles': ['MANAGE_EXTERNAL_STORAGE'],
    'camera': ['CAMERA'],
    'micro': ['RECORD_AUDIO', 'MODIFY_AUDIO_SETTINGS'],
    'location': ['ACCESS_FINE_LOCATION', 'ACCESS_COARSE_LOCATION'],
    'notifications': ['POST_NOTIFICATIONS'],
    'contacts': ['READ_CONTACTS', 'WRITE_CONTACTS'],
    'calendar': ['READ_CALENDAR', 'WRITE_CALENDAR'],
    'bluetooth': ['BLUETOOTH_CONNECT', 'BLUETOOTH_SCAN'],
    'phone': ['READ_PHONE_STATE', 'CALL_PHONE'],
}
# Toujours demandées : réseau, vibration, et notifications (Android 13+) pour voir les téléchargements/alertes.
BASE = ['INTERNET', 'ACCESS_NETWORK_STATE', 'VIBRATE', 'POST_NOTIFICATIONS']


def lire(p):
    return open(p, encoding='utf-8').read()


def ecrire(p, t):
    open(p, 'w', encoding='utf-8').write(t)


def permissions(cfg):
    out = list(BASE)
    for g in cfg.get('permissions') or []:
        for n in TABLE.get(g, []):
            if n not in out:
                out.append(n)
    return out


# --------------------------------------------------------------------------- find
def trouver(dossier, noms):
    """Chemin le moins profond d'un des fichiers `noms` (ignore __MACOSX, node_modules, build)."""
    best = None
    for racine, dirs, files in os.walk(dossier):
        dirs[:] = [d for d in dirs if d not in ('__MACOSX', 'node_modules', 'build', '.git', '.gradle')]
        for n in noms:
            if n in files:
                p = os.path.join(racine, n)
                if best is None or p.count(os.sep) < best.count(os.sep):
                    best = p
    return best


# --------------------------------------------------------------------------- gradle
def module_application(racine):
    """Dossier du module qui applique le plugin com.android.application."""
    cands = []
    for racine_, dirs, files in os.walk(racine):
        dirs[:] = [d for d in dirs if d not in ('__MACOSX', 'node_modules', 'build', '.git', '.gradle')]
        for n in ('build.gradle', 'build.gradle.kts'):
            if n in files:
                t = lire(os.path.join(racine_, n))
                if re.search(r'com\.android\.application|android\.application', t) and \
                        os.path.exists(os.path.join(racine_, 'src', 'main', 'AndroidManifest.xml')):
                    cands.append((racine_, n))
    if not cands:
        sys.exit("Aucun module « com.android.application » trouvé dans le projet (il faut un module app avec src/main/AndroidManifest.xml).")
    cands.sort(key=lambda c: (c[0].count(os.sep), c[0] != os.path.join(racine, 'app')))
    return cands[0]


def patch_gradle(cfg, racine):
    mod, nom = module_application(racine)
    gp = os.path.join(mod, nom)
    kts = nom.endswith('.kts')
    t = lire(gp)
    pkg, vn, vc = cfg['pkg'], cfg['versionName'], int(cfg['versionCode'])
    eq = ' = ' if kts else ' '

    def remplacer(cle, valeur, motif_valeur):
        nonlocal t
        rx = re.compile(r'(\b%s\b\s*=?\s*)%s' % (cle, motif_valeur))
        if rx.search(t):
            t = rx.sub(lambda m: m.group(1) + valeur, t, count=1)
            return True
        return False

    ok_id = remplacer('applicationId', '"%s"' % pkg, r'["\'][^"\']*["\']')
    ok_vc = remplacer('versionCode', str(vc), r'[^\s\n;]+')
    ok_vn = remplacer('versionName', '"%s"' % vn, r'["\'][^"\']*["\']')
    ajout = ''
    if not ok_id:
        ajout += '        applicationId%s"%s"\n' % (eq, pkg)
    if not ok_vc:
        ajout += '        versionCode%s%d\n' % (eq, vc)
    if not ok_vn:
        ajout += '        versionName%s"%s"\n' % (eq, vn)
    if ajout:
        if re.search(r'defaultConfig\s*\{', t):
            t = re.sub(r'(defaultConfig\s*\{\s*\n)', lambda m: m.group(1) + ajout, t, count=1)
        else:
            t += '\nandroid {\n    defaultConfig {\n%s    }\n}\n' % ajout
    ecrire(gp, t)
    print('Module Gradle :', gp, '| applicationId =', pkg, '| version =', vn, '(%d)' % vc)

    # Manifeste
    mp = os.path.join(mod, 'src', 'main', 'AndroidManifest.xml')
    s = lire(mp)
    label = html.escape(cfg['name'], quote=True)
    if re.search(r'<application[^>]*android:label="[^"]*"', s):
        s = re.sub(r'(<application[^>]*?android:label=)"[^"]*"', lambda m: '%s"%s"' % (m.group(1), label), s, count=1)
    else:
        s = s.replace('<application', '<application android:label="%s"' % label, 1)
    lignes = ''
    for p in permissions(cfg):
        if 'android.permission.%s"' % p not in s:
            mx = ' android:maxSdkVersion="32"' if p in ('READ_EXTERNAL_STORAGE', 'WRITE_EXTERNAL_STORAGE') else ''
            lignes += '    <uses-permission android:name="android.permission.%s"%s/>\n' % (p, mx)
    s = s.replace('<application', lignes + '    <application', 1)
    ori = cfg.get('orientation', 'auto')
    ori = 'unspecified' if ori == 'auto' else ori
    if ori != 'unspecified' and 'android:screenOrientation' not in s:
        s = s.replace('<activity', '<activity android:screenOrientation="%s"' % ori, 1)
    if 'xmlns:tools' not in s and 'MANAGE_EXTERNAL_STORAGE' in s:
        pass
    ecrire(mp, s)
    print('Manifeste :', mp)
    print('MODULE=' + mod)
    return mod


# --------------------------------------------------------------------------- expo
def patch_expo(cfg, racine):
    """Écrit nom, paquet, version et orientation dans app.json (Expo). Crée app.json s'il n'existe pas."""
    p = os.path.join(racine, 'app.json')
    d = json.load(open(p, encoding='utf-8')) if os.path.exists(p) else {}
    e = d.setdefault('expo', {})
    e['name'] = cfg['name']
    e['slug'] = re.sub(r'[^a-z0-9-]', '-', cfg['name'].lower()).strip('-') or 'app'
    e['version'] = cfg['versionName']
    ori = cfg.get('orientation', 'auto')
    e['orientation'] = {'auto': 'default'}.get(ori, ori)
    a = e.setdefault('android', {})
    a['package'] = cfg['pkg']
    a['versionCode'] = int(cfg['versionCode'])
    a['permissions'] = permissions(cfg)
    json.dump(d, open(p, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    print('app.json (Expo) :', p)


# --------------------------------------------------------------------------- buildozer
def regler(txt, cle, valeur):
    """Règle `cle = valeur` dans la section [app] (réactive la ligne si elle est commentée)."""
    rx = re.compile(r'^[#\s]*%s\s*=.*$' % re.escape(cle), re.M)
    ligne = '%s = %s' % (cle, valeur)
    if rx.search(txt):
        return rx.sub(lambda m: ligne, txt, count=1)
    if re.search(r'^\[app\]\s*$', txt, re.M):
        return re.sub(r'^\[app\]\s*$', lambda m: '[app]\n' + ligne, txt, count=1, flags=re.M)
    return txt + '\n' + ligne + '\n'


def valeur(txt, cle, defaut=''):
    m = re.search(r'^%s\s*=\s*(.*)$' % re.escape(cle), txt, re.M)
    return m.group(1).strip() if m else defaut


def patch_spec(cfg, specp):
    t = lire(specp)
    pkg = cfg['pkg']
    domaine, _, court = pkg.rpartition('.')
    court = re.sub(r'[^a-z0-9]', '', court.lower()) or 'app'
    if not domaine:
        domaine = 'org.app'
    ori = {'auto': 'all', 'portrait': 'portrait', 'landscape': 'landscape'}.get(cfg.get('orientation', 'auto'), 'all')
    t = regler(t, 'title', cfg['name'])
    t = regler(t, 'package.name', court)
    t = regler(t, 'package.domain', domaine)
    t = regler(t, 'version', cfg['versionName'])
    t = regler(t, 'orientation', ori)
    t = regler(t, 'fullscreen', '1' if cfg.get('fullscreen') else '0')
    t = regler(t, 'android.permissions', ','.join(permissions(cfg)))
    t = regler(t, 'android.api', '34')
    t = regler(t, 'android.minapi', '24')
    t = regler(t, 'android.archs', 'arm64-v8a, armeabi-v7a')
    t = regler(t, 'android.accept_sdk_license', 'True')
    t = regler(t, 'android.release_artifact', 'apk')
    t = regler(t, 'source.include_exts', 'py,png,jpg,jpeg,gif,webp,kv,atlas,ttf,otf,json,txt,csv,xml,wav,mp3,ogg,mp4,db,sqlite,ini,yaml,yml')
    t = regler(t, 'source.dir', '.')
    # requirements : conserve ceux du projet, ajoute python3 + kivy et ceux de requirements.txt
    req = [x.strip() for x in valeur(t, 'requirements', 'python3,kivy').split(',') if x.strip()]
    rt = os.path.join(os.path.dirname(specp), 'requirements.txt')
    if os.path.exists(rt):
        for l in lire(rt).splitlines():
            n = re.split(r'[<>=!~\[;# ]', l.strip(), maxsplit=1)[0].strip().lower()
            if n and n not in [r.split('==')[0].lower() for r in req]:
                req.append(n)
    for base in ('python3', 'kivy'):
        if base not in [r.split('==')[0].lower() for r in req]:
            req.insert(0, base)
    t = regler(t, 'requirements', ','.join(req))
    if cfg.get('icon') and os.path.exists(os.path.join(os.path.dirname(specp), 'icon.png')):
        t = regler(t, 'icon.filename', '%(source.dir)s/icon.png')
    ecrire(specp, t)
    print('buildozer.spec :', specp, '| requirements =', ','.join(req))


# --------------------------------------------------------------------------- main
if __name__ == '__main__':
    mode = sys.argv[1]
    if mode == 'find':
        r = trouver(sys.argv[2], sys.argv[3:])
        print(r or '')
        sys.exit(0 if r else 1)
    cfg = json.load(open(sys.argv[2], encoding='utf-8'))
    if mode == 'gradle':
        patch_gradle(cfg, sys.argv[3])
    elif mode == 'expo':
        patch_expo(cfg, sys.argv[3])
    elif mode == 'spec':
        patch_spec(cfg, sys.argv[3])
    else:
        sys.exit('Mode inconnu : ' + mode)
