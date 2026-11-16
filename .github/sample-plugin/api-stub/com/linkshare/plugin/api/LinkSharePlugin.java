package com.linkshare.plugin.api;

import java.util.List;
import java.util.Map;
import kotlin.coroutines.Continuation;

/** Stub JVM du contrat 2, utilisé uniquement par le test de packaging. */
public interface LinkSharePlugin {
    List<PluginAction> actions();
    Object run(PluginHost host, String actionId, List<PluginInput> inputs,
               Map<String, String> params, Continuation<? super PluginResult> continuation);
}
