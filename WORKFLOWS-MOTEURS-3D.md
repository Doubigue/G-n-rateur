# Workflows moteurs de jeu et Kotlin Multiplatform

DroidForge Studio ajoute quatre chaînes de compilation Android :

## Unity / C#
- ZIP attendu : projet Unity complet avec `Assets/`, `Packages/` et `ProjectSettings/ProjectVersion.txt`.
- GitHub Actions utilise `game-ci/unity-builder`.
- Dans GitHub > Settings > Secrets and variables > Actions, créer `UNITY_LICENSE`, `UNITY_EMAIL` et `UNITY_PASSWORD` selon la méthode de licence Unity utilisée.
- Le compte Unity doit avoir accès à Android Build Support. La licence Unity doit autoriser la compilation CI.
- Le workflow produit l'APK Android dans une Release GitHub.

## Godot / GDScript
- ZIP attendu : `project.godot`, scènes, scripts et ressources.
- Le preset d'export Android doit être nommé exactement `Android` et configuré dans le projet Godot.
- Installer/configurer les modèles d'export Android et les clés de signature dans les paramètres d'export Godot avant l'envoi.
- Le workflow utilise Godot 4.4.1 et publie l'APK.

## Unreal Engine
- ZIP attendu : fichier `.uproject`, `Content/` et `Config/`.
- La compilation Unreal nécessite un runner GitHub **self-hosted** Linux avec Unreal Engine installé, ainsi que Android SDK, NDK et JDK compatibles avec cette version d'Unreal.
- Enregistrer ce runner dans le dépôt avec les labels `self-hosted`, `linux`, `x64`, `unreal-android`.
- Ajouter le secret `UNREAL_ENGINE_ROOT` contenant le chemin absolu du dossier Unreal Engine (celui qui contient `Engine/`).
- Le projet doit avoir Android configuré dans Unreal (SDK/NDK acceptés par Turnkey). Le workflow lance `RunUAT.sh BuildCookRun`.
- Un runner GitHub hébergé standard ne contient pas Unreal Engine : cette compilation ne peut donc pas fonctionner sans runner préinstallé.

## Kotlin Multiplatform
- ZIP attendu : projet Gradle avec `settings.gradle(.kts)` et un module Android (`composeApp/`, `androidApp/` ou `shared/`).
- Le workflow lance `assembleDebug` et publie l'APK debug du module Android.
- Si le module Android porte un nom ou une configuration atypique, vérifiez que sa tâche Gradle `assembleDebug` existe.

## Limites communes
- Les workflows sont déclenchés par l'envoi du fichier de configuration dans `builds/<id>/`.
- Les APK sont publiées dans une Release GitHub ; la page DroidForge Studio récupère le workflow selon son nom.
- Les builds de production/signés nécessitent une configuration de signature propre au moteur. Ces workflows génèrent des APK de test/debug lorsque le moteur le permet.
