// Both plugins on the root classpath: AGP 9's built-in Kotlin and the Kotlin plugin must share one class loader.
// (Without an Android SDK, test the core alone as its own build: `./gradlew -p core test`; see core/settings.gradle.kts.)
plugins {
    id("com.android.application") version "9.4.1" apply false
    id("org.jetbrains.kotlin.jvm") version "2.4.21" apply false
}
