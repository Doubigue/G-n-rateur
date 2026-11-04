#!/usr/bin/env python3
"""Prépare les projets de JEUX envoyés depuis APK Studio (nom, paquet, version, orientation,
plein écran, autorisations, icône) avant la compilation.

Usage :
  game_setup.py godot-info <dossier_projet>                         → MM=4.3 / MONO=0|1
  game_setup.py godot  <config.json> <dossier_projet> <icon.png|-> <keystore>   → PRESET=<nom>
  game_setup.py love   <config.json> <dossier_love_android> <dossier_jeu>
  game_setup.py defold <config.json> <dossier_projet> <icon.png|->
  game_setup.py html5  <dossier_www>                                (bibliothèques CDN embarquées)
"""
import glob
import html
import json
import os
import re
import sys
import urllib.request

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)


def lire(p):
    return open(p, encoding='utf-8', errors='replace').read()


def ecrire(p, t):
    open(p, 'w', encoding='utf-8').write(t)


def charger_cfg(p):
    return json.load(open(p, encoding='utf-8'))


GROUPES = {
    'storage': ['read_external_storage', 'write_external_storage'],
    'media': ['read_media_images', 'read_media_video', 'read_media_audio'],
    'allfiles': ['manage_external_storage'],
    'camera': ['camera'],
    'micro': ['record_audio', 'modify_audio_settings'],
    'location': ['access_fine_location', 'access_coarse_location'],
    'notifications': ['post_notifications'],
    'contacts': ['read_contacts', 'write_contacts'],
    'calendar': ['read_calendar', 'write_calendar'],
    'bluetooth': ['bluetooth', 'bluetooth_admin', 'bluetooth_connect', 'bluetooth_scan'],
    'phone': ['read_phone_state', 'call_phone'],
}
BASE = ['internet', 'access_network_state', 'access_wifi_state', 'vibrate', 'wake_lock']


def permissions(cfg):
    out = list(BASE)
    for g in cfg.get('permissions') or []:
        for p in GROUPES.get(g, []):
            if p not in out:
                out.append(p)
    return out


# ------------------------------------------------------------------ fichiers INI (Godot / Defold)
def ini_set(txt, section, cle, valeur, sep='='):
    """Fixe `cle<sep>valeur` dans [section] (crée la section ou la clé si besoin)."""
    lignes = txt.split('\n')
    debut = None
    for i, l in enumerate(lignes):
        if l.strip() == '[%s]' % section:
            debut = i
            break
    nouvelle = '%s%s%s' % (cle, sep, valeur)
    if debut is None:
        if lignes and lignes[-1].strip():
            lignes.append('')
        lignes += ['[%s]' % section, '', nouvelle]
        return '\n'.join(lignes) + '\n'
    fin = len(lignes)
    for j in range(debut + 1, len(lignes)):
        if lignes[j].startswith('['):
            fin = j
            break
    rx = re.compile(r'^\s*%s\s*=' % re.escape(cle))
    for j in range(debut + 1, fin):
        if rx.match(lignes[j]):
            lignes[j] = nouvelle
            return '\n'.join(lignes)
    k = fin
    while k > debut + 1 and not lignes[k - 1].strip():
        k -= 1
    lignes.insert(k, nouvelle)
    return '\n'.join(lignes)


def ini_get(txt, section, cle):
    sec = None
    for l in txt.split('\n'):
        s = l.strip()
        if s.startswith('[') and s.endswith(']'):
            sec = s[1:-1]
        elif sec == section and re.match(r'^%s\s*=' % re.escape(cle), s):
            return s.split('=', 1)[1].strip()
    return None


def gq(s):
    """Chaîne au format Godot."""
    return '"%s"' % str(s).replace('\\', '\\\\').replace('"', '\\"')


# ------------------------------------------------------------------ icônes
def icones(icon, dossier, tailles, secours='#2a2f6b'):
    """Génère dans `dossier` les PNG demandés : {'nom.png': ('plein'|'fg'|'bg', taille)}."""
    import icon_setup as ic
    from PIL import Image
    im = ic.charger(icon)
    fond = ic.couleur_bords(im, secours)
    os.makedirs(dossier, exist_ok=True)
    for nom, (genre, t) in tailles.items():
        if genre == 'plein':
            im.resize((t, t), Image.LANCZOS).save(os.path.join(dossier, nom))
        elif genre == 'fg':
            ic.adaptatif(im, t, fond).save(os.path.join(dossier, nom))
        else:
            Image.new('RGBA', (t, t), fond + (255,)).save(os.path.join(dossier, nom))
    return fond


