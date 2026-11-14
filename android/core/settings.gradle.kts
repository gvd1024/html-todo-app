// Used only when the core is built on its own (`./gradlew -p core test`, e.g. a machine without the Android SDK).
// From android/ the main settings file includes it as :core and this file is ignored.
pluginManagement {
    repositories { mavenCentral(); gradlePluginPortal() }
    plugins { id("org.jetbrains.kotlin.jvm") version "2.4.21" }
}
dependencyResolutionManagement { repositories { mavenCentral() } }
rootProject.name = "hta-alarms-core"
