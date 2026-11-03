#!/usr/bin/env bash
# Clé de signature UNIQUE pour toutes les applications générées par APK Studio.
# Sans cette clé identique d'une version à l'autre, Android refuse d'installer la mise à jour
# par-dessus l'application déjà installée (« Application non installée » / « conflit de paquet »).
#
#   signing.sh setup          crée/réutilise signing/debug.keystore, force Gradle à l'utiliser
#                             (même si le projet déclare sa propre clé) et exporte SIGN_SHA256
#   signing.sh verify <apk>   vérifie que l'APK produit est bien signé avec cette clé
set -euo pipefail

WS="${GITHUB_WORKSPACE:-$(pwd)}"
K="$WS/signing/debug.keystore"
PASS=android
ALIAS=androiddebugkey

empreinte_cle() {
  keytool -list -v -keystore "$1" -storepass "$PASS" -alias "$ALIAS" 2>/dev/null \
    | sed -n 's/^[[:space:]]*SHA256:[[:space:]]*//p' | head -n1 | tr -d ':[:space:]' | tr 'A-F' 'a-f'
}

case "${1:-}" in
setup)
  mkdir -p ~/.android "$WS/signing"
  if [ -f "$K" ]; then
    echo "Clé de signature stable réutilisée : signing/debug.keystore"
  else
    keytool -genkeypair -keystore "$K" -storepass "$PASS" -keypass "$PASS" \
      -alias "$ALIAS" -keyalg RSA -keysize 2048 -validity 36500 \
      -dname "CN=Android Debug,O=Android,C=US"
    ( cd "$WS"
      git config user.name "github-actions"
      git config user.email "github-actions@users.noreply.github.com"
      git add -f signing/debug.keystore
      git commit -qm "Clé de signature stable [skip ci]" || true
      git pull --rebase -q || true
      git push -q || true )
    echo "Nouvelle clé de signature créée et enregistrée dans signing/ (les applis installées AVANT doivent être désinstallées une seule fois)"
  fi
  cp "$K" ~/.android/debug.keystore

  # Script d'initialisation Gradle : s'applique à TOUS les builds Gradle de la machine
  # (Capacitor, Kotlin/Java, React Native, Flutter, Cordova, BeeWare, Buildozer…).
  # Il remplace la clé « debug » et la clé de chaque type de build par la clé stable,
  # après la lecture du build.gradle du projet : une clé propre au ZIP ne peut plus s'imposer.
  mkdir -p ~/.gradle/init.d
  cat > ~/.gradle/init.d/apkstudio-signing.gradle <<'GRADLE'
def apkKs = System.getenv('APKSTUDIO_KEYSTORE')
if (apkKs && new File(apkKs).isFile()) {
    def apkSign = { ext ->
        def sc = ext.signingConfigs.findByName('debug')
        if (sc == null) sc = ext.signingConfigs.create('debug')
        sc.storeFile = new File(apkKs)
        sc.storePassword = 'android'
        sc.keyAlias = 'androiddebugkey'
        sc.keyPassword = 'android'
        ext.buildTypes.all { bt -> bt.signingConfig = sc }
    }
    gradle.allprojects { p ->
        p.plugins.withId('com.android.application') {
            boolean ok = false
            def ac = p.extensions.findByName('androidComponents')
            if (ac != null) {
                try { ac.finalizeDsl { ext -> apkSign(ext) }; ok = true } catch (Throwable ignored) { }
            }
            if (!ok) p.afterEvaluate { apkSign(p.android) }
            p.logger.lifecycle("APK Studio : signature forcée avec la clé stable (" + p.path + ")")
        }
    }
}
GRADLE

  SHA=$(empreinte_cle "$K")
  if [ -n "${GITHUB_ENV:-}" ]; then
    echo "APKSTUDIO_KEYSTORE=$K" >> "$GITHUB_ENV"
    echo "SIGN_SHA256=$SHA" >> "$GITHUB_ENV"
  fi
  echo "Empreinte SHA-256 de la clé : $SHA"
  ;;

verify)
  APK="${2:?APK manquant}"
  ATT=$(empreinte_cle "$K")
  BT=$(ls -d "${ANDROID_HOME:-${ANDROID_SDK_ROOT:-/usr/local/lib/android/sdk}}"/build-tools/* 2>/dev/null | sort -V | tail -n1 || true)
  if [ -z "$BT" ] || [ ! -x "$BT/apksigner" ]; then
    echo "apksigner introuvable : vérification de signature ignorée."
    exit 0
  fi
  OUT=$("$BT/apksigner" verify --print-certs "$APK" 2>&1 || true)
  GOT=$(printf '%s\n' "$OUT" | sed -n 's/^Signer #1 certificate SHA-256 digest: //p' | head -n1 | tr -d ':[:space:]' | tr 'A-F' 'a-f')
  echo "Signature de l'APK : ${GOT:-inconnue}"
  echo "Clé stable attendue : $ATT"
  if [ "$GOT" != "$ATT" ]; then
    echo "ERREUR : l'APK n'est pas signé avec la clé stable du dépôt."
    echo "Android refuserait de l'installer par-dessus la version déjà installée."
    printf '%s\n' "$OUT" | head -n 20
    exit 1
  fi
  echo "Signature conforme : la mise à jour s'installera par-dessus l'ancienne version."
  ;;

*)
  echo "Usage : signing.sh setup | verify <apk>" >&2
  exit 2
  ;;
esac