# ------------------------------------------------------------------ Godot
def godot_info(proj):
    t = lire(os.path.join(proj, 'project.godot'))
    cv = re.search(r'^config_version\s*=\s*(\d+)', t, re.M)
    if cv and int(cv.group(1)) < 5:
        sys.exit("Projet Godot 3 détecté : seul Godot 4 est pris en charge. Ouvre le projet dans Godot 4 "
                 "(Projet > Outils > Mettre à niveau) puis renvoie le ZIP.")
    m = re.search(r'config/features\s*=\s*PackedStringArray\(([^)]*)\)', t)
    mm = '4.3'
    if m:
        v = re.search(r'"(4\.\d+)"', m.group(1))
        if v:
            mm = v.group(1)
    mono = bool(glob.glob(os.path.join(proj, '**', '*.csproj'), recursive=True)) or '[dotnet]' in t
    print('MM=%s' % mm)
    print('MONO=%d' % (1 if mono else 0))


def godot(cfg, proj, icon, keystore):
    pg = os.path.join(proj, 'project.godot')
    t = lire(pg)
    t = ini_set(t, 'rendering', 'textures/vram_compression/import_etc2_astc', 'true')
    ori = cfg.get('orientation', 'auto')
    if ori in ('landscape', 'portrait'):
        t = ini_set(t, 'display', 'window/handheld/orientation', '4' if ori == 'landscape' else '5')
    ecrire(pg, t)

    # Préréglage d'export Android (réutilise celui du projet s'il existe)
    ep = os.path.join(proj, 'export_presets.cfg')
    e = lire(ep) if os.path.exists(ep) else ''
    idx, nom = None, 'Android'
    for m in re.finditer(r'^\[preset\.(\d+)\]\s*$', e, re.M):
        bloc = e[m.end():].split('\n[preset.', 1)[0]
        if re.search(r'^platform\s*=\s*"Android"', bloc, re.M):
            idx = int(m.group(1))
            n = re.search(r'^name\s*=\s*"([^"]*)"', bloc, re.M)
            nom = n.group(1) if n else 'Android'
            break
    if idx is None:
        nums = [int(x) for x in re.findall(r'^\[preset\.(\d+)\]', e, re.M)]
        idx = max(nums) + 1 if nums else 0
        sec = 'preset.%d' % idx
        for k, v in [('name', '"Android"'), ('platform', '"Android"'), ('runnable', 'true'),
                     ('dedicated_server', 'false'), ('custom_features', '""'),
                     ('export_filter', '"all_resources"'), ('include_filter', '""'),
                     ('exclude_filter', '""'), ('export_path', '""')]:
            e = ini_set(e, sec, k, v)
    o = 'preset.%d.options' % idx
    opts = [
        ('gradle_build/use_gradle_build', 'false'),
        ('architectures/armeabi-v7a', 'true'),
        ('architectures/arm64-v8a', 'true'),
        ('architectures/x86', 'false'),
        ('architectures/x86_64', 'false'),
        ('keystore/debug', gq(keystore)),
        ('keystore/debug_user', '"androiddebugkey"'),
        ('keystore/debug_password', '"android"'),
        ('keystore/release', gq(keystore)),
        ('keystore/release_user', '"androiddebugkey"'),
        ('keystore/release_password', '"android"'),
        ('version/code', str(int(cfg['versionCode']))),
        ('version/name', gq(cfg['versionName'])),
        ('package/unique_name', gq(cfg['pkg'])),
        ('package/name', gq(cfg['name'])),
        ('package/signed', 'true'),
        ('screen/immersive_mode', 'true' if cfg.get('fullscreen') else 'false'),
    ]
    for p in permissions(cfg):
        opts.append(('permissions/' + p, 'true'))
    if icon and os.path.exists(icon):
        icones(icon, proj, {'apk_studio_icon.png': ('plein', 192),
                            'apk_studio_icon_fg.png': ('fg', 432),
                            'apk_studio_icon_bg.png': ('bg', 432)}, cfg.get('color', '#2a2f6b'))
        opts += [('launcher_icons/main_192x192', '"res://apk_studio_icon.png"'),
                 ('launcher_icons/adaptive_foreground_432x432', '"res://apk_studio_icon_fg.png"'),
                 ('launcher_icons/adaptive_background_432x432', '"res://apk_studio_icon_bg.png"')]
    if not re.search(r'^\[%s\]' % re.escape(o), e, re.M):
        e = ini_set(e, o, 'gradle_build/use_gradle_build', 'false')
    for k, v in opts:
        e = ini_set(e, o, k, v)
    ecrire(ep, e)
    print('project.godot et export_presets.cfg mis à jour (préréglage « %s »)' % nom)
    print('PRESET=' + nom)


