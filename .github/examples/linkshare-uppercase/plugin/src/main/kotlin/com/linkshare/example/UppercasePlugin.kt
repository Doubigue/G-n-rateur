package com.linkshare.example

import com.linkshare.plugin.api.LinkSharePlugin
import com.linkshare.plugin.api.PluginAction
import com.linkshare.plugin.api.PluginHost
import com.linkshare.plugin.api.PluginInput
import com.linkshare.plugin.api.PluginResult
import java.util.Locale

/** Exemple réel de contrat 2 : utilise uniquement l'API LinkShare v1.7. */
class UppercasePlugin : LinkSharePlugin {
    override fun actions() = listOf(
        PluginAction(
            id = "upper",
            label = "Texte en majuscules",
            icon = "🔠",
            accepts = listOf("txt", "md", "text/plain"),
            minFiles = 1,
            maxFiles = 1,
        )
    )

    override suspend fun run(
        host: PluginHost,
        actionId: String,
        inputs: List<PluginInput>,
        params: Map<String, String>,
    ): PluginResult {
        if (actionId != "upper") return PluginResult.Failure("Action inconnue : $actionId")
        val input = inputs.firstOrNull() ?: return PluginResult.Failure("Aucun fichier sélectionné")
        host.progress(10, "Lecture de ${input.name}")
        val content = host.openInput(input).bufferedReader(Charsets.UTF_8).use { it.readText() }
        if (host.isCancelled()) return PluginResult.Failure("Opération annulée")
        val outputName = input.name.substringBeforeLast('.', input.name) + "_MAJ." + input.name.substringAfterLast('.', "txt")
        host.progress(70, "Conversion du texte")
        val converted = content.uppercase(Locale.ROOT)
        host.createOutput(outputName, "text/plain").bufferedWriter(Charsets.UTF_8).use { it.write(converted) }
        host.progress(100, "Terminé")
        return PluginResult.Success(listOf(outputName), "${converted.length} caractères convertis")
    }
}
