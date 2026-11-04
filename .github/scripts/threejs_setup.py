#!/usr/bin/env python3
"""Prépare un jeu Three.js / WebGL envoyé depuis APK Studio avant l'emballage Capacitor.

Usage : threejs_setup.py <dossier_www>

Étapes :
  1. Projet npm (package.json avec un script « build », ex. Vite) : npm install + build,
     le dossier produit (dist/, build/…) devient l'application.
  2. Modules ES chargés depuis un CDN (importmap, three/addons/…, three.core.js,
     décodeurs Draco/Basis, modèles .glb, textures HDR…) : téléchargés en gardant
     l'arborescence, et les adresses réécrites pour que le jeu marche HORS LIGNE.
  3. OpenStreetMap : si le ZIP contient osm.json, les rues, bâtiments, eaux, parcs et
     monuments de la zone sont téléchargés une fois pour toutes dans osm/data.json,
     avec osm/osm.js pour les convertir en mètres (x, z) dans la scène.
"""
import json
import math
import os
import re
import shutil
import subprocess
import sys
import urllib.parse
import urllib.request

UA = {'User-Agent': 'APK-Studio-Generateur/1.0 (compilation de jeux)'}
HOTES = ['cdnjs.cloudflare.com', 'cdn.jsdelivr.net', 'unpkg.com', 'esm.sh', 'cdn.skypack.dev', 'ga.jspm.io',
         'threejs.org', 'raw.githubusercontent.com', 'www.gstatic.com', 'cdn.babylonjs.com', 'code.jquery.com']
URL_RE = re.compile(r'https://(?:%s)/[^"\'\s)<>`]*' % '|'.join(re.escape(h) for h in HOTES))
EXT_RES = re.compile(r'\.(m?js|cjs|css|wasm|json|glb|gltf|bin|hdr|exr|png|jpe?g|webp|avif|ktx2|basis|mp3|ogg|wav|m4a|ttf|otf|woff2?|fnt|obj|mtl|fbx|svg|txt)$', re.I)
IMPORT_RE = re.compile(r'(\bfrom\s*|\bimport\s*\(\s*|\bimport\s+)(["\'])([^"\'\n]+)\2')
MAX_FICHIERS = 600
MAX_OCTETS = 80 * 1024 * 1024
DECODEURS = {
    'draco': ['draco_decoder.js', 'draco_decoder.wasm', 'draco_wasm_wrapper.js'],
    'basis': ['basis_transcoder.js', 'basis_transcoder.wasm'],
}


def lire(p):
    return open(p, encoding='utf-8', errors='replace').read()


def ecrire(p, t):
    open(p, 'w', encoding='utf-8').write(t)


def telecharger(u, timeout=90):
    return urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=timeout).read()


# ------------------------------------------------------------------ 1. projet npm (Vite, Webpack…)
def construire_npm(www):
    pj = os.path.join(www, 'package.json')
    if not os.path.isfile(pj):
        return
    try:
        pkg = json.load(open(pj, encoding='utf-8'))
    except Exception:
        return
    scripts = pkg.get('scripts') or {}
    if 'build' not in scripts:
        print('package.json sans script « build » : fichiers utilisés tels quels')
        return
    deps = dict(pkg.get('dependencies') or {}, **(pkg.get('devDependencies') or {}))
    print('Projet npm détecté : installation des dépendances puis « npm run build »')
    lock = os.path.isfile(os.path.join(www, 'package-lock.json'))
    subprocess.run(['npm', 'ci' if lock else 'install', '--no-audit', '--no-fund'], cwd=www, check=True)
    cmd = ['npm', 'run', 'build']
    if 'vite' in deps and 'vite' in scripts['build']:
        # chemins relatifs obligatoires dans l'APK (pas de serveur à la racine « / »)
        cmd += ['--', '--base', './']
    subprocess.run(cmd, cwd=www, check=True)
    for d in ('dist', 'build', 'out', 'public_html', 'www'):
        sortie = os.path.join(www, d)
        if os.path.isfile(os.path.join(sortie, 'index.html')):
            tmp = www.rstrip('/') + '__build'
            shutil.move(sortie, tmp)
            shutil.rmtree(www)
            shutil.move(tmp, www)
            print('Application construite :', d + '/')
            return
    sys.exit('Le build npm n\'a produit aucun index.html (cherché dans dist/, build/, out/).')


