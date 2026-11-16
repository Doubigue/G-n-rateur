#!/usr/bin/env bash
# Assemble un plugin LinkShare (.lsplugin) à partir de l'APK qui vient d'être compilé.
# Usage : plugin_pack.sh CONFIG.json APK SORTIE.lsplugin
# Ne fait rien (code 3) si la demande n'a pas coché « plugin LinkShare ». Ne bloque jamais la publication de l'APK.
CF="$1"; APK="$2"; OUT="$3"
[ -f "$CF" ] && [ -f "$APK" ] || exit 2
command -v zip >/dev/null || { echo "::warning::zip absent : plugin LinkShare non créé" >&2; exit 4; }

TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
APKNAME="$(basename "$APK")"

# Package réel de l'APK (certains workflows réécrivent l'identifiant) ; sinon LinkShare le lit lui-même dans l'APK
PKG=""
AAPT="$(ls -1 "${ANDROID_HOME:-/usr/local/lib/android/sdk}"/build-tools/*/aapt2 2>/dev/null | sort -V | tail -n1)"
[ -n "$AAPT" ] && PKG="$("$AAPT" dump packagename "$APK" 2>/dev/null | head -n1)"

python3 - "$CF" "$APK" "$APKNAME" "$PKG" "$TMP" <<'PY'
import hashlib, json, sys
cf, apk, apkname, pkg, tmp = sys.argv[1:6]
c = json.load(open(cf, encoding="utf-8"))
p = c.get("plugin")
if not p:                       # absent, false ou vide : pas de plugin
    sys.exit(3)
opt = p if isinstance(p, dict) else {}
sha = hashlib.sha256(open(apk, "rb").read()).hexdigest()
name = str(c.get("name") or "Plugin")
meta = {
    "id": str(opt.get("id") or c.get("pkg") or "plugin"),
    "name": name,
    "version": str(c.get("versionName") or "1.0"),
    "contract": 1,
    "description": str(opt.get("description") or "Plugin créé avec le Générateur : " + name),
    "actions": [str(a) for a in (opt.get("actions") or [])],
    "apk": apkname,
    "sha256": sha,
}
if pkg:
    meta["package"] = pkg
json.dump(meta, open(tmp + "/plugin.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)
PY
RC=$?
[ "$RC" = 0 ] || exit "$RC"

cp "$APK" "$TMP/$APKNAME"
OUT_ABS="$(cd "$(dirname "$OUT")" && pwd)/$(basename "$OUT")"
( cd "$TMP" && zip -q -X "$OUT_ABS" plugin.json "$APKNAME" ) || exit 6
echo "Plugin LinkShare créé : $OUT" >&2
exit 0
