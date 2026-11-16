#!/usr/bin/env python3
"""Assemble un plugin LinkShare INTÉGRÉ (contrat 2) : un .lsplugin contenant classes.dex.

Usage :
  plugin_embed.py CONFIG.json RACINE_PROJET SORTIE.lsplugin
                  [--plugin-json CHEMIN] [--jar CHEMIN] [--api-jar CHEMIN] [--sdk DOSSIER] [--d8 CHEMIN]

Entrées (convention « prépare ce projet pour LinkShare ») :
  RACINE/plugin/plugin.json   fiche du plugin : id, name, version, description, entryClass, …
                              clés facultatives de build (retirées du plugin.json final) :
                                jar        jar du module, relatif à RACINE/plugin (défaut : build/libs/*.jar)
                                assetsDir  dossier d'assets, relatif à RACINE/plugin (défaut : src/main/assets)
                                libDir     dossier des .so par ABI (défaut : src/main/jniLibs)
  le jar produit par la tâche Gradle « assemblePlugin » du module « plugin ».

Étapes : lecture → vérification de entryClass (existe + implémente com.linkshare.plugin.api.LinkSharePlugin)
→ exclusion des bibliothèques fournies par LinkShare → d8 (--release --min-api 30) → ajout assets/ et lib/<abi>/
→ sha256 de chaque fichier écrit dans plugin.json (objet map, format LinkShare 1.7) → NomApp-version.lsplugin.

Code de sortie 0 = plugin créé ; autre = échec (message sur stderr). Le workflow n'en fait qu'un avertissement.
"""
import argparse
import glob
import hashlib
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import zipfile

API_INTERFACE = "com/linkshare/plugin/api/LinkSharePlugin"
MIN_API = "30"
ABIS = ("arm64-v8a", "armeabi-v7a", "x86", "x86_64")

# Fournis par LinkShare à l'exécution : on ne les embarque pas dans classes.dex.
PROVIDED = (
    ("kotlin/", "Kotlin"),
    ("kotlinx/", "Kotlin coroutines"),
    ("androidx/core/", "androidx.core"),
    ("androidx/compose/", "Compose"),
    ("com/linkshare/plugin/api/", "API LinkShare"),
)
# Annotations embarquées par Kotlin : sans effet à l'exécution, retirées avec lui.
ANNOTATIONS = ("org/jetbrains/annotations/", "org/intellij/lang/annotations/")
# Types qui ne peuvent pas implémenter l'API : un parent « inconnu » de ces paquets n'est pas un problème.
TERMINAL = ("java/", "javax/", "android/", "dalvik/", "kotlin/", "kotlinx/")


def avertir(msg):
    print("::warning::" + msg, flush=True)


def echec(msg):
    print("Erreur : " + msg, file=sys.stderr, flush=True)
    sys.exit(1)


# --------------------------------------------------------------------------- lecture des .class
def lire_classe(data):
    """Retourne (nom, super, [interfaces], access_flags) d'un fichier .class, ou None si illisible."""
    try:
        if data[:4] != b"\xca\xfe\xba\xbe":
            return None
        n = struct.unpack(">H", data[8:10])[0]
        i, cp = 10, [None] * n
        k = 1
        while k < n:
            tag = data[i]
            if tag == 1:
                ln = struct.unpack(">H", data[i + 1:i + 3])[0]
                cp[k] = ("u", data[i + 3:i + 3 + ln].decode("utf-8", "replace"))
                i += 3 + ln
            elif tag == 7:
                cp[k] = ("c", struct.unpack(">H", data[i + 1:i + 3])[0])
                i += 3
            elif tag in (3, 4, 9, 10, 11, 12, 17, 18):
                i += 5
            elif tag in (5, 6):
                i += 9
                k += 1
            elif tag in (8, 16, 19, 20):
                i += 3
            elif tag == 15:
                i += 4
            else:
                return None
            k += 1

        def nom(idx):
            if not idx:
                return None
            return cp[cp[idx][1]][1]

        flags, this_c, super_c, ni = struct.unpack(">HHHH", data[i:i + 8])
        itf = [nom(struct.unpack(">H", data[i + 8 + 2 * j:i + 10 + 2 * j])[0]) for j in range(ni)]
        return nom(this_c), nom(super_c), itf, flags
    except Exception:
        return None


