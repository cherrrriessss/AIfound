# 앱에서 매칭 서버(8000) 연결하기 — 이민서 님용

앱은 지금 김준희 서버(8001)만 부른다. 매칭·알림·수령 화면은 아래처럼 **두 번째 Retrofit**으로 8000번을 부르면 된다.
로그인 토큰, 오류 처리(`ApiCallback`), snake_case 변환은 기존 것을 그대로 쓴다.

## 1. 서버 주소: 8001 → 8000

`TokenStore.baseUrl()` 이 `http://10.0.2.2:8001/` 이면 포트만 바꿔서 쓴다 (실제 폰도 '서버 설정' 하나로 둘 다 맞춰짐).

```java
// data/TokenStore.java 에 추가
public static String matchUrl(Context c) {
    return baseUrl(c).replace(":8001/", ":8000/");
}
```

## 2. API 목록 `net/MatchService.java`

```java
package com.aifound.app.net;

import java.util.List;
import retrofit2.Call;
import retrofit2.http.*;

/** 주희선 매칭 서버(8000). match-server/README.md 4번 표. */
public interface MatchService {
    @POST("devices")                       Call<Models.Ok> registerDevice(@Body MatchModels.DeviceIn body);          // 03
    @GET("matches/summary")                Call<MatchModels.Summary> summary();                                     // 06
    @GET("lost-reports/{id}/matches")      Call<MatchModels.MatchList> matchesForLost(@Path("id") String lostId);   // 18
    @GET("matches/{id}")                   Call<MatchModels.MatchDetail> matchDetail(@Path("id") String matchId);   // 19
    @POST("matches/{id}/claim")            Call<MatchModels.ClaimOut> claim(@Path("id") String matchId);            // 19 내 물건이에요
    @POST("matches/{id}/reject")           Call<Models.Ok> reject(@Path("id") String matchId, @Body MatchModels.RejectIn body); // 21
    @GET("matches/{id}/pickup")            Call<MatchModels.PickupGuide> pickupGuide(@Path("id") String matchId);   // 20
    @GET("matches/{id}/pickup/code")       Call<MatchModels.PickupCode> pickupCode(@Path("id") String matchId);     // 20 (expires_in 초마다)
    @GET("matches/{id}/pickup/status")     Call<MatchModels.PickupStatus> pickupStatus(@Path("id") String matchId); // 20 수령 완료 확인
    @GET("pickups")                        Call<MatchModels.PickupList> pickups(@Query("kind") String kind);        // 25 all/mine/given
    @GET("notifications")                  Call<MatchModels.NotificationList> notifications();                      // 27
    @POST("notifications/read-all")        Call<Models.Ok> readAll();                                               // 27
    @GET("settings/notifications")         Call<MatchModels.Settings> settings();                                   // 26
    @PUT("settings/notifications")         Call<MatchModels.Settings> saveSettings(@Body MatchModels.Settings body);// 26
}
```

`ApiClient.java` 에 `get()` 과 같은 방식으로 `match(Context)` 를 하나 더 만든다 (baseUrl 만 `TokenStore.matchUrl(app)`).

## 3. 응답 모양 `net/MatchModels.java` (필요한 필드만)

```java
package com.aifound.app.net;

import java.util.List;
import java.util.Map;

public final class MatchModels {
    public static class DeviceIn { public String fcmToken; public DeviceIn(String t) { fcmToken = t; } }
    public static class RejectIn { public List<String> reasons; }   // category, color, brand_model, place_time, other

    public static class Summary { public int newCount; public Map<String, Object> top; }

    public static class MatchItem {           // 18 목록 한 줄
        public String matchId; public int score; public String shortReason; public String status;
        public Map<String, Object> foundItem;  // id, attrs, building, location_detail, found_at, photo_path, lockers
    }
    public static class MatchList { public List<MatchItem> matches; }

    public static class Bar { public String label; public int max; public int value; }   // 19 점수 막대
    public static class MatchDetail {
        public String matchId; public int score; public String reason; public String status;
        public List<Bar> breakdown; public Map<String, Object> myReport; public Map<String, Object> foundItem;
    }

    public static class ClaimOut { public String status; public String pickupDeadline; }
    public static class PickupCode { public String code; public String display; public String qr; public int expiresIn; }
    public static class PickupGuide { public Map<String, Object> item; public String deadline; public List<Map<String, Object>> steps; public PickupCode code; }
    public static class PickupStatus { public boolean received; }
    public static class PickupList { public List<Map<String, Object>> pickups; }

    public static class Notification { public String id; public String type; public String title; public String body; public Map<String, Object> data; public boolean read; public String createdAt; }
    public static class NotificationList { public List<Notification> notifications; }

    public static class Settings {
        public Boolean matchAlert, ownerAlert, pickupReminder;
        public String quietStart, quietEnd;    // "23:00"
        public List<String> interestBuildings;
    }
}
```

