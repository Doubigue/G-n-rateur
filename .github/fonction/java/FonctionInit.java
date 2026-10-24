package studio.apk.fonction;

import android.app.Application;
import android.content.ContentProvider;
import android.content.ContentValues;
import android.content.Context;
import android.database.Cursor;
import android.net.Uri;

/**
 * Démarre automatiquement avec l'application (aucune modification du code du projet) :
 * installe l'onglet « Fonction » sur les écrans de l'application.
 */
public class FonctionInit extends ContentProvider {
    @Override
    public boolean onCreate() {
        try {
            Context c = getContext();
            Context a = c == null ? null : c.getApplicationContext();
            Application app = a instanceof Application ? (Application) a
                    : (c instanceof Application ? (Application) c : null);
            if (app != null) app.registerActivityLifecycleCallbacks(new FonctionTab());
        } catch (Throwable ignored) {
            // l'onglet Fonction ne doit jamais empêcher l'application de démarrer
        }
        return true;
    }

    @Override public Cursor query(Uri u, String[] p, String s, String[] a, String o) { return null; }
    @Override public String getType(Uri u) { return null; }
    @Override public Uri insert(Uri u, ContentValues v) { return null; }
    @Override public int delete(Uri u, String s, String[] a) { return 0; }
    @Override public int update(Uri u, ContentValues v, String s, String[] a) { return 0; }
}