# ------------------------------------------------------------------ 2. modules et ressources hors ligne
def chemin_local(u):
    """https://hote/a/b.js?x → apk_lib/hote/a/b.js (arborescence conservée, extension .js ajoutée si besoin)."""
    p = urllib.parse.urlsplit(u)
    chemin = urllib.parse.unquote(p.path).lstrip('/') or 'index'
    chemin = re.sub(r'[^A-Za-z0-9._@+/-]', '_', chemin)
    if p.query:
        chemin += '_' + re.sub(r'[^A-Za-z0-9]', '_', p.query)[:40]
    if chemin.endswith('/'):
        chemin += 'index'
    if not EXT_RES.search(chemin) or chemin.lower().endswith(('.mjs', '.cjs')):
        chemin += '.js'  # le serveur local de l'APK exige un type MIME JavaScript pour les modules
    return os.path.join('apk_lib', p.netloc, chemin)


def relatif(cible, depuis_fichier):
    r = os.path.relpath(cible, os.path.dirname(depuis_fichier)).replace(os.sep, '/')
    return r if r.startswith('.') else './' + r


def importmaps(textes):
    im = {}
    for t in textes:
        for bloc in re.findall(r'<script[^>]*type=["\']importmap["\'][^>]*>(.*?)</script>', t, re.S | re.I):
            try:
                im.update(json.loads(bloc).get('imports') or {})
            except Exception:
                pass
    return im


def resoudre_nu(spec, im):
    if spec in im:
        return im[spec]
    meilleur = ''
    for k in im:
        if k.endswith('/') and spec.startswith(k) and len(k) > len(meilleur):
            meilleur = k
    return im[meilleur] + spec[len(meilleur):] if meilleur else None


def est_js(u):
    return bool(re.search(r'\.(m?js|cjs)$', urllib.parse.urlsplit(u).path, re.I)) or 'esm.sh' in u or '+esm' in u \
        or 'skypack' in u or 'jspm.io' in u or not EXT_RES.search(urllib.parse.urlsplit(u).path)


def hors_ligne(www):
    www = os.path.abspath(www)
    locaux = [os.path.join(r, f) for r, _, fs in os.walk(www) for f in fs
              if '/apk_lib' not in r and '/node_modules' not in r and re.search(r'\.(html?|m?js|css|json)$', f, re.I)]
    textes = {p: lire(p) for p in locaux}
    im = importmaps(textes.values())
    file, vus, prefixes = [], set(), set()

    def ajouter(u):
        u = u.rstrip('.,;\\')
        if not u.startswith('https://') or u in vus:
            return
        if u.endswith('/'):
            prefixes.add(u)
            for nom, fichiers in DECODEURS.items():
                if nom in u.lower():
                    for f in fichiers:
                        ajouter(u + f)
            return
        vus.add(u)
        file.append(u)

    for v in im.values():
        ajouter(v)
    for p, t in textes.items():
        for u in URL_RE.findall(t):
            chemin = urllib.parse.urlsplit(u).path
            if EXT_RES.search(chemin) or u.endswith('/') or 'esm' in u or 'skypack' in u:
                ajouter(u)
        if re.search(r'\.(m?js|html?)$', p, re.I):
            for _, _, spec in IMPORT_RE.findall(t):
                if not spec.startswith(('.', '/', 'http', 'data:')):
                    r = resoudre_nu(spec, im)
                    if r:
                        ajouter(r)

    telecharges, total = {}, 0
    while file and len(telecharges) < MAX_FICHIERS and total < MAX_OCTETS:
        u = file.pop(0)
        try:
            data = telecharger(u)
        except Exception as ex:
            print('  (gardé en ligne) %s : %s' % (u, ex))
            continue
        loc = os.path.join(www, chemin_local(u))
        os.makedirs(os.path.dirname(loc), exist_ok=True)
        open(loc, 'wb').write(data)
        telecharges[u] = loc
        total += len(data)
        if est_js(u):
            t = data.decode('utf-8', 'replace')
            for _, _, spec in IMPORT_RE.findall(t):
                if spec.startswith(('data:', 'node:')):
                    continue
                if spec.startswith(('.', '/', 'https://')):
                    ajouter(urllib.parse.urljoin(u, spec))
                else:
                    r = resoudre_nu(spec, im)
                    if r:
                        ajouter(r)
    print('  %d fichier(s) embarqué(s), %.1f Mo' % (len(telecharges), total / 1048576))

    # réécriture des imports dans les fichiers téléchargés
    for u, loc in telecharges.items():
        if not est_js(u):
            continue
        t = lire(loc)

        def rempl(m):
            spec = m.group(3)
            if spec.startswith(('.', '/', 'https://')) and not spec.startswith('//'):
                cible = urllib.parse.urljoin(u, spec)
                if cible in telecharges:
                    return m.group(1) + m.group(2) + relatif(telecharges[cible], loc) + m.group(2)
            return m.group(0)
        n = IMPORT_RE.sub(rempl, t)
        if n != t:
            ecrire(loc, n)

    # réécriture des adresses dans les fichiers du jeu (plus longues d'abord)
    remplacements = [(u, loc) for u, loc in telecharges.items()]
    for pre in prefixes:
        if not any(u.startswith(pre) for u in telecharges):
            continue
        remplacements.append((pre, os.path.join(www, chemin_local(pre + 'x')).rsplit('/', 1)[0] + '/'))
    remplacements.sort(key=lambda x: -len(x[0]))
    for p, t in textes.items():
        n = t
        for u, loc in remplacements:
            if u in n:
                r = relatif(loc.rstrip('/'), p) + ('/' if loc.endswith('/') else '')
                n = n.replace(u, r)
        if n != t:
            ecrire(p, n)


