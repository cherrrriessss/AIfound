plugins {
    id("com.android.application")
}

// S05 푸시: Firebase 설정 파일(깃에 안 올림)이 있으면 FCM 을 켜고, 없으면 푸시 없이 그대로 빌드된다.
// 파일은 팀원에게 받아 android/app/google-services.json 에 넣기 (match-server/ANDROID.md 4번)
if (file("google-services.json").exists()) {
    apply(plugin = "com.google.gms.google-services")
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
    // S18·S23 당겨서 새로고침, S20 수령 QR 코드 만들기
    implementation("androidx.swiperefreshlayout:swiperefreshlayout:1.1.0")
    implementation("com.google.zxing:core:3.5.3")
    // S05 푸시 알림 (FCM)
    implementation(platform("com.google.firebase:firebase-bom:33.7.0"))
    implementation("com.google.firebase:firebase-messaging")
}
