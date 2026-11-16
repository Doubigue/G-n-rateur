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

Le mode « Intégré » construit l’API réelle LinkShare 1.7 automatiquement depuis le ZIP source de référence fourni dans `.github/linkshare-reference/`, ou depuis le projet LinkShare importé. Un ZIP de remplacement peut être fourni dans le formulaire. Le JAR est exporté par `:plugin-api:exportApiJar`, transmis dynamiquement à `assemblePlugin` en `compileOnly`, puis converti par D8 en `classes.dex`. Le fichier `.lsplugin` est validé avant publication par `validate_lsplugin.py`.

Le détail de l’architecture, le format du manifeste, l’exemple Kotlin et les tests se trouvent dans [README-LINKSHARE-INTEGRATION.md](README-LINKSHARE-INTEGRATION.md). Le mode « Appli installée » conserve son ancien flux contrat 1. Le mode « Aucun » reste inchangé. Une erreur LinkShare empêche uniquement la publication du plugin intégré ; elle ne bloque pas la publication de l’APK.
