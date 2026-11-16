package com.linkshare.sample;

import com.linkshare.plugin.api.LinkSharePlugin;
import com.linkshare.plugin.api.PluginAction;
import com.linkshare.plugin.api.PluginHost;
import com.linkshare.plugin.api.PluginInput;
import com.linkshare.plugin.api.PluginResult;
import kotlin.coroutines.Continuation;
import java.util.Collections;
import java.util.List;
import java.util.Map;

public class SamplePlugin implements LinkSharePlugin {
    @Override
    public List<PluginAction> actions() {
        return Collections.singletonList(
            new PluginAction("hello", "Exemple LinkShare", "🧩",
                Collections.singletonList("txt"), 1, 1, Collections.emptyList())
        );
    }

    @Override
    public Object run(PluginHost host, String actionId, List<PluginInput> inputs,
                     Map<String, String> params, Continuation<? super PluginResult> continuation) {
        return new PluginResult.Failure("Exemple de test : remplacez cette action par votre traitement.");
    }
}
