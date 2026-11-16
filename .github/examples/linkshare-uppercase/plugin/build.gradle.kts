plugins { kotlin("jvm") }

java {
    sourceCompatibility = JavaVersion.VERSION_17
    targetCompatibility = JavaVersion.VERSION_17
}
kotlin { compilerOptions { jvmTarget.set(org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_17) } }

val apiJar = providers.gradleProperty("linkshareApiJar").orNull
    ?: error("Passe -PlinkshareApiJar=<JAR réel exporté par LinkShare>")
val androidJar = providers.gradleProperty("androidJar").orNull
    ?: System.getenv("ANDROID_HOME")?.let { "$it/platforms/android-35/android.jar" }
    ?: error("android.jar introuvable")

dependencies {
    compileOnly(files(apiJar))
    compileOnly(files(androidJar))
}

tasks.register("assemblePlugin") {
    group = "build"
    description = "Compile le plugin contre l'API LinkShare réelle (compileOnly)."
    dependsOn(tasks.named("jar"))
}
