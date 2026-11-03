#!/usr/bin/env bash
# Exécuté DANS l'émulateur Android (lancé par reactivecircus/android-emulator-runner).
# Installe work/app.apk, la lance, exécute les actions demandées, prend des captures,
# repère les plantages dans logcat et écrit $DIR/emu-report.json.
set -u
cd "$GITHUB_WORKSPACE"
CFG="$DIR/emulate.json"
PKG=$(jq -r '.pkg' "$CFG")
SECS=$(jq -r '.seconds // 20' "$CFG")
OUT="$GITHUB_WORKSPACE/$DIR/emu-report.json"
SH=work/shots; LOG=work/logcat.txt
mkdir -p "$SH"; : > "$LOG"
IM=$(command -v magick || command -v convert || true)
N=0; CRASHED=0; INST=""
num() { echo "${1:-0}" | tr -cd '0-9'; }

shot() {                       # $1 = légende
  [ "$N" -ge 10 ] && return 0
  N=$((N+1)); local F; F=$(printf '%s/%02d' "$SH" "$N")
  adb exec-out screencap -p > "$F.png" 2>/dev/null
  if [ -s "$F.png" ] && [ -n "$IM" ]; then
    "$IM" "$F.png" -resize 320x -quality 55 "$F.jpg" && printf '%s' "$1" > "$F.txt"
  else
    N=$((N-1))
  fi
  return 0
}

alive() { [ -n "$(adb shell pidof "$PKG" 2>/dev/null | tr -d '\r')" ]; }

report() {                     # $1 = ok(true/false)  $2 = message d'erreur
  local shots='[]' j lab
  for j in "$SH"/*.jpg; do
    [ -f "$j" ] || continue
    lab=$(cat "${j%.jpg}.txt" 2>/dev/null)
    base64 -w0 "$j" > work/b64.txt
    shots=$(printf '%s' "$shots" | jq --arg l "$lab" --rawfile d work/b64.txt '. + [{label:$l, data:$d}]')
  done
  local crash tail
  crash=$(awk '/FATAL EXCEPTION|Fatal signal|ANR in|signal 11|SIGSEGV|UnsatisfiedLinkError/{c=45} c>0{print; c--}' "$LOG" | head -c 6000)
  tail=$(grep -E "$PKG|AndroidRuntime|flutter|ReactNative|python|E/" "$LOG" | tail -n 60 | cut -c1-300)
  jq -n --argjson ok "$1" --arg error "${2:-}" --arg pkg "$PKG" --argjson shots "$shots" \
        --arg crash "$crash" --arg tail "$tail" --arg inst "$INST" \
        --argjson alive "$( alive && echo true || echo false )" --argjson secs "$SECS" \
        '{ok:$ok,error:$error,pkg:$pkg,alive:$alive,seconds:$secs,device:"Pixel 6 · Android 14 (API 34)",install:$inst,crash:$crash,logTail:$tail,shots:$shots}' > "$OUT"
  # garde le rapport sous 900 Ko (lecture par l'API contents de GitHub)
  while [ "$(wc -c < "$OUT")" -gt 900000 ] && [ "$(jq '.shots|length' "$OUT")" -gt 1 ]; do
    jq '.shots |= [ .[range(0; length; 2)] ]' "$OUT" > "$OUT.tmp" && mv "$OUT.tmp" "$OUT"
  done
}

adb logcat -c || true
adb logcat -v time '*:W' 'flutter:V' > "$LOG" 2>&1 &
LOGPID=$!

INST=$(adb install -r -t -g work/app.apk 2>&1 | tr -d '\r' | tail -n 3)
echo "$INST"
if ! echo "$INST" | grep -q Success; then
  MSG="Installation impossible : $INST"
  echo "$INST" | grep -q NO_MATCHING_ABIS && MSG="$MSG — l'APK n'a pas de bibliothèque x86_64 (Python/Kivy : ajoute x86_64 aux architectures buildozer)."
  kill "$LOGPID" 2>/dev/null; report false "$MSG"; exit 0
fi

adb shell monkey -p "$PKG" -c android.intent.category.LAUNCHER 1 >/dev/null 2>&1
sleep 7
shot "Démarrage"
alive || CRASHED=1

if [ "$CRASHED" = 0 ]; then
  while IFS= read -r L; do
    [ -z "$L" ] && continue
    set -f; set -- $L; set +f
    case "$1" in
      wait)  sleep "$(num "${2:-2}")" ;;
      tap)   adb shell input tap "$(num "$2")" "$(num "$3")" ;;
      swipe) adb shell input swipe "$(num "$2")" "$(num "$3")" "$(num "$4")" "$(num "$5")" "$(num "${6:-300}")" ;;
      text)  shift; T=$(echo "$*" | tr -cd 'A-Za-z0-9 ._@-'); adb shell input text "${T// /%s}" ;;
      key)   adb shell input keyevent "KEYCODE_$(echo "$2" | tr a-z A-Z | tr -cd 'A-Z_')" ;;
      shot)  ;;
    esac
    sleep 1.5
    shot "$L"
    alive || { CRASHED=1; break; }
  done < <(jq -r '.steps[]?' "$CFG")
fi

if [ "$CRASHED" = 0 ]; then
  END=$((SECS - 7)); K=0
  while [ "$END" -gt 0 ] && [ "$K" -lt 6 ]; do
    sleep 5; END=$((END-5)); K=$((K+1))
    shot "+${K}×5 s"
    alive || { CRASHED=1; break; }
  done
fi

[ "$CRASHED" = 1 ] && shot "Après la fermeture"
sleep 1; kill "$LOGPID" 2>/dev/null
if [ "$CRASHED" = 1 ]; then report true "L'application s'est fermée pendant le test."; else report true ""; fi
exit 0
