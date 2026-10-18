plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.plugin.compose")
}
val configuredApiBaseUrl = providers.gradleProperty("API_BASE_URL")
    .orElse(providers.environmentVariable("API_BASE_URL"))
    .getOrElse("https://bangla-ai-voice-video-maker-api.onrender.com")
android {
    namespace = "com.rajuhossain.banglaaivoicevideomaker"
    compileSdk = 35
    defaultConfig {
        applicationId = "com.rajuhossain.banglaaivoicevideomaker"
        minSdk = 26
        targetSdk = 35
        // Use the GitHub Actions run number so every released APK can update the previous install.
        versionCode = providers.environmentVariable("APP_VERSION_CODE").getOrElse("4").toInt()
        versionName = providers.environmentVariable("APP_VERSION_NAME").getOrElse("0.3.0")
        buildConfigField("String", "API_BASE_URL", "\"$configuredApiBaseUrl\"")
    }
    buildFeatures { compose = true; buildConfig = true }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions { jvmTarget = "17" }
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
