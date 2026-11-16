#!/usr/bin/env bash
# Publie une release GitHub en réessayant si l'envoi échoue.
# Usage : identique à « gh release create », ex. :
#   bash .github/scripts/release_create.sh "apk-$ID" fichier.apk --title "Nom" --notes "Notes"
# Les gros APK (150 Mo et plus) peuvent échouer sur une coupure réseau chez GitHub :
# on supprime la release incomplète puis on recommence (4 essais au total).
TAG="$1"
for TRY in 1 2 3 4; do
  if gh release create "$@"; then exit 0; fi
  echo "::warning::Publication de la release $TAG échouée (essai $TRY/4)"
  [ "$TRY" = 4 ] && break
  gh release delete "$TAG" --cleanup-tag -y >/dev/null 2>&1 || true
  sleep $((TRY * 15))
done
# Dernier recours : le plugin .lsplugin ne doit jamais empêcher la publication de l'APK.
REST=(); SANS=0
for A in "$@"; do
  if [[ "$A" == *.lsplugin && -f "$A" ]]; then SANS=1; else REST+=("$A"); fi
done
if [ "$SANS" = 1 ]; then
  echo "::warning::Nouvel essai sans le plugin .lsplugin (publié avec l'APK seulement)"
  gh release delete "$TAG" --cleanup-tag -y >/dev/null 2>&1 || true
  if gh release create "${REST[@]}"; then exit 0; fi
fi
echo "::error::Impossible de publier la release $TAG après 4 essais"
exit 1
