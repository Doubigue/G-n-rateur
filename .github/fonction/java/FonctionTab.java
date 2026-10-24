package studio.apk.fonction;

import android.app.Activity;
import android.app.Application;
import android.content.ComponentName;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.os.Bundle;
import android.view.Gravity;
import android.view.MotionEvent;
import android.view.View;
import android.view.ViewGroup;
import android.widget.FrameLayout;
import android.widget.TextView;

/** Onglet flottant « Fonction » : collé au bord droit, déplaçable verticalement, ouvre l'écran Fonction. */
class FonctionTab implements Application.ActivityLifecycleCallbacks {
    private static final String TAG = "studio.apk.fonction.tab";
    private static final String PREFS = "studio_apk_fonction";
    private static String prefix;   // paquet des classes de l'application (activité de lancement)
    private static boolean prefixOk;

    @Override
    public void onActivityResumed(Activity a) {
        try {
            if (a instanceof FonctionActivity || !estEcranDeLApp(a)) return;
            ajouter(a);
        } catch (Throwable ignored) {
            // jamais bloquant
        }
    }

    /** Vrai pour l'activité de lancement et celles du même paquet (pas pour les écrans de bibliothèques). */
    private static boolean estEcranDeLApp(Activity a) {
        if (!prefixOk) {
            prefixOk = true;
            try {
                Intent li = a.getPackageManager().getLaunchIntentForPackage(a.getPackageName());
                ComponentName cn = li == null ? null : li.getComponent();
                if (cn != null) {
                    String n = cn.getClassName();
                    int i = n.lastIndexOf('.');
                    prefix = i > 0 ? n.substring(0, i) : null;
                }
            } catch (Throwable ignored) { }
        }
        if (prefix == null) return true;
        String n = a.getClass().getName();
        return n.startsWith(prefix + ".") || n.equals(prefix);
    }

    private void ajouter(final Activity a) {
        final ViewGroup decor = (ViewGroup) a.getWindow().getDecorView();
        if (decor.findViewWithTag(TAG) != null) return;
        final float d = a.getResources().getDisplayMetrics().density;
        final SharedPreferences sp = a.getSharedPreferences(PREFS, Context.MODE_PRIVATE);

        final TextView t = new TextView(a);
        t.setTag(TAG);
        t.setText("\u24D8  Fonction");
        t.setTextColor(Color.WHITE);
        t.setTextSize(13);
        t.setTypeface(Typeface.DEFAULT_BOLD);
        t.setGravity(Gravity.CENTER);
        t.setPadding((int) (14 * d), (int) (10 * d), (int) (12 * d), (int) (10 * d));
        GradientDrawable g = new GradientDrawable();
        g.setColor(0xF2FF3F1A);
        float r = 18 * d;
        g.setCornerRadii(new float[]{r, r, 0, 0, 0, 0, r, r});
        t.setBackground(g);
        t.setElevation(10 * d);
        t.setContentDescription("Fonction");

        FrameLayout.LayoutParams lp = new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT,
                Gravity.END | Gravity.BOTTOM);
        lp.bottomMargin = (int) (150 * d);
        t.setLayoutParams(lp);
        t.setTranslationY(sp.getFloat("y", 0f));

        final float slop = 10 * d;
        t.setOnTouchListener(new View.OnTouchListener() {
            float downY, startT;
            boolean moved;

            @Override
            public boolean onTouch(View v, MotionEvent e) {
                switch (e.getActionMasked()) {
                    case MotionEvent.ACTION_DOWN:
                        downY = e.getRawY();
                        startT = v.getTranslationY();
                        moved = false;
                        return true;
                    case MotionEvent.ACTION_MOVE: {
                        float dy = e.getRawY() - downY;
                        if (Math.abs(dy) > slop) moved = true;
                        if (moved) {
                            float h = decor.getHeight();
                            float lim = Math.max(0, h / 2f - 220 * d);
                            v.setTranslationY(Math.max(-lim, Math.min(lim, startT + dy)));
                        }
                        return true;
                    }
                    case MotionEvent.ACTION_UP:
                        if (moved) {
                            sp.edit().putFloat("y", v.getTranslationY()).apply();
                        } else {
                            a.startActivity(new Intent(a, FonctionActivity.class));
                        }
                        return true;
                    default:
                        return true;
                }
            }
        });
        decor.addView(t);
    }

    @Override public void onActivityCreated(Activity a, Bundle b) { }
    @Override public void onActivityStarted(Activity a) { }
    @Override public void onActivityPaused(Activity a) { }
    @Override public void onActivityStopped(Activity a) { }
    @Override public void onActivitySaveInstanceState(Activity a, Bundle b) { }
    @Override public void onActivityDestroyed(Activity a) { }
}
