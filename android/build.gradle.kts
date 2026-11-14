// The Kotlin plugin is declared here so every module shares one copy (AGP 9's built-in Kotlin uses it too).
// The Android plugin's version is in settings.gradle.kts and only :app applies it, so a core-only build (no
// Android SDK) never downloads it.
plugins {
    id("org.jetbrains.kotlin.jvm") version "2.4.21" apply false
}
