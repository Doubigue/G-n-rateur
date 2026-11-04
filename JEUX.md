# Compiler des jeux avec APK Studio

APK Studio reconnaît automatiquement le type de projet quand tu déposes un ZIP, puis règle
le jeu en **paysage plein écran** (modifiable avant de lancer la compilation).

| Type | Langage | Ce qu'il faut dans le ZIP | Workflow | Compilation |
|---|---|---|---|---|
| 🎮 Godot | GDScript ou C# | dossier du projet avec `project.godot` (Godot **4.x**) | `build-godot.yml` | Godot sans interface, version lue dans le projet (ex. 4.3 → 4.3-stable) ; projets C# : version .NET + .NET 8 |
| 🎮 LÖVE | Lua | `main.lua` (+ `conf.lua`), ZIP ou fichier `.love` | `build-love.yml` | love-android 11.5 (le jeu est embarqué) |
| 🎮 Defold | Lua | dossier du projet avec `game.project` | `build-defold.yml` | `bob.jar` officiel (dernière version stable) |
| 🎮 Pygame | Python | `main.py` qui fait `import pygame` (+ `requirements.txt` facultatif) | `build-pygame.yml` | Buildozer, amorce SDL2, sans Kivy |
| 🎮 Three.js / WebGL | JavaScript / TypeScript | `index.html` avec importmap ou CDN, **ou** projet Vite/npm (`package.json` + script `build`) ; `osm.json` facultatif | `build-apk.yml` | Capacitor ; build npm si besoin, modules ES et ressources embarqués **hors ligne**, données OpenStreetMap téléchargées à la compilation |
| 🎮 Jeu HTML5 | JavaScript | `index.html` (Phaser, Three.js, PixiJS, Babylon, Kaboom, exports Construct 3 / GDevelop…) | `build-apk.yml` | Capacitor ; les bibliothèques chargées depuis un CDN sont téléchargées et intégrées pour jouer **hors ligne** |
| Flutter (Flame) | Dart | `pubspec.yaml` + `lib/` | `build-flutter.yml` | inchangé |
| Kotlin / Java (libGDX) | Java / Kotlin | `settings.gradle` + module Android | `build-native.yml` | inchangé |

Pour tous les jeux, APK Studio applique : nom, identifiant du paquet, version, autorisations,
plein écran, icône et la **même clé de signature** que tes autres APK (mises à jour sans désinstaller).

## Détails par moteur

**Godot**
- Le préréglage d'export « Android » du projet est réutilisé s'il existe, sinon il est créé.
- Réglages forcés : export sans Gradle, architectures arm64-v8a + armeabi-v7a, compression ETC2/ASTC.
- L'icône est ajoutée au projet (`apk_studio_icon*.png`) et utilisée comme icône classique et adaptative.
- Godot 3 n'est pas pris en charge : ouvre le projet dans Godot 4 (Projet > Outils > Mettre à niveau).
- Le premier build d'une version télécharge Godot et ses modèles d'export (~1 Go) ; les suivants
  utilisent le cache GitHub Actions.

**LÖVE** : l'orientation automatique est déduite de `conf.lua` (largeur > hauteur → paysage).
Les jeux écrits pour LÖVE 12 ne sont pas encore pris en charge par love-android stable.

**Defold** : titre, version, paquet et icônes sont écrits dans `game.project`. Les extensions natives
passent par le serveur de compilation officiel de Defold (connexion Internet du runner).

**Pygame** : la recette pygame de python-for-android est utilisée (Pygame 2, SDL2). Les modules
listés dans `requirements.txt` sont ajoutés automatiquement.

**Jeu HTML5** : CDN reconnus pour le mode hors ligne : cdnjs, jsDelivr, unpkg, code.jquery.com,
cdn.babylonjs.com, pixijs.download, esm.sh, Skypack. Un fichier introuvable reste chargé en ligne.

**Three.js / WebGL**
- *Sans outil de build* : `index.html` + `<script type="importmap">` (ex. `"three"` et `"three/addons/"` vers jsDelivr).
  Tout ce qui est importé est téléchargé **avec ses dépendances** (`three.core.js`, addons, `+esm`, esm.sh),
  ainsi que les ressources appelées depuis un CDN : modèles `.glb/.gltf`, textures, HDR, polices,
  décodeurs Draco/Basis (`setDecoderPath(...)`). L'arborescence est conservée dans `apk_lib/`.
- *Avec Vite (ou autre)* : `npm ci`/`npm install` puis `npm run build` ; pour Vite, `--base ./` est ajouté
  automatiquement. Le dossier `dist/` (ou `build/`, `out/`) devient l'application.
- *Vraies rues avec OpenStreetMap* : ajoute un `osm.json` à côté de `index.html` :
  ```json
  { "lieu": "Gombe, Kinshasa", "rayon": 800, "elements": ["routes", "batiments", "eau", "parcs", "monuments"] }
  ```
  (ou `"centre": [lat, lon]`, ou `"bbox": [sud, ouest, nord, est]` ; rayon max 3 km ; `"rails"` possible).
  À la compilation, les données sont téléchargées une fois (Nominatim + Overpass) dans `osm/data.json`,
  et `osm/osm.js` fournit `chargerOSM()` : routes (largeur réelle), bâtiments (hauteur réelle ou estimée),
  eaux, parcs et monuments, en mètres (x = est, z = sud). Le jeu marche ensuite **sans connexion**.
  Mention obligatoire dans le jeu : « © contributeurs OpenStreetMap ».
- Réglages mobiles ajoutés : viewport sans zoom, pas de défilement ni de sélection, écran gardé allumé.
- Exemple prêt à compiler : `exemples/threejs-ville/` (voiture dans une vraie ville ; zippe le dossier).

## Non pris en charge
- **Unity** et **Unreal** : licence et éditeur obligatoires, impossible sur GitHub Actions gratuit.
- **Ren'Py**, **Solar2D**, **GameMaker** : pas d'export Android en ligne de commande sous Linux.
- L'onglet « Fonction » n'est pas ajouté aux jeux (Godot, LÖVE, Defold, Pygame).
