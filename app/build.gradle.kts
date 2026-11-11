plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.plugin.compose")
}
val configuredApiBaseUrl = providers.gradleProperty("API_BASE_URL")
    .orElse(providers.environmentVariable("API_BASE_URL"))
    .getOrElse("https://bangla-ai-voice-video-maker-api.onrender.com")
val hasPersistentReleaseKey = providers.environmentVariable("ANDROID_KEYSTORE_PATH")
    .orNull?.isNotBlank() == true
android {
    namespace = "com.rajuhossain.banglaaivoicemaker"
    compileSdk = 35
    defaultConfig {
        // Keep the original package ID so releases update the same installed app.
        applicationId = "com.rajuhossain.banglaaivoicemaker"
        minSdk = 26
        targetSdk = 35
        versionCode = providers.environmentVariable("APP_VERSION_CODE").getOrElse("4").toInt()
        versionName = providers.environmentVariable("APP_VERSION_NAME").getOrElse("0.3.0")
        buildConfigField("String", "API_BASE_URL", "\"$configuredApiBaseUrl\"")
    }
    signingConfigs {
        create("release") {
            if (hasPersistentReleaseKey) {
                storeFile = file(providers.environmentVariable("ANDROID_KEYSTORE_PATH").get())
                storePassword = providers.environmentVariable("ANDROID_KEYSTORE_PASSWORD").get()
                keyAlias = providers.environmentVariable("ANDROID_KEY_ALIAS").get()
                keyPassword = providers.environmentVariable("ANDROID_KEY_PASSWORD").get()
            }
        }
    }
    buildTypes {
        getByName("release") {
            signingConfig = if (hasPersistentReleaseKey) {
                signingConfigs.getByName("release")
            } else {
                signingConfigs.getByName("debug")
            }
        }
    }
    buildFeatures { compose = true; buildConfig = true }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions { jvmTarget = "17" }
}

// Fail the Android build immediately if a future edit changes the installed app identity.
tasks.register("verifyStableApplicationId") {
    doLast {
        val actualApplicationId = android.defaultConfig.applicationId
        check(actualApplicationId == "com.rajuhossain.banglaaivoicemaker") {
            "Unexpected applicationId: $actualApplicationId. Releases must update the existing app."
        }
        val actualVersionCode = android.defaultConfig.versionCode
        check(actualVersionCode != null && actualVersionCode > 0) {
            "Android versionCode must be a positive integer for in-place updates."
        }
    }
}
tasks.named("preBuild") {
    dependsOn("verifyStableApplicationId")
}

dependencies {
    implementation(platform("androidx.compose:compose-bom:2024.12.01"))
    implementation("androidx.activity:activity-compose:1.10.0")
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.ui:ui-tooling-preview")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.compose.material:material-icons-extended")
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.8.7")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.9.0")
    debugImplementation("androidx.compose.ui:ui-tooling")
}