## 4. 푸시 받기 (Firebase)

1. 주희선 님에게 **`google-services.json`** 받아서 `android/app/` 에 넣기 (깃허브에 올리지 않기, `.gitignore` 에 있음)
   - Firebase 에 등록한 패키지 이름: `com.aifound.app`
2. `android/build.gradle.kts` plugins 에 `id("com.google.gms.google-services") version "4.4.2" apply false`
3. `android/app/build.gradle.kts`
   - plugins 에 `id("com.google.gms.google-services")`
   - dependencies 에 `implementation(platform("com.google.firebase:firebase-bom:33.7.0"))`, `implementation("com.google.firebase:firebase-messaging")`
   - (버전은 Android Studio 가 더 새 버전을 권하면 그걸 써도 됨)
4. `util/PushService.java`

```java
public class PushService extends FirebaseMessagingService {
    @Override public void onNewToken(String token) { PushService.sendToken(this, token); }

    /** 로그인 직후에도 한 번 부르기: FirebaseMessaging.getInstance().getToken().addOnSuccessListener(t -> sendToken(ctx, t)); */
    public static void sendToken(Context c, String token) {
        if (TokenStore.token(c) == null) return;   // 로그인 전이면 다음에
        ApiClient.match(c).registerDevice(new MatchModels.DeviceIn(token)).enqueue(new retrofit2.Callback<Models.Ok>() {
            public void onResponse(retrofit2.Call<Models.Ok> call, retrofit2.Response<Models.Ok> r) {}
            public void onFailure(retrofit2.Call<Models.Ok> call, Throwable t) {}
        });
    }

    @Override public void onMessageReceived(RemoteMessage msg) {
        // 앱이 켜져 있을 때만 여기로 옴 (꺼져 있으면 시스템이 알림을 띄우고, 누르면 런처 액티비티 extras 에 data 가 들어옴)
        String matchId = msg.getData().get("match_id");   // type=match -> 19 매칭 상세로
        // NotificationCompat 으로 알림 표시, PendingIntent 로 MatchDetailActivity(matchId)
    }
}
```

5. `AndroidManifest.xml` 의 `<application>` 안에

```xml
<service android:name=".util.PushService" android:exported="false">
    <intent-filter><action android:name="com.google.firebase.MESSAGING_EVENT" /></intent-filter>
</service>
```
`POST_NOTIFICATIONS` 권한은 이미 있음 → 03 '알림 허용하기' 버튼에서 런타임 권한 요청.

## 5. 화면별로 어디에 붙이나

| TODO 표시 / 화면 | 할 일 |
|---|---|
| `TODO(S18)` 탭바 매칭 | `matchesForLost(lostId)` 목록, 일치율 높은 순 |
| S08 '내 물건이에요' | 매칭에서 온 경우 `claim(matchId)` → S20 |
| S06 배너 | `summary()` 의 `new_count` |
| S19 | `matchDetail()` 의 `breakdown` 4개를 막대로, `reason` 을 'AI가 찾은 이유'에 |
| S20 | `pickupGuide()` → 코드 표시, `expires_in` 초 뒤 `pickupCode()` 다시. QR 은 `qr` 문자열을 그대로 QR 이미지로 |
| S26, S27 | `settings()/saveSettings()`, `notifications()/readAll()` |