def hierarchie(jars):
    """Table nom → (super, interfaces, flags) pour toutes les classes des jars donnés."""
    t = {}
    for j in jars:
        if not j or not os.path.isfile(j):
            continue
        try:
            with zipfile.ZipFile(j) as z:
                for e in z.namelist():
                    if e.endswith(".class") and not e.startswith("META-INF/"):
                        r = lire_classe(z.read(e))
                        if r and r[0]:
                            t[r[0]] = (r[1], r[2], r[3])
        except zipfile.BadZipFile:
            echec("jar illisible : " + j)
    return t


def implemente(table, nom, cible, vus=None, inconnus=None):
    """True si `nom` hérite de/implémente `cible`. Remplit `inconnus` avec les parents introuvables."""
    vus = set() if vus is None else vus
    if nom is None or nom in vus:
        return False
    vus.add(nom)
    if nom == cible:
        return True
    if nom not in table:
        if inconnus is not None and not nom.startswith(TERMINAL):
            inconnus.add(nom)
        return False
    sup, itf, _ = table[nom]
    return any(implemente(table, p, cible, vus, inconnus) for p in [sup] + itf)


# --------------------------------------------------------------------------- SDK
def _vkey(s):
    return [int(x) if x.isdigit() else 0 for x in re.split(r"[.\-]", s)]


def trouver_d8(sdk, force):
    if force:
        return [force]
    for cand in (os.environ.get("D8"),):
        if cand:
            return [cand]
    if sdk:
        bt = sorted(glob.glob(os.path.join(sdk, "build-tools", "*")), key=lambda p: _vkey(os.path.basename(p)))
        for d in reversed(bt):
            p = os.path.join(d, "d8")
            if os.path.isfile(p):
                return [p]
            jar = os.path.join(d, "lib", "d8.jar")
            if os.path.isfile(jar):
                return ["java", "-cp", jar, "com.android.tools.r8.D8"]
    p = shutil.which("d8")
    if p:
        return [p]
    echec("d8 introuvable (SDK Android : build-tools/<version>/d8). Définis ANDROID_HOME ou --sdk.")


def trouver_android_jar(sdk):
    if not sdk:
        return None
    pl = sorted(glob.glob(os.path.join(sdk, "platforms", "android-*", "android.jar")),
                key=lambda p: _vkey(os.path.basename(os.path.dirname(p)).replace("android-", "")))
    return pl[-1] if pl else None


# --------------------------------------------------------------------------- outils
def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def trouver_jar(dossier_plugin, pj):
    if pj.get("jar"):
        p = os.path.normpath(os.path.join(dossier_plugin, str(pj["jar"])))
        if not os.path.isfile(p):
            echec("jar indiqué par plugin.json introuvable : " + p)
        return p
    for motif in ("build/libs/*.jar", "build/**/libs/*.jar", "build/outputs/**/*.jar", "build/intermediates/**/*.jar"):
        c = [p for p in glob.glob(os.path.join(dossier_plugin, motif), recursive=True)
             if not re.search(r"-(sources|javadoc)\.jar$", p)]
        if c:
            return max(c, key=os.path.getmtime)
    echec("aucun jar du module « plugin » trouvé sous %s/build (la tâche assemblePlugin doit produire un jar)." % dossier_plugin)


def trouver_api_jar(explicite):
    cands = [explicite] if explicite else []
    cands.append(os.environ.get("LINKSHARE_API_JAR"))
    ici = os.path.dirname(os.path.abspath(__file__))
    cands += sorted(glob.glob(os.path.join(ici, "..", "plugin-api", "linkshare-plugin-api*.jar")))
    for c in cands:
        if c and os.path.isfile(c):
            return os.path.abspath(c)
    return None


def fichiers_dossier(base):
    out = []
    for r, ds, fs in os.walk(base):
        ds[:] = sorted(d for d in ds if not d.startswith("."))
        for f in sorted(fs):
            if f.startswith(".") or f == "Thumbs.db":
                continue
            p = os.path.join(r, f)
            out.append((os.path.relpath(p, base).replace(os.sep, "/"), p))
    return out


