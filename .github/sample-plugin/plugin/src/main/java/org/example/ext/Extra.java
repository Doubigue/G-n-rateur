package org.example.ext;

/** Simule une bibliothèque tierce restée dans le jar : plugin_embed.py doit la signaler. */
public final class Extra {
    private Extra() {}
    public static String suffix() { return "ext"; }
}