# ------------------------------------------------------------------ 3. OpenStreetMap
OVERPASS = ['https://overpass-api.de/api/interpreter', 'https://overpass.kumi.systems/api/interpreter',
            'https://maps.mail.ru/osm/tools/overpass/api/interpreter']
FILTRES = {
    'routes': 'way["highway"]["highway"!~"footway|path|steps|cycleway|bridleway|corridor|proposed|construction"]',
    'batiments': 'way["building"]',
    'eau': 'way["natural"="water"];way["waterway"~"river|canal"];relation["natural"="water"]',
    'parcs': 'way["leisure"~"park|garden|pitch|stadium"];way["landuse"~"grass|forest|recreation_ground"]',
    'monuments': 'node["tourism"~"attraction|museum|viewpoint"];way["tourism"~"attraction|museum"];'
                 'node["historic"];way["historic"];node["amenity"="place_of_worship"];way["amenity"="place_of_worship"]',
    'rails': 'way["railway"~"rail|tram|light_rail"]',
}

OSM_JS = r'''// Généré par APK Studio : lecture des données OpenStreetMap embarquées (osm/data.json).
// Coordonnées converties en mètres autour du centre : x = est, z = sud (repère Three.js, y = haut).
export async function chargerOSM(url = './osm/data.json') {
  const d = await (await fetch(url)).json();
  const [lat0, lon0] = d.centre, R = 6378137, k = Math.cos(lat0 * Math.PI / 180);
  const xz = (lat, lon) => [(lon - lon0) * Math.PI / 180 * R * k, -(lat - lat0) * Math.PI / 180 * R];
  const pts = el => (el.geometry || []).map(g => xz(g.lat, g.lon));
  const out = { centre: d.centre, lieu: d.lieu || '', routes: [], batiments: [], eau: [], parcs: [], monuments: [], rails: [] };
  const LARG = { motorway: 14, trunk: 12, primary: 11, secondary: 9, tertiary: 8, residential: 6.5, unclassified: 6, service: 4.5, living_street: 5 };
  for (const el of d.elements) {
    const t = el.tags || {};
    if (el.type === 'node') {
      if (t.tourism || t.historic || t.amenity === 'place_of_worship') out.monuments.push({ nom: t.name || '', pos: xz(el.lat, el.lon), tags: t });
      continue;
    }
    const p = pts(el);
    if (p.length < 2) continue;
    if (t.highway) {
      const lanes = parseFloat(t.lanes) || 0;
      out.routes.push({ nom: t.name || '', type: t.highway, largeur: lanes ? lanes * 3.3 : (LARG[t.highway] || 6), sensUnique: t.oneway === 'yes', points: p });
    } else if (t.building) {
      const niv = parseFloat(t['building:levels']) || 0, h = parseFloat(t.height) || (niv ? niv * 3.2 : 0);
      out.batiments.push({ nom: t.name || '', hauteur: h || 6 + ((el.id * 7919) % 9), points: p, tags: t });
      if (t.tourism || t.historic || t.amenity === 'place_of_worship') out.monuments.push({ nom: t.name || '', pos: p[0], tags: t, contour: p });
    } else if (t.railway) out.rails.push({ points: p });
    else if (t.natural === 'water' || t.waterway) out.eau.push({ riviere: !!t.waterway, points: p });
    else if (t.leisure || t.landuse) out.parcs.push({ type: t.leisure || t.landuse, points: p });
    else if (t.tourism || t.historic || t.amenity) out.monuments.push({ nom: t.name || '', pos: p[0], tags: t, contour: p });
  }
  return out;
}
'''


