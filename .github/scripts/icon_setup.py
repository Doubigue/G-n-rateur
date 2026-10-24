#!/usr/bin/env python3
"""Génère les icônes Android pour que le logo REMPLISSE l'icône (plus de petit logo au centre).

Usage :
  icon_setup.py gradle <dossier_res> <icon.png> [couleur_secours]   (Capacitor, Flutter, Kotlin/Java, React Native)
  icon_setup.py spec   <dossier_projet> <icon.png> [couleur_secours] (Python/Kivy : écrit icon_fg.png / icon_bg.png)

- Icônes classiques (mdpi → xxxhdpi) : le logo occupe toute la surface (version ronde incluse).
- Icône adaptative (Android 8+) : le logo est calé sur la zone réellement visible du masque
  du lanceur, sur un fond uni de la couleur de ses bords : aucune marge blanche.
"""
import glob
import os
import sys

try:
    from PIL import Image, ImageChops, ImageDraw
except ImportError:  # pragma: no cover
    import subprocess
    for cmd in ([sys.executable, '-m', 'pip', 'install', '-q', 'pillow'],
                [sys.executable, '-m', 'pip', 'install', '-q', '--break-system-packages', 'pillow'],
                ['sudo', 'apt-get', 'install', '-y', 'python3-pil']):
        if subprocess.run(cmd).returncode == 0:
            break
    from PIL import Image, ImageChops, ImageDraw

LEGACY = {'mdpi': 48, 'hdpi': 72, 'xhdpi': 96, 'xxhdpi': 144, 'xxxhdpi': 192}
ADAPT = {'mdpi': 108, 'hdpi': 162, 'xhdpi': 216, 'xxhdpi': 324, 'xxxhdpi': 432}
# Le masque adaptatif montre ~72 dp sur 108 dp : le logo y est calé (légèrement débordant pour remplir)
ZONE = 0.72


def charger(p):
    im = Image.open(p).convert('RGBA')
    bb = im.getchannel('A').point(lambda a: 255 if a > 12 else 0).getbbox()
    if bb:
        im = im.crop(bb)
    w, h = im.size
    c = min(w, h) if 0.9 <= w / h <= 1.1 else None
    if c:  # presque carré : recadrage centré pour remplir
        im = im.crop(((w - c) // 2, (h - c) // 2, (w - c) // 2 + c, (h - c) // 2 + c))
    else:  # forme allongée : on garde tout, centré sur un carré transparent
        m = max(w, h)
        f = Image.new('RGBA', (m, m), (0, 0, 0, 0))
        f.paste(im, ((m - w) // 2, (m - h) // 2))
        im = f
    return im


def couleur_bords(im, secours):
    """Couleur moyenne du pourtour opaque du logo (sert de fond à l'icône adaptative)."""
    s = im.resize((64, 64), Image.LANCZOS)
    px, n, r, g, b = s.load(), 0, 0, 0, 0
    for i in range(64):
        for j in range(64):
            if min(i, j, 63 - i, 63 - j) > 3:
                continue
            R, G, B, A = px[i, j]
            if A > 200:
                n += 1
                r += R
                g += G
                b += B
    if n < 20:
        t = (secours or '#1B1F2A').lstrip('#')
        return tuple(int(t[k:k + 2], 16) for k in (0, 2, 4))
    return (r // n, g // n, b // n)


def rond(im):
    s = im.size[0]
    m = Image.new('L', (s * 4, s * 4), 0)
    ImageDraw.Draw(m).ellipse((0, 0, s * 4 - 1, s * 4 - 1), fill=255)
    m = m.resize((s, s), Image.LANCZOS)
    out = im.copy()
    out.putalpha(ImageChops.multiply(m, im.getchannel('A')))
    return out


def adaptatif(im, taille, fond):
    f = Image.new('RGBA', (taille, taille), (0, 0, 0, 0))
    z = round(taille * ZONE)
    g = im.resize((z, z), Image.LANCZOS)
    f.paste(g, ((taille - z) // 2, (taille - z) // 2), g)
    return f


def gradle(res, icon, secours):
    im = charger(icon)
    fond = couleur_bords(im, secours)
    hexa = '#%02X%02X%02X' % fond
    # supprime toutes les anciennes icônes pour éviter les doublons de ressources
    for d in glob.glob(os.path.join(res, 'mipmap*')):
        for old in glob.glob(os.path.join(d, 'ic_launcher*')):
            os.remove(old)
    for dens, t in LEGACY.items():
        d = os.path.join(res, 'mipmap-' + dens)
        os.makedirs(d, exist_ok=True)
        base = im.resize((t, t), Image.LANCZOS)
        base.save(os.path.join(d, 'ic_launcher.png'))
        rond(base).save(os.path.join(d, 'ic_launcher_round.png'))
        adaptatif(im, ADAPT[dens], fond).save(os.path.join(d, 'omni_icon_fg.png'))
    os.makedirs(os.path.join(res, 'values'), exist_ok=True)
    with open(os.path.join(res, 'values', 'omni_icon_bg.xml'), 'w', encoding='utf-8') as f:
        f.write('<?xml version="1.0" encoding="utf-8"?>\n<resources><color name="omni_icon_bg">%s</color></resources>\n' % hexa)
    ad = os.path.join(res, 'mipmap-anydpi-v26')
    os.makedirs(ad, exist_ok=True)
    xml = ('<?xml version="1.0" encoding="utf-8"?>\n'
           '<adaptive-icon xmlns:android="http://schemas.android.com/apk/res/android">\n'
           '  <background android:drawable="@color/omni_icon_bg"/>\n'
           '  <foreground android:drawable="@mipmap/omni_icon_fg"/>\n</adaptive-icon>\n')
    for n in ('ic_launcher.xml', 'ic_launcher_round.xml'):
        with open(os.path.join(ad, n), 'w', encoding='utf-8') as f:
            f.write(xml)
    print('Icône pleine taille générée (fond adaptatif %s)' % hexa)


def spec(dossier, icon, secours):
    im = charger(icon)
    fond = couleur_bords(im, secours)
    im.resize((512, 512), Image.LANCZOS).save(os.path.join(dossier, 'icon.png'))
    adaptatif(im, 432, fond).save(os.path.join(dossier, 'icon_fg.png'))
    Image.new('RGBA', (432, 432), fond + (255,)).save(os.path.join(dossier, 'icon_bg.png'))
    print('Icône Kivy pleine taille générée (fond %s)' % ('#%02X%02X%02X' % fond))


if __name__ == '__main__':
    if len(sys.argv) < 4 or sys.argv[1] not in ('gradle', 'spec'):
        sys.exit(__doc__)
    (gradle if sys.argv[1] == 'gradle' else spec)(sys.argv[2], sys.argv[3], sys.argv[4] if len(sys.argv) > 4 else '')
