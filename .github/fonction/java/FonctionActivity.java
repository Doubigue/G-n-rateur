package studio.apk.fonction;

import android.app.Activity;
import android.graphics.Color;
import android.os.Bundle;
import android.view.ViewGroup;
import android.webkit.JavascriptInterface;
import android.webkit.ValueCallback;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.LinearLayout;

/** Écran « Fonction » : description, captures d'écran et animation du projet (assets/omni_fonction). */
public class FonctionActivity extends Activity {
    private WebView wv;

    @Override
    protected void onCreate(Bundle b) {
        super.onCreate(b);
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setFitsSystemWindows(true);
        root.setBackgroundColor(Color.parseColor("#FAF6F3"));

        wv = new WebView(this);
        WebSettings s = wv.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setAllowFileAccess(true);
        s.setAllowContentAccess(false);
        s.setMediaPlaybackRequiresUserGesture(false);
        s.setLoadWithOverviewMode(false);
        wv.setWebViewClient(new WebViewClient());
        wv.addJavascriptInterface(new Object() {
            @JavascriptInterface
            public void close() {
                runOnUiThread(new Runnable() { public void run() { finish(); } });
            }
        }, "Fonction");
        root.addView(wv, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));
        setContentView(root);
        wv.loadUrl("file:///android_asset/omni_fonction/index.html");
    }

    @Override
    public void onBackPressed() {
        // la visionneuse de captures se ferme d'abord, puis l'écran
        wv.evaluateJavascript("(function(){return !!(window.__back&&window.__back())})()", new ValueCallback<String>() {
            @Override public void onReceiveValue(String v) {
                if (!"true".equals(v)) finish();
            }
        });
    }

    @Override protected void onPause() { super.onPause(); if (wv != null) wv.onPause(); }
    @Override protected void onResume() { super.onResume(); if (wv != null) wv.onResume(); }

    @Override
    protected void onDestroy() {
        if (wv != null) { wv.destroy(); wv = null; }
        super.onDestroy();
    }
}
