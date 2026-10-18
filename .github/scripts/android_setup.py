#!/usr/bin/env python3
"""Autorisations, partage entrant et activité principale des APK générés.
Usage (à la racine du projet) : android_setup.py <capacitor|flutter> <config.json>"""
import glob, json, os, re, subprocess, sys

if sys.argv[1] == 'fetch':
    # Prépare builds/<id>/app.zip (et icon.png) depuis un lien, une application existante ou un site web.
    import subprocess, urllib.request, zipfile
    cfgp, d = sys.argv[2], sys.argv[3]
    flutter = len(sys.argv) > 4  # tout type autre que « web » refuse un lien de site
    cfg = json.load(open(cfgp, encoding='utf-8'))
    dest, icon = os.path.join(d, 'app.zip'), os.path.join(d, 'icon.png')
    url, frm, kind = cfg.get('sourceUrl', ''), cfg.get('fromRelease', ''), cfg.get('sourceKind', '')

    def telecharger(u, out):
        req = urllib.request.Request(u, headers={'User-Agent': 'apk-studio'})
        with urllib.request.urlopen(req, timeout=120) as r, open(out, 'wb') as f:
            n = 0
            while True:
                b = r.read(1 << 16)
                if not b:
                    break
                n += len(b)
                if n > 200 * 1048576:
                    sys.exit('Fichier trop volumineux (200 Mo max).')
                f.write(b)

    if not os.path.exists(dest):
        if url:
            if not url.startswith(('https://', 'http://')):
                sys.exit('Lien invalide.')
            if kind == 'site':
                if flutter:
                    sys.exit("Un lien de site web n'est compatible qu'avec le mode Site web.")
                with zipfile.ZipFile(dest, 'w') as z:
                    z.writestr('index.html', '<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Chargement</title><body style="font-family:sans-serif;text-align:center;padding:3rem">Chargement…</body>')
            else:
                m = re.match(r'https?://github\.com/([^/]+)/([^/#?]+?)(?:\.git)?(?:/tree/([^#?]+))?/?(?:[#?].*)?$', url)
                if re.search(r'\.zip($|\?)', url, re.I):
                    telecharger(url, dest)
                elif m:
                    o, r, ref = m.groups()
                    if not ref:
                        try:
                            hdr = {'User-Agent': 'apk-studio'}
                            if os.environ.get('GH_TOKEN'):
                                hdr['Authorization'] = 'Bearer ' + os.environ['GH_TOKEN']
                            api = urllib.request.Request('https://api.github.com/repos/%s/%s' % (o, r), headers=hdr)
                            ref = json.load(urllib.request.urlopen(api, timeout=60))['default_branch']
                        except Exception:
                            ref = ''
                    essais = [ref] if ref else ['main', 'master']
                    for k, br in enumerate(essais):
                        try:
                            telecharger('https://codeload.github.com/%s/%s/zip/%s' % (o, r, br), dest)
                            break
                        except Exception as e:
                            if k == len(essais) - 1:
                                sys.exit('Téléchargement impossible (dépôt public ?) : %s' % e)
                else:
                    sys.exit('Lien non pris en charge : utilise un ZIP, un dépôt GitHub public ou un site web.')
        elif frm:
            subprocess.run(['gh', 'release', 'download', frm, '-p', 'source.zip', '-O', dest], check=True)
        else:
            sys.exit('Aucune source : ni ZIP, ni lien.')
    src_icon = cfg.get('iconFrom') or frm
    if cfg.get('icon') and not os.path.exists(icon) and src_icon:
        subprocess.run(['gh', 'release', 'download', src_icon, '-p', 'icon.png', '-O', icon])
    if cfg.get('icon') and not os.path.exists(icon):
        cfg['icon'] = False
        json.dump(cfg, open(cfgp, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    print('Source prête :', dest, '| icône :', os.path.exists(icon))
    sys.exit(0)

kind, cfgpath = sys.argv[1], sys.argv[2]
cfg = json.load(open(cfgpath, encoding='utf-8'))
groups = cfg.get('permissions') or []
share = cfg.get('share', True) is not False
ask = cfg.get('askStart', True) is not False

TABLE = {
    'storage': [('READ_EXTERNAL_STORAGE', 32), ('WRITE_EXTERNAL_STORAGE', 32)],
    'media': [('READ_MEDIA_IMAGES', 0), ('READ_MEDIA_VIDEO', 0), ('READ_MEDIA_AUDIO', 0)],
    'allfiles': [('MANAGE_EXTERNAL_STORAGE', 0)],
    'camera': [('CAMERA', 0)],
    'micro': [('RECORD_AUDIO', 0), ('MODIFY_AUDIO_SETTINGS', 0)],
    'location': [('ACCESS_FINE_LOCATION', 0), ('ACCESS_COARSE_LOCATION', 0)],
    'notifications': [('POST_NOTIFICATIONS', 0)],
    'contacts': [('READ_CONTACTS', 0), ('WRITE_CONTACTS', 0)],
    'calendar': [('READ_CALENDAR', 0), ('WRITE_CALENDAR', 0)],
    'bluetooth': [('BLUETOOTH', 30), ('BLUETOOTH_ADMIN', 30), ('BLUETOOTH_CONNECT', 0), ('BLUETOOTH_SCAN', 0)],
    'phone': [('READ_PHONE_STATE', 0), ('CALL_PHONE', 0)],
}
BASE = ['INTERNET', 'ACCESS_NETWORK_STATE', 'ACCESS_WIFI_STATE', 'VIBRATE', 'WAKE_LOCK', 'FOREGROUND_SERVICE', 'POST_NOTIFICATIONS']
SANS_DEMANDE = {'MODIFY_AUDIO_SETTINGS', 'MANAGE_EXTERNAL_STORAGE', 'BLUETOOTH', 'BLUETOOTH_ADMIN'}

# ---------- Manifeste : autorisations + filtres de partage ----------
m = 'android/app/src/main/AndroidManifest.xml'
s = open(m, encoding='utf-8').read()
lines = []

def add(n, mx=0):
    full = 'android.permission.' + n
    if '"%s"' % full in s or any(full in l for l in lines):
        return
    lines.append('    <uses-permission android:name="%s"%s/>\n' % (full, ' android:maxSdkVersion="%d"' % mx if mx else ''))

for n in BASE:
    add(n)
add('WRITE_EXTERNAL_STORAGE', 28)
for g in groups:
    for n, mx in TABLE.get(g, []):
        add(n, mx)
s = s.replace('<application', ''.join(lines) + '    <application', 1)
if 'storage' in groups or 'allfiles' in groups:
    s = s.replace('<application', '<application android:requestLegacyExternalStorage="true"', 1)
if share:
    flt = ''.join('''      <intent-filter>
        <action android:name="android.intent.action.%s"/>
        <category android:name="android.intent.category.DEFAULT"/>
        <data android:mimeType="*/*"/>
      </intent-filter>
''' % a for a in ('SEND', 'SEND_MULTIPLE'))
    s = s.replace('</activity>', flt + '    </activity>', 1)
s = s.replace('android:launchMode="singleTop"', 'android:launchMode="singleTask"')
open(m, 'w', encoding='utf-8').write(s)

# ---------- Activité principale ----------
rt = []
for g in groups:
    for p, _ in TABLE.get(g, []):
        if p not in SANS_DEMANDE and p not in rt:
            rt.append(p)
found = sorted(glob.glob('android/app/src/main/**/MainActivity.*', recursive=True))[0]
pkg = re.search(r'^package\s+([\w.]+)', open(found, encoding='utf-8').read(), re.M).group(1)
bool_ = lambda b: 'true' if b else 'false'

JAVA = r'''package %PKG%;

import android.app.DownloadManager;
import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import androidx.core.app.NotificationCompat;
import android.content.Context;
import android.content.ContentValues;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.database.Cursor;
import android.net.Uri;
import android.media.MediaScannerConnection;
import android.os.Build;
import android.os.Bundle;
import android.os.Environment;
import android.provider.MediaStore;
import android.provider.OpenableColumns;
import android.provider.Settings;
import android.util.Base64;
import android.webkit.JavascriptInterface;
import com.getcapacitor.BridgeActivity;
import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.util.ArrayList;
import org.json.JSONArray;
import org.json.JSONObject;

public class MainActivity extends BridgeActivity {
  private static final String[] PERMS = {%PERMS%};
  private static final boolean ALL_FILES = %ALLFILES%;
  private static final boolean ASK = %ASK%;
  private static final boolean SHARE = %SHARE%;
  private static String pending = null;

  @Override
  public void onCreate(Bundle savedInstanceState) {
    super.onCreate(savedInstanceState);
    if (getBridge() != null) {
      getBridge().getWebView().addJavascriptInterface(new Object() {
        @JavascriptInterface
        public String take() { String p = pending; pending = null; return p; }
      }, "AndroidShare");
      getBridge().getWebView().addJavascriptInterface(new Telechargeur(), "AndroidDownload");
    }
    if (SHARE) lire(getIntent());
    if (ASK) getWindow().getDecorView().postDelayed(this::demander, 800);
  }


  /** Écrit un fichier dans le dossier Téléchargements (MediaStore dès Android 10, sans autorisation). */
  private class Telechargeur {
    private OutputStream out;
    private Uri uri;
    private File fichier;

    @JavascriptInterface
    public synchronized boolean begin(String nom, String mime) {
      abort();
      try {
        nom = nom.replaceAll("[\\\\/:*?\"<>|]", "_");
        if (mime == null || mime.isEmpty()) mime = "application/octet-stream";
        if (Build.VERSION.SDK_INT >= 29) {
          ContentValues v = new ContentValues();
          v.put(MediaStore.MediaColumns.DISPLAY_NAME, nom);
          v.put(MediaStore.MediaColumns.MIME_TYPE, mime);
          v.put(MediaStore.MediaColumns.RELATIVE_PATH, Environment.DIRECTORY_DOWNLOADS);
          v.put(MediaStore.MediaColumns.IS_PENDING, 1);
          uri = getContentResolver().insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI, v);
          if (uri == null) return false;
          out = getContentResolver().openOutputStream(uri);
        } else {
          File d = Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_DOWNLOADS);
          d.mkdirs();
          fichier = new File(d, nom);
          out = new FileOutputStream(fichier);
        }
        return out != null;
      } catch (Exception e) { abort(); return false; }
    }

    @JavascriptInterface
    public synchronized boolean chunk(String b64) {
      try { out.write(Base64.decode(b64, Base64.DEFAULT)); return true; }
      catch (Exception e) { abort(); return false; }
    }

    @JavascriptInterface
    public synchronized boolean end() {
      try {
        out.flush(); out.close(); out = null;
        if (uri != null) {
          ContentValues v = new ContentValues();
          v.put(MediaStore.MediaColumns.IS_PENDING, 0);
          getContentResolver().update(uri, v, null, null);
        } else if (fichier != null) {
          MediaScannerConnection.scanFile(MainActivity.this, new String[]{fichier.getAbsolutePath()}, null, null);
        }
        uri = null; fichier = null;
        return true;
      } catch (Exception e) { abort(); return false; }
    }

    /** Télécharge via le gestionnaire de téléchargement d'Android (notification, progression, annulation).
     *  Avec un jeton (dépôt privé), l'adresse signée est d'abord résolue ici, puis confiée au gestionnaire. */
    @JavascriptInterface
    public boolean systeme(String url, String nom, String mime, String jeton) {
      try {
        nom = nom.replaceAll("[\\\\/:*?\"<>|]", "_");
        if (mime == null || mime.isEmpty()) mime = "application/octet-stream";
        String cible = url;
        if (jeton != null && !jeton.isEmpty()) {
          HttpURLConnection c = (HttpURLConnection) new URL(url).openConnection();
          c.setInstanceFollowRedirects(false);
          c.setConnectTimeout(15000);
          c.setReadTimeout(15000);
          c.setRequestProperty("Authorization", "Bearer " + jeton);
          c.setRequestProperty("Accept", "application/octet-stream");
          c.setRequestProperty("X-GitHub-Api-Version", "2022-11-28");
          int code = c.getResponseCode();
          String loc = c.getHeaderField("Location");
          c.disconnect();
          if (code < 300 || code >= 400 || loc == null) return false;
          cible = loc;
        }
        DownloadManager.Request r = new DownloadManager.Request(Uri.parse(cible));
        r.setTitle(nom);
        r.setDescription("APK Studio");
        r.setMimeType(mime);
        r.setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED);
        r.setDestinationInExternalPublicDir(Environment.DIRECTORY_DOWNLOADS, nom);
        DownloadManager dm = (DownloadManager) getSystemService(Context.DOWNLOAD_SERVICE);
        if (dm == null) return false;
        dm.enqueue(r);
        return true;
      } catch (Exception e) { return false; }
    }

    /* ---------- Téléchargement avec notification de progression (barre d'état) ---------- */
    private int compteur = 100;

    @JavascriptInterface
    public boolean notifOk() {
      return Build.VERSION.SDK_INT < 33 || checkSelfPermission("android.permission.POST_NOTIFICATIONS") == PackageManager.PERMISSION_GRANTED;
    }

    @JavascriptInterface
    public void notifDemander() {
      if (notifOk()) return;
      runOnUiThread(() -> { try { requestPermissions(new String[]{"android.permission.POST_NOTIFICATIONS"}, 4243); } catch (Exception e) { } });
    }

    /** Lance le téléchargement en arrière-plan : notification « en cours » avec barre de progression, puis « terminé ». */
    @JavascriptInterface
    public boolean demarrer(final String url, String nom, String mime, final String jeton) {
      try {
        final String n = nom.replaceAll("[\\\\/:*?\"<>|]", "_");
        final String m = (mime == null || mime.isEmpty()) ? "application/octet-stream" : mime;
        final int id = ++compteur;
        NotificationManager nm = (NotificationManager) getSystemService(Context.NOTIFICATION_SERVICE);
        if (nm == null) return false;
        if (Build.VERSION.SDK_INT >= 26) {
          NotificationChannel ch = new NotificationChannel("baobab_dl", "Téléchargements", NotificationManager.IMPORTANCE_LOW);
          ch.setDescription("Progression des téléchargements");
          ch.setShowBadge(false);
          nm.createNotificationChannel(ch);
        }
        notifDemander();
        notifier(nm, id, n, 0, 0, false, true, false);
        new Thread(() -> flux(nm, id, url, n, m, jeton), "baobab-dl").start();
        return true;
      } catch (Exception e) { return false; }
    }

    private void notifier(NotificationManager nm, int id, String nom, int pct, long fait, boolean connu, boolean encours, boolean echec) {
      try {
        NotificationCompat.Builder b = new NotificationCompat.Builder(MainActivity.this, "baobab_dl")
          .setContentTitle(nom)
          .setOnlyAlertOnce(true)
          .setPriority(NotificationCompat.PRIORITY_LOW);
        if (encours) {
          b.setSmallIcon(android.R.drawable.stat_sys_download).setOngoing(true);
          if (connu) b.setProgress(100, pct, false).setContentText(pct + " %");
          else b.setProgress(0, 0, true).setContentText(fait > 0 ? (fait / 1024 / 1024) + " Mo" : "Connexion…");
        } else {
          b.setSmallIcon(echec ? android.R.drawable.stat_notify_error : android.R.drawable.stat_sys_download_done)
           .setOngoing(false).setAutoCancel(true).setProgress(0, 0, false)
           .setContentText(echec ? "Échec du téléchargement" : "Téléchargement terminé");
          if (!echec) {
            Intent i = new Intent(DownloadManager.ACTION_VIEW_DOWNLOADS);
            int fl = PendingIntent.FLAG_UPDATE_CURRENT | (Build.VERSION.SDK_INT >= 23 ? PendingIntent.FLAG_IMMUTABLE : 0);
            b.setContentIntent(PendingIntent.getActivity(MainActivity.this, id, i, fl));
          }
        }
        nm.notify(id, b.build());
      } catch (Exception e) { }
    }

    private void prevenir(final String etat, final String nom, final String msg) {
      try {
        JSONObject d = new JSONObject().put("etat", etat).put("nom", nom).put("msg", msg == null ? "" : msg);
        final String js = "window.dispatchEvent(new CustomEvent('appdl',{detail:" + d.toString() + "}))";
        runOnUiThread(() -> { if (getBridge() != null) getBridge().getWebView().evaluateJavascript(js, null); });
      } catch (Exception e) { }
    }

    private void flux(NotificationManager nm, int id, String url, String nom, String mime, String jeton) {
      HttpURLConnection c = null;
      OutputStream o = null;
      Uri cible = null;
      File f = null;
      try {
        String u = url;
        boolean avecJeton = jeton != null && !jeton.isEmpty();
        for (int k = 0; k < 6; k++) {
          c = (HttpURLConnection) new URL(u).openConnection();
          c.setInstanceFollowRedirects(false);
          c.setConnectTimeout(20000);
          c.setReadTimeout(30000);
          c.setRequestProperty("User-Agent", "apk-studio");
          if (avecJeton && k == 0) {
            c.setRequestProperty("Authorization", "Bearer " + jeton);
            c.setRequestProperty("Accept", "application/octet-stream");
            c.setRequestProperty("X-GitHub-Api-Version", "2022-11-28");
          }
          int code = c.getResponseCode();
          if (code >= 300 && code < 400 && c.getHeaderField("Location") != null) {
            u = new URL(new URL(u), c.getHeaderField("Location")).toString();
            c.disconnect();
            c = null;
            continue;
          }
          if (code != 200) throw new Exception("HTTP " + code);
          break;
        }
        if (c == null) throw new Exception("trop de redirections");
        long total = Build.VERSION.SDK_INT >= 24 ? c.getContentLengthLong() : c.getContentLength();
        if (Build.VERSION.SDK_INT >= 29) {
          ContentValues v = new ContentValues();
          v.put(MediaStore.MediaColumns.DISPLAY_NAME, nom);
          v.put(MediaStore.MediaColumns.MIME_TYPE, mime);
          v.put(MediaStore.MediaColumns.RELATIVE_PATH, Environment.DIRECTORY_DOWNLOADS);
          v.put(MediaStore.MediaColumns.IS_PENDING, 1);
          cible = getContentResolver().insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI, v);
          if (cible == null) throw new Exception("dossier Téléchargements inaccessible");
          o = getContentResolver().openOutputStream(cible);
        } else {
          File d = Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_DOWNLOADS);
          d.mkdirs();
          f = new File(d, nom);
          o = new FileOutputStream(f);
        }
        InputStream in = c.getInputStream();
        byte[] buf = new byte[65536];
        long fait = 0, dernier = 0;
        int n, dernierPct = -1;
        while ((n = in.read(buf)) > 0) {
          o.write(buf, 0, n);
          fait += n;
          long t = System.currentTimeMillis();
          int pct = total > 0 ? (int) (fait * 100 / total) : 0;
          if (t - dernier > 400 && (pct != dernierPct || total <= 0)) {
            dernier = t; dernierPct = pct;
            notifier(nm, id, nom, pct, fait, total > 0, true, false);
          }
        }
        o.flush(); o.close(); o = null;
        if (cible != null) {
          ContentValues v = new ContentValues();
          v.put(MediaStore.MediaColumns.IS_PENDING, 0);
          getContentResolver().update(cible, v, null, null);
        } else if (f != null) {
          MediaScannerConnection.scanFile(MainActivity.this, new String[]{f.getAbsolutePath()}, null, null);
        }
        notifier(nm, id, nom, 100, fait, true, false, false);
        prevenir("fini", nom, null);
      } catch (Exception e) {
        try { if (o != null) o.close(); } catch (Exception e2) { }
        try { if (cible != null) getContentResolver().delete(cible, null, null); } catch (Exception e2) { }
        try { if (f != null) f.delete(); } catch (Exception e2) { }
        notifier(nm, id, nom, 0, 0, false, false, true);
        prevenir("echec", nom, e.getMessage());
      } finally {
        if (c != null) c.disconnect();
      }
    }

    @JavascriptInterface
    public synchronized void abort() {
      try { if (out != null) out.close(); } catch (Exception e) { }
      try { if (uri != null) getContentResolver().delete(uri, null, null); } catch (Exception e) { }
      try { if (fichier != null) fichier.delete(); } catch (Exception e) { }
      out = null; uri = null; fichier = null;
    }
  }

  @Override
  protected void onNewIntent(Intent intent) {
    super.onNewIntent(intent);
    setIntent(intent);
    if (SHARE && lire(intent) && getBridge() != null) {
      getBridge().getWebView().post(() -> getBridge().getWebView().evaluateJavascript(
        "(function(){var s=window.AndroidShare&&AndroidShare.take();if(s)window.dispatchEvent(new CustomEvent('appshare',{detail:JSON.parse(s)}))})()", null));
    }
  }

  @SuppressWarnings("deprecation")
  private boolean lire(Intent i) {
    if (i == null) return false;
    String a = i.getAction();
    if (!Intent.ACTION_SEND.equals(a) && !Intent.ACTION_SEND_MULTIPLE.equals(a)) return false;
    try {
      JSONArray out = new JSONArray();
      String t = i.getStringExtra(Intent.EXTRA_TEXT);
      if (t != null) out.put(new JSONObject().put("kind", "text").put("text", t));
      ArrayList<Uri> uris = new ArrayList<>();
      if (Intent.ACTION_SEND_MULTIPLE.equals(a)) {
        ArrayList<Uri> l = i.getParcelableArrayListExtra(Intent.EXTRA_STREAM);
        if (l != null) uris.addAll(l);
      } else {
        Uri u = i.getParcelableExtra(Intent.EXTRA_STREAM);
        if (u != null) uris.add(u);
      }
      for (Uri u : uris) out.put(copier(u));
      if (out.length() > 0) { pending = out.toString(); return true; }
    } catch (Exception e) { }
    return false;
  }

  private JSONObject copier(Uri u) throws Exception {
    String nom = "fichier";
    Cursor c = null;
    try {
      c = getContentResolver().query(u, null, null, null, null);
      if (c != null && c.moveToFirst()) {
        int k = c.getColumnIndex(OpenableColumns.DISPLAY_NAME);
        if (k >= 0 && c.getString(k) != null) nom = c.getString(k);
      }
    } finally { if (c != null) c.close(); }
    File dir = new File(getCacheDir(), "partages");
    dir.mkdirs();
    File f = new File(dir, System.currentTimeMillis() + "_" + nom.replaceAll("[^A-Za-z0-9._-]", "_"));
    try (InputStream in = getContentResolver().openInputStream(u); OutputStream o = new FileOutputStream(f)) {
      byte[] b = new byte[65536];
      int n;
      while (in != null && (n = in.read(b)) > 0) o.write(b, 0, n);
    }
    String mime = getContentResolver().getType(u);
    return new JSONObject().put("kind", "file").put("name", nom).put("mime", mime == null ? "" : mime)
      .put("path", f.getAbsolutePath()).put("size", f.length());
  }

  private void demander() {
    SharedPreferences sp = getSharedPreferences("baobab", MODE_PRIVATE);
    if (sp.getBoolean("asked", false)) return;
    sp.edit().putBoolean("asked", true).apply();
    ArrayList<String> need = new ArrayList<>();
    for (String p : PERMS) if (checkSelfPermission(p) != PackageManager.PERMISSION_GRANTED) need.add(p);
    if (!need.isEmpty() && Build.VERSION.SDK_INT >= 23) requestPermissions(need.toArray(new String[0]), 4242);
    else tousFichiers();
  }

  @Override
  public void onRequestPermissionsResult(int code, String[] perms, int[] res) {
    super.onRequestPermissionsResult(code, perms, res);
    if (code == 4242) tousFichiers();
  }

  private void tousFichiers() {
    if (!ALL_FILES || Build.VERSION.SDK_INT < 30 || Environment.isExternalStorageManager()) return;
    try {
      startActivity(new Intent(Settings.ACTION_MANAGE_APP_ALL_FILES_ACCESS_PERMISSION, Uri.parse("package:" + getPackageName())));
    } catch (Exception e) {
      try { startActivity(new Intent(Settings.ACTION_MANAGE_ALL_FILES_ACCESS_PERMISSION)); } catch (Exception e2) { }
    }
  }
}
'''

KOTLIN = r'''package %PKG%

import android.content.ContentValues
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.Environment
import android.os.Handler
import android.provider.MediaStore
import android.provider.OpenableColumns
import android.provider.Settings
import android.view.WindowManager
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel
import java.io.File
import org.json.JSONArray
import org.json.JSONObject

class MainActivity : FlutterActivity() {
  private val perms = arrayOf<String>(%PERMS%)
  private val allFiles = %ALLFILES%
  private val ask = %ASK%
  private val share = %SHARE%
  private var pending: String? = null
  private var canalPartage: MethodChannel? = null

  override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
    super.configureFlutterEngine(flutterEngine)
    val m = flutterEngine.dartExecutor.binaryMessenger
    MethodChannel(m, "baobab/secure").setMethodCallHandler { call, result ->
      runOnUiThread {
        if (call.method == "on") window.addFlags(WindowManager.LayoutParams.FLAG_SECURE)
        else window.clearFlags(WindowManager.LayoutParams.FLAG_SECURE)
        result.success(null)
      }
    }
    MethodChannel(m, "baobab/download").setMethodCallHandler { call, result ->
      if (call.method == "save") {
        try {
          val nom = (call.argument<String>("name") ?: "fichier").replace(Regex("[^A-Za-z0-9._ -]"), "_")
          val mime = call.argument<String>("mime") ?: "application/octet-stream"
          val octets = call.argument<ByteArray>("bytes")
          result.success(if (octets == null) null else enregistrerTelechargement(nom, mime, octets))
        } catch (e: Exception) { result.success(null) }
      } else result.notImplemented()
    }
    canalPartage = MethodChannel(m, "baobab/share")
    canalPartage?.setMethodCallHandler { call, result ->
      if (call.method == "take") { result.success(pending); pending = null } else result.notImplemented()
    }
    if (share) lire(intent)
    if (ask) Handler(mainLooper).postDelayed({ demander() }, 800)
  }

  /** Écrit le fichier dans le dossier Téléchargements (MediaStore dès Android 10 : visible dans « Téléchargements »). */
  private fun enregistrerTelechargement(nom: String, mime: String, octets: ByteArray): String? {
    if (Build.VERSION.SDK_INT >= 29) {
      val v = ContentValues().apply {
        put(MediaStore.MediaColumns.DISPLAY_NAME, nom)
        put(MediaStore.MediaColumns.MIME_TYPE, mime)
        put(MediaStore.MediaColumns.RELATIVE_PATH, Environment.DIRECTORY_DOWNLOADS)
        put(MediaStore.MediaColumns.IS_PENDING, 1)
      }
      val uri = contentResolver.insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI, v) ?: return null
      val ecrit = contentResolver.openOutputStream(uri)?.use { it.write(octets); true } ?: false
      if (!ecrit) { contentResolver.delete(uri, null, null); return null }
      val fin = ContentValues().apply { put(MediaStore.MediaColumns.IS_PENDING, 0) }
      contentResolver.update(uri, fin, null, null)
      return uri.toString()
    }
    val dir = Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_DOWNLOADS)
    dir.mkdirs()
    val f = File(dir, nom)
    f.writeBytes(octets)
    android.media.MediaScannerConnection.scanFile(this, arrayOf(f.absolutePath), null, null)
    return f.absolutePath
  }

  override fun onNewIntent(intent: Intent) {
    super.onNewIntent(intent)
    setIntent(intent)
    if (share && lire(intent)) {
      canalPartage?.invokeMethod("shared", pending)
      pending = null
    }
  }

  @Suppress("DEPRECATION")
  private fun lire(i: Intent?): Boolean {
    if (i == null) return false
    val a = i.action
    if (a != Intent.ACTION_SEND && a != Intent.ACTION_SEND_MULTIPLE) return false
    return try {
      val out = JSONArray()
      i.getStringExtra(Intent.EXTRA_TEXT)?.let { out.put(JSONObject().put("kind", "text").put("text", it)) }
      val uris = ArrayList<Uri>()
      if (a == Intent.ACTION_SEND_MULTIPLE) {
        i.getParcelableArrayListExtra<Uri>(Intent.EXTRA_STREAM)?.let { uris.addAll(it) }
      } else {
        i.getParcelableExtra<Uri>(Intent.EXTRA_STREAM)?.let { uris.add(it) }
      }
      for (u in uris) out.put(copier(u))
      if (out.length() > 0) { pending = out.toString(); true } else false
    } catch (e: Exception) { false }
  }

  private fun copier(u: Uri): JSONObject {
    var nom = "fichier"
    contentResolver.query(u, null, null, null, null)?.use { c ->
      if (c.moveToFirst()) {
        val k = c.getColumnIndex(OpenableColumns.DISPLAY_NAME)
        if (k >= 0) nom = c.getString(k) ?: nom
      }
    }
    val dir = File(cacheDir, "partages").apply { mkdirs() }
    val f = File(dir, "${System.currentTimeMillis()}_" + nom.replace(Regex("[^A-Za-z0-9._-]"), "_"))
    contentResolver.openInputStream(u)?.use { i -> f.outputStream().use { o -> i.copyTo(o) } }
    return JSONObject().put("kind", "file").put("name", nom).put("mime", contentResolver.getType(u) ?: "")
      .put("path", f.absolutePath).put("size", f.length())
  }

  private fun demander() {
    val sp = getSharedPreferences("baobab", MODE_PRIVATE)
    if (sp.getBoolean("asked", false)) return
    sp.edit().putBoolean("asked", true).apply()
    val need = perms.filter { checkSelfPermission(it) != PackageManager.PERMISSION_GRANTED }
    if (need.isNotEmpty() && Build.VERSION.SDK_INT >= 23) requestPermissions(need.toTypedArray(), 4242)
    else tousFichiers()
  }

  override fun onRequestPermissionsResult(requestCode: Int, permissions: Array<out String>, grantResults: IntArray) {
    super.onRequestPermissionsResult(requestCode, permissions, grantResults)
    if (requestCode == 4242) tousFichiers()
  }

  private fun tousFichiers() {
    if (!allFiles || Build.VERSION.SDK_INT < 30 || Environment.isExternalStorageManager()) return
    try {
      startActivity(Intent(Settings.ACTION_MANAGE_APP_ALL_FILES_ACCESS_PERMISSION, Uri.parse("package:$packageName")))
    } catch (e: Exception) {
      try { startActivity(Intent(Settings.ACTION_MANAGE_ALL_FILES_ACCESS_PERMISSION)) } catch (e2: Exception) { }
    }
  }
}
'''

DART = r'''import 'dart:async';
import 'dart:convert';

import 'package:flutter/services.dart';

/// Aides fournies par APK Studio : partages reçus et protection contre les captures d'écran.
/// Chaque élément partagé est une Map : {kind: 'file', name, mime, path, size} ou {kind: 'text', text}.
class BaobabSystem {
  static const _partage = MethodChannel('baobab/share');
  static const _secure = MethodChannel('baobab/secure');
  static final _flux = StreamController<List<Map<String, dynamic>>>.broadcast();

  static List<Map<String, dynamic>> _lire(dynamic s) =>
      s == null ? [] : (jsonDecode(s as String) as List).cast<Map<String, dynamic>>();

  /// Éléments reçus via « Partager » (à appeler au démarrage de l'application).
  static Future<List<Map<String, dynamic>>> partagesRecus() async {
    try {
      return _lire(await _partage.invokeMethod('take'));
    } catch (_) {
      return [];
    }
  }

  /// Nouveaux partages reçus pendant que l'application est ouverte.
  static Stream<List<Map<String, dynamic>>> get partages {
    _partage.setMethodCallHandler((c) async {
      if (c.method == 'shared') _flux.add(_lire(c.arguments));
    });
    return _flux.stream;
  }

  static Future<void> bloquerCaptures(bool on) async {
    try {
      await _secure.invokeMethod(on ? 'on' : 'off');
    } catch (_) {}
  }
}
'''

ext = 'java' if kind == 'capacitor' else 'kt'
code = (JAVA if kind == 'capacitor' else KOTLIN)
code = (code.replace('%PKG%', pkg)
        .replace('%PERMS%', ', '.join('"android.permission.%s"' % p for p in rt))
        .replace('%ALLFILES%', bool_('allfiles' in groups))
        .replace('%ASK%', bool_(ask)).replace('%SHARE%', bool_(share)))
os.remove(found)
open(os.path.join(os.path.dirname(found), 'MainActivity.' + ext), 'w', encoding='utf-8').write(code)

if kind == 'flutter' and os.path.isdir('lib'):
    open('lib/baobab_system.dart', 'w', encoding='utf-8').write(DART)

# ---------- Flutter : aligne le compileSdk des plugins (erreur « requires compileSdk 36 or later ») ----------
GRADLE_KTS = """
// --- Ajouté par le générateur : monte le compileSdk des plugins trop anciens à 36 ---
subprojects {
    val aligner = { p: Project ->
        runCatching {
            val ext = p.extensions.findByName("android")
            if (ext != null && p.name != "app") {
                val m = ext.javaClass.methods
                val cur = m.firstOrNull { it.name == "getCompileSdk" && it.parameterCount == 0 }?.invoke(ext) as? Int
                val setter = m.firstOrNull { it.name == "setCompileSdk" && it.parameterCount == 1 }
                    ?: m.firstOrNull { it.name == "setCompileSdkVersion" && it.parameterCount == 1 && it.parameterTypes[0] == Int::class.javaPrimitiveType }
                if (setter != null && (cur == null || cur < 36)) setter.invoke(ext, 36)
            }
        }
    }
    if (state.executed) aligner(this) else afterEvaluate { aligner(this) }
}
"""
GRADLE_GROOVY = """
// --- Ajouté par le générateur : monte le compileSdk des plugins trop anciens à 36 ---
subprojects { p ->
    def aligner = {
        try {
            def a = p.extensions.findByName('android')
            if (a != null && p.name != 'app') {
                def cur = a.hasProperty('compileSdk') ? a.compileSdk : null
                if (cur == null || cur < 36) { a.compileSdk = 36 }
            }
        } catch (Throwable t) { }
    }
    if (p.state.executed) { aligner() } else { p.afterEvaluate { aligner() } }
}
"""

def aligner_compile_sdk():
    for name, snippet in (('android/build.gradle.kts', GRADLE_KTS), ('android/build.gradle', GRADLE_GROOVY)):
        if os.path.exists(name):
            txt = open(name, encoding='utf-8').read()
            if 'Ajouté par le générateur : monte le compileSdk' not in txt:
                open(name, 'w', encoding='utf-8').write(txt.rstrip('\n') + '\n' + snippet)
            return name
    return None

if kind == 'flutter':
    print('compileSdk des plugins aligné dans :', aligner_compile_sdk())

print('Autorisations :', groups or '(aucune supplémentaire)', '| partage :', share, '| demande au démarrage :', ask)

# ---------- Flutter : notifications/alarmes (flutter_local_notifications) ----------
# Active le « core library desugaring » (obligatoire pour ce plugin) et ajoute les autorisations/récepteurs d'alarme.
if kind == 'flutter':
    for f in glob.glob('android/app/build.gradle*'):
        t = open(f, encoding='utf-8').read()
        if 'coreLibraryDesugaring' in t:
            continue
        if f.endswith('.kts'):
            t = re.sub(r'compileOptions\s*\{', 'compileOptions {\n        isCoreLibraryDesugaringEnabled = true', t, count=1)
            t += '\ndependencies {\n    coreLibraryDesugaring("com.android.tools:desugar_jdk_libs:2.1.4")\n}\n'
        else:
            t = re.sub(r'compileOptions\s*\{', 'compileOptions {\n        coreLibraryDesugaringEnabled true', t, count=1)
            t += '\ndependencies {\n    coreLibraryDesugaring "com.android.tools:desugar_jdk_libs:2.1.4"\n}\n'
        open(f, 'w', encoding='utf-8').write(t)
    mf = 'android/app/src/main/AndroidManifest.xml'
    s2 = open(mf, encoding='utf-8').read()
    extra = ''.join('    <uses-permission android:name="android.permission.%s"/>\n' % p
                    for p in ('POST_NOTIFICATIONS', 'SCHEDULE_EXACT_ALARM', 'USE_EXACT_ALARM', 'USE_FULL_SCREEN_INTENT', 'RECEIVE_BOOT_COMPLETED')
                    if 'android.permission.%s"' % p not in s2)
    s2 = s2.replace('<application', extra + '    <application', 1)
    if 'ScheduledNotificationReceiver' not in s2:
        s2 = s2.replace('</application>', '''    <receiver android:exported="false" android:name="com.dexterous.flutterlocalnotifications.ScheduledNotificationReceiver"/>
    <receiver android:exported="false" android:name="com.dexterous.flutterlocalnotifications.ScheduledNotificationBootReceiver">
      <intent-filter>
        <action android:name="android.intent.action.BOOT_COMPLETED"/>
        <action android:name="android.intent.action.MY_PACKAGE_REPLACED"/>
      </intent-filter>
    </receiver>
  </application>''', 1)
    s2 = s2.replace('<activity', '<activity android:showWhenLocked="true" android:turnScreenOn="true"', 1) if 'showWhenLocked' not in s2 else s2
    open(mf, 'w', encoding='utf-8').write(s2)
    print('Alarmes : desugaring + autorisations ajoutés')

    # --- Plugins qui exigent une déclaration dans le manifeste / un minSdk (ajouté) ---
    _pub = open('pubspec.yaml', encoding='utf-8').read() if os.path.exists('pubspec.yaml') else ''
    _mx = open(mf, encoding='utf-8').read()
    _perm = []   # (nom, maxSdk)
    _svc = ''
    _min = 0
    if 'flutter_foreground_task' in _pub:
        # PATCH Sentinel Cam : si l'app filme (flutter_webrtc), le service doit etre de type "camera"
        # (sinon Android 14+ coupe la camera en arriere-plan / ecran eteint).
        _cam = 'flutter_webrtc' in _pub
        _stype = 'camera' if _cam else 'connectedDevice'
        _perm += [('FOREGROUND_SERVICE', 0), ('FOREGROUND_SERVICE_CONNECTED_DEVICE', 0)]
        if _cam:
            _perm += [('FOREGROUND_SERVICE_CAMERA', 0), ('CAMERA', 0), ('WAKE_LOCK', 0),
                      ('REQUEST_IGNORE_BATTERY_OPTIMIZATIONS', 0), ('MODIFY_AUDIO_SETTINGS', 0),
                      ('CHANGE_NETWORK_STATE', 0), ('ACCESS_NETWORK_STATE', 0)]
        if 'com.pravera.flutter_foreground_task.service.ForegroundService' not in _mx:
            _svc = ('    <service android:name="com.pravera.flutter_foreground_task.service.ForegroundService"'
                    ' android:foregroundServiceType="' + _stype + '" tools:replace="android:foregroundServiceType"'
                    ' android:exported="false"/>\n')
    if 'open_filex' in _pub:
        _perm += [('REQUEST_INSTALL_PACKAGES', 0)]   # PATCH : mises à jour intégrées
    if 'nearby_connections' in _pub:
        _min = 23
        _perm += [('CHANGE_WIFI_STATE', 0), ('CHANGE_NETWORK_STATE', 0), ('ACCESS_FINE_LOCATION', 0),
                  ('BLUETOOTH', 30), ('BLUETOOTH_ADMIN', 30), ('BLUETOOTH_ADVERTISE', 0),
                  ('BLUETOOTH_CONNECT', 0), ('BLUETOOTH_SCAN', 0), ('NEARBY_WIFI_DEVICES', 0)]
    if 'flutter_webrtc' in _pub:
        _min = max(_min, 23)   # PATCH : 23 requis par Firebase / WebRTC
    if 'cloud_firestore' in _pub or 'firebase_core' in _pub:
        _min = max(_min, 23)
    _add = ''.join('    <uses-permission android:name="android.permission.%s"%s/>\n'
                   % (n, ' android:maxSdkVersion="%d"' % mx if mx else '')
                   for n, mx in _perm if 'android.permission.%s"' % n not in _mx)
    if _add:
        _mx = _mx.replace('<application', _add + '    <application', 1)
    if _svc:
        _mx = _mx.replace('</application>', _svc + '  </application>', 1)
        if 'xmlns:tools=' not in _mx:
            _mx = _mx.replace('<manifest ', '<manifest xmlns:tools="http://schemas.android.com/tools" ', 1)
    open(mf, 'w', encoding='utf-8').write(_mx)
    if _min > 21:
        for f in glob.glob('android/app/build.gradle*'):
            t = open(f, encoding='utf-8').read()
            t2 = re.sub(r'(minSdk(?:Version)?\s*=?\s*)flutter\.minSdkVersion', r'\g<1>%d' % _min, t)
            if t2 != t:
                open(f, 'w', encoding='utf-8').write(t2)
    if _perm or _svc:
        print('Plugins : autorisations/service ajoutés au manifeste (minSdk %s)' % (_min or 'inchangé'))

    # Sonneries des notifications : Android lit les sons dans res/raw (les assets Flutter ne suffisent pas)
    import shutil
    raw = 'android/app/src/main/res/raw'
    if os.path.isdir('assets/sounds'):
        os.makedirs(raw, exist_ok=True)
        for fsnd in glob.glob('assets/sounds/*.wav'):
            shutil.copy(fsnd, os.path.join(raw, os.path.basename(fsnd).lower()))
        # sans ce fichier, le build « release » supprime les sons (ils ne sont lus que par leur nom)
        open(os.path.join(raw, 'keep.xml'), 'w', encoding='utf-8').write(
            '<?xml version="1.0" encoding="utf-8"?>\n<resources xmlns:tools="http://schemas.android.com/tools" tools:keep="@raw/*" />\n')
        print('Sonneries copiées dans res/raw :', sorted(os.listdir(raw)))

    # Icône de l'appli : grande, sans marge (le badge remplit toute la zone visible de l'icône adaptative)
    fg, lg = 'android_icon/icon_foreground.png', 'android_icon/icon_legacy.png'
    if os.path.exists(fg) and os.path.exists(lg):
        try:
            try:
                from PIL import Image
            except ImportError:
                subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', 'pillow'], check=True)
                from PIL import Image
            res = 'android/app/src/main/res'
            tailles = {'mdpi': (48, 108), 'hdpi': (72, 162), 'xhdpi': (96, 216), 'xxhdpi': (144, 324), 'xxxhdpi': (192, 432)}
            for dens, (leg, ada) in tailles.items():
                d = os.path.join(res, 'mipmap-' + dens)
                os.makedirs(d, exist_ok=True)
                for vieux in glob.glob(os.path.join(d, 'ic_launcher*')):
                    os.remove(vieux)  # évite les doublons (.webp / .png)
                Image.open(lg).convert('RGBA').resize((leg, leg), Image.LANCZOS).save(os.path.join(d, 'ic_launcher.png'))
                Image.open(lg).convert('RGBA').resize((leg, leg), Image.LANCZOS).save(os.path.join(d, 'ic_launcher_round.png'))
                Image.open(fg).convert('RGBA').resize((ada, ada), Image.LANCZOS).save(os.path.join(d, 'ic_launcher_foreground.png'))
            os.makedirs(os.path.join(res, 'values'), exist_ok=True)
            open(os.path.join(res, 'values', 'baobab_icon.xml'), 'w', encoding='utf-8').write(
                '<?xml version="1.0" encoding="utf-8"?>\n<resources><color name="baobab_icon_bg">#1B5E20</color></resources>\n')
            ad = os.path.join(res, 'mipmap-anydpi-v26')
            os.makedirs(ad, exist_ok=True)
            xml = ('<?xml version="1.0" encoding="utf-8"?>\n<adaptive-icon xmlns:android="http://schemas.android.com/apk/res/android">\n'
                   '  <background android:drawable="@color/baobab_icon_bg"/>\n  <foreground android:drawable="@mipmap/ic_launcher_foreground"/>\n</adaptive-icon>\n')
            for nom in ('ic_launcher.xml', 'ic_launcher_round.xml'):
                open(os.path.join(ad, nom), 'w', encoding='utf-8').write(xml)
            print('Icône adaptative grande taille générée')
        except Exception as ex:
            print('Icône non générée :', ex)
