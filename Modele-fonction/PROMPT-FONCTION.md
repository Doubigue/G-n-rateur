# Prompt « Fonction » : à coller à chaque création ou modification d'appli

Joins aussi le fichier `Animation/animation.html` du dossier Modele-fonction.

```
À la RACINE du projet, ajoute ces 3 éléments en plus du code :

1) Description.md (en français)
   - Titre + une phrase : à quoi sert l'appli.
   - « Fonctions » : une ligne par fonction, y compris celles que je viens de demander.
   - « Comment l'utiliser » : étapes numérotées.
   - « Captures » : nom de fichier + écran pour chaque capture (01-accueil.png…).

2) Captures/ : crée TOI-MÊME les captures d'écran de l'appli, une par écran
   principal, en PNG 1080×2400 (portrait téléphone), dans l'ordre d'utilisation :
   01-accueil.png, 02-….png
   - Appli web/HTML : ouvre le vrai projet dans un navigateur sans interface
     (Playwright/Chromium, viewport 360×800, échelle 3), simule les clics et
     saisies, avec des données d'exemple réalistes, et capture chaque écran.
   - Flutter, Kotlin/Java, React Native, Python : si tu ne peux pas lancer l'appli,
     reproduis chaque écran fidèlement (mêmes libellés, couleurs, polices,
     disposition) en HTML, puis capture-le en PNG.
   - Sans cadre de téléphone, sans texte ajouté, sans lien externe.
   - Garde le fichier LISEZ-MOI.txt dans le dossier.
   - Ouvre chaque PNG pour vérifier qu'il n'est pas vide ni coupé.
   - À la fin, dis-moi quelles captures sont réelles et lesquelles sont reconstituées.

3) Animation/animation.html : copie le modèle joint et modifie UNIQUEMENT la zone SCÉNARIO.
   - APP : nom, couleur principale.
   - SCREENS : reproduis les vrais écrans de l'appli (mêmes libellés), un id sur
     chaque élément à toucher.
   - STEPS : une étape par fonction, dans l'ordre d'utilisation d'une vraie personne
     (toucher, écrire, glisser), texte court en français qui explique le « pourquoi ».
   Un seul fichier, sans lien externe. Ne touche pas au moteur sous la zone SCÉNARIO.

Vérifie : chaque fonction de Description.md a au moins une étape, chaque sélecteur
d'une étape existe dans SCREENS, et chaque écran de SCREENS a sa capture.

Fonctionnalités de cette appli : [colle ici ce que tu veux]
```

Dans APK Studio : dépose le ZIP du projet. Le contenu de Description.md remplit le champ
Description du formulaire ; l'appli compilée affiche l'onglet « Fonction » (description,
captures, animation).
