# Intégration automatique LinkShare Explorer v1.7 — Générateur de plugins

## Ce qui a changé

Le mode **Intégré** du générateur Android natif produit un plugin LinkShare **contrat 2** (`.lsplugin`) contenant `plugin.json`, `classes.dex` et, si présents, `assets/` et `lib/`. Il utilise le véritable module `plugin-api` de LinkShare 1.7 : aucun JAR à téléverser, aucune GitHub Release externe et aucun stub de production.

Le ZIP source de référence livré avec le générateur est :

`.github/linkshare-reference/LinkShare-Explorer-v1.7.zip`

Il peut être remplacé pour une compilation par un autre ZIP source via le champ **Projet source LinkShare (ZIP facultatif)** affiché lorsque le mode « Intégré » est sélectionné. L'archive est déposée dans `builds/<id>/linkshare-source.zip` et supprimée avec les fichiers temporaires de la demande. Si le projet Android importé est lui-même LinkShare et contient un `plugin-api` conforme, il est prioritaire sur la référence externe.

## Pipeline GitHub Actions

Dans `.github/workflows/build-native.yml` :

1. Extraction du projet Android importé et détection de sa racine Gradle.
2. Si le mode n'est pas « Intégré », aucun travail LinkShare n'est exécuté.
3. Si le mode est « Intégré », `linkshare_api.py` détecte le projet LinkShare (ou extrait le ZIP de référence), contrôle `settings.gradle(.kts)`, `plugin-api/build.gradle.kts`, la tâche `exportApiJar` et les sources Kotlin de l'API.
4. Installation/préparation du SDK Android 35 puis exécution de `gradle :plugin-api:exportApiJar --no-daemon` avec Java 17 / Gradle 8.9.
5. Vérification du JAR et des classes d'API essentielles. Le chemin réel est récupéré dynamiquement.
6. Compilation du module `plugin` contre ce JAR en `compileOnly`, puis génération DEX par D8.
7. Assemblage du `.lsplugin`, calcul SHA-256 de chaque fichier sauf `plugin.json`, puis validation indépendante.
8. Publication du `.lsplugin` uniquement si tous les contrôles réussissent. L'APK reste publiable si la chaîne intégrée échoue ; aucun plugin invalide n'est présenté comme compatible.

Le JAR API utilisé est aussi archivé comme artefact GitHub Actions temporaire (`linkshare-plugin-api-2.0`). Il est transmis directement au processus de compilation du même job, sans chemin codé en dur.

## Structure attendue du projet plugin

À la racine du projet Android importé :

```text
plugin/
  build.gradle[.kts]
  plugin.json
  src/main/kotlin/.../MonPlugin.kt
  src/main/assets/       (facultatif)
  src/main/jniLibs/      (facultatif)
```

Le module `plugin` doit fournir une tâche Gradle `assemblePlugin` produisant un JAR dans `plugin/build/libs/`. Déclarez le vrai JAR API en `compileOnly`, par exemple :

```kotlin
dependencies {
    compileOnly(files(providers.gradleProperty("linkshareApiJar").get()))
}
```

Ne mettez pas dans le DEX l'API LinkShare, Kotlin stdlib, Android SDK (`android.jar`) ou les bibliothèques Android déjà fournies par l'hôte. Les dépendances tierces réellement nécessaires doivent être incluses selon une stratégie de packaging compatible et ne doivent pas dupliquer les bibliothèques fournies par LinkShare.

La classe `entryClass` doit être concrète, avoir un constructeur sans argument et implémenter l'interface `com.linkshare.plugin.api.LinkSharePlugin`. Les IDs de `actions[]` doivent être réellement retournés par `actions()`.

## Exemple fonctionnel

`.github/examples/linkshare-uppercase/` est un exemple Kotlin basé sur les signatures présentes dans LinkShare v1.7. Il lit un fichier texte avec `host.openInput`, vérifie l'annulation, crée le résultat avec `host.createOutput` et retourne un `PluginResult.Success`.

## Format .lsplugin

Le manifeste contient `id`, `name`, `version`, `description`, `entryClass`, `contract: 2`, `permissions`, `actions`, `settings` et `sha256` (objet). `sha256` doit référencer exactement tous les fichiers de l'archive sauf `plugin.json`. `classes.dex` est obligatoire.

Le validateur `.github/scripts/validate_lsplugin.py` contrôle : intégrité ZIP/CRC, chemins, entrées en double, fichiers interdits, schéma minimal, contrat, identifiants, permissions, actions, présence de la classe d'entrée dans le DEX, interface LinkShare, exclusion des classes fournies par l'hôte et toutes les empreintes SHA-256.

## Tests

Le workflow `.github/workflows/test-plugin.yml` construit le véritable JAR API depuis l'archive LinkShare fournie, compile l'exemple Kotlin contre ce JAR, génère le DEX et le `.lsplugin`, valide l'archive, puis vérifie qu'une API absente est refusée. Les stubs présents dans les anciens dossiers de tests ne sont pas utilisés pour les builds de production.

## Limites et sécurité

- Le mode « Intégré » reste réservé au flux Android natif, comme dans l'interface actuelle.
- Un plugin intégré s'exécute dans le processus de LinkShare avec les capacités accordées par l'hôte : n'installez que du code de confiance.
- La validation statique prouve la structure du DEX et la présence des IDs d'action ; le comportement métier doit aussi être testé sur appareil avec LinkShare.
- Le workflow GitHub Actions doit disposer d'un accès réseau aux dépôts Maven/Google pour résoudre les plugins Gradle Android/Kotlin.
