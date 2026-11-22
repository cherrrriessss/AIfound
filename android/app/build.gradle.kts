plugins {
    id("com.android.application")
}

android {
    namespace = "com.aifound.app"
    compileSdk = 34

    defaultConfig {
        applicationId = "com.aifound.app"
        minSdk = 26
        targetSdk = 34
        versionCode = 1
        versionName = "0.1.0"
        // 에뮬레이터에서 내 컴퓨터(김준희 서버, 8001)를 가리키는 주소. 실제 폰은 로그인 화면 '서버 설정'에서 바꾼다.
        buildConfigField("String", "DEFAULT_BASE_URL", "\"http://10.0.2.2:8001/\"")
    }

    buildFeatures {
        buildConfig = true
    }

    buildTypes {
        release {
            isMinifyEnabled = false
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
}

dependencies {
    implementation("androidx.appcompat:appcompat:1.7.0")
    implementation("com.google.android.material:material:1.12.0")
    implementation("androidx.exifinterface:exifinterface:1.3.7")
    implementation("com.squareup.retrofit2:retrofit:2.11.0")
    implementation("com.squareup.retrofit2:converter-gson:2.11.0")
    implementation("com.squareup.okhttp3:okhttp:4.12.0")
    implementation("com.squareup.okhttp3:logging-interceptor:4.12.0")
    // 이민서 파트: 목록(RecyclerView), 사진 불러오기(Glide)
    implementation("androidx.recyclerview:recyclerview:1.3.2")
    implementation("com.github.bumptech.glide:glide:4.16.0")
}
