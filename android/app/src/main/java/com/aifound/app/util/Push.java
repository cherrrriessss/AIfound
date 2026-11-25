package com.aifound.app.util;

import android.app.Activity;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.content.Context;
import android.content.Intent;
import android.os.Bundle;
import android.util.Log;

import com.aifound.app.data.TokenStore;
import com.aifound.app.net.ApiClient;
import com.aifound.app.net.MatchModels;
import com.aifound.app.net.Models;
import com.aifound.app.ui.ClaimActivity;
import com.aifound.app.ui.HistoryActivity;
import com.aifound.app.ui.HomeActivity;
import com.aifound.app.ui.MatchDetailActivity;
import com.aifound.app.ui.MyFoundActivity;
import com.google.firebase.FirebaseApp;
import com.google.firebase.messaging.FirebaseMessaging;

import retrofit2.Call;
import retrofit2.Callback;
import retrofit2.Response;

/**
 * S05 푸시 알림 공통 (이민서).
 * - register(): 로그인 뒤 FCM 토큰을 매칭 서버 POST /devices 에 등록
 * - unregister(): 로그아웃·탈퇴 때 이 폰의 토큰을 지워서 다른 계정 알림이 오지 않게
 * - open(): 알림(푸시·S27 알림함)을 눌렀을 때 갈 화면. 서버 data 의 type 으로 정한다.
 *     match → S19 매칭 상세, reminder → S20 수령 안내, owner_found → S24 내가 등록한 습득물, received → S25 수령 기록
 *
 * google-services.json 이 없으면 Firebase 가 꺼진 채로 빌드되고, 여기 함수들은 아무 일도 안 한다.
 */
public final class Push {

    private static final String TAG = "Push";
    public static final String CHANNEL = "aifound_alerts";
    public static final String EXTRA_TYPE = "type";          // 서버 data 키와 같게 (앱이 꺼져 있을 때 시스템 알림이 그대로 넘겨줌)
    public static final String EXTRA_MATCH_ID = "match_id";

    private Push() {}

    /** Firebase 설정 파일(google-services.json)을 넣고 빌드했는지 */
    public static boolean enabled(Context c) {
        return !FirebaseApp.getApps(c).isEmpty();
    }

    public static void createChannel(Context c) {
        NotificationChannel ch = new NotificationChannel(CHANNEL, "매칭·수령 알림", NotificationManager.IMPORTANCE_HIGH);
        ch.setDescription("내 분실물과 비슷한 물건, 수령 기한, 주인 확인 알림");
        c.getSystemService(NotificationManager.class).createNotificationChannel(ch);
    }

    public static void register(Context c) {
        if (!enabled(c)) {
            Log.i(TAG, "google-services.json 이 없어 푸시를 건너뜀");
            return;
        }
        createChannel(c);
        FirebaseMessaging.getInstance().getToken()
                .addOnSuccessListener(t -> sendToken(c, t))
                .addOnFailureListener(e -> Log.w(TAG, "FCM 토큰을 받지 못함", e));
    }

    public static void sendToken(Context c, String token) {
        if (TokenStore.token(c) == null || token == null) return;   // 로그인 전이면 로그인 뒤 register() 에서 다시
        ApiClient.match(c).registerDevice(new MatchModels.DeviceIn(token)).enqueue(new Callback<Models.Ok>() {
            @Override public void onResponse(Call<Models.Ok> call, Response<Models.Ok> r) {
                Log.i(TAG, "토큰 등록 " + r.code());
            }

            @Override public void onFailure(Call<Models.Ok> call, Throwable t) {
                Log.w(TAG, "토큰 등록 실패 (매칭 서버 꺼짐?)", t);
            }
        });
    }

    public static void unregister(Context c) {
        if (enabled(c)) FirebaseMessaging.getInstance().deleteToken();
    }

    /** 알림 data 에 갈 화면이 있는지 */
    public static boolean hasTarget(Bundle extras) {
        return extras != null && extras.getString(EXTRA_TYPE) != null;
    }

    /** 앱이 꺼져 있을 때 누른 푸시: 홈을 아래에 깔고 그 위에 대상 화면 */
    public static void openFromLaunch(Activity a, Bundle extras) {
        Intent home = new Intent(a, HomeActivity.class);
        Intent target = target(a, extras.getString(EXTRA_TYPE), extras.getString(EXTRA_MATCH_ID));
        if (target == null) {
            a.startActivity(home);
        } else {
            a.startActivities(new Intent[]{home, target});
        }
    }

    /** S27 알림함 등 앱 안에서 누를 때 */
    public static void open(Activity a, String type, String matchId) {
        Intent i = target(a, type, matchId);
        if (i != null) a.startActivity(i);
    }

    public static Intent target(Context c, String type, String matchId) {
        if (type == null) return null;
        switch (type) {
            case "match":
                return matchId == null ? null : MatchDetailActivity.intent(c, matchId);
            case "reminder":
                return matchId == null ? null : ClaimActivity.intent(c, matchId);
            case "owner_found":
                return new Intent(c, MyFoundActivity.class);
            case "received":
                return new Intent(c, HistoryActivity.class);
            default:
                return null;
        }
    }
}
