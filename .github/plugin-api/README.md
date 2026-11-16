# API LinkShare réelle — génération automatique

Les builds de production ne lisent aucun JAR déposé manuellement ici et n'utilisent aucun stub.

La référence source LinkShare Explorer v1.7 est conservée dans :

`.github/linkshare-reference/LinkShare-Explorer-v1.7.zip`

Le workflow Android natif extrait ce projet et exécute :

```bash
gradle :plugin-api:exportApiJar --no-daemon
```

Le JAR résultant est attendu à `LinkShare/build/plugin-api/linkshare-plugin-api-2.0.jar`. Le chemin réel est contrôlé et transmis au module plugin en `compileOnly`. Si le projet Android importé est lui-même LinkShare et contient le module `plugin-api` conforme, il est utilisé en priorité.

Un ZIP de référence différent peut être importé dans le formulaire « Intégré ». Il est stocké temporairement sous `builds/<id>/linkshare-source.zip` pour le build en cours.

Voir `README-LINKSHARE-INTEGRATION.md` pour l'architecture, les exigences de plugin et les tests.
