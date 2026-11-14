import org.jetbrains.kotlin.gradle.dsl.JvmTarget

plugins { id("org.jetbrains.kotlin.jvm") }

java { sourceCompatibility = JavaVersion.VERSION_17; targetCompatibility = JavaVersion.VERSION_17 }
kotlin { compilerOptions { jvmTarget.set(JvmTarget.JVM_17) } }

dependencies {
    compileOnly("org.json:json:20250517")        // Android has org.json built in; the JVM tests use the jar
    testImplementation("org.json:json:20250517")
    testImplementation("junit:junit:4.13.2")
}

tasks.test {
    // the shared fixtures live with the web app's tests (rule 13: one contract, two implementations)
    systemProperty("fixtures", rootProject.projectDir.resolve("../tests/fixtures/frontmatter").absolutePath)
    testLogging { events("failed"); exceptionFormat = org.gradle.api.tasks.testing.logging.TestExceptionFormat.FULL }
}