# --------------------------------------------------------------------------- principal
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("config")
    ap.add_argument("racine")
    ap.add_argument("sortie")
    ap.add_argument("--plugin-json")
    ap.add_argument("--jar")
    ap.add_argument("--api-jar")
    ap.add_argument("--classpath", action="append", default=[], help="JAR compileOnly supplémentaire nécessaire à la résolution D8 (répétable)")
    ap.add_argument("--sdk")
    ap.add_argument("--d8")
    a = ap.parse_args()

    cfg = json.load(open(a.config, encoding="utf-8"))
    opt = cfg.get("plugin") if isinstance(cfg.get("plugin"), dict) else {}
    dossier = os.path.join(a.racine, "plugin")
    pjp = a.plugin_json or os.path.join(dossier, "plugin.json")
    if not os.path.isfile(pjp):
        echec("plugin/plugin.json introuvable dans le projet (%s). Utilise le prompt « prépare ce projet pour LinkShare »." % pjp)
    try:
        pj = json.load(open(pjp, encoding="utf-8"))
    except ValueError as e:
        echec("plugin.json invalide : %s" % e)

    entry = str(pj.get("entryClass") or "").strip()
    if not entry:
        echec("plugin.json : « entryClass » manquant.")
    entry_path = entry.replace(".", "/")

    # Prévalidation du manifeste selon PluginManifestParser de LinkShare 1.7.
    plugin_id = str(opt.get("id") or pj.get("id") or "").strip()
    if not plugin_id:
        plugin_id = re.sub(r"[^a-z0-9_-]+", "-", str(cfg.get("pkg") or "plugin").lower()).strip("-_")
        plugin_id = plugin_id[:40] if len(plugin_id) >= 2 else "plugin"
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{1,39}", plugin_id):
        echec("plugin.json : id invalide pour LinkShare (2 à 40 caractères, minuscules, chiffres, - et _).")
    actions = pj.get("actions")
    if not isinstance(actions, list) or not actions:
        echec("plugin.json : au moins une action est obligatoire pour LinkShare (actions[]).")
    if len(actions) > 30:
        echec("plugin.json : LinkShare accepte 30 actions au maximum.")
    action_ids = []
    for action in actions:
        if not isinstance(action, dict) or not re.fullmatch(r"[A-Za-z0-9_.-]{1,40}", str(action.get("id") or "")) or not str(action.get("label") or "").strip():
            echec("plugin.json : chaque action doit avoir un id valide et un label non vide.")
        action_ids.append(action["id"])
    if len(set(action_ids)) != len(action_ids):
        echec("plugin.json : identifiants d'action en double.")
    permissions = pj.get("permissions", [])
    if not isinstance(permissions, list) or any(x not in ("storage", "notifications", "network") for x in permissions):
        echec("plugin.json : permissions autorisées : storage, notifications, network.")

    jar = a.jar or trouver_jar(dossier, pj)
    if not os.path.isfile(jar):
        echec("jar introuvable : " + jar)
    print("Jar du module : " + jar)
    api = trouver_api_jar(a.api_jar)
    if not api:
        echec("API LinkShare réelle absente : le contrat 2 ne peut pas être compilé/validé sans le JAR exporté du projet source LinkShare. Aucun stub n'est accepté en production.")
    print("Jar API LinkShare réel : " + api)

    # 1) entryClass : existe + implémente LinkSharePlugin
    table = hierarchie([jar, api])
    if entry_path not in table:
        echec("entryClass « %s » absente du jar (%s)." % (entry, os.path.basename(jar)))
    flags = table[entry_path][2]
    if flags & 0x0200 or flags & 0x0400:
        echec("entryClass « %s » est une interface ou une classe abstraite : il faut une classe concrète." % entry)
    inconnus = set()
    if not implemente(table, entry_path, API_INTERFACE, inconnus=inconnus):
        detail = (" Parents introuvables : " + ", ".join(sorted(inconnus)[:5])) if inconnus else ""
        echec("entryClass « %s » n'implémente pas l'interface réelle %s.%s" % (entry, API_INTERFACE.replace("/", "."), detail))
    # Vérifie les constantes réellement référencées dans le bytecode de la méthode actions().
    javap = shutil.which("javap")
    if not javap:
        echec("javap introuvable : JDK 17 requis pour vérifier les IDs de actions().")
    cp = os.pathsep.join([jar, api] + list(a.classpath))
    jr = subprocess.run([javap, "-classpath", cp, "-c", "-p", entry], capture_output=True, text=True)
    if jr.returncode:
        echec("Impossible d'inspecter entryClass avec javap : " + (jr.stderr.strip() or str(jr.returncode)))
    lines = jr.stdout.splitlines()
    start = next((i for i, line in enumerate(lines) if re.search(r"\bactions\(\);?$", line.strip())), None)
    if start is None:
        echec("entryClass ne déclare pas de méthode actions() visible.")
    end = next((i for i in range(start + 1, len(lines)) if re.match(r"\s*(public|protected|private)\s+.+\);$", lines[i])), len(lines))
    actions_code = "\n".join(lines[start:end])
    for action_id in action_ids:
        if action_id not in actions_code:
            echec("Action « %s » déclarée dans plugin.json mais absente des constantes bytecode de entryClass.actions()." % action_id)
    print("entryClass OK : " + entry + " ; actions() confirme : " + ", ".join(action_ids))

    # 2) exclusions + signalement des bibliothèques restantes
    tmp = tempfile.mkdtemp(prefix="lsembed-")
    try:
        gardees, exclues, autres_res = [], {}, 0
        filtre = os.path.join(tmp, "module.jar")
        with zipfile.ZipFile(jar) as zi, zipfile.ZipFile(filtre, "w", zipfile.ZIP_DEFLATED) as zo:
            for e in zi.namelist():
                if e.endswith("/"):
                    continue
                if not e.endswith(".class") or e.startswith("META-INF/") or e == "module-info.class":
                    if not e.startswith("META-INF/"):
                        autres_res += 1
                    continue
                lib = next((n for p, n in PROVIDED if e.startswith(p)), None) or \
                    ("annotations Kotlin" if e.startswith(ANNOTATIONS) else None)
                if lib:
                    exclues[lib] = exclues.get(lib, 0) + 1
                    continue
                zo.writestr(e, zi.read(e))
                gardees.append(e)
        for lib, n in sorted(exclues.items()):
            print("Exclu (fourni par LinkShare) : %s — %d classe(s)" % (lib, n))
        if not gardees:
            echec("plus aucune classe à convertir après exclusion des bibliothèques fournies.")
        if autres_res:
            avertir("%d ressource(s) non-.class du jar ignorée(s) : place les fichiers à embarquer dans plugin/src/main/assets." % autres_res)

        parts = entry.split(".")
        racine_pkg = "/".join(parts[:2]) + "/" if len(parts) > 2 else "/".join(parts[:-1]) + "/"
        propres = [x.rstrip("/") for x in pj.get("ownPackages", [])] if isinstance(pj.get("ownPackages"), list) else []
        reste = {}
        for e in gardees:
            if e.startswith(racine_pkg) or any(e.startswith(p.replace(".", "/") + "/") for p in propres):
                continue
            pk = "/".join(e.split("/")[:3]).replace("/", ".")
            reste[pk] = reste.get(pk, 0) + 1
        for pk, n in sorted(reste.items()):
            avertir("Bibliothèque non fournie par LinkShare restée dans le plugin : %s (%d classe(s)). "
                    "Elle sera embarquée dans classes.dex : vérifie qu'elle est nécessaire." % (pk, n))

        # 3) d8 → classes.dex
        sdk = a.sdk or os.environ.get("ANDROID_HOME") or os.environ.get("ANDROID_SDK_ROOT")
        d8 = trouver_d8(sdk, a.d8)
        sortie_dex = os.path.join(tmp, "dex")
        os.makedirs(sortie_dex)
        cmd = d8 + ["--release", "--min-api", MIN_API, "--output", sortie_dex]
        aj = trouver_android_jar(sdk)
        if aj:
            cmd += ["--lib", aj]
        if api:
            cmd += ["--classpath", api]
        for cpjar in a.classpath:
            if not os.path.isfile(cpjar):
                echec("JAR de classpath D8 introuvable : " + cpjar)
            cmd += ["--classpath", cpjar]
        cmd.append(filtre)
        print("d8 : " + " ".join(cmd))
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.stdout.strip():
            print(r.stdout.strip())
        if r.stderr.strip():
            print(r.stderr.strip())
        if r.returncode != 0:
            echec("d8 a échoué (code %d)." % r.returncode)
        dex = sorted(glob.glob(os.path.join(sortie_dex, "classes*.dex")), key=lambda p: (len(p), p))
        if not dex or os.path.basename(dex[0]) != "classes.dex":
            echec("d8 n'a pas produit classes.dex.")

        # 4) contenu de l'archive : (nom dans l'archive, chemin disque)
        contenu = [(os.path.basename(p), p) for p in dex]
        ass = os.path.normpath(os.path.join(dossier, str(pj.get("assetsDir") or "src/main/assets")))
        if os.path.isdir(ass):
            contenu += [("assets/" + rel, p) for rel, p in fichiers_dossier(ass)]
        lib = os.path.normpath(os.path.join(dossier, str(pj.get("libDir") or "src/main/jniLibs")))
        abis = []
        if os.path.isdir(lib):
            for abi in sorted(os.listdir(lib)):
                d = os.path.join(lib, abi)
                if not os.path.isdir(d):
                    continue
                if abi not in ABIS:
                    avertir("ABI inconnue ignorée : lib/%s (attendu : %s)" % (abi, ", ".join(ABIS)))
                    continue
                fs = [(rel, p) for rel, p in fichiers_dossier(d)]
                if fs:
                    abis.append(abi)
                    contenu += [("lib/%s/%s" % (abi, rel), p) for rel, p in fs]

        # 5) plugin.json (contrat 2) avec le sha256 de chaque fichier
        meta = {k: v for k, v in pj.items() if k not in ("jar", "assetsDir", "libDir", "ownPackages", "files")}
        meta["id"] = plugin_id
        meta["name"] = str(cfg.get("name") or pj.get("name") or "Plugin")
        meta["version"] = str(cfg.get("versionName") or pj.get("version") or "1.0")
        meta["description"] = str(opt.get("description") or pj.get("description") or "Plugin créé avec le Générateur : " + meta["name"])
        meta["contract"] = 2
        meta["entryClass"] = entry
        meta.setdefault("settings", [])
        meta["minApi"] = int(MIN_API)
        if abis:
            meta["abis"] = abis
        # LinkShare 1.7 attend un OBJET sha256 contenant l'empreinte de CHAQUE entrée
        # (classes.dex, assets/* et lib/<abi>/*.so), pas un champ files ni une empreinte unique.
        meta.pop("files", None)
        meta["sha256"] = {nom: sha256(p) for nom, p in contenu}
        pjs = os.path.join(tmp, "plugin.json")
        json.dump(meta, open(pjs, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

        # 6) archive
        out = os.path.abspath(a.sortie)
        os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
        if os.path.exists(out):
            os.remove(out)
        noms = [nom for nom, _ in contenu]
        if len(noms) != len(set(noms)) or any(n.startswith("/") or ".." in n.split("/") or "\\" in n for n in noms):
            echec("Chemin d'archive dangereux ou doublonné dans assets/lib.")
        if "classes.dex" not in noms:
            echec("classes.dex obligatoire absent du contenu final.")
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
            z.write(pjs, "plugin.json")
            for nom, p in contenu:
                z.write(p, nom)
        with zipfile.ZipFile(out) as check:
            if check.testzip() is not None:
                echec("Archive .lsplugin corrompue après assemblage.")
            final_names = set(check.namelist())
            if final_names != set(["plugin.json"] + noms):
                echec("Contenu de l'archive différent du manifeste calculé.")
        validator = os.path.join(os.path.dirname(os.path.abspath(__file__)), "validate_lsplugin.py")
        vr = subprocess.run([sys.executable, validator, out], capture_output=True, text=True)
        if vr.stdout.strip(): print(vr.stdout.strip())
        if vr.stderr.strip(): print(vr.stderr.strip(), file=sys.stderr)
        if vr.returncode: echec("validation finale contrat 2 échouée.")
        print("Plugin intégré créé : %s (%d fichier(s), contrat 2)" % (out, len(contenu) + 1))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