# ------------------------------------------------------------------ LÖVE (love-android)
def love(cfg, la, jeu):
    gp = os.path.join(la, 'gradle.properties')
    nom = cfg['name']
    ori = {'auto': 'fullSensor', 'landscape': 'sensorLandscape', 'portrait': 'sensorPortrait'}.get(cfg.get('orientation', 'auto'), 'fullSensor')
    conf = os.path.join(jeu, 'conf.lua')
    if cfg.get('orientation', 'auto') == 'auto' and os.path.exists(conf):
        c = lire(conf)
        w = re.search(r'window\.width\s*=\s*(\d+)', c)
        h = re.search(r'window\.height\s*=\s*(\d+)', c)
        if w and h:
            ori = 'sensorLandscape' if int(w.group(1)) >= int(h.group(1)) else 'sensorPortrait'
    vals = {'app.name': nom, 'app.application_id': cfg['pkg'], 'app.orientation': ori,
            'app.version_code': str(int(cfg['versionCode'])), 'app.version_name': cfg['versionName']}
    if os.path.exists(gp):
        t = lire(gp)
        for k, v in vals.items():
            rx = re.compile(r'^\s*#?\s*%s\s*=.*$' % re.escape(k), re.M)
            if rx.search(t):
                t = rx.sub(lambda m: '%s=%s' % (k, v), t, count=1)
            else:
                t += '\n%s=%s' % (k, v)
        rx = re.compile(r'^\s*#?\s*app\.name_byte_array\s*=.*$', re.M)
        if all(ord(ch) < 128 for ch in nom):
            t = rx.sub('#app.name_byte_array=', t)
        else:
            octets = ','.join(str(b if b < 128 else b - 256) for b in nom.encode('utf-8'))
            t = rx.sub('app.name_byte_array=' + octets, t) if rx.search(t) else t + '\napp.name_byte_array=' + octets
        ecrire(gp, t + ('' if t.endswith('\n') else '\n'))
        print('gradle.properties :', vals)
    # Repli : si le projet n'utilise pas ces propriétés, on modifie directement build.gradle
    for bg in glob.glob(os.path.join(la, 'app', 'build.gradle*')):
        t = lire(bg)
        if 'app.application_id' not in t and 'applicationId' in t:
            t = re.sub(r'(applicationId\s*=?\s*)["\'][^"\']*["\']', lambda m: m.group(1) + '"%s"' % cfg['pkg'], t, count=1)
            t = re.sub(r'(versionCode\s*=?\s*)\d+', lambda m: m.group(1) + str(int(cfg['versionCode'])), t, count=1)
            t = re.sub(r'(versionName\s*=?\s*)["\'][^"\']*["\']', lambda m: m.group(1) + '"%s"' % cfg['versionName'], t, count=1)
            ecrire(bg, t)
    # Autorisations, plein écran et icône dans le manifeste
    for mp in glob.glob(os.path.join(la, 'app', 'src', 'main', 'AndroidManifest.xml')):
        s = lire(mp)
        lignes = ''
        for p in permissions(cfg):
            full = 'android.permission.' + p.upper()
            if '"%s"' % full not in s:
                lignes += '    <uses-permission android:name="%s"/>\n' % full
        s = s.replace('<application', lignes + '    <application', 1)
        if cfg.get('icon') and os.path.exists(os.path.join(la, 'app', 'src', 'main', 'res', 'mipmap-mdpi', 'ic_launcher.png')):
            s = re.sub(r'android:icon="[^"]*"', 'android:icon="@mipmap/ic_launcher"', s)
            if 'android:roundIcon' in s:
                s = re.sub(r'android:roundIcon="[^"]*"', 'android:roundIcon="@mipmap/ic_launcher_round"', s)
        if 'android:label="${NAME}"' not in s and 'android:label=' in s and '@string' not in s.split('android:label=', 1)[1][:20]:
            s = re.sub(r'(<application[^>]*?android:label=)"[^"]*"', lambda m: '%s"%s"' % (m.group(1), html.escape(nom, quote=True)), s, count=1)
        ecrire(mp, s)
        print('Manifeste LÖVE :', mp)


