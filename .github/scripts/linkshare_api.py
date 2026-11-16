#!/usr/bin/env python3
"""Détecte LinkShare 1.7, construit son API réelle et imprime le chemin du JAR."""
import argparse, os, re, shutil, subprocess, sys, zipfile

EXCLUDE={'.git','.gradle','build','node_modules','__MACOSX'}
def candidates(base):
    out=[]
    for root, dirs, files in os.walk(base):
        dirs[:] = [d for d in dirs if d not in EXCLUDE]
        if not ({'settings.gradle.kts','settings.gradle'} & set(files)): continue
        api=os.path.join(root,'plugin-api')
        build=next((os.path.join(api,n) for n in ('build.gradle.kts','build.gradle') if os.path.isfile(os.path.join(api,n))),None)
        settings=os.path.join(root,next(n for n in ('settings.gradle.kts','settings.gradle') if n in files))
        if not build: continue
        text=open(build,encoding='utf-8',errors='replace').read()
        st=open(settings,encoding='utf-8',errors='replace').read()
        if 'exportApiJar' not in text or 'plugin-api' not in st: continue
        src=os.path.join(api,'src','main','kotlin','com','linkshare','plugin','api')
        required={'LinkSharePlugin.kt','PluginHost.kt','Models.kt'}
        if not required.issubset(set(os.listdir(src)) if os.path.isdir(src) else set()): continue
        out.append(root)
    return sorted(out,key=lambda p:(p.count(os.sep),p))
def main():
    p=argparse.ArgumentParser()
    p.add_argument('--project',help='Racine du projet Android importé')
    p.add_argument('--reference-zip',help='ZIP du projet source LinkShare')
    p.add_argument('--work',required=True)
    p.add_argument('--gradle',default='gradle')
    a=p.parse_args(); work=os.path.abspath(a.work); shutil.rmtree(work,ignore_errors=True); os.makedirs(work)
    roots=[]
    # Priorité au projet LinkShare lui-même (source la plus fidèle à l'application en cours).
    if a.project and os.path.isdir(a.project): roots += candidates(os.path.abspath(a.project))
    if not roots and a.reference_zip:
        if not zipfile.is_zipfile(a.reference_zip): sys.exit('ERREUR LINKSHARE: le fichier de référence n’est pas un ZIP valide.')
        extracted=os.path.join(work,'reference'); os.makedirs(extracted)
        with zipfile.ZipFile(a.reference_zip) as z:
            for info in z.infolist():
                name=info.filename.replace('\\','/')
                if name.startswith('/') or any(x in ('..','') for x in name.split('/')[:-1]):
                    sys.exit('ERREUR LINKSHARE: chemin dangereux dans le ZIP : '+name)
                if info.is_dir(): continue
                dest=os.path.realpath(os.path.join(extracted,*name.split('/')))
                if not dest.startswith(os.path.realpath(extracted)+os.sep): sys.exit('ERREUR LINKSHARE: chemin ZIP hors dossier.')
                os.makedirs(os.path.dirname(dest),exist_ok=True)
                with z.open(info) as src, open(dest,'wb') as dst: shutil.copyfileobj(src,dst)
        roots=candidates(extracted)
    if not roots:
        sys.exit('ERREUR LINKSHARE: projet source incompatible. Il faut settings.gradle(.kts), plugin-api/build.gradle(.kts), exportApiJar et les sources Kotlin LinkSharePlugin/PluginHost/Models.')
    root=roots[0]
    print('Projet LinkShare détecté : '+root,flush=True)
    print('Tâche API : :plugin-api:exportApiJar',flush=True)
    env=os.environ.copy()
    sdk=env.get('ANDROID_HOME') or env.get('ANDROID_SDK_ROOT')
    if not sdk: sys.exit('ERREUR LINKSHARE: Android SDK absent (ANDROID_HOME).')
    # La source v1.7 déclare compileSdk 35 ; la plateforme et les build-tools sont préparés par le workflow.
    cmd=[a.gradle,':plugin-api:exportApiJar','--no-daemon']
    r=subprocess.run(cmd,cwd=root,env=env)
    if r.returncode: sys.exit('ERREUR LINKSHARE: exportApiJar a échoué (code %d).'%r.returncode)
    jar=os.path.join(root,'build','plugin-api','linkshare-plugin-api-2.0.jar')
    if not os.path.isfile(jar) or os.path.getsize(jar)<1000: sys.exit('ERREUR LINKSHARE: le JAR réel attendu est absent ou vide : '+jar)
    with zipfile.ZipFile(jar) as z:
        entries=set(z.namelist())
        for cls in ('com/linkshare/plugin/api/LinkSharePlugin.class','com/linkshare/plugin/api/PluginHost.class','com/linkshare/plugin/api/PluginAction.class','com/linkshare/plugin/api/PluginInput.class','com/linkshare/plugin/api/PluginResult.class'):
            if cls not in entries: sys.exit('ERREUR LINKSHARE: classe API manquante dans le JAR : '+cls)
    print(jar)
if __name__=='__main__': main()
