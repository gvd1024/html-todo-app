// HTA Alarms (R2-22 Phase 2). `core` = the task-file contract and the time math in plain Kotlin (unit-tested on any
// JVM); `app` = the Android app. The app module needs the Android SDK (ANDROID_HOME or local.properties sdk.dir);
// without one (e.g. a cloud session) only `core` is built.
pluginManagement {
    repositories { google(); mavenCentral(); gradlePluginPortal() }
}
dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {
        google()
        mavenCentral()
        // MSAL for Android pulls one small library (display-mask) from Microsoft's public feed
        maven { url = uri("https://pkgs.dev.azure.com/MicrosoftDeviceSDK/DuoSDK-Public/_packaging/Duo-SDK-Feed/maven/v1") }
    }
}
rootProject.name = "hta-alarms"
include(":core")
val sdk = System.getenv("ANDROID_HOME") ?: System.getenv("ANDROID_SDK_ROOT")
    ?: file("local.properties").takeIf { it.exists() }?.readLines()?.firstOrNull { it.startsWith("sdk.dir=") }?.substringAfter("=")
if (sdk != null && file(sdk).resolve("platforms").exists()) include(":app")
else println("HTA Alarms: no Android SDK found — building :core only")
