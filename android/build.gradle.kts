plugins {
    id("com.android.application") version "8.5.2" apply false
    // S05 푸시 (FCM). app/google-services.json 이 있을 때만 app 에서 켠다
    id("com.google.gms.google-services") version "4.4.2" apply false
}
