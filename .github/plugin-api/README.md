# API LinkShare — intégration automatique (contrat 2)

Le générateur détecte automatiquement le module `plugin-api` dans le ZIP Android fourni.

## Projet LinkShare lui-même

Lorsque le ZIP contient `LinkShare/settings.gradle.kts`, `LinkShare/plugin-api/` et `sample-plugin/` :

1. Le workflow choisit `LinkShare/` comme racine Android (et non le projet Kotlin JVM `sample-plugin/`).
2. Il compile `:plugin-api:exportApiJar` dans le même job GitHub Actions que l'APK.
3. Il place temporairement le JAR réel dans `sample-plugin/libs/`.
4. Il compile `sample-plugin` avec `gradle buildLsplugin` et génère le `.lsplugin` de démonstration.
5. Il publie l'APK LinkShare et le plugin de démonstration dans la même release de compilation.

Aucune GitHub Release externe, aucun dépôt supplémentaire et aucun transfert manuel ne sont nécessaires.

## Autres projets hôtes

Si un projet Android contient `plugin-api/build.gradle(.kts)` avec la tâche `exportApiJar`, le workflow construit automatiquement le JAR et l'utilise pour compiler `ROOT/plugin/`. Si l'API réelle est absente, la génération du `.lsplugin` contrat 2 échoue explicitement : le stub CI n'est jamais utilisé en production.

## Format et sécurité

Le fichier `.lsplugin` suit le contrat 2 de LinkShare 1.7 : `plugin.json`, `classes.dex`, éventuellement `assets/` et `lib/<abi>/*.so`, avec un objet `sha256` couvrant chaque fichier hors manifeste. Le code d'un plugin s'exécute avec les droits de LinkShare : n'installer que des plugins de confiance.
