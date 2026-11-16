# Nouveaux workflows DroidForge Studio

Les modes Unity, Godot, Unreal Engine et Kotlin Multiplatform sont ajoutés au sélecteur de technologies.

Consultez `WORKFLOWS-MOTEURS-3D.md` pour les formats ZIP, secrets GitHub, prérequis et limites de compilation.

## Plugin LinkShare (.lsplugin)
Case « Créer aussi un plugin LinkShare » dans le formulaire (champ `plugin` du fichier de config) : après la compilation,
`.github/scripts/plugin_pack.sh` assemble `NomApp-version.lsplugin` (APK + `plugin.json` avec empreinte SHA-256) et l'ajoute
à la release, à côté de l'APK. Dans LinkShare : Paramètres › Install plugins › Ajouter un nouveau plugin.

`plugin` peut aussi être un objet pour personnaliser la fiche : `{"id":"mediastudio","description":"…","actions":["MP3","PDF"]}`.

Workflows concernés : apk, beeware, defold, dotnet, flutter, godot, love, native, pygame, python, reactnative.
Non concernés pour l'instant (publication différente) : c-cpp, cordova, ionic, kmp, unity, unreal.

Boutons « Télécharger le plugin » : sur l'écran « Ton application est prête » et dans l'onglet « Mes applications »
(visibles seulement si la release contient un fichier `.lsplugin`).

## Plugin LinkShare « intégré » (contrat 2, classes.dex) — Android natif uniquement
Dans le formulaire, le choix **Aucun / Appli installée / Intégré** remplace la case précédente. « Intégré » n'apparaît que pour le type
Kotlin / Java (Android natif). Champ `plugin` du fichier de config :
- `true` → plugin « appli installée » (inchangé : `plugin_pack.sh`, contrat 1, APK dans le .lsplugin) ;
- `{"mode":"embedded","id":"…","description":"…"}` → plugin intégré, sans installer l'appli. `id` / `description` vides = valeurs de `plugin.json`. L'identifiant doit contenir 2 à 40 caractères parmi `a-z`, `0-9`, `-` et `_` (pas de points).
Le choix est restauré en mode modification et remis à zéro à la réinitialisation.

**Convention du projet** (issue du prompt « prépare ce projet pour LinkShare ») :
- module Gradle `plugin` avec la tâche `assemblePlugin` qui produit un jar (`plugin/build/libs/*.jar`) ;
- `plugin/plugin.json` : `id`, `name`, `version`, `description`, **`entryClass`**, `contract: 2`, `permissions` et au moins une `actions[]` (avec `id`, `label`, `accepts`, `minFiles`, `maxFiles`, `params`) ; `entryClass` doit être une classe concrète implémentant `com.linkshare.plugin.api.LinkSharePlugin` et `actions()` doit retourner les mêmes identifiants d'action ;
  clés de build facultatives (retirées du fichier final) : `jar`, `assetsDir` (défaut `src/main/assets`), `libDir` (défaut `src/main/jniLibs/<abi>`), `ownPackages` ;
- l'API se déclare en `compileOnly files(project.findProperty('linkshareApiJar') ?: 'libs/linkshare-plugin-api.jar')`.
  Le jar est stocké dans `.github/plugin-api/` (voir son README pour l'export `:plugin-api:exportApiJar` depuis LinkShare 1.7).

**Chaîne dans `build-native.yml`** : après « Compiler l'APK », l'étape « Plugin intégré (assemblage) » lance `assemblePlugin`, puis
`.github/scripts/plugin_embed.py` qui : lit `plugin.json` et le jar ; vérifie que `entryClass` existe et implémente `LinkSharePlugin` ;
exclut Kotlin, coroutines, `androidx.core`, Compose (et l'API) et signale (avertissement) les autres bibliothèques restées ;
convertit en `classes.dex` avec le `d8` du SDK (`--release --min-api 30`) ; ajoute `assets/` et `lib/<abi>/` ; écrit le sha256 de chaque fichier
dans `plugin.json` sous la clé `sha256` (objet associant chaque chemin à son empreinte, comme l'exige LinkShare 1.7) ; produit `NomApp-version.lsplugin` (`"contract": 2`).
Les ressources non-`.class` du jar ne sont pas conservées : les placer dans `src/main/assets`.

**Publication** : le `.lsplugin` est ajouté à la release avec l'APK. Si le plugin échoue (assemblage ou envoi), seul un avertissement est émis
et l'APK est publiée normalement (`release_create.sh` réessaie sans le plugin en dernier recours).
Les boutons « Télécharger le plugin » affichent « (intégré) » ou « (installée) » selon la config.

**Test** : le workflow `test-plugin.yml` (déclenchement manuel ou modification des fichiers concernés) compile `.github/sample-plugin`
contre un stub d'API de test, produit le `.lsplugin` et vérifie : contrat 2, sha256, `classes.dex`, assets, exclusion de Kotlin/androidx.core,
signalement d'une bibliothèque tierce, refus d'un mauvais `entryClass`.

