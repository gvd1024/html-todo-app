plugins { id("com.android.application") }   // AGP 9: Kotlin support is built in

// versionName = the HTA BUILD-style date; versionCode must always go up (CI passes the run number)
val htaVersion = (findProperty("htaVersion") as String?) ?: "2026-11-15a"
val htaCode = ((findProperty("htaCode") as String?) ?: "1").toInt()

android {
    namespace = "io.github.gvd1024.htaalarms"
    compileSdk { version = release(37) }          // Android 17
    defaultConfig {
        applicationId = "io.github.gvd1024.htaalarms"
        minSdk = 29
        targetSdk = 37
        versionCode = htaCode
        versionName = htaVersion
    }
    // Release signing only from the environment (GitHub Actions secrets → a temp keystore). Never from the repo.
    val ks = System.getenv("HTA_KS_FILE")
    signingConfigs {
        if (ks != null) create("release") {
            storeFile = file(ks)
            storeType = "PKCS12"
            storePassword = System.getenv("HTA_KS_PASSWORD")
            keyAlias = System.getenv("HTA_KEY_ALIAS") ?: "htaalarms"
            keyPassword = System.getenv("HTA_KS_PASSWORD")
        }
    }
    buildTypes {
        release {
            isMinifyEnabled = false
            if (ks != null) signingConfig = signingConfigs.getByName("release")
        }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    packaging { resources { excludes += setOf("META-INF/DEPENDENCIES", "META-INF/LICENSE*", "META-INF/NOTICE*") } }
}

dependencies {
    implementation(project(":core"))
    implementation("com.microsoft.identity.client:msal:8.7.0")
}
