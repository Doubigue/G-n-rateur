package com.linkshare.plugin.api;
import java.util.List;
public class PluginAction {
    public final String id;
    public PluginAction(String id, String label, String icon, List<String> accepts,
                        int minFiles, int maxFiles, List<Object> params) { this.id = id; }
}
