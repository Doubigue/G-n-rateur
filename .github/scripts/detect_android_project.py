#!/usr/bin/env python3
"""Détecte la racine Gradle Android qui contient un module application."""
import os, re, sys

BASE = os.path.abspath(sys.argv[1])
EXCLUDE = {".git", ".gradle", "build", "node_modules", "__MACOSX"}

def files_under(root):
    for cur, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in EXCLUDE]
        yield cur, files

candidates = []
for cur, files in files_under(BASE):
    settings = next((n for n in ("settings.gradle.kts", "settings.gradle") if n in files), None)
    if not settings:
        continue
    settings_path = os.path.join(cur, settings)
    # Avoid treating nested projects as modules of an outer candidate.
    has_app = False
    has_api = False
    for sub, subfiles in files_under(cur):
        if sub != cur and any(n in subfiles for n in ("settings.gradle", "settings.gradle.kts")):
            continue
        build = next((n for n in ("build.gradle.kts", "build.gradle") if n in subfiles), None)
        if not build:
            continue
        text = open(os.path.join(sub, build), encoding="utf-8", errors="ignore").read()
        if re.search(r"com\.android\.application|android\.application", text) and os.path.isfile(os.path.join(sub, "src", "main", "AndroidManifest.xml")):
            has_app = True
        if os.path.basename(sub) == "plugin-api" and re.search(r"exportApiJar", text):
            has_api = True
    if has_app:
        depth = cur.count(os.sep)
        score = (100 if has_api else 0) - depth
        candidates.append((score, cur, has_api))
if not candidates:
    sys.exit("Aucun projet Gradle Android avec module application trouvé dans le ZIP.")
candidates.sort(reverse=True)
_, selected, has_api = candidates[0]
print(selected)
if has_api:
    print("LinkShare plugin-api détecté", file=sys.stderr)