def osm(www):
    cfg_p = os.path.join(www, 'osm.json')
    if not os.path.isfile(cfg_p):
        return
    cfg = json.load(open(cfg_p, encoding='utf-8'))
    lieu = cfg.get('lieu', '')
    if cfg.get('bbox'):
        s, w, n, e = [float(v) for v in cfg['bbox']]
        lat, lon = (s + n) / 2, (w + e) / 2
    else:
        if cfg.get('centre'):
            lat, lon = [float(v) for v in cfg['centre']]
        else:
            q = urllib.parse.urlencode({'q': lieu, 'format': 'json', 'limit': 1})
            res = json.loads(telecharger('https://nominatim.openstreetmap.org/search?' + q, 60))
            if not res:
                sys.exit('osm.json : lieu « %s » introuvable sur OpenStreetMap' % lieu)
            lat, lon = float(res[0]['lat']), float(res[0]['lon'])
            print('OpenStreetMap : « %s » → %.5f, %.5f' % (lieu, lat, lon))
        r = min(float(cfg.get('rayon', 800)), 3000.0)
        dlat = r / 111320.0
        dlon = r / (111320.0 * math.cos(math.radians(lat)))
        s, w, n, e = lat - dlat, lon - dlon, lat + dlat, lon + dlon
    quoi = cfg.get('elements') or ['routes', 'batiments', 'eau', 'parcs', 'monuments']
    bb = '(%f,%f,%f,%f)' % (s, w, n, e)
    parties = []
    for k in quoi:
        for f in FILTRES.get(k, '').split(';'):
            if f:
                parties.append(f + bb + ';')
    req = '[out:json][timeout:180];(' + ''.join(parties) + ');out geom;'
    data = None
    for ep in OVERPASS:
        try:
            body = urllib.parse.urlencode({'data': req}).encode()
            data = json.loads(urllib.request.urlopen(urllib.request.Request(ep, data=body, headers=UA), timeout=200).read())
            break
        except Exception as ex:
            print('  Overpass %s indisponible : %s' % (ep, ex))
    if data is None:
        sys.exit('Impossible de télécharger les données OpenStreetMap (serveurs Overpass indisponibles).')
    el = data.get('elements', [])
    d = os.path.join(www, 'osm')
    os.makedirs(d, exist_ok=True)
    json.dump({'lieu': lieu, 'centre': [lat, lon], 'bbox': [s, w, n, e], 'elements': el,
               'licence': '© contributeurs OpenStreetMap, ODbL'}, open(os.path.join(d, 'data.json'), 'w'), separators=(',', ':'))
    ecrire(os.path.join(d, 'osm.js'), OSM_JS)
    print('OpenStreetMap : %d éléments enregistrés dans osm/data.json (%.1f Mo)'
          % (len(el), os.path.getsize(os.path.join(d, 'data.json')) / 1048576))


# ------------------------------------------------------------------ 4. réglages WebGL mobile
def ajuster_html(www):
    p = os.path.join(www, 'index.html')
    t = lire(p)
    n = t
    if not re.search(r'<meta[^>]+name=["\']viewport', t, re.I):
        n = re.sub(r'(<head[^>]*>)', r'\1\n<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no,viewport-fit=cover">', n, 1, re.I)
    if 'apk-studio-webgl' not in n:
        css = '<style id="apk-studio-webgl">html,body{margin:0;height:100%;overflow:hidden;overscroll-behavior:none;' \
              '-webkit-user-select:none;user-select:none;-webkit-tap-highlight-color:transparent}canvas{touch-action:none}</style>'
        # écran gardé allumé pendant le jeu (Wake Lock, au premier toucher)
        js = '<script>addEventListener("pointerdown",function w(){try{navigator.wakeLock&&navigator.wakeLock.request("screen")}catch(e){}' \
             'removeEventListener("pointerdown",w)});</script>'
        n = re.sub(r'(</head>)', css + js + r'\n\1', n, 1, re.I)
    if n != t:
        ecrire(p, n)


if __name__ == '__main__':
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    w = sys.argv[1]
    construire_npm(w)
    print('Three.js / WebGL : intégration des modules et ressources pour jouer hors ligne')
    hors_ligne(w)
    osm(w)
    ajuster_html(w)