# ------------------------------------------------------------------ Defold
def defold(cfg, proj, icon):
    gp = os.path.join(proj, 'game.project')
    t = lire(gp)
    sep = ' = '
    t = ini_set(t, 'project', 'title', cfg['name'], sep)
    t = ini_set(t, 'project', 'version', cfg['versionName'], sep)
    t = ini_set(t, 'android', 'package', cfg['pkg'], sep)
    t = ini_set(t, 'android', 'version_code', str(int(cfg['versionCode'])), sep)
    if cfg.get('fullscreen'):
        t = ini_set(t, 'display', 'fullscreen', '1', sep)
    if icon and os.path.exists(icon):
        d = os.path.join(proj, 'apk_studio_icons')
        tailles = {'icon_%d.png' % s: ('plein', s) for s in (36, 48, 72, 96, 144, 192)}
        icones(icon, d, tailles, cfg.get('color', '#2a2f6b'))
        for s in (36, 48, 72, 96, 144, 192):
            t = ini_set(t, 'android', 'app_icon_%dx%d' % (s, s), '/apk_studio_icons/icon_%d.png' % s, sep)
    ecrire(gp, t)
    print('game.project mis à jour :', cfg['name'], cfg['pkg'], cfg['versionName'])


# ------------------------------------------------------------------ HTML5 (hors ligne)
CDN = r'https://(?:cdnjs\.cloudflare\.com|cdn\.jsdelivr\.net|unpkg\.com|code\.jquery\.com|cdn\.babylonjs\.com|pixijs\.download|esm\.sh|cdn\.skypack\.dev)/[^"\'\s)<>]+'


def html5(www):
    """Télécharge les bibliothèques chargées depuis un CDN (Phaser, Three.js, Pixi…) pour jouer hors ligne."""
    lib = os.path.join(www, 'apk_lib')
    fichiers = [p for p in glob.glob(os.path.join(www, '**', '*'), recursive=True)
                if os.path.isfile(p) and re.search(r'\.(html?|js|mjs|css|json)$', p, re.I) and '/apk_lib/' not in p]
    urls = set()
    for p in fichiers:
        for u in re.findall(CDN, lire(p)):
            u = u.rstrip('.,;')
            if re.search(r'\.(m?js|css|wasm|json)(\?|$)', u, re.I) or 'esm.sh' in u or '/+esm' in u:
                urls.add(u)
    local = {}
    for u in sorted(urls):
        nom = re.sub(r'[^A-Za-z0-9._-]', '_', u.split('://', 1)[1])[-120:]
        if not re.search(r'\.(m?js|css|wasm|json)$', nom, re.I):
            nom += '.js'
        try:
            req = urllib.request.Request(u, headers={'User-Agent': 'apk-studio'})
            data = urllib.request.urlopen(req, timeout=60).read()
            os.makedirs(lib, exist_ok=True)
            open(os.path.join(lib, nom), 'wb').write(data)
            local[u] = os.path.join(lib, nom)
            print('  embarqué :', u)
        except Exception as ex:
            print('  (gardé en ligne) %s : %s' % (u, ex))
    for p in fichiers:
        t = lire(p)
        n = t
        for u, chemin in local.items():
            rel = os.path.relpath(chemin, os.path.dirname(p)).replace(os.sep, '/')
            if not rel.startswith('.'):
                rel = './' + rel
            n = n.replace(u, rel)
        if n != t:
            ecrire(p, n)
    print('Jeu HTML5 : %d bibliothèque(s) embarquée(s) pour jouer hors ligne' % len(local))


if __name__ == '__main__':
    mode = sys.argv[1] if len(sys.argv) > 1 else ''
    if mode == 'godot-info':
        godot_info(sys.argv[2])
    elif mode == 'godot':
        godot(charger_cfg(sys.argv[2]), sys.argv[3], sys.argv[4] if sys.argv[4] != '-' else '', sys.argv[5])
    elif mode == 'love':
        love(charger_cfg(sys.argv[2]), sys.argv[3], sys.argv[4])
    elif mode == 'defold':
        defold(charger_cfg(sys.argv[2]), sys.argv[3], sys.argv[4] if sys.argv[4] != '-' else '')
    elif mode == 'html5':
        html5(sys.argv[2])
    else:
        sys.exit(__doc__)
